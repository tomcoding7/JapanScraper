# Yu-Gi-Oh Card Arbitrage Bot - Design Document

## Overview

This document outlines the complete design for the Yu-Gi-Oh Card Arbitrage Bot, which automates the process of finding profitable Yu-Gi-Oh cards on Buyee.jp, comparing them with eBay sold prices, and facilitating the purchase process through ZenMarket.

## System Architecture

The system is designed with a modular architecture consisting of the following components:

1. **Core Engine**: Orchestrates the workflow and manages interactions between modules
2. **Buyee Scraper**: Handles searching and extracting card listings from Buyee.jp
3. **Card Analyzer**: Processes card information, condition, and value
4. **Price Comparator**: Fetches and analyzes eBay/130point.com sold prices
5. **Profit Calculator**: Determines potential profit margins
6. **Bookmarking System**: Saves promising auctions and exports to ZenMarket
7. **User Interface**: Provides command-line and optional web interface

### Architecture Diagram

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Buyee Scraper  │────▶│  Card Analyzer  │────▶│Price Comparator │
│                 │     │                 │     │                 │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │                       ▼                       │
         │              ┌─────────────────┐              │
         │              │                 │              │
         └─────────────▶│   Core Engine   │◀─────────────┘
                        │                 │
                        └────────┬────────┘
                                 │
                                 ▼
         ┌──────────────────────────────────────────┐
         │                                          │
