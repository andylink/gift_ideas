import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

# Load environment variables from .env file
load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    
     # MySQL configuration
    MYSQL_USER = os.environ.get('MYSQL_USER')
    MYSQL_PASSWORD = quote_plus(os.environ.get('MYSQL_PASSWORD', ''))  # URL encode the password
    MYSQL_HOST = os.environ.get('MYSQL_HOST')
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE')
    # SQLAlchemy configuration with SSL parameters
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DATABASE}"
        "?ssl_ca=none"
        "&ssl_verify_cert=false"
        "&ssl_verify_identity=false"
    )
    
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'ssl': {
                'verify_cert': False,
                'ssl_disabled': True,
            }
        }
    }
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # API Keys (for future use)
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    
    # Scraping settings
    SCRAPING_DELAY = 2  # Delay between requests in seconds
    
    # Pagination
    GIFTS_PER_PAGE = 20
    
    # OpenAI
    USE_OPENAI = False

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False 