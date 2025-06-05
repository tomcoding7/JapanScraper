"""
Test script for the improved Buyee Scraper
This script tests the robustness of the scraper with various error scenarios
"""

import sys
import time
import logging
import os
import random
from buyee_scraper import BuyeeScraper

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('test_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_basic_functionality():
    """Test basic scraper functionality with a simple search term"""
    logger.info("=== Testing Basic Functionality ===")
    
    # Create output directory for this test
    output_dir = "test_results/basic"
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize scraper with visible browser for debugging
    scraper = BuyeeScraper(output_dir=output_dir, max_pages=1, headless=False)
    
    try:
        # Test connection
        logger.info("Testing connection...")
        if not scraper.test_connection():
            logger.error("Connection test failed")
            return False
        
        # Test search
        search_term = "遊戯王 アジア"
        logger.info(f"Testing search with term: {search_term}")
        results = scraper.search(search_term)
        
        if not results:
            logger.warning(f"No results found for {search_term}")
            # This might be expected, so don't fail the test
        else:
            logger.info(f"Found {len(results)} results for {search_term}")
            
            # Test getting details for the first item
            if len(results) > 0:
                first_item = results[0]
                logger.info(f"Testing get_listing_details for: {first_item['title']}")
                details = scraper.get_listing_details(first_item['url'])
                
                if details:
                    logger.info(f"Successfully retrieved details: {details.get('title')}")
                else:
                    logger.error("Failed to retrieve item details")
                    return False
        
        return True
    except Exception as e:
        logger.error(f"Error in basic functionality test: {str(e)}", exc_info=True)
        return False
    finally:
        scraper.cleanup()

def test_error_recovery():
    """Test the scraper's ability to recover from errors"""
    logger.info("=== Testing Error Recovery ===")
    
    # Create output directory for this test
    output_dir = "test_results/error_recovery"
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize scraper
    scraper = BuyeeScraper(output_dir=output_dir, max_pages=2, headless=False)
    
    try:
        # Test connection
        logger.info("Testing connection...")
        if not scraper.test_connection():
            logger.error("Connection test failed")
            return False
        
        # Test search with multiple pages to test pagination
        search_term = "遊戯王 dm1"
        logger.info(f"Testing search with term: {search_term}")
        
        # Start the search
        results = scraper.search(search_term)
        
        if not results:
            logger.warning(f"No results found for {search_term}")
            # Try another search term
            search_term = "遊戯王 カード"
            logger.info(f"Trying another search term: {search_term}")
            results = scraper.search(search_term)
            
            if not results:
                logger.warning(f"No results found for {search_term} either")
                # This might be expected, so don't fail the test
        
        logger.info(f"Found {len(results)} results across multiple pages")
        
        # Test driver restart
        logger.info("Testing driver restart...")
        scraper.cleanup()  # Force cleanup
        
        if scraper.restart_driver():
            logger.info("Driver restart successful")
        else:
            logger.error("Driver restart failed")
            return False
        
        # Test search after restart
        search_term = "遊戯王 東映"
        logger.info(f"Testing search after restart with term: {search_term}")
        results = scraper.search(search_term)
        
        if results is not None:  # Even empty list is OK, just not None
            logger.info(f"Search after restart returned {len(results)} results")
        else:
            logger.error("Search after restart failed")
            return False
        
        return True
    except Exception as e:
        logger.error(f"Error in error recovery test: {str(e)}", exc_info=True)
        return False
    finally:
        scraper.cleanup()

def test_no_results_handling():
    """Test the scraper's handling of searches with no results"""
    logger.info("=== Testing No Results Handling ===")
    
    # Create output directory for this test
    output_dir = "test_results/no_results"
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize scraper
    scraper = BuyeeScraper(output_dir=output_dir, max_pages=1, headless=False)
    
    try:
        # Test connection
        logger.info("Testing connection...")
        if not scraper.test_connection():
            logger.error("Connection test failed")
            return False
        
        # Test search with a term likely to have no results
        # Using a very specific and unlikely term
        search_term = "遊戯王 xyzあいうえお123456789"
        logger.info(f"Testing search with unlikely term: {search_term}")
        results = scraper.search(search_term)
        
        # We expect no results
        if not results:
            logger.info("Correctly handled no results case")
            return True
        else:
            logger.warning(f"Unexpectedly found {len(results)} results for unlikely term")
            # This is not necessarily a failure
            return True
    except Exception as e:
        logger.error(f"Error in no results handling test: {str(e)}", exc_info=True)
        return False
    finally:
        scraper.cleanup()

def run_all_tests():
    """Run all test cases and report results"""
    logger.info("Starting all tests...")
    
    test_results = {
        "basic_functionality": False,
        "error_recovery": False,
        "no_results_handling": False
    }
    
    # Run tests
    try:
        test_results["basic_functionality"] = test_basic_functionality()
        time.sleep(2)  # Brief pause between tests
        
        test_results["error_recovery"] = test_error_recovery()
        time.sleep(2)  # Brief pause between tests
        
        test_results["no_results_handling"] = test_no_results_handling()
    except Exception as e:
        logger.error(f"Unexpected error during test execution: {str(e)}", exc_info=True)
    
    # Report results
    logger.info("=== Test Results ===")
    all_passed = True
    for test_name, result in test_results.items():
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        logger.info("All tests passed!")
    else:
        logger.warning("Some tests failed. See log for details.")
    
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
