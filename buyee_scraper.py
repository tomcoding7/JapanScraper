from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.remote.webelement import WebElement
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
import pandas as pd
import time
import json
import os
from datetime import datetime
import logging
from urllib.parse import urljoin, quote
from search_terms import SEARCH_TERMS
import csv
import traceback
from typing import Dict, List, Optional, Any, Tuple
from scraper_utils import RequestHandler, CardInfoExtractor, PriceAnalyzer, ConditionAnalyzer
from dotenv import load_dotenv
import re
import socket
import requests.exceptions
import urllib3
import argparse
import statistics
from image_analyzer import ImageAnalyzer
import glob
from card_analyzer import CardAnalyzer, CardInfo, CardCondition
from rank_analyzer import RankAnalyzer
from dataclasses import asdict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Set up logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    logger.error("OPENAI_API_KEY not found. Please check your .env file and its location.")
    import sys
    sys.exit(1)

class BuyeeScraper:
    def __init__(self, output_dir: str = "scraped_results", max_pages: int = 5, headless: bool = True):
        """
        Initialize the BuyeeScraper with configuration options.
        
        Args:
            output_dir (str): Directory to save scraped data
            max_pages (int): Maximum number of pages to scrape per search
            headless (bool): Run Chrome in headless mode
        """
        self.base_url = "https://buyee.jp"
        self.output_dir = output_dir
        self.max_pages = max_pages
        self.headless = headless
        self.driver = None
        self.request_handler = RequestHandler()
        self.card_analyzer = CardAnalyzer()
        self.rank_analyzer = RankAnalyzer()
        
        # Load selectors from JSON file
        self.selectors = self._load_selectors()
        
        # Session management
        self.session_retry_count = 0
        self.max_session_retries = 3
        self.session_retry_delay = 5  # seconds
        
        # Element location configuration
        self.default_wait_time = 30  # seconds
        self.element_wait_time = 20  # seconds
        self.page_load_timeout = 30  # seconds
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, 'debug'), exist_ok=True)
        
        # Initialize driver
        if not self.setup_driver():
            raise Exception("Failed to initialize WebDriver")

    def _load_selectors(self) -> Dict[str, Any]:
        """Load CSS selectors from the JSON configuration file."""
        try:
            with open('selectors.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load selectors.json: {str(e)}")
            raise

    def save_debug_info(self, identifier: str, error_type: str, page_source: str) -> None:
        """Save debug information about a failed request."""
        try:
            # Sanitize the identifier for use in filenames
            safe_identifier = self.sanitize_filename(identifier)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create debug directory if it doesn't exist
            debug_dir = os.path.join(self.output_dir, 'debug')
            os.makedirs(debug_dir, exist_ok=True)
            
            # Save HTML source
            html_path = os.path.join(debug_dir, f"{safe_identifier}_{timestamp}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(page_source)
            
            # Take screenshot if driver is available
            if self.driver:
                screenshot_path = os.path.join(debug_dir, f"{safe_identifier}_{timestamp}.png")
                self.driver.save_screenshot(screenshot_path)
            
            logger.info(f"Debug info saved: {html_path}")
            
        except Exception as e:
            logger.error(f"Error saving debug info: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((WebDriverException, TimeoutException))
    )
    def handle_cookie_consent(self) -> bool:
        """Handle cookie consent popup with improved reliability."""
        try:
            # Wait for cookie banner to be present
            cookie_banner = self.wait_for_element(
                By.CSS_SELECTOR,
                self.selectors['popups']['cookie_banner'],
                timeout=10,
                condition="presence"
            )
            
            if not cookie_banner:
                logger.debug("No cookie banner found")
                return True
            
            # Wait for accept button to be clickable
            accept_button = self.wait_for_element(
                By.CSS_SELECTOR,
                self.selectors['popups']['cookie_accept'],
                timeout=10,
                condition="clickable",
                parent=cookie_banner
            )
            
            if not accept_button:
                logger.warning("Cookie accept button not found")
                return False
            
            # Click the accept button
            accept_button.click()
            
            # Wait for banner to disappear
            try:
                WebDriverWait(self.driver, 10).until_not(
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.selectors['popups']['cookie_banner']))
                )
                logger.info("Cookie consent handled successfully")
                return True
            except TimeoutException:
                logger.warning("Cookie banner did not disappear after clicking accept")
                return False
                
        except Exception as e:
            logger.error(f"Error handling cookie consent: {str(e)}")
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((WebDriverException, TimeoutException))
    )
    def get_item_summaries_from_search_page(self, page_number: int = 1) -> List[Dict]:
        """Get item summaries from the current search page with improved error handling."""
        try:
            # Wait for the search results container
            container = self.wait_for_element(
                By.CSS_SELECTOR,
                self.selectors['search_results']['container'],
                timeout=self.element_wait_time
            )
            
            if not container:
                logger.error("Could not find item list container")
                self.save_debug_info(
                    f"page_{page_number}_no_container",
                    "container_not_found",
                    self.driver.page_source
                )
                return []
            
            # Get all item cards
            item_cards = container.find_elements(By.CSS_SELECTOR, self.selectors['search_results']['item_card'])
            
            if not item_cards:
                logger.warning(f"No items found on page {page_number}")
                return []
            
            items = []
            for index, card in enumerate(item_cards):
                try:
                    if not self.is_element_attached(card):
                        continue
                    
                    item_info = self.extract_card_info(card, index)
                    if item_info:
                        items.append(item_info)
                        
                except StaleElementReferenceException:
                    logger.warning(f"Stale element reference for item {index}")
                    continue
                except Exception as e:
                    logger.error(f"Error extracting info for item {index}: {str(e)}")
                    continue
            
            return items
            
        except Exception as e:
            logger.error(f"Error getting item summaries: {str(e)}")
            self.save_debug_info(
                f"page_{page_number}_error",
                "get_summaries_error",
                self.driver.page_source
            )
            return []

    def extract_card_info(self, card: WebElement, index: int) -> Optional[Dict[str, Any]]:
        """Extract information from a card element with improved error handling."""
        try:
            # Extract title
            title_elem = self.wait_for_element(
                By.CSS_SELECTOR,
                self.selectors['search_results']['title'],
                timeout=5,
                parent=card
            )
            title = title_elem.text if title_elem else "Unknown Title"
            
            # Extract price
            price_elem = self.wait_for_element(
                By.CSS_SELECTOR,
                self.selectors['search_results']['price'],
                timeout=5,
                parent=card
            )
            price = self.clean_price(price_elem.text) if price_elem else 0.0
            
            # Extract image URL
            img_elem = self.wait_for_element(
                By.CSS_SELECTOR,
                self.selectors['search_results']['image'],
                timeout=5,
                parent=card
            )
            image_url = img_elem.get_attribute('src') if img_elem else None
            
            # Extract link
            link_elem = self.wait_for_element(
                By.CSS_SELECTOR,
                self.selectors['search_results']['link'],
                timeout=5,
                parent=card
            )
            url = link_elem.get_attribute('href') if link_elem else None
            
            # Extract time left
            time_elem = self.wait_for_element(
                By.CSS_SELECTOR,
                self.selectors['search_results']['time_left'],
                timeout=5,
                parent=card
            )
            time_left = time_elem.text if time_elem else "Unknown"
            
            # Extract seller
            seller_elem = self.wait_for_element(
                By.CSS_SELECTOR,
                self.selectors['search_results']['seller'],
                timeout=5,
                parent=card
            )
            seller = seller_elem.text if seller_elem else "Unknown"
            
            # Extract condition
            condition_elem = self.wait_for_element(
                By.CSS_SELECTOR,
                self.selectors['search_results']['condition'],
                timeout=5,
                parent=card
            )
            condition = condition_elem.text if condition_elem else "Unknown"
            
            return {
                'title': title,
                'price': price,
                'image_url': image_url,
                'url': url,
                'time_left': time_left,
                'seller': seller,
                'condition': condition,
                'index': index
            }
            
        except Exception as e:
            logger.error(f"Error extracting card info: {str(e)}")
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((WebDriverException, TimeoutException))
    )
    def search_items(self, search_term: str) -> List[Dict[str, Any]]:
        """Search for items with improved error handling and retry mechanism."""
        try:
            # Construct search URL
            search_url = f"{self.base_url}/item/search/query/{quote(search_term)}"
            
            # Navigate to search page
            self.driver.get(search_url)
            
            # Handle cookie consent
            if not self.handle_cookie_consent():
                logger.warning("Failed to handle cookie consent, but continuing...")
            
            # Wait for page to be ready
            if not self.wait_for_page_ready():
                logger.error("Page failed to load properly")
                return []
            
            all_items = []
            current_page = 1
            
            while current_page <= self.max_pages:
                logger.info(f"Scraping page {current_page} for search term: {search_term}")
                
                # Get items from current page
                items = self.get_item_summaries_from_search_page(current_page)
                
                if not items:
                    logger.warning(f"No items found on page {current_page}")
                    break
                
                all_items.extend(items)
                
                # Check if there's a next page
                if not self.has_next_page():
                    logger.info("No more pages available")
                    break
                
                # Go to next page
                if not self.go_to_next_page():
                    logger.warning("Failed to navigate to next page")
                    break
                
                current_page += 1
                time.sleep(2)  # Add delay between pages
            
            return all_items
            
        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            self.save_debug_info(
                f"search_{search_term}_error",
                "search_error",
                self.driver.page_source
            )
            return []

    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a string to be used as a valid filename on Windows.
        
        Args:
            filename (str): Original filename to sanitize
            
        Returns:
            str: Sanitized filename
        """
        try:
            # Replace invalid characters with underscores
            invalid_chars = r'[<>:"/\\|?*]'
            sanitized = re.sub(invalid_chars, '_', filename)
            
            # Remove any leading/trailing spaces and dots
            sanitized = sanitized.strip('. ')
            
            # Ensure the filename isn't too long (Windows has a 255 character limit)
            if len(sanitized) > 240:  # Leave room for extension
                sanitized = sanitized[:240]
                
            return sanitized
            
        except Exception as e:
            logger.error(f"Error sanitizing filename: {str(e)}")
            return f"invalid_filename_{hash(filename)}"

    def test_connection(self):
        """Test basic connectivity to Buyee and perform network diagnostics."""
        try:
            # First, test basic HTTPS connectivity with a simple site
            logger.info("Testing basic HTTPS connectivity with example.com")
            try:
                self.driver.get("https://example.com")
                logger.info("Successfully connected to example.com")
            except Exception as e:
                logger.error(f"Failed to connect to example.com: {str(e)}")
                return False
            
            # Then test Google (another reliable HTTPS site)
            logger.info("Testing HTTPS connectivity with google.com")
            try:
                self.driver.get("https://www.google.com")
                logger.info("Successfully connected to google.com")
            except Exception as e:
                logger.error(f"Failed to connect to google.com: {str(e)}")
                return False
            
            # Finally, test Buyee
            logger.info(f"Testing connection to {self.base_url}")
            try:
                self.driver.get(self.base_url)
                time.sleep(2)  # Short wait to let any initial scripts run
                
                # Check for common issues
                if "SSL" in self.driver.title or "Error" in self.driver.title:
                    logger.error(f"SSL or error page detected: {self.driver.title}")
                    self.save_debug_info("connection_test", "ssl_error", self.driver.page_source)
                    return False
                
                # Check for CAPTCHA
                if "captcha" in self.driver.page_source.lower():
                    logger.error("CAPTCHA detected")
                    self.save_debug_info("connection_test", "captcha", self.driver.page_source)
                    return False
                
                # Check for successful page load
                if not self.driver.title:
                    logger.error("Page title is empty, possible connection issue")
                    self.save_debug_info("connection_test", "empty_title", self.driver.page_source)
                    return False
                
                logger.info(f"Successfully connected to {self.base_url}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to connect to Buyee: {str(e)}")
                self.save_debug_info("connection_test", "connection_failed", self.driver.page_source)
                return False
                
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False

    def clean_price(self, price_text: str) -> float:
        """Clean and convert price text to float."""
        try:
            # Remove currency symbols, commas, and convert to float
            cleaned = re.sub(r'[^\d.]', '', price_text)
            return float(cleaned)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse price: {price_text}")
            return 0.0

    def analyze_page_content(self) -> Dict[str, Any]:
        """
        Analyze the current page content and return detailed information about its state.
        """
        try:
            page_source = self.driver.page_source
            title = self.driver.title
            current_url = self.driver.current_url
            
            # Save detailed page analysis
            debug_dir = os.path.join(self.output_dir, "debug")
            os.makedirs(debug_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            analysis = {
                "timestamp": timestamp,
                "title": title,
                "url": current_url,
                "page_source_length": len(page_source),
                "has_item_cards": False,
                "has_item_container": False,
                "has_maintenance": False,
                "has_captcha": False,
                "has_error": False,
                "has_no_results": False,
                "maintenance_context": None,
                "error_context": None,
                "key_elements_found": [],
                "page_state": "unknown",
                "content_analysis": {
                    "has_header": False,
                    "has_footer": False,
                    "has_search_box": False,
                    "has_category_menu": False,
                    "has_translate_widget": False,
                    "has_pagination": False,
                    "has_breadcrumbs": False,
                    "has_cookie_popup": False
                },
                "item_analysis": {
                    "container_found": False,
                    "container_selector": "ul.auctionSearchResult.list_layout",
                    "items_found": 0,
                    "item_selector": "li.itemCard",
                    "first_item_html": None,
                    "container_candidates": []
                },
                "javascript_errors": [],
                "network_requests": []
            }
            
            # Save full page source
            source_path = os.path.join(debug_dir, f"full_page_source_{timestamp}.html")
            with open(source_path, "w", encoding="utf-8") as f:
                f.write(page_source)
            logger.info(f"Saved full page source to {source_path}")
            
            # Save screenshot
            screenshot_path = os.path.join(debug_dir, f"full_screenshot_{timestamp}.png")
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Saved full screenshot to {screenshot_path}")
            
            # Check for JavaScript errors
            try:
                js_errors = self.driver.execute_script("""
                    return window.performance.getEntries()
                        .filter(entry => entry.initiatorType === 'script' && entry.duration > 1000)
                        .map(entry => ({
                            name: entry.name,
                            duration: entry.duration,
                            startTime: entry.startTime
                        }));
                """)
                analysis["javascript_errors"] = js_errors
            except Exception as e:
                logger.warning(f"Could not check JavaScript errors: {str(e)}")
            
            # Check for essential page elements with explicit waits
            try:
                # First, wait for the page to be in a stable state
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script('return document.readyState') == 'complete'
                )
                
                # Check for cookie popup
                try:
                    cookie_popup = self.driver.find_element(By.CSS_SELECTOR, "div.cookiePolicyPopup.expanded")
                    analysis["content_analysis"]["has_cookie_popup"] = True
                    analysis["key_elements_found"].append("Cookie popup present")
                except NoSuchElementException:
                    analysis["content_analysis"]["has_cookie_popup"] = False
                
                # Try to find the item container with the correct selector
                try:
                    logger.info(f"Waiting for item container: {analysis['item_analysis']['container_selector']}")
                    item_container = WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, analysis['item_analysis']['item_selector']))
                    )
                    analysis["has_item_container"] = True
                    analysis["item_analysis"]["container_found"] = True
                    analysis["key_elements_found"].append("Found item container")
                    
                    # If we have the container, wait for at least one item card
                    logger.info(f"Waiting for item cards: {analysis['item_analysis']['item_selector']}")
                    try:
                        # Wait for at least one item to be present
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, analysis['item_analysis']['item_selector']))
                        )
                        
                        # Now get all items
                        item_cards = self.driver.find_elements(By.CSS_SELECTOR, analysis['item_analysis']['item_selector'])
                        analysis["has_item_cards"] = len(item_cards) > 0
                        analysis["item_analysis"]["items_found"] = len(item_cards)
                        
                        if item_cards:
                            analysis["key_elements_found"].append(f"Found {len(item_cards)} item cards")
                            # Save the HTML of the first item for debugging
                            analysis["item_analysis"]["first_item_html"] = item_cards[0].get_attribute('outerHTML')
                            logger.debug(f"First item HTML: {analysis['item_analysis']['first_item_html']}")
                            
                    except TimeoutException:
                        logger.warning("Item container found but no items appeared within timeout")
                        analysis["item_analysis"]["items_found"] = 0
                        
                except TimeoutException:
                    logger.warning("Item container not found within timeout")
                    analysis["has_item_container"] = False
                
                # Check for other essential page elements
                header = self.driver.find_elements(By.CSS_SELECTOR, "header")
                analysis["content_analysis"]["has_header"] = len(header) > 0
                
                footer = self.driver.find_elements(By.CSS_SELECTOR, "footer")
                analysis["content_analysis"]["has_footer"] = len(footer) > 0
                
                search_box = self.driver.find_elements(By.CSS_SELECTOR, "input[type='search']")
                analysis["content_analysis"]["has_search_box"] = len(search_box) > 0
                
                category_menu = self.driver.find_elements(By.CSS_SELECTOR, "nav.category-menu")
                analysis["content_analysis"]["has_category_menu"] = len(category_menu) > 0
                
                translate_widget = self.driver.find_elements(By.CSS_SELECTOR, "#google_translate_element")
                analysis["content_analysis"]["has_translate_widget"] = len(translate_widget) > 0
                
                # Check for pagination
                pagination = self.driver.find_elements(By.CSS_SELECTOR, "div.pagination")
                analysis["content_analysis"]["has_pagination"] = len(pagination) > 0
                
                # Check for breadcrumbs
                breadcrumbs = self.driver.find_elements(By.CSS_SELECTOR, "div.breadcrumbs")
                analysis["content_analysis"]["has_breadcrumbs"] = len(breadcrumbs) > 0
                
            except Exception as e:
                logger.debug(f"Error checking page elements: {str(e)}")
            
            # Check for actual maintenance messages (more specific indicators)
            maintenance_indicators = [
                # Japanese maintenance messages
                'ただいまメンテナンス作業を実施しております',
                'システムメンテナンス中',
                '現在メンテナンス中です',
                'メンテナンス作業のため',
                'メンテナンスのため',
                'メンテナンスにより',
                'メンテナンスの影響で',
                'メンテナンスの関係で',
                'メンテナンスの都合上',
                'メンテナンスの都合により',
                'メンテナンスの都合で',
                # English maintenance messages
                'site is currently under maintenance',
                'undergoing maintenance',
                'system maintenance',
                'maintenance in progress',
                'temporarily unavailable due to maintenance'
            ]
            
            # Check for maintenance with context
            for indicator in maintenance_indicators:
                if indicator in page_source.lower():
                    # Get more context around the maintenance message
                    start = max(0, page_source.lower().find(indicator) - 200)
                    end = min(len(page_source), page_source.lower().find(indicator) + len(indicator) + 200)
                    context = page_source[start:end]
                    
                    # Only consider it maintenance if it's a prominent message
                    if any(phrase in context.lower() for phrase in ['maintenance', 'メンテナンス']):
                        analysis["has_maintenance"] = True
                        analysis["maintenance_context"] = context
                        analysis["page_state"] = "maintenance"
                        break
            
            # Check for CAPTCHA
            captcha_indicators = ['captcha', 'recaptcha', 'robot', 'verify', 'reCAPTCHA']
            if any(indicator in page_source.lower() for indicator in captcha_indicators):
                analysis["has_captcha"] = True
                analysis["key_elements_found"].append("CAPTCHA detected")
                analysis["page_state"] = "captcha"
            
            # Check for no results
            no_results_indicators = [
                'no results', 'no items found', '検索結果がありません',
                '検索結果はありませんでした', '該当する商品が見つかりませんでした',
                '商品が見つかりませんでした', '検索条件に一致する商品はありませんでした'
            ]
            if any(indicator in page_source.lower() for indicator in no_results_indicators):
                analysis["has_no_results"] = True
                analysis["key_elements_found"].append("No results message found")
                analysis["page_state"] = "no_results"
            
            # Check for error messages
            error_indicators = [
                'error', '申し訳ございません', 'エラー', '問題が発生しました',
                'system error', 'error occurred', '申し訳ありませんが',
                'アクセスできません', 'アクセス制限', 'too many requests',
                'rate limit', 'not available in your region', '地域制限'
            ]
            for indicator in error_indicators:
                if indicator in page_source.lower():
                    analysis["has_error"] = True
                    start = max(0, page_source.lower().find(indicator) - 200)
                    end = min(len(page_source), page_source.lower().find(indicator) + len(indicator) + 200)
                    analysis["error_context"] = page_source[start:end]
                    analysis["page_state"] = "error"
                    break
            
            # Determine page state based on content analysis
            if analysis["has_item_container"]:
                if analysis["has_item_cards"]:
                    analysis["page_state"] = "ready"
                elif analysis["has_no_results"]:
                    analysis["page_state"] = "no_results"
                else:
                    analysis["page_state"] = "error"
            elif not any([
                analysis["content_analysis"]["has_header"],
                analysis["content_analysis"]["has_footer"],
                analysis["content_analysis"]["has_search_box"],
                analysis["content_analysis"]["has_category_menu"]
            ]):
                # If we don't have the item container AND we're missing other essential elements,
                # the page is likely not loaded properly
                analysis["page_state"] = "error"
                analysis["has_error"] = True
                analysis["error_context"] = "Page appears to be incompletely loaded - missing essential elements"
            
            # Save analysis results
            analysis_path = os.path.join(debug_dir, f"page_analysis_{timestamp}.json")
            with open(analysis_path, "w", encoding="utf-8") as f:
                json.dump(analysis, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved page analysis to {analysis_path}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing page content: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "page_state": "error"
            }

    def check_page_state(self):
        """Check the current page state and return (state, is_error) tuple."""
        try:
            # Save current page state for debugging
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            page_source = self.driver.page_source
            page_title = self.driver.title
            current_url = self.driver.current_url
            
            # Save full page source and screenshot
            debug_dir = os.path.join(self.output_dir, 'debug')
            os.makedirs(debug_dir, exist_ok=True)
            
            with open(os.path.join(debug_dir, f'full_page_source_{timestamp}.html'), 'w', encoding='utf-8') as f:
                f.write(page_source)
            
            self.driver.save_screenshot(os.path.join(debug_dir, f'full_screenshot_{timestamp}.png'))
            
            # Perform detailed page analysis
            analysis = {
                'timestamp': timestamp,
                'url': current_url,
                'title': page_title,
                'page_state': 'unknown',
                'has_item_container': False,
                'has_item_cards': False,
                'content_analysis': {
                    'has_header': False,
                    'has_footer': False,
                    'has_search_box': False,
                    'has_category_menu': False,
                    'has_translate_widget': False,
                    'has_pagination': False,
                    'has_breadcrumbs': False,
                    'has_cookie_popup': False,
                    'has_no_results_message': False,
                    'no_results_message': None,
                    'no_results_indicators': []
                },
                'error_context': None,
                'javascript_errors': [],
                'container_candidates': []
            }
            
            # Check for essential elements
            try:
                # First, wait for the page to be in a stable state
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script('return document.readyState') == 'complete'
                )
                
                # Check for cookie popup
                try:
                    cookie_popup = self.driver.find_element(By.CSS_SELECTOR, "div.cookiePolicyPopup.expanded")
                    analysis['content_analysis']['has_cookie_popup'] = True
                except NoSuchElementException:
                    analysis['content_analysis']['has_cookie_popup'] = False
                
                # Check for no results message first - using exact selectors from observed HTML
                no_results_selectors = [
                    "div.bidNotfound_middle",  # From the Pokemon Card Starter example
                    "div.noResults",
                    "div.searchResult__noResults",
                    "div.searchResult__empty",
                    "div.searchResult__message",
                    "div.messageBox--noResults",
                    "div.searchResult__noItems",
                    "div.searchResult__emptyMessage",
                    "div.searchResult__noData",
                    "div.searchResult__noDataMessage"
                ]
                
                # Also check for common no results text in Japanese and English
                no_results_texts = [
                    # English messages
                    "No Results Found",
                    "Could not find any results for",
                    # Japanese messages
                    "該当する商品が見つかりませんでした",
                    "検索結果はありませんでした",
                    "商品が見つかりませんでした",
                    "検索条件に一致する商品はありませんでした",
                    "該当する商品はありませんでした",
                    "検索結果がありません",
                    "商品が見つかりません",
                    "該当する商品はありません",
                    "検索条件に一致する商品はありません"
                ]
                
                # Check for no results message using selectors
                for selector in no_results_selectors:
                    try:
                        no_results_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        message = no_results_element.text.strip()
                        analysis['content_analysis']['has_no_results_message'] = True
                        analysis['content_analysis']['no_results_message'] = message
                        analysis['content_analysis']['no_results_indicators'].append(f"Found no results element: {selector}")
                        logger.info(f"Found no results message: {message}")
                        return 'no_results', False
                    except NoSuchElementException:
                        continue
                
                # Check for no results text in page source
                for text in no_results_texts:
                    if text in page_source:
                        analysis['content_analysis']['has_no_results_message'] = True
                        analysis['content_analysis']['no_results_message'] = text
                        analysis['content_analysis']['no_results_indicators'].append(f"Found no results text: {text}")
                        logger.info(f"Found no results text in page source: {text}")
                        return 'no_results', False
                
                # Try to find the item container with the correct selector
                try:
                    logger.info("Waiting for item container: ul.auctionSearchResult.list_layout")
                    item_container = WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "ul.auctionSearchResult.list_layout"))
                    )
                    analysis['has_item_container'] = True
                    
                    # Check for item cards
                    item_cards = self.driver.find_elements(By.CSS_SELECTOR, "li.itemCard")
                    analysis['has_item_cards'] = len(item_cards) > 0
                    
                    if analysis['has_item_cards']:
                        analysis['page_state'] = 'ready'
                        return 'ready', False
                    else:
                        # If we have the container but no items, check for no results message again
                        # (some pages might show the container even with no results)
                        for selector in no_results_selectors:
                            try:
                                no_results_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                                message = no_results_element.text.strip()
                                analysis['content_analysis']['has_no_results_message'] = True
                                analysis['content_analysis']['no_results_message'] = message
                                analysis['content_analysis']['no_results_indicators'].append(f"Found no results element in empty container: {selector}")
                                logger.info(f"Found no results message in empty container: {message}")
                                return 'no_results', False
                            except NoSuchElementException:
                                continue
                        
                        # If we still don't have a no results message, this might be a loading issue
                        analysis['page_state'] = 'error'
                        analysis['error_context'] = "Container found but no items and no no-results message"
                        return 'error', True
                        
                except TimeoutException:
                    logger.warning("Item container not found within timeout")
                    analysis['error_context'] = "Item container not found"
                    
                    # Check if we have other essential elements to determine if page loaded properly
                    try:
                        analysis['content_analysis']['has_header'] = len(self.driver.find_elements(By.CSS_SELECTOR, "header")) > 0
                        analysis['content_analysis']['has_footer'] = len(self.driver.find_elements(By.CSS_SELECTOR, "footer")) > 0
                        analysis['content_analysis']['has_search_box'] = len(self.driver.find_elements(By.CSS_SELECTOR, "input[type='search']")) > 0
                        analysis['content_analysis']['has_category_menu'] = len(self.driver.find_elements(By.CSS_SELECTOR, "nav.categoryMenu")) > 0
                        
                        # If we have essential elements but no container, this might be a no results page
                        if (analysis['content_analysis']['has_header'] and 
                            analysis['content_analysis']['has_footer'] and 
                            analysis['content_analysis']['has_search_box']):
                            
                            # Check for no results message one more time
                            for selector in no_results_selectors:
                                try:
                                    no_results_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                                    message = no_results_element.text.strip()
                                    analysis['content_analysis']['has_no_results_message'] = True
                                    analysis['content_analysis']['no_results_message'] = message
                                    analysis['content_analysis']['no_results_indicators'].append(f"Found no results element after container timeout: {selector}")
                                    logger.info(f"Found no results message after container timeout: {message}")
                                    return 'no_results', False
                                except NoSuchElementException:
                                    continue
                            
                            # Check for no results text in page source one more time
                            for text in no_results_texts:
                                if text in page_source:
                                    analysis['content_analysis']['has_no_results_message'] = True
                                    analysis['content_analysis']['no_results_message'] = text
                                    analysis['content_analysis']['no_results_indicators'].append(f"Found no results text in page source after container timeout: {text}")
                                    logger.info(f"Found no results text in page source after container timeout: {text}")
                                    return 'no_results', False
                            
                            # If we have essential elements but no container and no no-results message,
                            # this might be a loading issue
                            analysis['page_state'] = 'error'
                            analysis['error_context'] = "Essential elements present but no container found"
                            return 'error', True
                        else:
                            # Missing essential elements suggests a more serious loading issue
                            analysis['page_state'] = 'error'
                            analysis['error_context'] = "Missing essential page elements"
                            return 'error', True
                            
                    except Exception as e:
                        logger.warning(f"Error checking page elements: {str(e)}")
                        analysis['page_state'] = 'error'
                        analysis['error_context'] = f"Error checking page elements: {str(e)}"
                        return 'error', True
            
                # Save analysis results
                with open(os.path.join(debug_dir, f'page_analysis_{timestamp}.json'), 'w', encoding='utf-8') as f:
                    json.dump(analysis, f, ensure_ascii=False, indent=2)
                
                return analysis['page_state'], analysis['page_state'].startswith('error')
                
            except Exception as e:
                logger.error(f"Error checking page state: {str(e)}")
                return 'error', True
            
        except Exception as e:
            logger.error(f"Error checking page state: {str(e)}")
            return 'error', True

    def handle_maintenance(self, search_term: str) -> bool:
        """
        Handle site maintenance by saving debug info and deciding whether to continue.
        Returns True if should continue, False if should stop.
        """
        # Save detailed maintenance info
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_dir = os.path.join(self.output_dir, "debug")
        os.makedirs(debug_dir, exist_ok=True)
        
        # Save maintenance page source
        maintenance_source_path = os.path.join(debug_dir, f"maintenance_page_{timestamp}.html")
        with open(maintenance_source_path, "w", encoding="utf-8") as f:
            f.write(self.driver.page_source)
        logger.info(f"Saved maintenance page source to {maintenance_source_path}")
        
        # Save maintenance screenshot
        maintenance_screenshot_path = os.path.join(debug_dir, f"maintenance_screenshot_{timestamp}.png")
        self.driver.save_screenshot(maintenance_screenshot_path)
        logger.info(f"Saved maintenance screenshot to {maintenance_screenshot_path}")
        
        # Create maintenance status file
        status_path = os.path.join(self.output_dir, "maintenance_status.txt")
        with open(status_path, "w", encoding="utf-8") as f:
            f.write(f"Maintenance detected at: {datetime.now().isoformat()}\n")
            f.write(f"Current URL: {self.driver.current_url}\n")
            f.write(f"Page title: {self.driver.title}\n")
            f.write(f"Search term: {search_term}\n")
            f.write(f"Page source (first 1000 chars):\n{self.driver.page_source[:1000]}\n")
        
        # Check if we should continue based on maintenance duration
        if os.path.exists(status_path):
            try:
                with open(status_path, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        maintenance_start = datetime.fromisoformat(first_line.split(": ")[1])
                        maintenance_duration = datetime.now() - maintenance_start
                        
                        # If maintenance has been ongoing for more than 2 hours, stop
                        if maintenance_duration.total_seconds() > 7200:  # 2 hours
                            logger.error("Maintenance has been ongoing for more than 2 hours. Stopping script.")
                            return False
            except Exception as e:
                logger.error(f"Error reading maintenance status: {str(e)}")
        
        # Wait 30 minutes before next retry
        logger.info("Waiting 30 minutes before next retry...")
        time.sleep(1800)  # 30 minutes
        return True

    def wait_for_page_ready(self, timeout: int = 30) -> bool:
        """
        Wait for the page to be in a ready state, handling various conditions.
        Returns True if page is ready for processing, False otherwise.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            state, is_error = self.check_page_state()
            
            if state == 'ready':
                return True
            elif state == 'no_results':
                return True  # No results is a valid state
            elif is_error:
                return False
            elif state == 'loading':
                time.sleep(2)  # Wait a bit before checking again
                continue
                
        logger.warning(f"Page did not reach ready state within {timeout} seconds")
        return False

    def has_next_page(self) -> bool:
        """Check if there is a next page of results."""
        try:
            next_button = self.driver.find_element(By.CSS_SELECTOR, "a.pagination__next:not(.pagination__next--disabled)")
            return True
        except NoSuchElementException:
            return False

    def go_to_next_page(self) -> bool:
        """Navigate to the next page of results."""
        try:
            next_button = self.driver.find_element(By.CSS_SELECTOR, "a.pagination__next:not(.pagination__next--disabled)")
            next_button.click()
            return self.wait_for_page_ready()
        except (NoSuchElementException, WebDriverException) as e:
            logger.warning(f"Failed to navigate to next page: {str(e)}")
            return False

    def save_initial_promising_links(self, item_summaries: List[Dict[str, Any]], search_term: str) -> None:
        """Save initial promising links to a separate file before detailed analysis."""
        if not item_summaries:
            logger.warning(f"No promising items to save for search term: {search_term}")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"initial_leads_{search_term}_{timestamp}"
            
            # Prepare data for saving
            leads_data = []
            for summary in item_summaries:
                # Extract Yahoo Auction ID from Buyee URL
                yahoo_id_match = re.search(r'/([a-z]\d+)(?:\?|$)', summary['url'])
                yahoo_auction_id = yahoo_id_match.group(1) if yahoo_id_match else None
                yahoo_auction_url = f"https://page.auctions.yahoo.co.jp/jp/auction/{yahoo_auction_id}" if yahoo_auction_id else None
                
                lead_info = {
                    'title': summary['title'],
                    'buyee_url': summary['url'],
                    'yahoo_auction_id': yahoo_auction_id,
                    'yahoo_auction_url': yahoo_auction_url,
                    'price_yen': summary['price_yen'],
                    'price_text': summary['price_text'],
                    'thumbnail_url': summary['thumbnail_url'],
                    'preliminary_analysis': summary['preliminary_analysis'],
                    'timestamp': timestamp
                }
                leads_data.append(lead_info)
            
            # Save as CSV
            df = pd.DataFrame(leads_data)
            csv_path = os.path.join(self.output_dir, f"{base_filename}.csv")
            df.to_csv(csv_path, index=False, encoding='utf-8')
            logger.info(f"Saved {len(leads_data)} initial promising leads to {csv_path}")
            
            # Save as JSON
            json_path = os.path.join(self.output_dir, f"{base_filename}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(leads_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(leads_data)} initial promising leads to {json_path}")
            
        except Exception as e:
            logger.error(f"Error saving initial promising links: {str(e)}")
            logger.error(traceback.format_exc())

    def scrape_item_detail_page(self, url):
        """Scrape detailed information from an item's detail page."""
        try:
            logger.info(f"Scraping item details from: {url}")
            
            # Quick check for invalid URLs
            if not url or not url.startswith(self.base_url):
                logger.warning(f"Invalid URL format: {url}")
                return None
            
            # Add a delay before loading the detail page
            time.sleep(3)  # Add a 3-second delay to avoid rate limiting
            
            # Navigate to the item page with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"Attempting to load item page (attempt {attempt + 1}/{max_retries}): {url}")
                    self.driver.get(url)
                    
                    # Wait for page to be in a stable state
                    try:
                        WebDriverWait(self.driver, 10).until(
                            lambda driver: driver.execute_script('return document.readyState') == 'complete'
                        )
                        logger.info("Page reached complete state")
                    except TimeoutException:
                        logger.warning("Page did not reach complete state within timeout")
                    
                    # Quick check for error pages before waiting
                    current_title = self.driver.title.lower()
                    page_content = self.driver.page_source.lower()
                    
                    # Check for various error conditions
                    error_indicators = {
                        'captcha': ['captcha', 'recaptcha', 'robot', 'verify', 'reCAPTCHA'],
                        'maintenance': ['maintenance', 'メンテナンス', 'system maintenance'],
                        'not_found': ['not found', '404', 'page not found', 'ページが見つかりません'],
                        'access_denied': ['access denied', '403', 'forbidden', 'アクセスできません'],
                        'rate_limit': ['too many requests', 'rate limit', 'アクセス制限'],
                        'region_block': ['not available in your region', '地域制限'],
                        'error': ['error', 'エラー', '問題が発生しました', 'system error']
                    }
                    
                    for error_type, indicators in error_indicators.items():
                        if any(indicator in current_title or indicator in page_content for indicator in indicators):
                            logger.warning(f"Detected {error_type} page for {url}")
                            self.save_debug_info(url.split('/')[-1], f"detail_{error_type}", self.driver.page_source)
                            return None
                    
                    # Quick check for valid item page structure
                    if not any(selector in page_content for selector in ['itemDetail', 'item-detail', 'auction-item-detail']):
                        logger.warning("Page does not appear to be a valid item page")
                        self.save_debug_info(url.split('/')[-1], "invalid_page", self.driver.page_source)
                        return None
                    
                    break
                    
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to load page after {max_retries} attempts: {str(e)}")
                        return None
                    logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                    time.sleep(2)
            
            # Handle cookie popup if present (with shorter timeout)
            try:
                cookie_selectors = [
                    "div.cookiePolicyPopup__buttonWrapper button.accept_cookie",
                    "button#js-accept-cookies",
                    "button.accept-cookies",
                    "button[data-testid='cookie-accept']"
                ]
                
                for selector in cookie_selectors:
                    try:
                        cookie_button = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        cookie_button.click()
                        time.sleep(1)
                        break
                    except TimeoutException:
                        continue
            except Exception as e:
                logger.debug(f"Cookie handling error (non-critical): {str(e)}")
            
            # Wait for and extract essential elements with robust selectors
            item_details = {}
            
            # 1. Main item description (with multiple selectors and fallbacks)
            description_selectors = [
                "section#auction_item_description",
                "div.itemDescription",
                "div#itemDetail_sec",
                "div.item-description",
                "div[data-testid='item-description']",
                "div.description",
                "div.item-details"
            ]
            
            for selector in description_selectors:
                try:
                    description_element = WebDriverWait(self.driver, 25).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if description_element:
                        item_details['description'] = description_element.text.strip()
                        logger.info("Found item description")
                        break
                except (TimeoutException, NoSuchElementException):
                    continue
            
            if 'description' not in item_details:
                logger.warning("Could not find item description")
                return None
            
            # 2. Seller-stated condition
            condition_selectors = [
                "//em[normalize-space(.)='Item Condition']/following-sibling::span[1]",
                "//em[contains(text(), 'Condition')]/following-sibling::span[1]",
                "//div[contains(@class, 'condition')]//span",
                "//div[contains(@class, 'itemCondition')]//span"
            ]
            
            for selector in condition_selectors:
                try:
                    condition_element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    if condition_element:
                        item_details['seller_condition'] = condition_element.text.strip()
                        logger.info("Found seller condition")
                        break
                except (TimeoutException, NoSuchElementException):
                    continue
            
            # 3. Direct Yahoo Auction link
            yahoo_link_selectors = [
                "//a[contains(normalize-space(.), 'View on the original site')]",
                "//a[contains(@href, 'page.auctions.yahoo.co.jp')]",
                "//a[contains(@class, 'original-site-link')]"
            ]
            
            for selector in yahoo_link_selectors:
                try:
                    yahoo_link = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    if yahoo_link:
                        item_details['yahoo_link'] = yahoo_link.get_attribute('href')
                        logger.info("Found Yahoo Auction link")
                        break
                except (TimeoutException, NoSuchElementException):
                    continue
            
            # 4. Main image URL
            image_selectors = [
                "div.photo_gallery_main img",
                "div.itemPhoto img",
                "div[data-testid='item-image'] img",
                "div.item-image img"
            ]
            
            for selector in image_selectors:
                try:
                    img_element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if img_element:
                        # Try data-src first, then src
                        item_details['main_image_url'] = img_element.get_attribute('data-src') or img_element.get_attribute('src')
                        if item_details['main_image_url']:
                            logger.info("Found main image URL")
                            break
                except (TimeoutException, NoSuchElementException):
                    continue
            
            # Return the collected details
            if item_details:
                logger.info("Successfully collected item details")
                return item_details
            else:
                logger.warning("No item details could be collected")
                return None
            
        except Exception as e:
            logger.error(f"Error scraping item details: {str(e)}")
            return None

    def is_element_attached(self, element: WebElement) -> bool:
        """Check if an element is still attached to the DOM."""
        try:
            # Try to access any property of the element
            element.tag_name
            return True
        except (StaleElementReferenceException, WebDriverException):
            return False

    def ensure_valid_session(self) -> bool:
        """Ensure the WebDriver session is valid, reconnecting if necessary."""
        try:
            # Try a simple command to check if session is valid
            self.driver.current_url
            return True
        except Exception as e:
            logger.warning(f"Session validation failed: {str(e)}")
            
            if self.session_retry_count >= self.max_session_retries:
                logger.error("Max session retry attempts reached")
                return False
            
            try:
                # Clean up old session
                self.cleanup()
                
                # Wait before retrying
                time.sleep(self.session_retry_delay)
                
                # Attempt to create new session
                if self.setup_driver():
                    self.session_retry_count = 0
                    logger.info("Successfully reconnected WebDriver session")
                    return True
                else:
                    self.session_retry_count += 1
                    logger.error(f"Failed to reconnect WebDriver session (attempt {self.session_retry_count})")
                    return False
                    
            except Exception as reconnect_error:
                self.session_retry_count += 1
                logger.error(f"Error during session reconnection: {str(reconnect_error)}")
                return False

    def wait_for_element(self, by: By, value: str, timeout: int = None, 
                        condition: str = "presence", parent: WebElement = None) -> Optional[WebElement]:
        """Wait for an element with configurable conditions and timeout.
        
        Args:
            by: The locator strategy (e.g., By.CSS_SELECTOR)
            value: The locator value
            timeout: Maximum time to wait in seconds
            condition: The condition to wait for ("presence", "visibility", "clickable")
            parent: Optional parent element to search within
            
        Returns:
            WebElement if found, None otherwise
        """
        if timeout is None:
            timeout = self.element_wait_time
            
        try:
            wait = WebDriverWait(self.driver, timeout)
            
            # Define the expected condition based on the condition parameter
            if condition == "presence":
                expected_condition = EC.presence_of_element_located((by, value))
            elif condition == "visibility":
                expected_condition = EC.visibility_of_element_located((by, value))
            elif condition == "clickable":
                expected_condition = EC.element_to_be_clickable((by, value))
            else:
                logger.warning(f"Unknown condition '{condition}', defaulting to presence")
                expected_condition = EC.presence_of_element_located((by, value))
            
            # If parent is provided, use it as the context for finding the element
            if parent:
                try:
                    # First check if parent is still attached to DOM
                    if not self.is_element_attached(parent):
                        logger.warning("Parent element is no longer attached to DOM")
                        return None
                        
                    # Wait for element within parent
                    element = wait.until(
                        lambda d: parent.find_element(by, value)
                    )
                    
                    # Additional wait for the specific condition
                    if condition == "visibility":
                        wait.until(EC.visibility_of(element))
                    elif condition == "clickable":
                        wait.until(EC.element_to_be_clickable(element))
                        
                    return element
                    
                except StaleElementReferenceException:
                    logger.warning("Parent element became stale while waiting for child element")
                    return None
                except Exception as e:
                    logger.debug(f"Error finding element within parent: {str(e)}")
                    return None
            else:
                # Wait for element in the entire document
                return wait.until(expected_condition)
                
        except TimeoutException:
            logger.debug(f"Timeout waiting for element {value} with condition {condition}")
            return None
        except Exception as e:
            logger.debug(f"Error waiting for element {value}: {str(e)}")
            return None

    def save_results(self, results: List[Dict[str, Any]], search_term: str) -> None:
        """Save results to CSV and JSON files with error handling."""
        if not results:
            logger.warning(f"No results to save for search term: {search_term}")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"buyee_listings_{search_term}_{timestamp}"
            
            # Save as CSV
            df = pd.DataFrame(results)
            csv_path = os.path.join(self.output_dir, f"{base_filename}.csv")
            df.to_csv(csv_path, index=False, encoding='utf-8')
            logger.info(f"Saved {len(results)} results to {csv_path}")
            
            # Save as JSON
            json_path = os.path.join(self.output_dir, f"{base_filename}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(results)} results to {json_path}")
            
        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")
            logger.error(traceback.format_exc())

    def close(self):
        """Close the WebDriver with error handling."""
        try:
            self.driver.quit()
            logger.info("WebDriver closed successfully")
        except Exception as e:
            logger.error(f"Error closing WebDriver: {str(e)}")

    def parse_card_details_from_buyee(self, title: str, description: str) -> Dict[str, Any]:
        """
        Parse card details from Buyee listing title and description.
        Returns a dictionary containing structured card information.
        """
        details = {
            'name': None,
            'set_code': None,
            'card_number': None,
            'rarity': None,
            'edition': None,
            'language': None,
            'rank': None,
            'condition_text': None
        }
        
        try:
            # Extract rank from description
            if description:
                rank_match = re.search(r'【ランク】\s*([A-Z]+)', description)
                if rank_match:
                    details['rank'] = rank_match.group(1)
                    logger.debug(f"Found rank: {details['rank']}")
            
            # Extract set code and card number
            set_code_match = re.search(r'([A-Z]{2,4})-([A-Z]{2})(\d{3})', title)
            if set_code_match:
                details['set_code'] = set_code_match.group(1)
                details['card_number'] = set_code_match.group(3)
                logger.debug(f"Found set code: {details['set_code']}, card number: {details['card_number']}")
            
            # Extract rarity
            rarity_keywords = {
                'Secret Rare': ['secret rare', 'シークレットレア', 'sr'],
                'Ultimate Rare': ['ultimate rare', 'アルティメットレア', 'ur'],
                'Ghost Rare': ['ghost rare', 'ゴーストレア', 'gr'],
                'Collector\'s Rare': ['collector\'s rare', 'コレクターズレア', 'cr'],
                'Starlight Rare': ['starlight rare', 'スターライトレア', 'str'],
                'Quarter Century Secret Rare': ['quarter century secret rare', 'クォーターセンチュリーシークレットレア', 'qcsr'],
                'Prismatic Secret Rare': ['prismatic secret rare', 'プリズマティックシークレットレア', 'psr'],
                'Platinum Secret Rare': ['platinum secret rare', 'プラチナシークレットレア', 'plsr'],
                'Gold Secret Rare': ['gold secret rare', 'ゴールドシークレットレア', 'gsr'],
                'Ultra Rare': ['ultra rare', 'ウルトラレア', 'ur'],
                'Super Rare': ['super rare', 'スーパーレア', 'sr'],
                'Rare': ['rare', 'レア', 'r'],
                'Common': ['common', 'ノーマル', 'n']
            }
            
            for rarity, keywords in rarity_keywords.items():
                if any(keyword.lower() in title.lower() for keyword in keywords):
                    details['rarity'] = rarity
                    logger.debug(f"Found rarity: {rarity}")
                    break
            
            # Extract edition
            edition_keywords = {
                '1st Edition': ['1st', 'first edition', '初版', '初刷'],
                'Unlimited': ['unlimited', '無制限', '再版', '再刷']
            }
            
            for edition, keywords in edition_keywords.items():
                if any(keyword.lower() in title.lower() for keyword in keywords):
                    details['edition'] = edition
                    logger.debug(f"Found edition: {edition}")
                    break
            
            # Extract language/region
            region_keywords = {
                'Asia': ['asia', 'asian', 'アジア', 'アジア版'],
                'English': ['english', '英', '英語版'],
                'Japanese': ['japanese', '日', '日本語版'],
                'Korean': ['korean', '韓', '韓国版']
            }
            
            for region, keywords in region_keywords.items():
                if any(keyword.lower() in title.lower() for keyword in keywords):
                    details['language'] = region
                    logger.debug(f"Found language/region: {region}")
                    break
            
            # Extract condition text from description
            if description:
                condition_section = re.search(r'【商品の状態】\s*(.*?)(?=\n|$)', description)
                if condition_section:
                    details['condition_text'] = condition_section.group(1).strip()
                    logger.debug(f"Found condition text: {details['condition_text']}")
            
            # Try to extract card name (this is more complex and might need improvement)
            # For now, we'll just use the title as the name
            details['name'] = title.strip()
            
            logger.info(f"Successfully parsed card details from Buyee listing")
            return details
            
        except Exception as e:
            logger.error(f"Error parsing card details: {str(e)}")
            return details

    def is_driver_valid(self) -> bool:
        """Check if the WebDriver is still valid and handle reconnection if needed."""
        try:
            # Try a simple command to check if driver is responsive
            self.driver.current_url
            return True
        except Exception as e:
            logger.error(f"WebDriver is not valid: {str(e)}")
            try:
                # Try to clean up the old driver
                self.cleanup()
            except:
                pass
            # Try to create a new driver
            try:
                self.setup_driver()
                return True
            except Exception as setup_error:
                logger.error(f"Failed to recreate WebDriver: {str(setup_error)}")
                return False