┌────────┴────────┐     ┌─────────────────┐     ┌───┴───────────┐
│                 │     │                 │     │               │
│Profit Calculator│     │   Bookmarking   │     │User Interface │
│                 │     │     System      │     │               │
└─────────────────┘     └─────────────────┘     └───────────────┘
```

## Detailed Component Design

### 1. Core Engine (`core_engine.py`)

The Core Engine orchestrates the entire workflow and manages interactions between modules.

**Key Responsibilities:**
- Initialize and configure all modules
- Execute the workflow steps in sequence
- Handle errors and exceptions
- Manage state and persistence
- Provide logging and reporting

**Key Methods:**
- `run_workflow()`: Main entry point that executes the complete workflow
- `search_listings()`: Initiates search on Buyee
- `analyze_listings()`: Processes search results
- `compare_prices()`: Triggers price comparison
- `calculate_profit()`: Determines profit potential
- `bookmark_auctions()`: Saves promising auctions
- `export_to_zenmarket()`: Exports to ZenMarket

### 2. Buyee Scraper (`buyee_scraper.py`)

The Buyee Scraper handles searching and extracting card listings from Buyee.jp.

**Key Responsibilities:**
- Search for Yu-Gi-Oh cards on Buyee
- Filter by popularity/relevance
- Extract listing details
- Navigate to detailed listing pages
- Extract images and descriptions

**Key Methods:**
- `search(query)`: Performs search with given query
- `filter_by_popularity()`: Sorts listings by popularity
- `get_listing_details(url)`: Extracts detailed information
- `extract_images(listing)`: Gets high-resolution images
- `extract_description(listing)`: Gets full description

### 3. Card Analyzer (`card_analyzer.py`, `image_analyzer.py`, `rank_analyzer.py`, `text_analyzer.py`)

The Card Analyzer processes card information, condition, and value.

**Key Responsibilities:**
- Analyze card names and sets
- Determine card condition from text
- Analyze images for condition verification
- Identify valuable cards
- Assess condition confidence

**Key Methods:**
- `analyze_card(listing)`: Main analysis method
- `determine_condition(text, images)`: Assesses condition
- `verify_authenticity(images)`: Checks for counterfeits
- `identify_value_factors(card_info)`: Identifies value-adding factors

### 4. Price Comparator (`price_comparator.py`)

The Price Comparator fetches and analyzes eBay/130point.com sold prices.

**Key Responsibilities:**
- Search for equivalent cards on 130point.com
- Extract sold prices for different conditions (raw, PSA 9, PSA 10)
- Calculate average prices
- Determine market trends

**Key Methods:**
- `search_sold_prices(card_name, set_code)`: Searches for sold listings
- `get_raw_prices(results)`: Extracts raw card prices
- `get_graded_prices(results, grade)`: Extracts graded card prices
- `calculate_average_price(prices)`: Calculates average price
- `get_price_trend(card_name, set_code)`: Analyzes price trends

### 5. Profit Calculator (`profit_calculator.py`)

The Profit Calculator determines potential profit margins.

**Key Responsibilities:**
- Calculate potential profit based on Buyee price and eBay sold prices
- Consider shipping, fees, and other costs
- Determine ROI percentage
- Flag high-profit opportunities

**Key Methods:**
- `calculate_profit(buyee_price, ebay_price)`: Calculates raw profit
- `calculate_roi(buyee_price, ebay_price)`: Calculates ROI percentage
- `estimate_fees(buyee_price)`: Estimates all associated fees
- `is_profitable(roi)`: Determines if ROI meets threshold

### 6. Bookmarking System (`bookmark_manager.py`)

The Bookmarking System saves promising auctions and exports to ZenMarket.

**Key Responsibilities:**
- Save promising auction details
- Export selected auctions to ZenMarket
- Manage watchlist
- Track auction status

**Key Methods:**
- `save_auction(auction_details)`: Saves auction to local database
- `export_to_zenmarket(auction_id)`: Exports to ZenMarket
- `get_watchlist()`: Retrieves current watchlist
- `update_auction_status(auction_id, status)`: Updates auction status

### 7. User Interface (`cli.py`, `web_interface.py`)

The User Interface provides command-line and optional web interface.

**Key Responsibilities:**
- Accept user commands and parameters
- Display results in a readable format
- Provide interactive filtering and sorting
- Enable manual review and selection

**Key Methods:**
- `display_results(listings)`: Shows search results
- `display_detail(listing)`: Shows detailed listing information
- `display_profit_analysis(analysis)`: Shows profit analysis
- `get_user_selection(listings)`: Gets user selection for bookmarking

## Workflow Implementation

The complete workflow will be implemented as follows:

1. **Search Phase**
   - Initialize the Core Engine
   - Load search terms from configuration
   - Execute search on Buyee
   - Filter results by popularity
   - Extract basic listing information

2. **Analysis Phase**
   - For each listing, extract detailed information
   - Analyze card name, set, and condition
   - Process images to verify condition
   - Determine card value factors

3. **Price Comparison Phase**
   - For each analyzed card, search 130point.com
   - Extract sold prices for different conditions
   - Calculate average prices
   - Determine market value

4. **Profit Calculation Phase**
   - Calculate potential profit for each listing
   - Consider all fees and costs
   - Calculate ROI percentage
   - Flag high-profit opportunities (2x or more)

5. **Selection Phase**
   - Display results sorted by profit potential
   - Allow user to review and select listings
   - Save selected listings to watchlist

6. **Export Phase**
   - Export selected listings to ZenMarket
   - Provide bidding recommendations
   - Track auction status

## New Files to Create

1. `core_engine.py`: Main orchestration module
2. `price_comparator.py`: eBay/130point.com price comparison
3. `profit_calculator.py`: Profit and ROI calculation
4. `bookmark_manager.py`: Auction bookmarking and export
5. `cli.py`: Command-line interface
6. `config.py`: Configuration management
7. `zenmarket_exporter.py`: ZenMarket integration

## Modifications to Existing Files

1. `buyee_scraper.py`: 
   - Add support for filtering by popularity
   - Enhance listing detail extraction
   - Improve error handling

2. `card_analyzer.py`:
   - Enhance condition analysis
   - Add more valuable card definitions

3. `image_analyzer.py`:
   - Improve condition detection accuracy
   - Add support for multiple image analysis

4. `rank_analyzer.py`:
   - Enhance Japanese rank interpretation
   - Improve confidence scoring

## Error Handling and Resilience

The system will implement comprehensive error handling:

1. **Network Errors**:
   - Automatic retry with exponential backoff
   - Session recovery
   - Proxy rotation if needed

2. **Parsing Errors**:
   - Fallback strategies for different page structures
   - Graceful degradation when information is missing

3. **API Limits**:
   - Rate limiting for external APIs
   - Caching of common requests

4. **Browser Detection**:
   - Stealth mode enhancements
   - Browser fingerprint randomization
   - CAPTCHA detection and handling

## Configuration Options

The system will be highly configurable through a `config.py` file:

1. **Search Options**:
   - Search terms
   - Maximum pages to scrape
   - Minimum card value

2. **Analysis Options**:
   - Condition thresholds
   - Value factor weights
   - Image analysis settings

3. **Profit Options**:
   - Minimum profit threshold (default 2x)
   - Fee calculation parameters
   - Currency conversion settings

4. **System Options**:
   - Headless mode
   - Log level
   - Output directory
   - Browser settings

## Implementation Plan

1. **Phase 1: Core Infrastructure**
   - Create core_engine.py
   - Implement configuration management
   - Set up improved logging

2. **Phase 2: Price Comparison**
   - Implement price_comparator.py
   - Enhance eBay/130point.com integration
   - Add currency conversion

3. **Phase 3: Profit Calculation**
   - Implement profit_calculator.py
   - Add fee estimation
   - Implement ROI calculation

4. **Phase 4: Bookmarking System**
   - Implement bookmark_manager.py
   - Add ZenMarket integration
   - Create watchlist management

5. **Phase 5: User Interface**
   - Implement improved CLI
   - Add optional web interface
   - Create result visualization

## Testing Strategy

1. **Unit Testing**:
   - Test each module independently
   - Mock external dependencies

2. **Integration Testing**:
   - Test module interactions
   - Verify workflow execution

3. **End-to-End Testing**:
   - Test complete workflow with real data
   - Verify profit calculations

4. **Performance Testing**:
   - Test with large result sets
   - Optimize bottlenecks

## Conclusion

This design document outlines a comprehensive solution for automating the Yu-Gi-Oh card arbitrage workflow. By implementing the components and workflow described above, the system will be able to efficiently search for cards on Buyee.jp, analyze their condition and value, compare prices with eBay sold listings, calculate potential profit, and facilitate the purchase process through ZenMarket.

The modular architecture ensures that each component can be developed, tested, and maintained independently, while the Core Engine provides seamless integration and workflow management. The system is designed to be resilient to errors and highly configurable to adapt to changing market conditions and user preferences.
