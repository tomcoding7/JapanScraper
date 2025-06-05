"""
Bookmark Manager for Yu-Gi-Oh Card Arbitrage Bot

This module handles saving promising auctions and exporting them to ZenMarket
for later bidding.
"""

import os
import json
import logging
import time
import random
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('arbitrage_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BookmarkManager:
    """
    Handles saving promising auctions and exporting them to ZenMarket.
    """
    
    def __init__(self, output_dir: str = "results", zenmarket_credentials: Dict[str, str] = None):
        """
        Initialize the BookmarkManager.
        
        Args:
            output_dir (str, optional): Output directory. Defaults to "results".
            zenmarket_credentials (Dict[str, str], optional): ZenMarket credentials. Defaults to None.
        """
        self.output_dir = output_dir
        self.bookmarks_dir = os.path.join(output_dir, "bookmarks")
        self.zenmarket_credentials = zenmarket_credentials or {}
        self.driver = None
        
        # Create directories
        os.makedirs(self.bookmarks_dir, exist_ok=True)
        
        # Load existing bookmarks
        self.bookmarks = self._load_bookmarks()
        
        logger.info("BookmarkManager initialized with output directory: %s", output_dir)
    
    def save_auction(self, auction_data: Dict[str, Any]) -> bool:
        """
        Save an auction to the bookmarks.
        
        Args:
            auction_data (Dict[str, Any]): Auction data to save.
        
        Returns:
            bool: Success status.
        """
        try:
            # Extract auction ID from URL
            url = auction_data.get('url', '')
            auction_id = self._extract_auction_id(url)
            
            if not auction_id:
                logger.warning("Could not extract auction ID from URL: %s", url)
                return False
            
            # Add timestamp and ID
            auction_data['bookmark_timestamp'] = datetime.now().isoformat()
            auction_data['auction_id'] = auction_id
            
            # Save to bookmarks
            self.bookmarks[auction_id] = auction_data
            
            # Save to file
            self._save_bookmarks()
            
            # Save individual auction file
            self._save_individual_auction(auction_id, auction_data)
            
            logger.info("Saved auction to bookmarks: %s", auction_id)
            return True
            
        except Exception as e:
            logger.error("Error saving auction: %s", str(e), exc_info=True)
            return False
    
    def get_watchlist(self) -> List[Dict[str, Any]]:
        """
        Get the current watchlist.
        
        Returns:
            List[Dict[str, Any]]: List of bookmarked auctions.
        """
        return list(self.bookmarks.values())
    
    def update_auction_status(self, auction_id: str, status: str) -> bool:
        """
        Update the status of an auction.
        
        Args:
            auction_id (str): Auction ID.
            status (str): New status.
        
        Returns:
            bool: Success status.
        """
        try:
            if auction_id not in self.bookmarks:
                logger.warning("Auction not found in bookmarks: %s", auction_id)
                return False
            
            # Update status
            self.bookmarks[auction_id]['status'] = status
            self.bookmarks[auction_id]['status_updated'] = datetime.now().isoformat()
            
            # Save to file
            self._save_bookmarks()
            
            # Update individual auction file
            self._save_individual_auction(auction_id, self.bookmarks[auction_id])
            
            logger.info("Updated auction status: %s -> %s", auction_id, status)
            return True
            
        except Exception as e:
            logger.error("Error updating auction status: %s", str(e), exc_info=True)
            return False
    
    def validate_zenmarket_credentials(self) -> bool:
        """
        Validate ZenMarket credentials by attempting to log in.
        
        Returns:
            bool: True if credentials are valid, False otherwise.
        """
        if not self.zenmarket_credentials:
            logger.error("ZenMarket credentials not set")
            return False
        
        try:
            # Initialize browser
            driver = self._init_browser()
            if not driver:
                return False
            
            try:
                # Navigate to login page
                driver.get("https://zenmarket.jp/en/login.aspx")
                
                # Wait for login form
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "email"))
                )
                
                # Enter credentials
                driver.find_element(By.ID, "email").send_keys(self.zenmarket_credentials['email'])
                driver.find_element(By.ID, "password").send_keys(self.zenmarket_credentials['password'])
                
                # Click login button
                driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
                
                # Wait for successful login
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "user-menu"))
                )
                
                logger.info("Successfully validated ZenMarket credentials")
                return True
                
            except Exception as e:
                logger.error("Error validating ZenMarket credentials: %s", str(e))
                return False
                
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error("Error initializing browser for credential validation: %s", str(e))
            return False
    
    def export_to_zenmarket(self, listing_ids: List[str] = None) -> bool:
        """
        Export bookmarked auctions to ZenMarket.
        
        Args:
            listing_ids (List[str], optional): List of auction IDs to export. Defaults to None.
        
        Returns:
            bool: True if export was successful, False otherwise.
        """
        if not self.validate_zenmarket_credentials():
            logger.error("Invalid ZenMarket credentials")
            return False
        
        try:
            # Initialize browser
            driver = self._init_browser()
            if not driver:
                return False
            
            try:
                # Log in to ZenMarket
                if not self._login_to_zenmarket(driver):
                    return False
                
                # Get watchlist
                watchlist = self.get_watchlist()
                
                # Filter by listing IDs if provided
                if listing_ids:
                    watchlist = [item for item in watchlist if item.get('auction_id') in listing_ids]
                
                if not watchlist:
                    logger.warning("No auctions to export")
                    return False
                
                # Export each auction
                success_count = 0
                for item in watchlist:
                    try:
                        # Navigate to auction URL
                        driver.get(item['url'])
                        
                        # Wait for page to load
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "item-detail"))
                        )
                        
                        # Click bookmark button
                        bookmark_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.CLASS_NAME, "bookmark-button"))
                        )
                        bookmark_button.click()
                        
                        # Wait for confirmation
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "bookmark-success"))
                        )
                        
                        success_count += 1
                        logger.info("Successfully exported auction %s", item['auction_id'])
                        
                        # Add delay between exports
                        time.sleep(random.uniform(2, 4))
                        
                    except Exception as e:
                        logger.error("Error exporting auction %s: %s", item.get('auction_id'), str(e))
                        continue
                
                logger.info("Exported %d/%d auctions successfully", success_count, len(watchlist))
                return success_count > 0
                
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error("Error in export_to_zenmarket: %s", str(e))
            return False
    
    def _init_browser(self) -> webdriver.Chrome:
        """
        Initialize WebDriver for ZenMarket integration.
        
        Returns:
            webdriver.Chrome: Selenium WebDriver instance.
        """
        try:
            chrome_options = Options()
            
            # Basic options
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-infobars')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            
            # Window size and user agent
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--start-maximized')
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Additional anti-detection measures
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Create the driver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set page load timeout
            driver.set_page_load_timeout(30)
            
            # Set window size explicitly after creation
            driver.set_window_size(1920, 1080)
            
            logger.info("WebDriver initialized successfully")
            return driver
            
        except Exception as e:
            logger.error("Failed to setup WebDriver: %s", str(e), exc_info=True)
            return None
    
    def _login_to_zenmarket(self, driver: webdriver.Chrome) -> bool:
        """
        Log in to ZenMarket.
        
        Args:
            driver (webdriver.Chrome): Selenium WebDriver instance.
        
        Returns:
            bool: True if login was successful, False otherwise.
        """
        try:
            # Navigate to login page
            driver.get("https://zenmarket.jp/en/login.aspx")
            
            # Wait for login form
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            
            # Enter credentials
            driver.find_element(By.ID, "email").send_keys(self.zenmarket_credentials['email'])
            driver.find_element(By.ID, "password").send_keys(self.zenmarket_credentials['password'])
            
            # Click login button
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            
            # Wait for successful login
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "user-menu"))
            )
            
            logger.info("Successfully logged in to ZenMarket")
            return True
            
        except Exception as e:
            logger.error("Error logging in to ZenMarket: %s", str(e))
            return False
    
    def _extract_auction_id(self, url: str) -> Optional[str]:
        """
        Extract auction ID from URL.
        
        Args:
            url (str): Auction URL.
        
        Returns:
            Optional[str]: Auction ID or None if not found.
        """
        try:
            # Extract auction ID from various URL formats
            if "auctions.yahoo.co.jp" in url or "page.auctions.yahoo.co.jp" in url:
                # Yahoo Auction URL format: https://page.auctions.yahoo.co.jp/jp/auction/x123456789
                parts = url.split("/")
                return parts[-1]
            elif "buyee.jp" in url:
                # Buyee URL format: https://buyee.jp/item/yahoo/auction/x123456789
                parts = url.split("/")
                return parts[-1]
            else:
                logger.warning("Unknown URL format: %s", url)
                return None
                
        except Exception as e:
            logger.error("Error extracting auction ID: %s", str(e))
            return None
    
    def _load_bookmarks(self) -> Dict[str, Dict[str, Any]]:
        """
        Load bookmarks from file.
        
        Returns:
            Dict[str, Dict[str, Any]]: Bookmarks dictionary.
        """
        bookmarks_file = os.path.join(self.bookmarks_dir, "bookmarks.json")
        
        if os.path.exists(bookmarks_file):
            try:
                with open(bookmarks_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Error loading bookmarks: %s", str(e))
                return {}
        else:
            return {}
    
    def _save_bookmarks(self) -> None:
        """
        Save bookmarks to file.
        """
        bookmarks_file = os.path.join(self.bookmarks_dir, "bookmarks.json")
        
        try:
            with open(bookmarks_file, 'w', encoding='utf-8') as f:
                json.dump(self.bookmarks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Error saving bookmarks: %s", str(e))
    
    def _save_individual_auction(self, auction_id: str, auction_data: Dict[str, Any]) -> None:
        """
        Save individual auction data to file.
        
        Args:
            auction_id (str): Auction ID.
            auction_data (Dict[str, Any]): Auction data.
        """
        auction_file = os.path.join(self.bookmarks_dir, f"{auction_id}.json")
        
        try:
            with open(auction_file, 'w', encoding='utf-8') as f:
                json.dump(auction_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Error saving individual auction data: %s", str(e))

# Example usage
if __name__ == "__main__":
    # Initialize BookmarkManager
    bookmark_manager = BookmarkManager()
    
    # Example auction data
    auction_data = {
        'title': 'Blue-Eyes White Dragon SDK-001 Ultra Rare',
        'price': 5000,
        'url': 'https://buyee.jp/item/yahoo/auction/x123456789',
        'image_url': 'https://example.com/image.jpg',
        'condition': 'Near Mint',
        'profit_analysis': {
            'roi': 2.5,
            'profit': 50.0
        }
    }
    
    # Save auction
    bookmark_manager.save_auction(auction_data)
    
    # Get watchlist
    watchlist = bookmark_manager.get_watchlist()
    
    # Print watchlist
    print(f"\nWatchlist ({len(watchlist)} items):")
    for item in watchlist:
        print(f"- {item.get('title', 'Unknown')}")
        print(f"  ID: {item.get('auction_id', 'Unknown')}")
        print(f"  Price: ¥{item.get('price', 0):,}")
        print(f"  ROI: {item.get('profit_analysis', {}).get('roi', 0):.2f}x")
        print()
