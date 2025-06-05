# Yu-Gi-Oh Card Arbitrage Bot - User Guide

## Overview

The Yu-Gi-Oh Card Arbitrage Bot automates the process of finding profitable Yu-Gi-Oh cards on Buyee.jp, comparing them with eBay sold prices, and facilitating the purchase process through ZenMarket. This guide explains how to use the bot and its various features.

## Installation

1. Clone the repository or extract the files to your desired location
2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your API keys (if using image analysis):
```
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key
```

## Configuration

Before using the bot, you should configure it with your preferences:

```bash
python cli.py config --update-rates --jpy-to-usd 0.0067
```

If you plan to export auctions to ZenMarket, set your credentials:

```bash
python cli.py config --set-zenmarket --email your_email@example.com --password your_password
```

## Basic Usage

### Searching for Cards

To search for Yu-Gi-Oh cards on Buyee:

```bash
python cli.py search --terms "遊戯王 アジア" "遊戯王 英語" --max-pages 3 --min-profit 2.0
```

This will:
1. Search for the specified terms on Buyee
2. Filter by popularity
3. Analyze card conditions
4. Compare with eBay sold prices
5. Calculate profit potential
6. Save profitable listings (with ROI >= 2.0)

### Viewing Your Watchlist

To view your saved auctions:

```bash
python cli.py watchlist
```

To view details for a specific auction:

```bash
python cli.py watchlist --list-id x123456789
```

### Exporting to ZenMarket

To export all bookmarked auctions to ZenMarket:

```bash
python cli.py export --export-all
```

To export specific auctions:

```bash
python cli.py export --export-ids x123456789 y987654321
```

## Advanced Usage

### Custom Output Directory

```bash
python cli.py search --output-dir my_results
```

### Including Grading Costs

```bash
python cli.py search --include-grading
```

### Non-Headless Mode

```bash
python cli.py search --headless false
```

## Command Reference

### Search Command

```
python cli.py search [options]
```

Options:
- `--terms`: Search terms to use
- `--max-pages`: Maximum pages to scrape per search (default: 5)
- `--max-listings`: Maximum listings to analyze per search term (default: 20)
- `--min-profit`: Minimum profit ratio threshold (default: 2.0)
- `--include-grading`: Include grading costs in profit calculation
- `--output-dir`: Output directory for results (default: results)
- `--headless`: Run browser in headless mode (default: true)

### Watchlist Command

```
python cli.py watchlist [options]
```

Options:
- `--list-id`: Specific auction ID to view details
- `--output-dir`: Output directory (default: results)

### Export Command

```
python cli.py export [options]
```

Options:
- `--export-ids`: Auction IDs to export to ZenMarket
- `--export-all`: Export all bookmarked auctions to ZenMarket
- `--output-dir`: Output directory (default: results)

### Config Command

```
python cli.py config [options]
```

Options:
- `--set-zenmarket`: Set ZenMarket credentials
- `--email`: ZenMarket email
- `--password`: ZenMarket password
- `--update-rates`: Update currency conversion rates
- `--jpy-to-usd`: JPY to USD conversion rate

## Workflow Explanation

The bot follows this workflow:

1. **Search Phase**: Searches Buyee for Yu-Gi-Oh cards using specified terms
2. **Analysis Phase**: Analyzes card details, condition, and value
3. **Price Comparison Phase**: Compares with eBay sold prices via 130point.com
4. **Profit Calculation Phase**: Calculates potential profit and ROI
5. **Selection Phase**: Identifies high-profit opportunities (2x or more)
6. **Export Phase**: Exports selected listings to ZenMarket for bidding

## Troubleshooting

### Browser Issues

If you encounter browser-related issues:
- Try running in non-headless mode: `--headless false`
- Check that Chrome is installed and up to date
- Verify that chromedriver is compatible with your Chrome version

### API Key Issues

If image analysis is not working:
- Check that your API keys are correctly set in the `.env` file
- Verify that you have sufficient credits on your API accounts

### ZenMarket Export Issues

If exporting to ZenMarket fails:
- Verify your credentials are correct
- Check that the auction is still active
- Try running in non-headless mode to see the browser actions

## File Structure

```
.
├── core_engine.py          # Main orchestration module
├── buyee_scraper.py        # Buyee.jp scraping functionality
├── card_analyzer.py        # Card analysis logic
├── image_analyzer.py       # Image processing and analysis
├── rank_analyzer.py        # Card ranking analysis
├── text_analyzer.py        # Text analysis for card details
├── price_comparator.py     # eBay/130point.com price comparison
├── profit_calculator.py    # Profit and ROI calculation
├── bookmark_manager.py     # Auction bookmarking and export
├── cli.py                  # Command-line interface
├── search_terms.py         # Search term definitions
├── scraper_utils.py        # Utility functions
├── requirements.txt        # Project dependencies
├── .env                    # Environment variables
└── results/                # Directory for scraped data
```

## Next Steps

To further enhance the bot, consider:
1. Adding a web interface for easier interaction
2. Implementing automatic bidding on ZenMarket
3. Adding more detailed card condition analysis
4. Expanding to other trading card games
5. Creating alerts for especially profitable cards

## Support

For issues or questions, please refer to the documentation or create an issue on the repository.
