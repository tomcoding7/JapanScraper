"""
Command Line Interface for Yu-Gi-Oh Card Arbitrage Bot

This module provides a command-line interface for the Yu-Gi-Oh Card Arbitrage Bot.
"""

import argparse
import logging
import os
import sys
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

# Import custom modules
from core_engine import CoreEngine
from bookmark_manager import BookmarkManager

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

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Yu-Gi-Oh Card Arbitrage Bot')
    
    # Main commands
    parser.add_argument('command', choices=['search', 'analyze', 'watchlist', 'export', 'config'],
                        help='Command to execute')
    
    # Search options
    parser.add_argument('--terms', nargs='+', help='Search terms to use')
    parser.add_argument('--max-pages', type=int, default=5, help='Maximum pages to scrape per search')
    parser.add_argument('--max-listings', type=int, default=20, help='Maximum listings to analyze per search term')
    
    # Analysis options
    parser.add_argument('--min-profit', type=float, default=2.0, help='Minimum profit ratio threshold (e.g., 2.0 for 2x)')
    parser.add_argument('--include-grading', action='store_true', help='Include grading costs in profit calculation')
    
    # Output options
    parser.add_argument('--output-dir', default='results', help='Output directory for results')
    parser.add_argument('--headless', action='store_true', default=True, help='Run browser in headless mode')
    
    # Watchlist options
    parser.add_argument('--list-id', help='Specific auction ID to view details')
    
    # Export options
    parser.add_argument('--export-ids', nargs='+', help='Auction IDs to export to ZenMarket')
    parser.add_argument('--export-all', action='store_true', help='Export all bookmarked auctions to ZenMarket')
    
    # Config options
    parser.add_argument('--set-zenmarket', action='store_true', help='Set ZenMarket credentials')
    parser.add_argument('--email', help='ZenMarket email')
    parser.add_argument('--password', help='ZenMarket password')
    parser.add_argument('--update-rates', action='store_true', help='Update currency conversion rates')
    parser.add_argument('--jpy-to-usd', type=float, help='JPY to USD conversion rate')
    
    return parser.parse_args()

def load_config() -> Dict[str, Any]:
    """Load configuration from file."""
    config_file = 'config.json'
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            return {}
    else:
        return {}