def main():
    parser = argparse.ArgumentParser(description='Scrape Buyee for Yu-Gi-Oh cards')
    parser.add_argument('--output-dir', default='scraped_results', help='Directory to save results')
    parser.add_argument('--max-pages', type=int, default=5, help='Maximum pages to scrape per search')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    args = parser.parse_args()
    
    scraper = None
    try:
        scraper = BuyeeScraper(
            output_dir=args.output_dir,
            max_pages=args.max_pages,
            headless=args.headless
        )
        
        # Test connection first
        if not scraper.test_connection():
            logger.error("Failed to establish connection. Exiting.")
            return
        
        # Process each search term
        for search_term in SEARCH_TERMS:
            try:
                # Check if driver is valid before each search
                if not scraper.is_driver_valid():
                    logger.error("WebDriver is not valid before starting search. Attempting to recreate...")
                    if not scraper.is_driver_valid():  # Try one more time
                        logger.error("Failed to recreate WebDriver. Skipping search term.")
                        continue
                
                logger.info(f"Starting search for term: {search_term}")
                results = scraper.search_items(search_term)
                
                if results:
                    logger.info(f"Found {len(results)} valuable items for {search_term}")
                else:
                    logger.info(f"No valuable items found for {search_term}")
                    
            except Exception as e:
                logger.error(f"Error processing search term {search_term}: {str(e)}")
                logger.error(traceback.format_exc())
                continue
                
    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        if scraper:
            try:
                scraper.close()
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")

if __name__ == "__main__":
    main() 