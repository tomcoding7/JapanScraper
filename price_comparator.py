"""
Price Comparator for Yu-Gi-Oh Card Arbitrage Bot

This module handles fetching and analyzing eBay/130point.com sold prices
for Yu-Gi-Oh cards to determine market value.
"""

import logging
import time
import random
import re
import statistics
from typing import Dict, List, Optional, Any, Tuple
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

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

class PriceComparator:
    """
    Handles fetching and analyzing eBay/130point.com sold prices for Yu-Gi-Oh cards.
    """
    
    def __init__(self):
        """
        Initialize the PriceComparator.
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self.retry_delays = [1, 2, 5, 10]  # Exponential backoff delays
        self.max_retries = 3
        self.timeout = 10
        
        # Cache for price data to avoid redundant requests
        self.price_cache = {}
        
        logger.info("PriceComparator initialized")
    
    def get_sold_prices(self, card_name: str, set_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get sold prices for a card from 130point.com.
        
        Args:
            card_name (str): Name of the card.
            set_code (Optional[str], optional): Set code. Defaults to None.
        
        Returns:
            Optional[Dict[str, Any]]: Price data or None if not found.
        """
        # Create cache key
        cache_key = f"{card_name}_{set_code}" if set_code else card_name
        
        # Check cache first
        if cache_key in self.price_cache:
            logger.info("Using cached price data for %s", cache_key)
            return self.price_cache[cache_key]
        
        try:
            # Prepare search term
            search_term = f"{card_name} {set_code}" if set_code else card_name
            search_term = quote(search_term)
            url = f"https://130point.com/sales/?item={search_term}"
            
            logger.info("Fetching sold prices for %s from 130point.com", search_term)
            
            # Add random delay to avoid rate limiting
            time.sleep(random.uniform(2, 4))
            
            # Fetch the page
            html_content = self._get_page(url)
            if not html_content:
                logger.warning("Could not fetch sold prices for %s", search_term)
                return None
            
            # Parse the page
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Initialize price lists
            raw_prices = []
            psa_9_prices = []
            psa_10_prices = []
            bgs_9_prices = []
            bgs_95_prices = []
            
            # Find all sale items
            sales = soup.find_all('div', class_='sale-item')
            logger.info("Found %d sales for %s", len(sales), search_term)
            
            for sale in sales:
                try:
                    # Extract price
                    price_elem = sale.find('span', class_='price')
                    if not price_elem:
                        continue
                    price_text = price_elem.text.strip()
                    price = self._clean_price(price_text)
                    
                    # Extract title and condition
                    title_elem = sale.find('span', class_='title')
                    condition_elem = sale.find('span', class_='condition')
                    
                    title = title_elem.text.strip().lower() if title_elem else ""
                    condition = condition_elem.text.strip().lower() if condition_elem else ""
                    
                    # Combine title and condition for analysis
                    full_text = f"{title} {condition}".lower()
                    
                    # Categorize based on condition
                    if 'psa 10' in full_text or 'gem mint' in full_text:
                        psa_10_prices.append(price)
                    elif 'psa 9' in full_text or 'mint' in full_text:
                        psa_9_prices.append(price)
                    elif 'bgs 9.5' in full_text:
                        bgs_95_prices.append(price)
                    elif 'bgs 9' in full_text:
                        bgs_9_prices.append(price)
                    else:
                        # Check if it's a raw card (ungraded)
                        if not any(term in full_text for term in ['psa', 'bgs', 'cgc', 'graded']):
                            raw_prices.append(price)
                    
                except (ValueError, AttributeError) as e:
                    logger.warning("Error parsing sale entry: %s", str(e))
                    continue
            
            # Calculate statistics
            price_data = {
                'raw_prices': raw_prices,
                'psa_9_prices': psa_9_prices,
                'psa_10_prices': psa_10_prices,
                'bgs_9_prices': bgs_9_prices,
                'bgs_95_prices': bgs_95_prices,
                'raw_avg': self._calculate_average(raw_prices),
                'raw_median': self._calculate_median(raw_prices),
                'raw_min': min(raw_prices) if raw_prices else None,
                'raw_max': max(raw_prices) if raw_prices else None,
                'raw_count': len(raw_prices),
                'psa_9_avg': self._calculate_average(psa_9_prices),
                'psa_9_median': self._calculate_median(psa_9_prices),
                'psa_9_count': len(psa_9_prices),
                'psa_10_avg': self._calculate_average(psa_10_prices),
                'psa_10_median': self._calculate_median(psa_10_prices),
                'psa_10_count': len(psa_10_prices),
                'bgs_9_avg': self._calculate_average(bgs_9_prices),
                'bgs_9_count': len(bgs_9_prices),
                'bgs_95_avg': self._calculate_average(bgs_95_prices),
                'bgs_95_count': len(bgs_95_prices),
                'total_sales': len(raw_prices) + len(psa_9_prices) + len(psa_10_prices) + len(bgs_9_prices) + len(bgs_95_prices)
            }
            
            # Add sell-through rate estimate based on number of sales
            if price_data['total_sales'] > 20:
                price_data['sell_through_rate'] = 'High'
            elif price_data['total_sales'] > 10:
                price_data['sell_through_rate'] = 'Medium'
            else:
                price_data['sell_through_rate'] = 'Low'
            
            # Cache the results
            self.price_cache[cache_key] = price_data
            
            logger.info("Successfully fetched price data for %s: %d total sales", 
                       search_term, price_data['total_sales'])
            
            return price_data
            
        except Exception as e:
            logger.error("Error getting sold prices for %s: %s", card_name, str(e), exc_info=True)
            return None
    
    def get_ebay_sold_prices(self, card_name: str, set_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get sold prices directly from eBay (alternative to 130point.com).
        
        Args:
            card_name (str): Name of the card.
            set_code (Optional[str], optional): Set code. Defaults to None.
        
        Returns:
            Optional[Dict[str, Any]]: Price data or None if not found.
        """
        # This is a placeholder for direct eBay scraping if needed
        # Currently using 130point.com as the primary source
        logger.warning("Direct eBay scraping not implemented, using 130point.com instead")
        return self.get_sold_prices(card_name, set_code)
    
    def _get_page(self, url: str) -> Optional[str]:
        """
        Get page content with retry logic.
        
        Args:
            url (str): URL to fetch.
        
        Returns:
            Optional[str]: Page content or None if failed.
        """
        last_error = None
        
        for retry in range(self.max_retries):
            try:
                # Add random delay between retries
                if retry > 0:
                    delay = self.retry_delays[min(retry - 1, len(self.retry_delays) - 1)]
                    delay += random.uniform(0, 2)  # Add jitter
                    logger.info("Retry %d/%d: Waiting %.2f seconds...", retry + 1, self.max_retries, delay)
                    time.sleep(delay)
                
                # Make request with timeout
                response = self.session.get(url, timeout=self.timeout)
                
                # Handle common error cases
                if response.status_code == 404:
                    logger.warning("Page not found (404): %s", url)
                    return None
                
                if response.status_code in [403, 429]:
                    logger.warning("Rate limiting or access denied (HTTP %d)", response.status_code)
                    if retry < self.max_retries - 1:
                        continue
                    return None
                
                if response.status_code >= 500:
                    logger.warning("Server error (HTTP %d)", response.status_code)
                    if retry < self.max_retries - 1:
                        continue
                    return None
                
                # Raise for any other HTTP errors
                response.raise_for_status()
                
                # Verify content type
                content_type = response.headers.get('content-type', '').lower()
                if 'text/html' not in content_type and 'application/json' not in content_type:
                    logger.warning("Unexpected content type: %s", content_type)
                    if retry < self.max_retries - 1:
                        continue
                    return None
                
                # Verify content length
                content_length = len(response.content)
                if content_length < 100:  # Arbitrary minimum length
                    logger.warning("Response too short (%d bytes)", content_length)
                    if retry < self.max_retries - 1:
                        continue
                    return None
                
                return response.text
                
            except requests.RequestException as e:
                last_error = e
                logger.error("Error fetching %s (attempt %d/%d): %s", 
                           url, retry + 1, self.max_retries, str(e))
                
                # Check if it's a connection error
                if isinstance(e, (requests.ConnectionError, requests.Timeout)):
                    if retry < self.max_retries - 1:
                        continue
                
                # Check if it's a proxy error
                if isinstance(e, requests.ProxyError):
                    logger.error("Proxy error, trying direct connection")
                    self.session.proxies = {}  # Clear proxies
                    if retry < self.max_retries - 1:
                        continue
        
        logger.error("Max retries reached for %s. Last error: %s", url, str(last_error))
        return None
    
    def _clean_price(self, price_text: str) -> float:
        """
        Clean and convert price text to float.
        
        Args:
            price_text (str): Price text to clean.
        
        Returns:
            float: Cleaned price.
        """
        try:
            # Remove currency symbols, commas, and convert to float
            cleaned = re.sub(r'[^\d.]', '', price_text)
            return float(cleaned)
        except (ValueError, TypeError):
            logger.warning("Could not parse price: %s", price_text)
            return 0.0
    
    def _calculate_average(self, prices: List[float]) -> Optional[float]:
        """
        Calculate average of prices.
        
        Args:
            prices (List[float]): List of prices.
        
        Returns:
            Optional[float]: Average price or None if list is empty.
        """
        if not prices:
            return None
        
        # Remove outliers (values more than 2 standard deviations from the mean)
        if len(prices) >= 5:
            mean = statistics.mean(prices)
            stdev = statistics.stdev(prices) if len(prices) > 1 else 0
            filtered_prices = [p for p in prices if abs(p - mean) <= 2 * stdev]
            
            # Only use filtered prices if we didn't filter too many
            if len(filtered_prices) >= len(prices) * 0.7:
                prices = filtered_prices
        
        return statistics.mean(prices)
    
    def _calculate_median(self, prices: List[float]) -> Optional[float]:
        """
        Calculate median of prices.
        
        Args:
            prices (List[float]): List of prices.
        
        Returns:
            Optional[float]: Median price or None if list is empty.
        """
        if not prices:
            return None
        return statistics.median(prices)

# Example usage
if __name__ == "__main__":
    # Example card to test
    card_name = "Blue-Eyes White Dragon"
    set_code = "SDK"
    
    # Initialize PriceComparator
    price_comparator = PriceComparator()
    
    # Get sold prices
    price_data = price_comparator.get_sold_prices(card_name, set_code)
    
    # Print results
    if price_data:
        print(f"\nPrice data for {card_name} ({set_code}):")
        print(f"Raw cards: {price_data['raw_count']} sales, Avg: ${price_data['raw_avg']:.2f}, Median: ${price_data['raw_median']:.2f}")
        print(f"PSA 9: {price_data['psa_9_count']} sales, Avg: ${price_data['psa_9_avg']:.2f}")
        print(f"PSA 10: {price_data['psa_10_count']} sales, Avg: ${price_data['psa_10_avg']:.2f}")
        print(f"Sell-through rate: {price_data['sell_through_rate']}")
    else:
        print(f"No price data found for {card_name} ({set_code})")
