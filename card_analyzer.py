from typing import Dict, List, Optional, Any, Tuple
import re
import logging
from dataclasses import dataclass
from enum import Enum

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

@dataclass
class CardInfo:
    title: str
    price: float
    url: str
    image_url: Optional[str]
    condition: CardCondition
    is_valuable: bool
    rarity: Optional[str]
    set_code: Optional[str]
    card_number: Optional[str]
    edition: Optional[str]
    region: Optional[str]
    confidence_score: float

class CardAnalyzer:
    def __init__(self):
        # Value indicators for card analysis
        self.value_indicators = {
            'rarity': ['secret', 'ultimate', 'collector', 'gold', 'platinum', 'prismatic'],
            'condition': ['mint', 'nm', 'ex', 'vg'],
            'set': ['lob', 'sdj', 'sdy', 'sdk', 'mfc', 'crv', 'rymp']
        }
        
        # Condition keywords in Japanese and English
        self.condition_keywords = {
            CardCondition.MINT: [
                "mint", "mint condition", "mint state",
                "未使用", "新品", "美品", "完全美品",
                "psa 10", "bgs 10", "psa 9.5", "bgs 9.5"
            ],
            CardCondition.NEAR_MINT: [
                "near mint", "nm", "nm-mt", "near mint condition",
                "ほぼ新品", "ほぼ未使用", "極美品", "極上美品"
            ],
            CardCondition.EXCELLENT: [
                "excellent", "ex", "ex-mt", "excellent condition",
                "美品", "上美品", "優良品"
            ],
            CardCondition.VERY_GOOD: [
                "very good", "vg", "vg-ex", "very good condition",
                "良品", "良好品"
            ],
            CardCondition.GOOD: [
                "good", "g", "good condition",
                "並品", "普通品"
            ],
            CardCondition.LIGHT_PLAYED: [
                "light played", "lp", "lightly played",
                "やや傷あり", "軽い傷あり"
            ],
            CardCondition.PLAYED: [
                "played", "p", "played condition",
                "傷あり", "使用感あり"
            ],
            CardCondition.POOR: [
                "poor", "damaged", "heavily played", "hp",
                "傷みあり", "破損あり", "状態悪い"
            ]
        }
        
        # Rarity keywords in Japanese and English
        self.rarity_keywords = {
            "Secret Rare": ["secret rare", "シークレットレア", "sr"],
            "Ultimate Rare": ["ultimate rare", "アルティメットレア", "ur"],
            "Ghost Rare": ["ghost rare", "ゴーストレア", "gr"],
            "Collector's Rare": ["collector's rare", "コレクターズレア", "cr"],
            "Starlight Rare": ["starlight rare", "スターライトレア", "str"],
            "Quarter Century Secret Rare": ["quarter century secret rare", "クォーターセンチュリーシークレットレア", "qcsr"],
            "Prismatic Secret Rare": ["prismatic secret rare", "プリズマティックシークレットレア", "psr"],
            "Platinum Secret Rare": ["platinum secret rare", "プラチナシークレットレア", "plsr"],
            "Gold Secret Rare": ["gold secret rare", "ゴールドシークレットレア", "gsr"],
            "Ultra Rare": ["ultra rare", "ウルトラレア", "ur"],
            "Super Rare": ["super rare", "スーパーレア", "sr"],
            "Rare": ["rare", "レア", "r"],
            "Common": ["common", "ノーマル", "n"]
        }
        
        # Known valuable cards with their set codes
        self.valuable_cards = {
            "Blue-Eyes White Dragon": ["LOB", "SDK", "SKE", "YAP1"],
            "Dark Magician": ["LOB", "SDY", "YAP1", "MVP1"],
            "Dark Magician Girl": ["MFC", "MVP1", "YAP1"],
            "Red-Eyes Black Dragon": ["LOB", "SDJ", "YAP1"],
            "Exodia the Forbidden One": ["LOB"],
            "Right Arm of the Forbidden One": ["LOB"],
            "Left Arm of the Forbidden One": ["LOB"],
            "Right Leg of the Forbidden One": ["LOB"],
            "Left Leg of the Forbidden One": ["LOB"],
            "Pot of Greed": ["LOB", "SRL", "DB1"],
            "Mirror Force": ["MRD", "DCR", "DB1"],
            "Monster Reborn": ["LOB", "SRL", "DB1"],
            "Raigeki": ["LOB", "SRL", "DB1"],
            "Harpie's Feather Duster": ["TP8", "SRL", "DB1"],
            "Change of Heart": ["MRD", "SRL", "DB1"],
            "Imperial Order": ["PSV", "SRL", "DB1"],
            "Crush Card Virus": ["DR1", "DPKB"],
            "Cyber Dragon": ["CRV", "RYMP"],
            "Elemental HERO Stratos": ["DP03", "RYMP"],
            "Judgment Dragon": ["LODT", "RYMP"],
            "Black Luster Soldier - Envoy of the Beginning": ["IOC", "RYMP"],
            "Chaos Emperor Dragon - Envoy of the End": ["IOC", "RYMP"],
            "Cyber-Stein": ["CRV", "RYMP"],
            "Dark Armed Dragon": ["PTDN", "RYMP"],
            "Destiny HERO - Disk Commander": ["DP05", "RYMP"],
            "Elemental HERO Air Neos": ["POTD", "RYMP"],
            "Elemental HERO Stratos": ["DP03", "RYMP"],
            "Gladiator Beast Gyzarus": ["GLAS", "RYMP"],
            "Goyo Guardian": ["TDGS", "RYMP"],
            "Honest": ["LODT", "RYMP"],
            "Judgment Dragon": ["LODT", "RYMP"],
            "Mezuki": ["CSOC", "RYMP"],
            "Plaguespreader Zombie": ["CSOC", "RYMP"],
            "Stardust Dragon": ["TDGS", "RYMP"],
            "Thought Ruler Archfiend": ["TDGS", "RYMP"]
        }
        
        # Set code patterns
        self.set_code_pattern = re.compile(r'([A-Z]{2,4})-([A-Z]{2})(\d{3})')
        
        # Edition keywords
        self.edition_keywords = {
            "1st Edition": ["1st", "first edition", "初版", "初刷"],
            "Unlimited": ["unlimited", "無制限", "再版", "再刷"]
        }
        
        # Region keywords
        self.region_keywords = {
            "Asia": ["asia", "asian", "アジア", "アジア版"],
            "English": ["english", "英", "英語版"],
            "Japanese": ["japanese", "日", "日本語版"],
            "Korean": ["korean", "韓", "韓国版"]
        }

    def analyze_card(self, item_data: Dict[str, Any]) -> CardInfo:
        """Analyze a card listing and return detailed information."""
        title = item_data.get('title', '').lower()
        price = self._extract_price(item_data.get('price', '0'))
        
        # Extract condition
        condition = self._determine_condition(title)
        
        # Extract rarity
        rarity = self._determine_rarity(title)
        
        # Extract set code and card number
        set_code, card_number = self._extract_set_info(title)
        
        # Extract edition
        edition = self._determine_edition(title)
        
        # Extract region
        region = self._determine_region(title)
        
        # Check if card is valuable
        is_valuable = self._is_valuable_card(title, set_code)
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(
            condition, rarity, set_code, card_number, edition, region
        )
        
        return CardInfo(
            title=item_data.get('title', ''),
            price=price,
            url=item_data.get('url', ''),
            image_url=item_data.get('image_url'),
            condition=condition,
            is_valuable=is_valuable,
            rarity=rarity,
            set_code=set_code,
            card_number=card_number,
            edition=edition,
            region=region,
            confidence_score=confidence_score
        )

    def _extract_price(self, price_text: str) -> float:
        """Extract numeric price from text."""
        try:
            # Remove currency symbols and commas
            cleaned = re.sub(r'[^\d.]', '', price_text)
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0

    def _determine_condition(self, title: str) -> CardCondition:
        """Determine card condition from title."""
        for condition, keywords in self.condition_keywords.items():
            if any(keyword.lower() in title.lower() for keyword in keywords):
                return condition
        return CardCondition.UNKNOWN

    def _determine_rarity(self, title: str) -> Optional[str]:
        """Determine card rarity from title."""
        for rarity, keywords in self.rarity_keywords.items():
            if any(keyword.lower() in title.lower() for keyword in keywords):
                return rarity
        return None

    def _extract_set_info(self, title: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract set code and card number from title."""
        match = self.set_code_pattern.search(title)
        if match:
            return match.group(1), match.group(3)
        return None, None

    def _determine_edition(self, title: str) -> Optional[str]:
        """Determine card edition from title."""
        for edition, keywords in self.edition_keywords.items():
            if any(keyword.lower() in title.lower() for keyword in keywords):
                return edition
        return None

    def _determine_region(self, title: str) -> Optional[str]:
        """Determine card region from title."""
        for region, keywords in self.region_keywords.items():
            if any(keyword.lower() in title.lower() for keyword in keywords):
                return region
        return None

    def _is_valuable_card(self, title: str, set_code: Optional[str]) -> bool:
        """Check if the card is valuable based on name and set code."""
        title_lower = title.lower()
        
        # Log the analysis process
        logger.debug(f"Analyzing card value for: {title}")
        
        # Check against known valuable cards
        for card_name, valid_sets in self.valuable_cards.items():
            if card_name.lower() in title_lower:
                if set_code is None or set_code in valid_sets:
                    logger.debug(f"Card matched valuable card list: {card_name}")
                    return True
        
        # Check for high rarity
        high_rarities = ["Secret Rare", "Ultimate Rare", "Ghost Rare", "Collector's Rare", "Starlight Rare"]
        for rarity in high_rarities:
            if rarity.lower() in title_lower:
                logger.debug(f"Card has high rarity: {rarity}")
                return True
        
        # Check for 1st Edition
        if any(keyword in title_lower for keyword in ["1st", "first edition", "初版", "初刷"]):
            logger.debug("Card is 1st Edition")
            return True
            
        # Check for sealed/unopened products
        if any(keyword in title_lower for keyword in ["sealed", "未開封", "新品未開封"]):
            logger.debug("Card is sealed/unopened")
            return True
            
        # Check for tournament/event items
        if any(keyword in title_lower for keyword in ["tournament", "event", "championship", "大会", "イベント"]):
            logger.debug("Card is from tournament/event")
            return True
            
        # Check for special editions
        if any(keyword in title_lower for keyword in ["special", "limited", "promo", "限定", "特典"]):
            logger.debug("Card is special/limited edition")
            return True
        
        logger.debug("Card did not meet any value criteria")
        return False

    def _calculate_confidence_score(self, condition: CardCondition, rarity: Optional[str],
                                  set_code: Optional[str], card_number: Optional[str],
                                  edition: Optional[str], region: Optional[str]) -> float:
        """Calculate confidence score for the card analysis."""
        score = 0.0
        
        # Condition score
        if condition != CardCondition.UNKNOWN:
            score += 0.3
        
        # Rarity score
        if rarity:
            score += 0.2
        
        # Set code and card number score
        if set_code and card_number:
            score += 0.2
        
        # Edition score
        if edition:
            score += 0.15
        
        # Region score
        if region:
            score += 0.15
        
        return score 