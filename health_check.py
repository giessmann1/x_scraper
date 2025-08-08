#!/usr/bin/env python3
"""
Health Check Script for X Scraper
Tests database connectivity and scraper functionality
"""

import os
import sys
import time
from typing import Dict, Any, Optional
import urllib.parse

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import pymongo
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import NoSuchElementException, WebDriverException
    import undetected_chromedriver as uc
    from selenium.webdriver.chrome.service import Service
    from bs4 import BeautifulSoup
    from database_wrapper import mongo_authenticate
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


def test_database_connection() -> bool:
    try:
        print("Testing database connection...")
        
        client = mongo_authenticate("")
        
        client.admin.command('ping')
        
        db = client.xdb
        collections = db.list_collection_names()
        
        print(f"Database connection successful!")
        print(f"   Available collections: {collections}")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


def setup_test_driver() -> Optional[uc.Chrome]:
    try:
        options = uc.ChromeOptions()
        options.headless = True
        
        if os.environ.get('DOCKER_ENV'):
            options.binary_location = "/usr/bin/chromium"
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-user-data-dir")
            service = Service(executable_path="/home/chromedriver")
            driver = uc.Chrome(
                use_subprocess=True, 
                options=options, 
                service=service, 
                driver_executable_path="/home/chromedriver", 
                version_main=138, 
                keep_alive=False
            )
        else:
            driver = uc.Chrome(use_subprocess=True, options=options, version_main=112)
        
        return driver
        
    except Exception as e:
        print(f"Failed to setup Chrome driver: {e}")
        return None


def test_scraper_functionality() -> bool:
    try:
        print("Testing scraper functionality...")
        
        driver = setup_test_driver()
        if not driver:
            return False
        
        test_url = "https://xcancel.com/elonmusk"
        
        print(f"   Loading test URL: {test_url}")
        driver.get(test_url)
        
        time.sleep(3)
        
        if "xcancel.com" not in driver.current_url:
            print("Failed to load test URL")
            driver.quit()
            return False
        
        try:
            profile_elements = driver.find_elements(By.CSS_SELECTOR, "[class*='profile']")
            if not profile_elements:
                profile_elements = driver.find_elements(By.CSS_SELECTOR, "[class*='user']")
            
            if profile_elements:
                print("Page loaded successfully")
                print(f"   Found profile elements: {len(profile_elements)}")
                
                for elem in profile_elements[:3]:
                    text = elem.text.strip()
                    if text and len(text) > 10:
                        print(f"   Profile info: {text[:100]}...")
                        break
            else:
                print("Page loaded but no profile elements found")
            
            tweet_elements = driver.find_elements(By.CSS_SELECTOR, "[class*='tweet']")
            if tweet_elements:
                print(f"   Found tweet elements: {len(tweet_elements)}")
            
            print("   Testing basic scraping logic...")
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            tweets = soup.find_all('article')
            if tweets:
                print(f"   Found {len(tweets)} potential tweet articles")
                
                first_tweet = tweets[0]
                tweet_text = first_tweet.get_text()[:100] + "..." if len(first_tweet.get_text()) > 100 else first_tweet.get_text()
                print(f"   Sample tweet content: {tweet_text}")
                
            print("Scraper functionality test passed!")
            driver.quit()
            return True
            
        except Exception as e:
            print(f"Error during scraping test: {e}")
            driver.quit()
            return False
            
    except Exception as e:
        print(f"Scraper functionality test failed: {e}")
        return False


def main() -> None:
    print("Starting X Scraper Health Check...")
    print("=" * 50)
    
    db_ok = test_database_connection()
    
    print()
    
    scraper_ok = test_scraper_functionality()
    
    print()
    print("=" * 50)
    print("Health Check Results:")
    print(f"   Database Connection: {'PASS' if db_ok else 'FAIL'}")
    print(f"   Scraper Functionality: {'PASS' if scraper_ok else 'FAIL'}")
    
    if db_ok and scraper_ok:
        print("All systems operational!")
        sys.exit(0)
    else:
        print("Some systems are not working properly")
        sys.exit(1)


if __name__ == "__main__":
    main()
