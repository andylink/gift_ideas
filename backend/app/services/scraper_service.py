import requests
from bs4 import BeautifulSoup
import time
from app.models.gift import Gift
from urllib.parse import urljoin
import logging
from fake_useragent import UserAgent
from concurrent.futures import ThreadPoolExecutor
from config import Config
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from tenacity import retry, stop_after_attempt, wait_exponential
from sqlalchemy import and_
from app import db
import os
from urllib.parse import urlparse
from pathlib import Path

class ScraperService:
    def __init__(self):
        self.headers = {'User-Agent': UserAgent().random}
        self.delay = Config.SCRAPING_DELAY
        self.session = requests.Session()
        
        # Initialize Chrome options and service
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.service = Service(ChromeDriverManager().install())
        
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # Define BuyAGift categories mapping
        self.buyagift_categories = {
            'experience': 'Experience+Boxes',
            'food_drink': 'Food+and+Drink',
            'spa': 'Spa+%26+Beauty',
            'short_breaks': 'Short+Breaks',
            'adventure': 'Adventure',
            'driving': 'Driving',
            'flying': 'Flying'
        }

        # Define static folder path relative to the app directory
        app_dir = Path(__file__).parent.parent  # gets the app/ directory
        self.image_folder = app_dir / 'static' / 'gift_images'
        self.debug_folder = app_dir / 'static' / 'debug_html'
        
        # Create the directories if they don't exist
        self.image_folder.mkdir(parents=True, exist_ok=True)
        self.debug_folder.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Image folder path: {self.image_folder}")

    def find_gifts(self, criteria):
        """
        Main method to find gifts based on criteria
        """
        gifts = []
        try:
            print("\n=== Starting Gift Search ===")
            self.logger.info(f"Starting gift search with criteria: {criteria}")
            
            # First check database
            existing_gifts = self._check_database(criteria)
            
            # If we found enough gifts in database
            if len(existing_gifts) >= 5:
                print(f"Found sufficient gifts in database ({len(existing_gifts)}), skipping scrape")
                return existing_gifts
                
            # If not enough gifts found, scrape new ones
            print("\nNot enough gifts in database, starting web scrape...")
            buyagift_gifts = self._scrape_buyagift(criteria)
            print(f"Found {len(buyagift_gifts)} new gifts from BuyAGift")
            
            # Combine results
            gifts.extend(existing_gifts)
            gifts.extend(buyagift_gifts)
            
            # Save new gifts
            if buyagift_gifts:
                print("\nSaving new gifts to database...")
                self._save_new_gifts(buyagift_gifts)
            
        except Exception as e:
            print(f"\nERROR during gift search: {str(e)}")
            self.logger.error(f"Error during gift search: {str(e)}")
        
        print(f"\nReturning total of {len(gifts)} gifts")
        print("=====================================\n")
        return gifts

    def _scrape_buyagift(self, criteria):
        """
        Scrapes BuyAGift website based on given criteria using Selenium
        """
        gifts = []
        base_url = "https://www.buyagift.co.uk"
        driver = None
        
        try:
            driver = self._get_driver()
            search_urls = self._get_buyagift_search_urls(criteria)
            max_price = criteria.get('max_price', 1000)
            
            for url in search_urls:
                try:
                    self.logger.info(f"Scraping URL: {url}")
                    driver.get(url)
                    
                    # Save page source for debugging
                    debug_file = self.debug_folder / 'buyagift_debug.html'
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(driver.page_source)
                    
                    wait = WebDriverWait(driver, 10)
                    gift_elements = wait.until(
                        EC.presence_of_all_elements_located(
                            (By.CSS_SELECTOR, '[data-product-id]')
                        )
                    )
                    
                    self.logger.info(f"Found {len(gift_elements)} gift elements")
                    
                    for element in gift_elements:
                        try:
                            title = element.find_element(By.CSS_SELECTOR, 'h3[data-testid="product-name"]').get_attribute('title')
                            price_text = element.find_element(By.CSS_SELECTOR, 'span[data-testid="price"]').text
                            price = float(price_text.replace('£', '').replace(',', ''))
                            link = element.find_element(By.CSS_SELECTOR, 'a').get_attribute('href')
                            full_link = base_url + link if not link.startswith('http') else link
                            
                            # Extract image URL - updated selectors
                            try:
                                # Try multiple possible image selectors
                                img_elem = element.find_element(
                                    By.CSS_SELECTOR, 
                                    'img[srcset], img[data-src], img[src*="images.buyagift.co.uk"]'
                                )
                                
                                # Try srcset first, then data-src, then src
                                image_url = (
                                    img_elem.get_attribute('srcset') or 
                                    img_elem.get_attribute('data-src') or 
                                    img_elem.get_attribute('src')
                                )
                                
                                # If srcset contains multiple URLs, get the largest one
                                if image_url and ' ' in image_url:
                                    # Split srcset into URL/size pairs and get the largest
                                    srcset_pairs = [pair.strip() for pair in image_url.split(',')]
                                    largest_image = max(
                                        srcset_pairs,
                                        key=lambda x: int(x.split(' ')[1].replace('w', ''))
                                    )
                                    image_url = largest_image.split(' ')[0]
                                
                                self.logger.info(f"Found image URL: {image_url}")
                            except Exception as img_error:
                                image_url = None
                                self.logger.warning(f"Could not find image for gift: {title}. Error: {str(img_error)}")
                            
                            if price <= max_price:
                                gift = Gift(
                                    name=title,
                                    price=price,
                                    affiliate_link=full_link,
                                    source="BuyAGift",
                                    image_path=self._download_image(image_url, title) if image_url else None
                                )
                                gifts.append(gift)
                                self.logger.info(f"Added gift: {title} (£{price}) with image: {image_url}")
                                
                        except Exception as e:
                            self.logger.error(f"Error parsing gift element: {str(e)}")
                            continue
                        
                except Exception as e:
                    self.logger.error(f"Error scraping BuyAGift URL {url}: {str(e)}")
                    continue
                
        finally:
            if driver:
                driver.quit()
        
        return gifts

    def _get_buyagift_search_urls(self, criteria):
        """
        Generates search URLs based on criteria using BuyAGift's URL structure
        """
        base_url = "https://www.buyagift.co.uk/Search/Results"
        urls = []
        
        # Extract and format search terms
        search_terms = []
        
        # Add relationship if it exists (e.g., "brother", "sister", etc.)
        if criteria.get('relationship'):
            if criteria['relationship'] == 'family':
                search_terms.append('brother')  # Default to brother for male family member
            else:
                search_terms.append(criteria['relationship'])
        
        # Add occasion
        if criteria.get('occasion'):
            search_terms.append(criteria['occasion'])
        
        # Add gender-specific term
        if criteria.get('gender'):
            search_terms.append(criteria['gender'])
        
        # Add interests
        if criteria.get('interests'):
            search_terms.extend(criteria['interests'])
        
        # Clean and join search terms with 'for' and spaces
        keyword = '+'.join(search_terms)
        if keyword:
            keyword = keyword.replace(' ', '+')
        
        # Map our categories to BuyAGift categories
        if criteria.get('categories'):
            for category in criteria['categories']:
                buyagift_category = None
                
                # Map our categories to BuyAGift's structure
                if category in ['fitness', 'sports_outdoor']:
                    buyagift_category = 'Adventure+Experiences'
                elif category == 'driving':
                    buyagift_category = 'Driving+Experiences'
                elif category == 'food':
                    buyagift_category = 'Food+and+Drink'
                # Add more category mappings as needed
                
                if buyagift_category:
                    url = f"{base_url}?filter=&Categories={buyagift_category}"
                    if keyword:
                        url += f"&keyword={keyword}"
                    urls.append(url)
        
        # If no specific categories, just use keyword search
        if not urls and keyword:
            urls.append(f"{base_url}?filter=&keyword={keyword}")
        
        # If no URLs generated, use default search
        if not urls:
            urls = [f"{base_url}?filter="]
        
        # Debug logging
        for url in urls:
            self.logger.info(f"Generated BuyAGift URL: {url}")
            
        return urls

    def _parse_buyagift_element(self, element, base_url):
        """
        Parses a single gift element from BuyAGift
        Returns a Gift object
        """
        try:
            # Name: Inside h3 with class ProductCard_productTitle__xxx
            name_elem = element.find('h3', class_=lambda x: x and x.startswith('ProductCard_productTitle__'))
            if not name_elem:
                return None
            name = name_elem.text.strip()
            
            # Price: Inside span with class ProductCard_price__xxx
            price_elem = element.find('span', class_=lambda x: x and x.startswith('ProductCard_price__'))
            if not price_elem:
                return None
            price_text = price_elem.text.strip()
            # Remove £ and convert to float
            price = float(price_text.replace('£', '').replace(',', ''))
            
            # Description: Inside div with class ProductCard_description__xxx
            description_elem = element.find('div', class_=lambda x: x and x.startswith('ProductCard_description__'))
            description = description_elem.text.strip() if description_elem else ''
            
            # URL: Inside anchor tag
            link_elem = element.find('a', class_=lambda x: x and x.startswith('ProductCard_card__'))
            if not link_elem:
                return None
            link = link_elem.get('href', '')
            
            # Image: Inside img tag within picture element
            image_elem = element.find('img', class_=lambda x: x and x.startswith('ProductCard_image__'))
            image_url = image_elem.get('src', '') if image_elem else ''
            
            # Debug logging
            self.logger.debug(f"Parsed gift: {name} - £{price}")
            
            # Convert relative URL to absolute URL
            url = urljoin(base_url, link)
            
            return Gift(
                name=name,
                description=description,
                price=price,
                url=url,
                image_url=image_url,
                source='buyagift',
                category=self._determine_category(name, description)
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing gift element: {str(e)}")
            return None

    def _make_request(self, url):
        """
        Makes an HTTP request with error handling and retries
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.get(
                    url,
                    headers=self.headers,
                    timeout=10
                )
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                if attempt == max_retries - 1:
                    self.logger.error(f"Failed to fetch {url} after {max_retries} attempts")
                    return None
                time.sleep(self.delay * (attempt + 1))  # Exponential backoff

    def _determine_category(self, name, description):
        """
        Determines the category based on gift name and description
        """
        text = f"{name} {description}".lower()
        
        # Updated keywords for BuyAGift categories
        keywords = {
            'experience': ['experience', 'activity', 'adventure'],
            'food_drink': ['dining', 'restaurant', 'food', 'drink', 'tasting'],
            'spa': ['spa', 'massage', 'beauty', 'treatment', 'pamper'],
            'short_breaks': ['hotel', 'getaway', 'break', 'stay', 'night'],
            'adventure': ['outdoor', 'extreme', 'adventure', 'adrenaline'],
            'driving': ['driving', 'car', 'track', 'racing'],
            'flying': ['flying', 'flight', 'helicopter', 'airplane']
        }
        
        for category, words in keywords.items():
            if any(word in text for word in words):
                return category
                
        return 'other'

    def _clean_text(self, text):
        """
        Cleans and normalizes text
        """
        if not text:
            return ""
        return " ".join(text.split()) 

    def _get_driver(self):
        """Creates and returns a new WebDriver instance"""
        return webdriver.Chrome(
            service=self.service,
            options=self.chrome_options
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _scrape_with_retry(self, url, driver):
        """Attempts to scrape a URL with retry logic"""
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        return wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, '.ProductCard_productCard__2zqAz')
            )
        )

    def _check_database(self, criteria):
        """
        Check database for existing gifts matching criteria
        """
        try:
            print("\n=== Checking Database for Existing Gifts ===")
            print(f"Criteria received: {criteria}")
            
            # First, let's see what's in the database
            all_gifts = Gift.query.all()
            print(f"\nTotal gifts in database: {len(all_gifts)}")
            print("Sample of gifts in database:")
            for gift in all_gifts[:5]:  # Show first 5 gifts
                print(f"- {gift.name} (£{gift.price}) [source: {gift.source}, tags: {gift.tags}]")
            
            # Build query filters
            filters = []
            
            # Price filter
            if max_price := criteria.get('max_price'):
                filters.append(Gift.price <= max_price)
                print(f"\nAdded price filter: <= {max_price}")
                # Debug: Show gifts that match price
                price_matches = Gift.query.filter(Gift.price <= max_price).all()
                print(f"Gifts matching price filter: {len(price_matches)}")
            
            # Source filter - let's check specifically for buyagift
            filters.append(Gift.source == 'buyagift')
            print(f"\nAdded source filter: buyagift")
            source_matches = Gift.query.filter(Gift.source == 'buyagift').all()
            print(f"Gifts matching source filter: {len(source_matches)}")
            
            # Category filter
            if categories := criteria.get('categories'):
                if len(categories) > 0:
                    filters.append(Gift.category.in_(categories))
                    print(f"\nAdded category filter: {categories}")
                    
            # Execute final query with all filters
            print("\nExecuting final database query...")
            query = Gift.query.filter(and_(*filters))
            print(f"SQL Query: {query}")  # Print the actual SQL query
            
            existing_gifts = query.all()
            
            print(f"\nFound {len(existing_gifts)} matching gifts in database")
            if existing_gifts:
                print("Matching gifts:")
                for gift in existing_gifts:
                    print(f"- {gift.name} (£{gift.price}) [source: {gift.source}]")
            else:
                print("No matching gifts found!")
                
            print("=====================================\n")
            
            return existing_gifts
            
        except Exception as e:
            print(f"\nERROR checking database: {str(e)}")
            self.logger.error(f"Error checking database: {str(e)}")
            return []

    def _save_new_gifts(self, gifts):
        """
        Save new gifts to database
        """
        try:
            for gift in gifts:
                # Check if gift already exists by URL to avoid duplicates
                existing = Gift.query.filter_by(affiliate_link=gift.affiliate_link).first()
                if not existing:
                    db.session.add(gift)
            
            db.session.commit()
            self.logger.info("Successfully saved new gifts to database")
        except Exception as e:
            self.logger.error(f"Error saving gifts to database: {str(e)}")
            db.session.rollback()

    def _download_image(self, image_url, gift_id):
        """
        Downloads and saves an image locally
        Returns the local path to the saved image
        """
        try:
            if not image_url:
                return None
                
            # Create filename from gift_id and original extension
            parsed_url = urlparse(image_url)
            ext = os.path.splitext(parsed_url.path)[1]
            if not ext:
                ext = '.jpg'  # Default extension
            filename = f"gift_{gift_id}{ext}"
            
            # Full path for saving
            image_path = self.image_folder / filename
            
            # Download and save image
            response = requests.get(image_url, stream=True)
            response.raise_for_status()
            
            with open(image_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            self.logger.info(f"Saved image for gift {gift_id} to {image_path}")
            
            # Return the URL path that Flask will use to serve the image
            return f"/static/gift_images/{filename}"
            
        except Exception as e:
            self.logger.error(f"Error downloading image from {image_url}: {str(e)}")
            return None