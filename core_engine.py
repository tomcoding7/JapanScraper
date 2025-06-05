"""
Core Engine for Yu-Gi-Oh Card Arbitrage Bot

This module orchestrates the entire workflow for finding profitable Yu-Gi-Oh cards
on Buyee.jp, comparing with eBay sold prices, and facilitating the purchase process.
"""

import os
import logging
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd

# Import custom modules
from buyee_scraper import BuyeeScraper
from card_analyzer import CardAnalyzer, CardInfo
from image_analyzer import ImageAnalyzer
from rank_analyzer import RankAnalyzer, CardCondition
from price_comparator import PriceComparator
from profit_calculator import ProfitCalculator
from bookmark_manager import BookmarkManager
from search_terms import SEARCH_TERMS

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

class CoreEngine:
    """
    Core Engine class that orchestrates the entire workflow for the Yu-Gi-Oh Card Arbitrage Bot.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Core Engine with configuration.
        
        Args:
            config (Dict[str, Any], optional): Configuration dictionary. Defaults to None.
        """
        # Default configuration
        self.config = {
            'output_dir': 'results',
            'max_pages': 5,
            'headless': True,
            'min_profit_ratio': 2.0,  # 2x profit threshold
            'max_listings_per_search': 20,
            'save_debug_info': True,
            'currency_conversion': {
                'JPY_to_USD': 0.0067  # Example rate, should be updated dynamically
            }
        }
        
        # Update with provided config
        if config:
            self.config.update(config)
        
        # Create output directory
        os.makedirs(self.config['output_dir'], exist_ok=True)
        
        # Initialize components
        self.buyee_scraper = BuyeeScraper(
            output_dir=self.config['output_dir'],
            max_pages=self.config['max_pages'],
            headless=self.config['headless']
        )
        self.card_analyzer = CardAnalyzer()
        self.image_analyzer = ImageAnalyzer()
        self.rank_analyzer = RankAnalyzer()
        self.price_comparator = PriceComparator()
        self.profit_calculator = ProfitCalculator(
            currency_conversion=self.config['currency_conversion']
        )
        self.bookmark_manager = BookmarkManager(
            output_dir=self.config['output_dir']
        )
        
        # Results storage
        self.search_results = []
        self.analyzed_listings = []
        self.profitable_listings = []
        
        logger.info("Core Engine initialized with configuration: %s", self.config)
    
    def run_workflow(self, search_terms: List[str] = None) -> List[Dict[str, Any]]:
        """
        Run the complete workflow.
        
        Args:
            search_terms (List[str], optional): List of search terms. Defaults to None.
        
        Returns:
            List[Dict[str, Any]]: List of profitable listings.
        """
        try:
            # Use provided search terms or default from SEARCH_TERMS
            terms = search_terms if search_terms else SEARCH_TERMS
            logger.info("Starting workflow with %d search terms", len(terms))
            
            print("\n🔍 Step 1: Searching for listings...")
            # Step 1: Search for listings
            self.search_results = self.search_listings(terms)
            print(f"Found {len(self.search_results)} total listings")
            
            if not self.search_results:
                print("No listings found. Exiting workflow.")
                return []
            
            print("\n📊 Step 2: Analyzing listings...")
            # Step 2: Analyze listings
            self.analyzed_listings = self.analyze_listings(self.search_results)
            print(f"Analyzed {len(self.analyzed_listings)} listings")
            
            if not self.analyzed_listings:
                print("No listings could be analyzed. Exiting workflow.")
                return []
            
            print("\n💰 Step 3: Finding profitable listings...")
            # Step 3: Compare prices and calculate profit
            self.profitable_listings = self.find_profitable_listings(self.analyzed_listings)
            print(f"Found {len(self.profitable_listings)} profitable listings")
            
            print("\n💾 Step 4: Saving results...")
            # Step 4: Save results
            self.save_results()
            print("Results saved successfully")
            
            return self.profitable_listings
            
        except Exception as e:
            logger.error("Error in workflow execution: %s", str(e), exc_info=True)
            print(f"\n❌ Error in workflow execution: {str(e)}")
            return []
    
    def search_listings(self, search_terms: List[str]) -> List[Dict[str, Any]]:
        """
        Search for listings on Buyee.jp.
        
        Args:
            search_terms (List[str]): List of search terms.
        
        Returns:
            List[Dict[str, Any]]: List of found listings.
        """
        all_listings = []
        
        try:
            for i, term in enumerate(search_terms, 1):
                print(f"\nSearching term {i}/{len(search_terms)}: {term}")
                
                # Use BuyeeScraper to search
                listings = self.buyee_scraper.search(term)
                
                # Filter by popularity
                popular_listings = self.buyee_scraper.filter_by_popularity(listings)
                
                # Limit results per search term
                limited_listings = popular_listings[:self.config['max_listings_per_search']]
                
                print(f"Found {len(listings)} listings, filtered to {len(limited_listings)} popular listings")
                
                all_listings.extend(limited_listings)
                
                # Add a delay between searches
                if i < len(search_terms):
                    print("Waiting before next search...")
                    time.sleep(2)
            
            # Remove duplicates based on URL
            unique_listings = []
            seen_urls = set()
            
            for listing in all_listings:
                if listing['url'] not in seen_urls:
                    seen_urls.add(listing['url'])
                    unique_listings.append(listing)
            
            print(f"\nRemoved {len(all_listings) - len(unique_listings)} duplicate listings")
            
            return unique_listings
            
        except Exception as e:
            logger.error("Error searching listings: %s", str(e), exc_info=True)
            print(f"\n❌ Error searching listings: {str(e)}")
            return []
    
    def analyze_listings(self, listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze listings to extract detailed information.
        
        Args:
            listings (List[Dict[str, Any]]): List of listings to analyze.
        
        Returns:
            List[Dict[str, Any]]: List of analyzed listings.
        """
        analyzed_listings = []
        
        try:
            total = len(listings)
            for i, listing in enumerate(listings, 1):
                print(f"\nAnalyzing listing {i}/{total}: {listing.get('title', 'Unknown')}")
                
                try:
                    # Get detailed listing information
                    detailed_listing = self.buyee_scraper.get_listing_details(listing['url'])
                    
                    if not detailed_listing:
                        print(f"❌ Could not get details for listing: {listing['url']}")
                        continue
                    
                    # Analyze card information
                    card_info = self.card_analyzer.analyze_card(detailed_listing)
                    
                    # Analyze images if available
                    image_analysis = None
                    if detailed_listing.get('image_urls'):
                        image_analysis = self.image_analyzer.analyze_image(detailed_listing['image_urls'])
                    
                    # Analyze condition from description
                    condition_analysis = self.rank_analyzer.analyze_condition(
                        detailed_listing.get('description', ''),
                        detailed_listing.get('condition', '')
                    )
                    
                    # Combine all analyses
                    analyzed_listing = {
                        **detailed_listing,
                        'card_info': card_info.__dict__ if card_info else None,
                        'image_analysis': image_analysis,
                        'condition_analysis': condition_analysis
                    }
                    
                    analyzed_listings.append(analyzed_listing)
                    print("✅ Analysis complete")
                    
                    # Add a delay between analyses
                    if i < total:
                        print("Waiting before next analysis...")
                        time.sleep(1)
                    
                except Exception as e:
                    logger.error("Error analyzing listing %s: %s", listing.get('url', 'Unknown'), str(e))
                    print(f"❌ Error analyzing listing: {str(e)}")
                    continue
            
            return analyzed_listings
            
        except Exception as e:
            logger.error("Error in analyze_listings: %s", str(e), exc_info=True)
            print(f"\n❌ Error in analyze_listings: {str(e)}")
            return []
    
    def find_profitable_listings(self, analyzed_listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find profitable listings by comparing prices and calculating profit.
        
        Args:
            analyzed_listings (List[Dict[str, Any]]): List of analyzed listings.
        
        Returns:
            List[Dict[str, Any]]: List of profitable listings.
        """
        profitable_listings = []
        
        try:
            total = len(analyzed_listings)
            for i, listing in enumerate(analyzed_listings, 1):
                print(f"\nChecking profitability {i}/{total}: {listing.get('title', 'Unknown')}")
                
                try:
                    # Get card info
                    card_info = listing.get('card_info', {})
                    card_name = card_info.get('name') if card_info else listing.get('title', '')
                    set_code = card_info.get('set_code') if card_info else None
                    
                    # Get price data
                    price_data = self.price_comparator.get_sold_prices(card_name, set_code)
                    
                    if not price_data:
                        print("❌ Could not fetch price data")
                        continue
                    
                    # Calculate profit
                    profit_analysis = self.profit_calculator.calculate_profit(
                        listing.get('price', 0),
                        price_data.get('raw_median', 0),
                        self.config.get('include_grading', False)
                    )
                    
                    # Add profit analysis to listing
                    listing['profit_analysis'] = profit_analysis
                    
                    # Check if it meets profit threshold
                    if profit_analysis.get('meets_threshold', False):
                        profitable_listings.append(listing)
                        print(f"✅ Profitable! ROI: {profit_analysis.get('roi', 0):.2f}x")
                    else:
                        print(f"❌ Not profitable. ROI: {profit_analysis.get('roi', 0):.2f}x")
                    
                    # Add a delay between checks
                    if i < total:
                        print("Waiting before next check...")
                        time.sleep(1)
                    
                except Exception as e:
                    logger.error("Error checking profitability for listing %s: %s", 
                               listing.get('url', 'Unknown'), str(e))
                    print(f"❌ Error checking profitability: {str(e)}")
                    continue
            
            return profitable_listings
            
        except Exception as e:
            logger.error("Error in find_profitable_listings: %s", str(e), exc_info=True)
            print(f"\n❌ Error in find_profitable_listings: {str(e)}")
            return []
    
    def _determine_ebay_price(self, listing: Dict[str, Any], price_data: Dict[str, Any]) -> float:
        """
        Determine which eBay price to use based on card condition.
        
        Args:
            listing (Dict[str, Any]): Analyzed listing.
            price_data (Dict[str, Any]): Price data from eBay/130point.
        
        Returns:
            float: Appropriate eBay price.
        """
        # Default to raw price
        ebay_price = price_data.get('raw_avg')
        
        # Check condition
        condition = CardCondition.UNKNOWN
        
        if listing.get('condition_analysis') and listing['condition_analysis'].get('condition'):
            condition = listing['condition_analysis']['condition']
        
        # Check image analysis for damage
        is_damaged = False
        if listing.get('image_analysis') and listing['image_analysis'].get('is_damaged') is not None:
            is_damaged = listing['image_analysis']['is_damaged']
        
        # Determine price based on condition
        if condition in [CardCondition.MINT, CardCondition.NEAR_MINT] and not is_damaged:
            # If in excellent condition, could potentially grade PSA 9
            if price_data.get('psa_9_avg') and price_data.get('psa_9_count', 0) > 2:
                ebay_price = price_data['psa_9_avg'] * 0.7  # 70% of PSA 9 price (accounting for grading costs/risk)
            elif price_data.get('raw_avg'):
                ebay_price = price_data['raw_avg'] * 1.2  # 20% premium for excellent condition
        elif condition in [CardCondition.EXCELLENT, CardCondition.VERY_GOOD] and not is_damaged:
            # Standard raw price
            if price_data.get('raw_avg'):
                ebay_price = price_data['raw_avg']
        else:
            # Damaged or poor condition
            if price_data.get('raw_avg'):
                ebay_price = price_data['raw_avg'] * 0.7  # 30% discount for poor condition
        
        return ebay_price
    
    def save_results(self) -> None:
        """
        Save results to files.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Save all listings
            if self.search_results:
                all_listings_file = os.path.join(self.config['output_dir'], f"all_listings_{timestamp}.json")
                with open(all_listings_file, 'w', encoding='utf-8') as f:
                    json.dump(self.search_results, f, ensure_ascii=False, indent=2)
                logger.info("Saved all listings to %s", all_listings_file)
            
            # Save analyzed listings
            if self.analyzed_listings:
                analyzed_file = os.path.join(self.config['output_dir'], f"analyzed_listings_{timestamp}.json")
                with open(analyzed_file, 'w', encoding='utf-8') as f:
                    json.dump(self.analyzed_listings, f, ensure_ascii=False, indent=2)
                logger.info("Saved analyzed listings to %s", analyzed_file)
            
            # Save profitable listings
            if self.profitable_listings:
                profitable_file = os.path.join(self.config['output_dir'], f"profitable_listings_{timestamp}.json")
                with open(profitable_file, 'w', encoding='utf-8') as f:
                    json.dump(self.profitable_listings, f, ensure_ascii=False, indent=2)
                logger.info("Saved profitable listings to %s", profitable_file)
                
                # Create CSV for easy viewing
                profitable_csv = os.path.join(self.config['output_dir'], f"profitable_listings_{timestamp}.csv")
                
                # Extract key information for CSV
                csv_data = []
                for listing in self.profitable_listings:
                    row = {
                        'Title': listing.get('title', ''),
                        'Buyee Price (JPY)': listing.get('price', 0),
                        'eBay Price (USD)': listing.get('profit_analysis', {}).get('ebay_price', 0),
                        'Profit (USD)': listing.get('profit_analysis', {}).get('profit', 0),
                        'ROI': listing.get('profit_analysis', {}).get('roi', 0),
                        'Condition': str(listing.get('condition_analysis', {}).get('condition', '')),
                        'URL': listing.get('url', '')
                    }
                    csv_data.append(row)
                
                # Save as CSV
                df = pd.DataFrame(csv_data)
                df.to_csv(profitable_csv, index=False)
                logger.info("Saved profitable listings CSV to %s", profitable_csv)
                
                # Bookmark profitable listings
                for listing in self.profitable_listings:
                    self.bookmark_manager.save_auction(listing)
                
                logger.info("Bookmarked %d profitable listings", len(self.profitable_listings))
            
        except Exception as e:
            logger.error("Error saving results: %s", str(e), exc_info=True)
    
    def export_to_zenmarket(self, listing_ids: List[str] = None) -> bool:
        """
        Export selected listings to ZenMarket.
        
        Args:
            listing_ids (List[str], optional): List of listing IDs to export. Defaults to None.
        
        Returns:
            bool: Success status.
        """
        try:
            if not listing_ids:
                # Export all profitable listings
                listing_ids = [listing.get('id') for listing in self.profitable_listings if listing.get('id')]
            
            if not listing_ids:
                logger.warning("No listings to export to ZenMarket")
                return False
            
            # Export to ZenMarket
            success = self.bookmark_manager.export_to_zenmarket(listing_ids)
            
            if success:
                logger.info("Successfully exported %d listings to ZenMarket", len(listing_ids))
            else:
                logger.error("Failed to export listings to ZenMarket")
            
            return success
            
        except Exception as e:
            logger.error("Error exporting to ZenMarket: %s", str(e), exc_info=True)
            return False

# Example usage
if __name__ == "__main__":
    # Initialize Core Engine
    engine = CoreEngine()
    
    # Run workflow
    profitable_listings = engine.run_workflow()
    
    # Print results
    print(f"\nFound {len(profitable_listings)} profitable listings:")
    for i, listing in enumerate(profitable_listings):
        profit_analysis = listing.get('profit_analysis', {})
        print(f"{i+1}. {listing.get('title', 'Unknown')}")
        print(f"   Buyee Price: ¥{listing.get('price', 0):,.0f}")
        print(f"   eBay Price: ${profit_analysis.get('ebay_price', 0):,.2f}")
        print(f"   Profit: ${profit_analysis.get('profit', 0):,.2f}")
        print(f"   ROI: {profit_analysis.get('roi', 0):.2f}x")
        print(f"   URL: {listing.get('url', '')}")
        print()
