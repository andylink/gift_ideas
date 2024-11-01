# base_scraper.py
from abc import ABC, abstractmethod
from app.models.gift import Gift
from typing import List, Dict, Optional
from pathlib import Path
import logging
from urllib.parse import urlparse
import os  # Also needed for os.path.splitext
import requests

class BaseScraper(ABC):
    def __init__(self, image_folder: Path, debug_folder: Path):
        self.image_folder = image_folder
        self.debug_folder = debug_folder
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def scrape(self, criteria: Dict) -> List[Gift]:
        """Scrape gifts based on given criteria"""
        pass

    @abstractmethod
    def get_search_urls(self, criteria: Dict) -> List[str]:
        """Generate search URLs based on criteria"""
        pass

    def _download_image(self, image_url: str, gift_id: str) -> Optional[str]:
        """Common image download functionality"""
        try:
            if not image_url:
                return None
                
            parsed_url = urlparse(image_url)
            ext = os.path.splitext(parsed_url.path)[1] or '.jpg'
            filename = f"gift_{gift_id}{ext}"
            image_path = self.image_folder / filename
            
            response = requests.get(image_url, stream=True)
            response.raise_for_status()
            
            with open(image_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            self.logger.info(f"Saved image for gift {gift_id} to {image_path}")
            return f"/static/gift_images/{filename}"
            
        except Exception as e:
            self.logger.error(f"Error downloading image from {image_url}: {str(e)}")
            return None

    def _determine_category(self, title: str, price: float) -> str:
        """Common category determination logic"""
        title_lower = title.lower()
        
        categories = {
            'driving': ['driving', 'car', 'racing', 'track day', 'supercar'],
            'food_drink': ['dining', 'restaurant', 'food', 'drink', 'tasting'],
            'spa': ['spa', 'massage', 'facial', 'beauty', 'treatment'],
            'adventure': ['adventure', 'outdoor', 'flying', 'skydiving'],
            'short_breaks': ['hotel', 'stay', 'break', 'getaway', 'night'],
            'entertainment': ['theatre', 'show', 'concert', 'cinema'],
            'sports': ['football', 'golf', 'stadium', 'match', 'training'],
            'experiences': ['experience', 'tour', 'lesson', 'class']
        }
        
        for category, keywords in categories.items():
            if any(keyword in title_lower for keyword in keywords):
                return category
                
        return 'luxury' if price >= 200 else 'experiences'

    def _generate_tags(self, title: str, category: str) -> str:
        """Common tag generation logic"""
        tags = {category}
        title_lower = title.lower()
        
        experience_keywords = {
            'romantic': ['couple', 'romantic', 'date', 'two'],
            'family': ['family', 'kids', 'children'],
            'adventure': ['thrill', 'adventure', 'exciting'],
            'relaxation': ['spa', 'massage', 'relax', 'pamper'],
            'food_lover': ['dining', 'tasting', 'gourmet'],
            'outdoor': ['outdoor', 'nature', 'garden'],
            'cultural': ['theatre', 'museum', 'art'],
            'learning': ['class', 'lesson', 'workshop']
        }
        
        for tag, keywords in experience_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                tags.add(tag)
        
        return ','.join(sorted(tags))