from app.models.gift import Gift
from app.services.scraper_service import ScraperService
from app import db

class GiftService:
    def __init__(self):
        self.scraper = ScraperService()
    
    def find_gifts(self, criteria):
        """
        Find gifts based on the given criteria
        """
        try:
            # Ensure criteria is a dictionary
            if not isinstance(criteria, dict):
                criteria = {}
            
            # First search in database
            gifts = self._search_database(criteria)
            
            # If not enough results, scrape more
            if len(gifts) < 10:
                scraped_gifts = self.scraper.find_gifts(criteria)
                self._save_new_gifts(scraped_gifts)
                gifts.extend(scraped_gifts)
            
            return gifts
            
        except Exception as e:
            print(f"Error in find_gifts: {str(e)}")
            return []
    
    def _search_database(self, criteria):
        """
        Search the database using the provided criteria
        """
        try:
            query = Gift.query
            
            # Safely access criteria values with .get()
            if criteria.get('max_price'):
                query = query.filter(Gift.price <= float(criteria['max_price']))
            
            if criteria.get('categories'):
                if isinstance(criteria['categories'], list):
                    query = query.filter(Gift.category.in_(criteria['categories']))
            
            # Add more filters based on criteria
            if criteria.get('gender'):
                query = query.filter(Gift.tags.like(f"%{criteria['gender']}%"))
                
            if criteria.get('age'):
                # You might want to implement age-appropriate filtering logic here
                pass
                
            return query.all()
            
        except Exception as e:
            print(f"Error in _search_database: {str(e)}")
            return []
    
    def _save_new_gifts(self, gifts):
        """
        Save new gifts to the database, avoiding duplicates
        """
        try:
            for gift in gifts:
                # Check for duplicates
                existing = Gift.query.filter_by(
                    name=gift.name,
                    source=gift.source
                ).first()
                
                if not existing:
                    db.session.add(gift)
            
            db.session.commit()
            
        except Exception as e:
            print(f"Error in _save_new_gifts: {str(e)}")
            db.session.rollback() 