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

class PrezzyboxScraper(BaseScraper):
    def __init__(self, image_folder, debug_folder):
        super().__init__(image_folder, debug_folder)
        self.base_url = "https://www.prezzybox.com/gift-finder?"
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.service = Service(ChromeDriverManager().install())

    def scrape(self, criteria: Dict) -> List[Gift]:
        gifts = []
        driver = None
        MAX_GIFTS = 25
        
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

    def get_search_urls(self, criteria: Dict) -> List[str]:
        """Generate Prezzybox search URLs based on criteria"""
        urls = []
        search_terms = []
        
        if criteria.get('relationship'):
            search_terms.append(criteria['relationship'])
        if criteria.get('occasion'):
            search_terms.append(criteria['occasion'])
        if criteria.get('gender'):
            search_terms.append(criteria['gender'])
        if criteria.get('interests'):
            search_terms.extend(criteria['interests'])
            
        # Map categories to Prezzybox categories
        category_mapping = {
            'food': 'food-and-drink-gifts',
            'sports_outdoor': 'sports-gifts',
            'technology': 'gadget-gifts',
            'experiences': 'experience-days',
            'gaming': 'gaming-gifts'
        }
        
        # Build category URLs
        if criteria.get('categories'):
            for category in criteria['categories']:
                if prezzy_category := category_mapping.get(category):
                    urls.append(f"{self.base_url}/{prezzy_category}")
        
        # Build search query URL if we have search terms
        if search_terms:
            search_query = '+'.join(search_terms)
            urls.append(f"{self.base_url}/search?q={search_query}")
            
        return urls or [f"{self.base_url}/gifts"]

    def _get_driver(self):
        return webdriver.Chrome(service=self.service, options=self.chrome_options)

    def _scroll_and_wait(self, driver):
        viewport_height = driver.execute_script("return window.innerHeight")
        scroll_amount = viewport_height // 2
        
        for _ in range(3):
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(2)
            
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

    def _parse_gift_element(self, element, max_price) -> Gift:
        try:
            title = element.find_element(By.CSS_SELECTOR, '.product-item__title').text
            price_text = element.find_element(By.CSS_SELECTOR, '.product-item__price').text
            price = float(price_text.replace('£', '').replace(',', ''))
            
            if price > max_price:
                return None
                
            link = element.find_element(By.CSS_SELECTOR, '.product-item__link').get_attribute('href')
            image_url = element.find_element(By.CSS_SELECTOR, '.product-item__image img').get_attribute('src')
            
            category = self._determine_category(title, price)
            tags = self._generate_tags(title, category)
            image_path = self._download_image(image_url, title) if image_url else None
            
            return Gift(
                name=title,
                price=price,
                affiliate_link=link,
                source="Prezzybox",
                image_path=image_path,
                category=category,
                tags=tags
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing gift element: {str(e)}")
            return None 