def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to file."""
    config_file = 'config.json'
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving config: {str(e)}")

def command_search(args, config: Dict[str, Any]) -> None:
    """Execute search command."""
    # Update config with command line arguments
    config.update({
        'output_dir': args.output_dir,
        'max_pages': args.max_pages,
        'headless': args.headless,
        'min_profit_ratio': args.min_profit,
        'max_listings_per_search': args.max_listings
    })
    
    # Initialize Core Engine
    engine = CoreEngine(config)
    
    # Run workflow with specified search terms
    search_terms = args.terms if args.terms else None
    profitable_listings = engine.run_workflow(search_terms)
    
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

def command_analyze(args, config: Dict[str, Any]) -> None:
    """Execute analyze command."""
    if not args.terms:
        print("Please provide at least one URL to analyze using --terms")
        return
    
    # Update config with command line arguments
    config.update({
        'output_dir': args.output_dir,
        'headless': args.headless,
        'min_profit_ratio': args.min_profit
    })
    
    # Initialize Core Engine
    engine = CoreEngine(config)
    
    # Analyze each URL
    for url in args.terms:
        print(f"\nAnalyzing URL: {url}")
        try:
            # Get listing details
            listing = engine.buyee_scraper.get_listing_details(url)
            if not listing:
                print(f"Could not fetch details for {url}")
                continue
            
            # Analyze card information
            card_info = engine.card_analyzer.analyze_card(listing)
            
            # Get price data
            price_data = engine.price_comparator.get_sold_prices(
                card_info.name if card_info else listing.get('title', ''),
                card_info.set_code if card_info else None
            )
            
            if not price_data:
                print("Could not fetch price data")
                continue
            
            # Calculate profit
            profit_analysis = engine.profit_calculator.calculate_profit(
                listing.get('price', 0),
                price_data.get('raw_median', 0),
                args.include_grading
            )
            
            # Print analysis
            print(f"\nTitle: {listing.get('title', 'Unknown')}")
            print(f"Price: ¥{listing.get('price', 0):,.0f}")
            print(f"Condition: {listing.get('condition', 'Unknown')}")
            
            if card_info:
                print(f"\nCard Information:")
                print(f"Name: {card_info.name}")
                print(f"Set: {card_info.set_name}")
                print(f"Set Code: {card_info.set_code}")
                print(f"Rarity: {card_info.rarity}")
            
            print(f"\nPrice Analysis:")
            print(f"Raw Card Median: ${price_data.get('raw_median', 0):,.2f}")
            print(f"PSA 9 Median: ${price_data.get('psa_9_median', 0):,.2f}")
            print(f"PSA 10 Median: ${price_data.get('psa_10_median', 0):,.2f}")
            print(f"Total Sales: {price_data.get('total_sales', 0)}")
            
            print(f"\nProfit Analysis:")
            print(f"Total Cost: ${profit_analysis.get('total_cost_usd', 0):,.2f}")
            print(f"Net Revenue: ${profit_analysis.get('net_revenue_usd', 0):,.2f}")
            print(f"Profit: ${profit_analysis.get('profit', 0):,.2f}")
            print(f"ROI: {profit_analysis.get('roi', 0):.2f}x")
            print(f"Profit Margin: {profit_analysis.get('profit_margin', 0):.1f}%")
            
            # Check if it meets profit threshold
            if profit_analysis.get('meets_threshold', False):
                print("\n✅ This listing meets the profit threshold!")
            else:
                print("\n❌ This listing does not meet the profit threshold")
            
        except Exception as e:
            logger.error(f"Error analyzing {url}: {str(e)}", exc_info=True)
            print(f"Error analyzing {url}: {str(e)}")

def command_watchlist(args, config: Dict[str, Any]) -> None:
    """Execute watchlist command."""
    # Initialize BookmarkManager
    bookmark_manager = BookmarkManager(output_dir=args.output_dir)
    
    # Get watchlist
    watchlist = bookmark_manager.get_watchlist()
    
    if args.list_id:
        # Show details for specific auction
        for item in watchlist:
            if item.get('auction_id') == args.list_id:
                print(f"\nDetails for auction {args.list_id}:")
                print(f"Title: {item.get('title', 'Unknown')}")
                print(f"Price: ¥{item.get('price', 0):,.0f}")
                print(f"URL: {item.get('url', '')}")
                print(f"Condition: {item.get('condition_analysis', {}).get('condition', 'Unknown')}")
                print(f"Profit Analysis:")
                profit_analysis = item.get('profit_analysis', {})
                for key, value in profit_analysis.items():
                    if isinstance(value, float):
                        print(f"  {key}: {value:.2f}")
                    else:
                        print(f"  {key}: {value}")
                return
        print(f"Auction {args.list_id} not found in watchlist")
    else:
        # Show all watchlist items
        print(f"\nWatchlist ({len(watchlist)} items):")
        for i, item in enumerate(watchlist):
            profit_analysis = item.get('profit_analysis', {})
            print(f"{i+1}. {item.get('title', 'Unknown')}")
            print(f"   ID: {item.get('auction_id', 'Unknown')}")
            print(f"   Price: ¥{item.get('price', 0):,.0f}")
            print(f"   ROI: {profit_analysis.get('roi', 0):.2f}x")
            print(f"   URL: {item.get('url', '')}")
            print()

def command_export(args, config: Dict[str, Any]) -> None:
    """Execute export command."""
    # Check if ZenMarket credentials are set
    if not config.get('zenmarket_credentials', {}).get('email') or not config.get('zenmarket_credentials', {}).get('password'):
        print("ZenMarket credentials not set. Use 'config --set-zenmarket --email EMAIL --password PASSWORD' to set them.")
        return
    
    # Initialize BookmarkManager
    bookmark_manager = BookmarkManager(
        output_dir=args.output_dir,
        zenmarket_credentials=config.get('zenmarket_credentials', {})
    )
    
    if args.export_all:
        # Export all bookmarked auctions
        print("Exporting all bookmarked auctions to ZenMarket...")
        success = bookmark_manager.export_to_zenmarket()
        if success:
            print("Successfully exported auctions to ZenMarket")
        else:
            print("Failed to export auctions to ZenMarket")
    elif args.export_ids:
        # Export specific auctions
        print(f"Exporting {len(args.export_ids)} auctions to ZenMarket...")
        success = bookmark_manager.export_to_zenmarket(args.export_ids)
        if success:
            print("Successfully exported auctions to ZenMarket")
        else:
            print("Failed to export auctions to ZenMarket")
    else:
        print("No auctions specified for export. Use --export-all or --export-ids.")

def command_config(args, config: Dict[str, Any]) -> None:
    """Execute config command."""
    if args.set_zenmarket:
        if not args.email or not args.password:
            print("Both --email and --password are required to set ZenMarket credentials")
            return
        
        # Set ZenMarket credentials
        if 'zenmarket_credentials' not in config:
            config['zenmarket_credentials'] = {}
        
        config['zenmarket_credentials']['email'] = args.email
        config['zenmarket_credentials']['password'] = args.password
        
        # Save config
        save_config(config)
        print("ZenMarket credentials set successfully")
    
    elif args.update_rates:
        if not args.jpy_to_usd:
            print("--jpy-to-usd is required to update currency conversion rates")
            return
        
        # Update currency conversion rates
        if 'currency_conversion' not in config:
            config['currency_conversion'] = {}
        
        config['currency_conversion']['JPY_to_USD'] = args.jpy_to_usd
        config['currency_conversion']['USD_to_JPY'] = 1 / args.jpy_to_usd
        
        # Save config
        save_config(config)
        print(f"Currency conversion rates updated: JPY to USD = {args.jpy_to_usd}")
    
    else:
        # Show current config
        print("\nCurrent Configuration:")
        for key, value in config.items():
            if key == 'zenmarket_credentials':
                print(f"ZenMarket Email: {value.get('email', 'Not set')}")
                print(f"ZenMarket Password: {'*****' if value.get('password') else 'Not set'}")
            elif key == 'currency_conversion':
                print(f"Currency Conversion:")
                for rate_key, rate_value in value.items():
                    print(f"  {rate_key}: {rate_value}")
            else:
                print(f"{key}: {value}")

def main():
    """Main entry point."""
    # Parse command line arguments
    args = parse_args()
    
    # Load configuration
    config = load_config()
    
    # Execute command
    if args.command == 'search':
        command_search(args, config)
    elif args.command == 'analyze':
        command_analyze(args, config)
    elif args.command == 'watchlist':
        command_watchlist(args, config)
    elif args.command == 'export':
        command_export(args, config)
    elif args.command == 'config':
        command_config(args, config)

if __name__ == "__main__":
    main()
