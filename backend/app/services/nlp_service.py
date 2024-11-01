import spacy
import re
from typing import Dict, List
import logging
from collections import defaultdict
from config import Config
from openai import OpenAI

class NLPService:
    def __init__(self, use_openai=False):
        # Load English language model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            # If model isn't installed, download it
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
            self.nlp = spacy.load("en_core_web_sm")
        
        # Initialize OpenAI only if flag is True and API key exists
        self.use_openai = use_openai and bool(Config.OPENAI_API_KEY)
        if self.use_openai:
            try:
                self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
            except Exception as e:
                self.logger.error(f"Failed to initialize OpenAI: {str(e)}")
                self.use_openai = False
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize keyword dictionaries
        self._initialize_keywords()

    def _initialize_keywords(self):
        """Initialize keyword dictionaries for pattern matching"""
        self.interest_keywords = {
            'sports': ['football', 'basketball', 'tennis', 'golf', 'fitness', 'running'],
            'technology': ['gaming', 'computers', 'gadgets', 'tech', 'electronics'],
            'cooking': ['cooking', 'baking', 'kitchen', 'food', 'culinary'],
            'art': ['painting', 'drawing', 'crafts', 'artistic', 'creative'],
            'music': ['music', 'guitar', 'piano', 'singing', 'concerts'],
            'reading': ['books', 'reading', 'literature', 'novels'],
            'outdoor': ['hiking', 'camping', 'adventure', 'nature'],
            'fashion': ['clothes', 'fashion', 'shopping', 'style'],
        }

        self.occasion_keywords = {
            'birthday': ['birthday', 'bday'],
            'christmas': ['christmas', 'xmas'],
            'anniversary': ['anniversary', 'wedding anniversary'],
            'wedding': ['wedding', 'marriage'],
            'graduation': ['graduation', 'graduating'],
            'housewarming': ['housewarming', 'new home'],
        }

    def extract_gift_criteria(self, description: str) -> Dict:
        """
        Main method to extract gift criteria from natural language description
        """
        if not description:
            return {}

        if self.use_openai:
            try:
                return self._extract_with_openai(description)
            except Exception as e:
                self.logger.error(f"OpenAI extraction failed: {str(e)}")
                return self._extract_with_spacy(description)
        else:
            return self._extract_with_spacy(description)

    def _extract_with_spacy(self, description: str) -> Dict:
        """
        Extract gift criteria using spaCy NLP
        """
        doc = self.nlp(description.lower())
        
        criteria = {
            'age': self._extract_age(doc),
            'gender': self._extract_gender(doc),
            'max_price': self._extract_price(doc),
            'interests': self._extract_interests(doc),
            'occasion': self._extract_occasion(doc),
            'relationship': self._extract_relationship(doc),
            'categories': [],  # Will be derived from interests
        }
        
        # Map interests to gift categories
        criteria['categories'] = self._map_interests_to_categories(criteria['interests'])
        
        return criteria

    def _extract_with_openai(self, description: str) -> Dict:
        """
        Extract gift criteria using OpenAI's API
        """
        try:
            prompt = f"""
            Extract gift-finding criteria from the following description. 
            Return a JSON object with these fields: age, gender, max_price, interests (list), 
            occasion, relationship.
            
            Description: {description}
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts gift criteria from text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
            )
            
            # Parse the response - updated to match new API format
            content = response.choices[0].message.content
            
            # Parse the response
            import json
            criteria = json.loads(content)
            
            # Add categories based on interests
            criteria['categories'] = self._map_interests_to_categories(criteria.get('interests', []))
            
            return criteria

        except Exception as e:
            self.logger.error(f"OpenAI API error: {str(e)}")
            # Fallback to spaCy if OpenAI fails
            return self._extract_with_spacy(description)

    def _extract_age(self, doc) -> int:
        """Extract age from text"""
        age_patterns = [
            r'\b(\d{1,2})\s*(?:year(?:s)?\s*old|\s*yo)\b',
            r'\bage(?:\s+is)?\s*:?\s*(\d{1,2})\b'
        ]
        
        text = doc.text.lower()
        for pattern in age_patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
        
        return None

    def _extract_gender(self, doc) -> str:
        """Extract gender from text"""
        gender_terms = {
            'male': ['man', 'boy', 'male', 'him', 'his', 'he'],
            'female': ['woman', 'girl', 'female', 'her', 'she'],
        }
        
        text = doc.text.lower()
        gender_counts = defaultdict(int)
        
        for gender, terms in gender_terms.items():
            for term in terms:
                gender_counts[gender] += len(re.findall(r'\b' + term + r'\b', text))
        
        if gender_counts:
            return max(gender_counts.items(), key=lambda x: x[1])[0]
        return None

    def _extract_price(self, doc) -> float:
        """Extract maximum price from text"""
        price_patterns = [
            r'(?:£|\$|EUR)\s*(\d+(?:\.\d{2})?)',
            r'(\d+(?:\.\d{2})?)\s*(?:pounds|dollars|euros)',
            r'budget(?:\s+is)?\s*:?\s*(?:£|\$|EUR)?\s*(\d+(?:\.\d{2})?)',
            r'spend(?:\s+up\s+to)?\s*(?:£|\$|EUR)?\s*(\d+(?:\.\d{2})?)',
        ]
        
        text = doc.text.lower()
        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1))
        
        return None

    def _extract_interests(self, doc) -> List[str]:
        """Extract interests and hobbies"""
        interests = set()
        text = doc.text.lower()
        
        # Check for keywords in our predefined categories
        for category, keywords in self.interest_keywords.items():
            for keyword in keywords:
                if re.search(r'\b' + keyword + r'\b', text):
                    interests.add(category)
        
        # Look for additional hobby patterns
        hobby_patterns = [
            r'likes? to (\w+)',
            r'enjoys? (\w+ing)',
            r'into (\w+ing)',
            r'fan of (\w+)',
        ]
        
        for pattern in hobby_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                interests.add(match.group(1))
        
        return list(interests)

    def _extract_occasion(self, doc) -> str:
        """Extract gift occasion"""
        text = doc.text.lower()
        
        for occasion, keywords in self.occasion_keywords.items():
            for keyword in keywords:
                if re.search(r'\b' + keyword + r'\b', text):
                    return occasion
        
        return None

    def _extract_relationship(self, doc) -> str:
        """Extract relationship to gift recipient"""
        relationship_terms = {
            'friend': ['friend'],
            'family': ['mother', 'father', 'sister', 'brother', 'mom', 'dad', 
                      'aunt', 'uncle', 'cousin', 'grandmother', 'grandfather'],
            'romantic': ['boyfriend', 'girlfriend', 'partner', 'spouse', 'husband', 'wife'],
            'colleague': ['colleague', 'coworker', 'boss', 'employee'],
        }
        
        text = doc.text.lower()
        for rel_type, terms in relationship_terms.items():
            for term in terms:
                if re.search(r'\b' + term + r'\b', text):
                    return rel_type
        
        return None

    def _map_interests_to_categories(self, interests: List[str]) -> List[str]:
        """Map interests to gift categories"""
        category_mapping = {
            'sports': ['sports_outdoor', 'fitness'],
            'technology': ['electronics', 'gadgets'],
            'cooking': ['kitchen', 'food_drink'],
            'art': ['crafts', 'creative'],
            'music': ['entertainment', 'experiences'],
            'reading': ['books', 'education'],
            'outdoor': ['adventure', 'experiences'],
            'fashion': ['fashion', 'accessories'],
        }
        
        categories = set()
        for interest in interests:
            if interest in category_mapping:
                categories.update(category_mapping[interest])
        
        return list(categories) 