"""
Profit Calculator for Yu-Gi-Oh Card Arbitrage Bot

This module handles calculating potential profit margins for Yu-Gi-Oh cards
by comparing Buyee prices with eBay sold prices and accounting for all fees.
"""

import logging
from typing import Dict, Any, Optional

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

class ProfitCalculator:
    """
    Handles calculating potential profit margins for Yu-Gi-Oh cards.
    """
    
    def __init__(self, currency_conversion: Dict[str, float] = None):
        """
        Initialize the ProfitCalculator.
        
        Args:
            currency_conversion (Dict[str, float], optional): Currency conversion rates. Defaults to None.
        """
        # Default currency conversion rates
        self.currency_conversion = {
            'JPY_to_USD': 0.0067,  # Example rate, should be updated dynamically
            'USD_to_JPY': 149.25
        }
        
        # Update with provided rates
        if currency_conversion:
            self.currency_conversion.update(currency_conversion)
        
        # Fee structure
        self.fees = {
            'buyee': {
                'service_fee_percent': 0.05,  # 5% service fee
                'payment_fee_percent': 0.035,  # 3.5% payment processing fee
                'shipping_domestic': 500,  # JPY, domestic shipping in Japan
                'consolidation': 1000,  # JPY, package consolidation fee
                'international_shipping': 2500  # JPY, international shipping (estimate)
            },
            'ebay': {
                'selling_fee_percent': 0.125,  # 12.5% selling fee
                'payment_fee_percent': 0.03,  # 3% payment processing fee
                'payment_fee_fixed': 0.30  # $0.30 fixed fee per transaction
            },
            'paypal': {
                'fee_percent': 0.029,  # 2.9% fee
                'fixed_fee': 0.30  # $0.30 fixed fee
            },
            'grading': {
                'psa_standard': 50,  # USD, PSA standard service
                'psa_express': 150,  # USD, PSA express service
                'bgs_standard': 35,  # USD, BGS standard service
                'bgs_express': 125  # USD, BGS express service
            }
        }
        
        logger.info("ProfitCalculator initialized with currency conversion rates: %s", self.currency_conversion)
    
    def calculate_profit(self, buyee_price: float, ebay_price: float, 
                        include_grading: bool = False, grading_service: str = None) -> Dict[str, Any]:
        """
        Calculate profit potential for a card.
        
        Args:
            buyee_price (float): Price on Buyee in JPY.
            ebay_price (float): Sold price on eBay in USD.
            include_grading (bool, optional): Whether to include grading costs. Defaults to False.
            grading_service (str, optional): Grading service to use. Defaults to None.
        
        Returns:
            Dict[str, Any]: Profit analysis.
        """
        try:
            # Convert Buyee price to USD
            buyee_price_usd = buyee_price * self.currency_conversion['JPY_to_USD']
            
            # Calculate Buyee fees
            buyee_service_fee = buyee_price * self.fees['buyee']['service_fee_percent']
            buyee_payment_fee = buyee_price * self.fees['buyee']['payment_fee_percent']
            
            # Calculate shipping and handling fees (in JPY)
            shipping_fees_jpy = (
                self.fees['buyee']['shipping_domestic'] + 
                self.fees['buyee']['consolidation'] + 
                self.fees['buyee']['international_shipping']
            )
            
            # Convert shipping fees to USD
            shipping_fees_usd = shipping_fees_jpy * self.currency_conversion['JPY_to_USD']
            
            # Calculate total cost in USD
            total_cost_usd = buyee_price_usd + (buyee_service_fee + buyee_payment_fee) * self.currency_conversion['JPY_to_USD'] + shipping_fees_usd
            
            # Add grading costs if applicable
            grading_cost = 0
            if include_grading:
                if grading_service == 'psa_standard':
                    grading_cost = self.fees['grading']['psa_standard']
                elif grading_service == 'psa_express':
                    grading_cost = self.fees['grading']['psa_express']
                elif grading_service == 'bgs_standard':
                    grading_cost = self.fees['grading']['bgs_standard']
                elif grading_service == 'bgs_express':
                    grading_cost = self.fees['grading']['bgs_express']
                else:
                    # Default to PSA standard
                    grading_cost = self.fees['grading']['psa_standard']
                
                total_cost_usd += grading_cost
            
            # Calculate eBay selling fees
            ebay_selling_fee = ebay_price * self.fees['ebay']['selling_fee_percent']
            ebay_payment_fee = ebay_price * self.fees['ebay']['payment_fee_percent'] + self.fees['ebay']['payment_fee_fixed']
            
            # Calculate net revenue from eBay sale
            net_revenue_usd = ebay_price - ebay_selling_fee - ebay_payment_fee
            
            # Calculate profit
            profit_usd = net_revenue_usd - total_cost_usd
            
            # Calculate ROI (Return on Investment)
            roi = net_revenue_usd / total_cost_usd if total_cost_usd > 0 else 0
            
            # Calculate profit margin percentage
            profit_margin = (profit_usd / ebay_price) * 100 if ebay_price > 0 else 0
            
            # Prepare detailed analysis
            analysis = {
                'buyee_price_jpy': buyee_price,
                'buyee_price_usd': buyee_price_usd,
                'buyee_fees_jpy': buyee_service_fee + buyee_payment_fee,
                'buyee_fees_usd': (buyee_service_fee + buyee_payment_fee) * self.currency_conversion['JPY_to_USD'],
                'shipping_fees_jpy': shipping_fees_jpy,
                'shipping_fees_usd': shipping_fees_usd,
                'grading_cost_usd': grading_cost,
                'total_cost_usd': total_cost_usd,
                'ebay_price': ebay_price,
                'ebay_fees': ebay_selling_fee + ebay_payment_fee,
                'net_revenue_usd': net_revenue_usd,
                'profit': profit_usd,
                'roi': roi,
                'profit_margin': profit_margin,
                'is_profitable': profit_usd > 0,
                'meets_threshold': roi >= 2.0  # 2x ROI threshold
            }
            
            logger.info("Profit analysis: Buyee ¥%.2f (%.2f USD) → eBay $%.2f, Profit: $%.2f, ROI: %.2fx", 
                       buyee_price, buyee_price_usd, ebay_price, profit_usd, roi)
            
            return analysis
            
        except Exception as e:
            logger.error("Error calculating profit: %s", str(e), exc_info=True)
            return {
                'error': str(e),
                'is_profitable': False,
                'meets_threshold': False
            }
    
    def update_currency_rates(self, rates: Dict[str, float]) -> None:
        """
        Update currency conversion rates.
        
        Args:
            rates (Dict[str, float]): New currency conversion rates.
        """
        self.currency_conversion.update(rates)
        logger.info("Updated currency conversion rates: %s", self.currency_conversion)
    
    def estimate_grading_roi(self, raw_price: float, graded_price: float, 
                           grading_service: str = 'psa_standard') -> Dict[str, Any]:
        """
        Estimate ROI for grading a card.
        
        Args:
            raw_price (float): Price of raw card in USD.
            graded_price (float): Price of graded card in USD.
            grading_service (str, optional): Grading service to use. Defaults to 'psa_standard'.
        
        Returns:
            Dict[str, Any]: Grading ROI analysis.
        """
        try:
            # Get grading cost
            grading_cost = 0
            if grading_service == 'psa_standard':
                grading_cost = self.fees['grading']['psa_standard']
            elif grading_service == 'psa_express':
                grading_cost = self.fees['grading']['psa_express']
            elif grading_service == 'bgs_standard':
                grading_cost = self.fees['grading']['bgs_standard']
            elif grading_service == 'bgs_express':
                grading_cost = self.fees['grading']['bgs_express']
            else:
                # Default to PSA standard
                grading_cost = self.fees['grading']['psa_standard']
            
            # Calculate eBay selling fees for graded card
            ebay_selling_fee = graded_price * self.fees['ebay']['selling_fee_percent']
            ebay_payment_fee = graded_price * self.fees['ebay']['payment_fee_percent'] + self.fees['ebay']['payment_fee_fixed']
            
            # Calculate net revenue from graded card sale
            net_revenue_usd = graded_price - ebay_selling_fee - ebay_payment_fee
            
            # Calculate total cost (raw card + grading)
            total_cost_usd = raw_price + grading_cost
            
            # Calculate profit
            profit_usd = net_revenue_usd - total_cost_usd
            
            # Calculate ROI
            roi = net_revenue_usd / total_cost_usd if total_cost_usd > 0 else 0
            
            # Prepare analysis
            analysis = {
                'raw_price': raw_price,
                'graded_price': graded_price,
                'grading_cost': grading_cost,
                'grading_service': grading_service,
                'ebay_fees': ebay_selling_fee + ebay_payment_fee,
                'net_revenue': net_revenue_usd,
                'total_cost': total_cost_usd,
                'profit': profit_usd,
                'roi': roi,
                'is_profitable': profit_usd > 0,
                'worth_grading': roi >= 1.5  # 1.5x ROI threshold for grading
            }
            
            logger.info("Grading ROI analysis: Raw $%.2f + Grading $%.2f → Graded $%.2f, Profit: $%.2f, ROI: %.2fx", 
                       raw_price, grading_cost, graded_price, profit_usd, roi)
            
            return analysis
            
        except Exception as e:
            logger.error("Error calculating grading ROI: %s", str(e), exc_info=True)
            return {
                'error': str(e),
                'is_profitable': False,
                'worth_grading': False
            }

