from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from .base_scraper import BaseScraper
from app.models.gift import Gift
from typing import List, Dict
import time
from urllib.parse import urlparse

class FireboxScraper(BaseScraper):
    def __init__(self, image_folder, debug_folder):
        super().__init__(image_folder, debug_folder)
        self.base_url = "https://firebox.com/gift-finder"
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.service = Service(ChromeDriverManager().install())

        # URL parameter mappings
        self.gender_mapping = {
            'male': '3246',
            'female': '3247'
        }
        
        self.price_mapping = {
            15: '2651',    # £0 - £15
            30: '2830',    # £15 - £30
            60: '2650',    # £30 - £60
            1000: '2649'   # >£60
        }
        
        self.personalizable_mapping = {
            True: '3350',
            False: '3351'
        }

        # New product tags mapping
        self.product_tags_mapping = {
            'self_care': '3234',
            'gaming': '3288',
            'cosy': '9706',
            'humour': '3292',
            'sports_fitness': '3270',
            'music': '3239',
            'wine': '3238',
            'beer': '3262',
            'chilli': '3236',
            'outdoors': '9517',
            'gardening': '9519',
            'geeky': '9547',
            'party_games': '9957',
            'boozing': '9559',
            'romance': '9560',
            'animals': '9561',
            'nsfw': '9562',
            'sugar_highs': '9564',
            'kitsch': '9565',
            'whisky': '3259',
            'office': '9675',
            'cooking': '3268',
            'harry_potter': '3274',
            'star_wars': '3275',
            'disney': '3276',
            'dad_gifts': '9749'
        }

        # Interest to product tag mapping
        self.interest_to_tag_mapping = {
            'beer': ['beer', 'boozing'],  # maps to 3262, 9559
            'alcohol': ['beer', 'wine', 'whisky', 'boozing'],
            'computers': ['geeky', 'gaming'],  # maps to 9547, 3288
            'technology': ['geeky', 'gaming'],
            'gadgets': ['geeky', 'gaming'],
            'gaming': ['gaming', 'geeky'],
            'animals': ['animals'],  # maps to 9561
            'geeky': ['geeky'],
            'nerdy': ['geeky'],
            'tech': ['geeky', 'gaming']
        }

    def get_search_urls(self, criteria: Dict) -> List[str]:
        """Generate Firebox search URLs based on criteria"""
        params = []
        
        # Handle gender
        if gender := criteria.get('gender'):
            if gender_param := self.gender_mapping.get(gender.lower()):
                params.append(f"gift_gender={gender_param}")
        
        # Handle price
        if max_price := criteria.get('max_price'):
            for price_threshold, param_value in sorted(self.price_mapping.items()):
                if max_price <= price_threshold:
                    params.append(f"price_filter={param_value}")
                    break
            if max_price > 60:
                params.append(f"price_filter={self.price_mapping[1000]}")
        
        # Handle personalization (defaulting to No)
        personalizable = criteria.get('personalizable', False)
        params.append(f"personalizable={self.personalizable_mapping[personalizable]}")
        
        # Handle product tags based on interests and categories
        interests = criteria.get('interests', [])
        categories = criteria.get('categories', [])
        
        # Collect all matching tag IDs
        tag_ids = set()  # Using set to avoid duplicates
        
        # Process interests through the mapping
        for interest in interests + categories:
            interest_lower = interest.lower()
            # Direct product tag mapping
            if tag_id := self.product_tags_mapping.get(interest_lower):
                tag_ids.add(tag_id)
            # Interest to tag mapping
            if mapped_tags := self.interest_to_tag_mapping.get(interest_lower):
                for tag in mapped_tags:
                    if tag_id := self.product_tags_mapping.get(tag):
                        tag_ids.add(tag_id)
        
        # Add product tags as a single parameter with comma-separated values
        if tag_ids:
            params.append(f"product_tags={','.join(tag_ids)}")
        
        # Construct URL
        url = f"{self.base_url}?{'&'.join(params)}"
        self.logger.info(f"Generated URL with tags: {tag_ids}")  # Debug log
        return [url]

    def _parse_gift_element(self, element, max_price) -> Gift:
        try:
            # Get title from the product name div
            title = element.find_element(By.CSS_SELECTOR, '.item-name.product-name-list').text
            
            # Get price - find the price div and clean the text
            price_text = element.find_element(By.CSS_SELECTOR, '.price').text
            price = float(price_text.replace('£', '').replace(',', ''))
            
            # Only check max_price if it's not None
            if max_price is not None and price > max_price:
                return None
            
            # Get the product link from the main anchor tag
            link = element.find_element(By.CSS_SELECTOR, 'a[href^="https://firebox.com/"]').get_attribute('href')
            
            # Get image URL - try webp first, fall back to png
            try:
                image_url = element.find_element(By.CSS_SELECTOR, 'picture source[type="image/webp"]').get_attribute('srcset')
            except:
                image_url = element.find_element(By.CSS_SELECTOR, 'picture img').get_attribute('src')
            
            # Determine category and tags based on Firebox's product tags
            category = self._determine_firebox_category(title, link)
            tags = self._generate_firebox_tags(title, category, link)
            image_path = self._download_image(image_url, title) if image_url else None
            
            return Gift(
                name=title,
                price=price,
                affiliate_link=link,
                source="Firebox",
                image_path=image_path,
                category=category,
                tags=tags
            )
        
        except Exception as e:
            self.logger.error(f"Error parsing gift element: {str(e)}")
            return None

    def _determine_firebox_category(self, title: str, link: str) -> str:
        """Determine the primary category based on Firebox's categorization"""
        # Mapping of keywords to categories
        category_keywords = {
            'gadgets': ['tech', 'gadget', 'electronic', 'smart', 'digital'],
            'food_drink': ['beer', 'wine', 'whisky', 'food', 'drink', 'snack', 'chocolate', 'coffee'],
            'gaming': ['game', 'gaming', 'playstation', 'xbox', 'nintendo', 'console'],
            'experiences': ['experience', 'adventure', 'activity', 'lesson', 'class'],
            'novelty': ['funny', 'joke', 'novelty', 'humor', 'weird'],
            'home': ['home', 'kitchen', 'garden', 'decor', 'living'],
            'entertainment': ['entertainment', 'movie', 'music', 'party', 'fun'],
            'sports_outdoor': ['sport', 'fitness', 'outdoor', 'exercise', 'camping']
        }
        
        title_lower = title.lower()
        
        # Check title against keywords
        for category, keywords in category_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                return category
                
        # Default to 'novelty' if no specific category is found
        return 'novelty'

    def _generate_firebox_tags(self, title: str, category: str, link: str) -> str:
        """Generate tags based on Firebox's product information"""
        tags = set()
        title_lower = title.lower()
        
        # Add category as a tag
        tags.add(category)
        
        # Add specific tags based on title keywords
        tag_keywords = {
            'beer': ['beer', 'ale', 'lager', 'craft beer'],
            'wine': ['wine', 'champagne', 'prosecco'],
            'whisky': ['whisky', 'whiskey', 'bourbon'],
            'geeky': ['geek', 'nerd', 'sci-fi', 'science', 'tech'],
            'gaming': ['game', 'gaming', 'playstation', 'xbox', 'nintendo'],
            'animals': ['animal', 'pet', 'dog', 'cat'],
            'gadgets': ['gadget', 'tech', 'electronic', 'digital'],
            'cooking': ['cook', 'kitchen', 'chef', 'food'],
            'outdoor': ['outdoor', 'garden', 'camping', 'nature'],
            'party': ['party', 'celebration', 'fun', 'entertainment'],
            'novelty': ['funny', 'joke', 'humor', 'weird', 'unusual']
        }
        
        # Add tags based on title keywords
        for tag, keywords in tag_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                tags.add(tag)
        
        # Convert set to comma-separated string
        return ', '.join(sorted(tags))

    def scrape(self, criteria: Dict) -> List[Gift]:
        gifts = []
        driver = None
        MAX_GIFTS = 100
        
        try:
            driver = self._get_driver()
            search_urls = self.get_search_urls(criteria)
            max_price = criteria.get('max_price', 1000)
            
            for url in search_urls:
                if len(gifts) >= MAX_GIFTS:
                    break
                    
                try:
                    self.logger.info(f"Scraping URL: {url}")
                    driver.get(url)
                    
                    self._scroll_and_wait(driver)
                    gift_elements = driver.find_elements(By.CSS_SELECTOR, '.product-item')
                    
                    for element in gift_elements[:MAX_GIFTS - len(gifts)]:
                        gift = self._parse_gift_element(element, max_price)
                        if gift:
                            gifts.append(gift)
                            
                except Exception as e:
                    self.logger.error(f"Error scraping URL {url}: {str(e)}")
                    continue
                    
        finally:
            if driver:
                driver.quit()
                
        return gifts[:MAX_GIFTS] 

    def _get_driver(self):
        """Create and return a configured Chrome WebDriver instance"""
        return webdriver.Chrome(service=self.service, options=self.chrome_options)

    def _scroll_and_wait(self, driver):
        """Scroll the page to load more content"""
        viewport_height = driver.execute_script("return window.innerHeight")
        scroll_amount = viewport_height // 2
        
        for _ in range(3):
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(2)
            
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)