from enum import Enum
from typing import Optional, Dict, Any
import re
import logging

logger = logging.getLogger(__name__)

class CardCondition(Enum):
    MINT = "Mint"
    NEAR_MINT = "Near Mint"
    EXCELLENT = "Excellent"
    VERY_GOOD = "Very Good"
    GOOD = "Good"
    LIGHT_PLAYED = "Light Played"
    PLAYED = "Played"
    POOR = "Poor"
    UNKNOWN = "Unknown"

class RankAnalyzer:
    def __init__(self):
        # Japanese rank to condition mapping
        self.rank_to_condition = {
            'SS': CardCondition.MINT,
            'S': CardCondition.MINT,
            'A': CardCondition.NEAR_MINT,
            'B+': CardCondition.EXCELLENT,
            'B': CardCondition.VERY_GOOD,
            'C': CardCondition.GOOD,
            'D': CardCondition.LIGHT_PLAYED,
            'E': CardCondition.PLAYED
        }
        
        # Common Japanese condition descriptions
        self.condition_keywords = {
            CardCondition.MINT: [
                "完全美品", "新品同様", "未使用", "新品", "美品",
                "傷なし", "汚れなし", "折れなし", "破れなし",
                "完全無傷", "完全新品", "完全新品同様"
            ],
            CardCondition.NEAR_MINT: [
                "ほぼ新品", "ほぼ未使用", "極美品", "極上美品",
                "微傷", "微汚れ", "微折れ", "微破れ",
                "ほぼ完全美品", "ほぼ完全新品"
            ],
            CardCondition.EXCELLENT: [
                "美品", "上美品", "優良品", "良好品",
                "軽微な傷", "軽微な汚れ", "軽微な折れ", "軽微な破れ"
            ],
            CardCondition.VERY_GOOD: [
                "良品", "良好品", "並良品",
                "小傷あり", "小汚れあり", "小折れあり", "小破れあり"
            ],
            CardCondition.GOOD: [
                "並品", "普通品",
                "傷あり", "汚れあり", "折れあり", "破れあり"
            ],
            CardCondition.LIGHT_PLAYED: [
                "やや傷あり", "やや汚れあり", "やや折れあり", "やや破れあり",
                "使用感あり", "経年変化あり"
            ],
            CardCondition.PLAYED: [
                "傷あり", "汚れあり", "折れあり", "破れあり",
                "使用感強め", "経年変化強め"
            ],
            CardCondition.POOR: [
                "傷みあり", "破損あり", "状態悪い",
                "大きな傷", "大きな汚れ", "大きな折れ", "大きな破れ"
            ]
        }
        
        # Rank description patterns
        self.rank_patterns = [
            r'【ランク】([A-Z+]+)',  # Standard rank format
            r'ランク[：:]\s*([A-Z+]+)',  # Alternative format with colon
            r'状態[：:]\s*([A-Z+]+)',  # State format
            r'グレード[：:]\s*([A-Z+]+)'  # Grade format
        ]

    def parse_rank(self, description: str) -> Optional[str]:
        """
        Parse the rank from the item description.
        Returns the rank (e.g., 'A', 'B+', 'S') if found, None otherwise.
        """
        if not description:
            return None
            
        description = description.lower()
        
        # Try each rank pattern
        for pattern in self.rank_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                rank = match.group(1).upper()
                # Validate the rank
                if rank in self.rank_to_condition:
                    return rank
                # Handle special cases
                if rank == 'A+':
                    return 'A'
                if rank == 'B++':
                    return 'B+'
        
        return None

    def get_condition_from_rank(self, rank: str) -> CardCondition:
        """
        Convert a rank to a card condition.
        Returns CardCondition.UNKNOWN if the rank is not recognized.
        """
        return self.rank_to_condition.get(rank.upper(), CardCondition.UNKNOWN)

    def analyze_condition(self, description: str, seller_condition: str) -> Dict[str, Any]:
        """
        Analyze the condition based on both the rank and seller's condition description.
        Returns a dictionary with the analysis results.
        """
        result = {
            'rank': None,
            'condition': CardCondition.UNKNOWN,
            'confidence': 0.0,
            'condition_indicators': [],
            'warnings': []
        }
        
        # Parse rank
        rank = self.parse_rank(description)
        if rank:
            result['rank'] = rank
            result['condition'] = self.get_condition_from_rank(rank)
            result['confidence'] += 0.6  # Rank provides strong confidence
            result['condition_indicators'].append(f"Rank {rank}")
        
        # Analyze seller's condition description
        if seller_condition:
            seller_condition = seller_condition.lower()
            found_indicators = []
            
            # Check for condition keywords
            for condition, keywords in self.condition_keywords.items():
                for keyword in keywords:
                    if keyword in seller_condition:
                        found_indicators.append(keyword)
                        # If we haven't found a condition from rank, use this
                        if result['condition'] == CardCondition.UNKNOWN:
                            result['condition'] = condition
                            result['confidence'] += 0.4
                        # If we have a condition from rank, check for consistency
                        elif condition != result['condition']:
                            result['warnings'].append(
                                f"Condition mismatch: Rank suggests {result['condition'].value}, "
                                f"but description suggests {condition.value}"
                            )
            
            if found_indicators:
                result['condition_indicators'].extend(found_indicators)
            else:
                result['warnings'].append("No specific condition indicators found in seller's description")
        
        # Normalize confidence score
        result['confidence'] = min(result['confidence'], 1.0)
        
        return result

    def is_good_condition(self, condition: CardCondition) -> bool:
        """
        Check if the condition is considered good for valuable cards.
        """
        return condition in [
            CardCondition.MINT,
            CardCondition.NEAR_MINT,
            CardCondition.EXCELLENT
        ] 