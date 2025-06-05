# Yu-Gi-Oh Card Arbitrage Bot - Integration Test

import os
import logging
import json
from typing import Dict, List, Any
from datetime import datetime

# Import custom modules
from core_engine import CoreEngine
from price_comparator import PriceComparator
from profit_calculator import ProfitCalculator
from bookmark_manager import BookmarkManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('integration_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_workflow():
    """Test the complete workflow with a sample card."""
    logger.info("Starting integration test")
    
    # Configuration
    config = {
        'output_dir': 'test_results',
        'max_pages': 1,
        'headless': True,
        'min_profit_ratio': 1.5,  # Lower threshold for testing
        'max_listings_per_search': 5,
        'currency_conversion': {
            'JPY_to_USD': 0.0067,
            'USD_to_JPY': 149.25
        }
    }
    
    # Create output directory
    os.makedirs(config['output_dir'], exist_ok=True)
    
    # Test search terms
    search_terms = ["遊戯王 アジア SDK"]  # Blue-Eyes White Dragon from Starter Deck Kaiba
    
    try:
        # Step 1: Test PriceComparator
        logger.info("Testing PriceComparator")
        price_comparator = PriceComparator()
        price_data = price_comparator.get_sold_prices("Blue-Eyes White Dragon", "SDK")
        
        if not price_data:
            logger.error("PriceComparator test failed: No price data returned")
            return False
        
        logger.info("PriceComparator test successful")
        logger.info(f"Found {price_data['total_sales']} sales for Blue-Eyes White Dragon (SDK)")
        
        # Step 2: Test ProfitCalculator
        logger.info("Testing ProfitCalculator")
        profit_calculator = ProfitCalculator(config['currency_conversion'])
        
        # Sample calculation with 5000 JPY Buyee price and $100 eBay price
        profit_analysis = profit_calculator.calculate_profit(5000, 100)
        
        if not profit_analysis or 'profit' not in profit_analysis:
            logger.error("ProfitCalculator test failed: Invalid profit analysis")
            return False
        
        logger.info("ProfitCalculator test successful")
        logger.info(f"Calculated profit: ${profit_analysis['profit']:.2f}, ROI: {profit_analysis['roi']:.2f}x")
        
        # Step 3: Test BookmarkManager
        logger.info("Testing BookmarkManager")
        bookmark_manager = BookmarkManager(output_dir=config['output_dir'])
        
        # Sample auction data
        auction_data = {
            'title': 'Blue-Eyes White Dragon SDK-001 Ultra Rare',
            'price': 5000,
            'url': 'https://buyee.jp/item/yahoo/auction/x123456789',
            'image_url': 'https://example.com/image.jpg',
            'condition': 'Near Mint',
            'profit_analysis': profit_analysis
        }
        
        # Save auction
        success = bookmark_manager.save_auction(auction_data)
        
        if not success:
            logger.error("BookmarkManager test failed: Could not save auction")
            return False
        
        # Get watchlist
        watchlist = bookmark_manager.get_watchlist()
        
        if not watchlist or len(watchlist) == 0:
            logger.error("BookmarkManager test failed: Empty watchlist")
            return False
        
        logger.info("BookmarkManager test successful")
        logger.info(f"Saved auction to watchlist: {watchlist[0].get('title')}")
        
        # Step 4: Test CoreEngine (limited functionality)
        logger.info("Testing CoreEngine (limited functionality)")
        
        # Create a mock method for testing without actual web scraping
        def mock_search_listings(self, search_terms):
            return [{
                'title': 'Blue-Eyes White Dragon SDK-001 Ultra Rare',
                'price': 5000,
                'url': 'https://buyee.jp/item/yahoo/auction/x123456789',
                'image_url': 'https://example.com/image.jpg'
            }]
        
        # Save the original method
        original_search_listings = CoreEngine.search_listings
        
        # Replace with mock method
        CoreEngine.search_listings = mock_search_listings
        
        # Initialize Core Engine
        engine = CoreEngine(config)
        
        # Run workflow with mock search
        engine.search_results = engine.search_listings(engine, search_terms)
        
        # Restore original method
        CoreEngine.search_listings = original_search_listings
        
        if not engine.search_results or len(engine.search_results) == 0:
            logger.error("CoreEngine test failed: No search results")
            return False
        
        logger.info("CoreEngine test successful")
        logger.info(f"Found {len(engine.search_results)} mock listings")
        
        # Save test results
        test_results = {
            'timestamp': datetime.now().isoformat(),
            'price_data': price_data,
            'profit_analysis': profit_analysis,
            'watchlist': watchlist,
            'search_results': engine.search_results
        }
        
        results_file = os.path.join(config['output_dir'], 'integration_test_results.json')
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(test_results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Integration test completed successfully. Results saved to {results_file}")
        return True
        
    except Exception as e:
        logger.error(f"Integration test failed with error: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_workflow()
    
    if success:
        print("\n✅ Integration test completed successfully!")
    else:
        print("\n❌ Integration test failed. Check integration_test.log for details.")