# Example usage
if __name__ == "__main__":
    # Initialize ProfitCalculator
    calculator = ProfitCalculator()
    
    # Example calculation
    buyee_price = 5000  # JPY
    ebay_price = 100  # USD
    
    # Calculate profit
    profit_analysis = calculator.calculate_profit(buyee_price, ebay_price)
    
    # Print results
    print("\nProfit Analysis:")
    print(f"Buyee Price: ¥{buyee_price} ({profit_analysis['buyee_price_usd']:.2f} USD)")
    print(f"eBay Price: ${ebay_price}")
    print(f"Total Cost: ${profit_analysis['total_cost_usd']:.2f}")
    print(f"Net Revenue: ${profit_analysis['net_revenue_usd']:.2f}")
    print(f"Profit: ${profit_analysis['profit']:.2f}")
    print(f"ROI: {profit_analysis['roi']:.2f}x")
    print(f"Profitable: {profit_analysis['is_profitable']}")
    print(f"Meets 2x Threshold: {profit_analysis['meets_threshold']}")
    
    # Example grading ROI calculation
    raw_price = 50  # USD
    graded_price = 200  # USD
    
    # Calculate grading ROI
    grading_analysis = calculator.estimate_grading_roi(raw_price, graded_price)
    
    # Print results
    print("\nGrading ROI Analysis:")
    print(f"Raw Price: ${raw_price}")
    print(f"Graded Price: ${graded_price}")
    print(f"Grading Cost: ${grading_analysis['grading_cost']}")
    print(f"Total Cost: ${grading_analysis['total_cost']:.2f}")
    print(f"Net Revenue: ${grading_analysis['net_revenue']:.2f}")
    print(f"Profit: ${grading_analysis['profit']:.2f}")
    print(f"ROI: {grading_analysis['roi']:.2f}x")
    print(f"Worth Grading: {grading_analysis['worth_grading']}")
