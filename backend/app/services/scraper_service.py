from typing import List, Dict
from app.models.gift import Gift
from app import db
import logging
from pathlib import Path
from .base_scraper import BaseScraper
from .buyagift_scraper import BuyAGiftScraper
from urllib.parse import urlparse
from .prezzybox_scraper import PrezzyboxScraper 
from .firebox_scraper import FireboxScraper
class ScraperService:
    def __init__(self):
        # Define static folder paths
        app_dir = Path(__file__).parent.parent
        self.image_folder = app_dir / 'static' / 'gift_images'
        self.debug_folder = app_dir / 'static' / 'debug_html'
        
        # Create directories
        self.image_folder.mkdir(parents=True, exist_ok=True)
        self.debug_folder.mkdir(parents=True, exist_ok=True)
        
        # Initialize scrapers
        self.scrapers: List[BaseScraper] = [
            #BuyAGiftScraper(self.image_folder, self.debug_folder),
            #PrezzyboxScraper(self.image_folder, self.debug_folder),
            FireboxScraper(self.image_folder, self.debug_folder)
        ]
        
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def find_gifts(self, criteria: Dict) -> List[Gift]:
        """Main method to find gifts based on criteria"""
        gifts = []
        
        try:
            self.logger.info(f"Starting gift search with criteria: {criteria}")
            
            # First check database
            existing_gifts = self._check_database(criteria)
            if len(existing_gifts) >= 20: # Minimum number of gifts in the database
                self.logger.info(f"Found sufficient gifts in database ({len(existing_gifts)})")
                return existing_gifts
            
            # If not enough gifts found, use scrapers
            self.logger.info("Not enough gifts in database, starting web scrape...")
            new_gifts = []
            
            for scraper in self.scrapers:
                scraper_gifts = scraper.scrape(criteria)
                self.logger.info(f"Found {len(scraper_gifts)} new gifts from {scraper.__class__.__name__}")
                new_gifts.extend(scraper_gifts)
            
            # Combine and save results
            gifts.extend(existing_gifts)
            gifts.extend(new_gifts)
            
            if new_gifts:
                self._save_new_gifts(new_gifts)
            
        except Exception as e:
            self.logger.error(f"Error during gift search: {str(e)}")
        
        self.logger.info(f"Returning total of {len(gifts)} gifts")
        return gifts

    def _check_database(self, criteria: Dict) -> List[Gift]:
        """Check database for existing gifts"""
        try:
            filters = []
            
            if max_price := criteria.get('max_price'):
                filters.append(Gift.price <= max_price)
            
            if categories := criteria.get('categories'):
                if categories:
                    filters.append(Gift.category.in_(categories))
            
            tag_filters = []
            for field in ['occasion', 'relationship', 'gender']:
                if value := criteria.get(field):
                    tag_filters.append(value)
            
            if interests := criteria.get('interests'):
                tag_filters.extend(interests)
            
            if tag_filters:
                tag_conditions = [Gift.tags.like(f'%{tag}%') for tag in tag_filters]
                filters.append(db.or_(*tag_conditions))
            
            query = Gift.query.filter(db.and_(*filters))
            return query.all()
            
        except Exception as e:
            self.logger.error(f"Error checking database: {str(e)}")
            return []

    def _save_new_gifts(self, gifts: List[Gift]):
        """Save new gifts to database"""
        try:
            new_count = 0
            for gift in gifts:
                if not Gift.query.filter(
                    db.or_(
                        Gift.affiliate_link == gift.affiliate_link,
                        Gift.name == gift.name
                    )
                ).first():
                    db.session.add(gift)
                    new_count += 1
            
            db.session.commit()
            self.logger.info(f"Saved {new_count} new gifts to database")
            
        except Exception as e:
            self.logger.error(f"Error saving gifts to database: {str(e)}")
            db.session.rollback()