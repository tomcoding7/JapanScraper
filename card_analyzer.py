from typing import Dict, List, Optional, Any, Tuple
import re
import logging
from dataclasses import dataclass
from enum import Enum
import os
from openai import OpenAI
from dotenv import load_dotenv
import json

logger = logging.getLogger(__name__)

class CardCondition(Enum):
    MINT = "Mint"
    NEAR_MINT = "Near Mint"
    EXCELLENT = "Excellent"
    VERY_GOOD = "Very Good"
    GOOD = "Good"
    LIGHT_PLAYED = "Light Played"
    PLAYED = "Played"
    HEAVILY_PLAYED = "Heavily Played"
    DAMAGED = "Damaged"
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
    matched_keywords: List[str] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    estimated_value: Optional[Dict[str, float]] = None
    profit_potential: Optional[float] = None
    recommendation: Optional[str] = None

class CardAnalyzer:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Initialize OpenAI client if API key is available
        self.openai_client = None
        if os.getenv('OPENAI_API_KEY'):
            self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
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
            CardCondition.HEAVILY_PLAYED: [
                "heavily played", "hp", "heavily played condition",
                "重度使用", "重度傷あり"
            ],
            CardCondition.DAMAGED: [
                "damaged", "damaged condition",
                "破損", "損傷", "状態悪い"
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

    def analyze_card(self, item_data: Dict[str, Any], rank_analysis_results: Optional[Dict] = None, llm_analysis: Optional[Dict] = None) -> CardInfo:
        """
        Analyze a card listing using both rule-based and AI analysis.
        
        Args:
            item_data: Dictionary containing card information (title, description, price, etc.)
            rank_analysis_results: Optional results from RankAnalyzer
            llm_analysis: Optional results from previous LLM analysis
            
        Returns:
            CardInfo object with analysis results
        """
        try:
            title = item_data.get('title', '')
            description = item_data.get('description', '')
            price = self._extract_price(item_data.get('price', '0'))
            url = item_data.get('url', '')
            image_url = item_data.get('image_url')
            
            # Initialize CardInfo with basic information
            card_info = CardInfo(
                title=title,
                price=price,
                url=url,
                image_url=image_url,
                condition=CardCondition.UNKNOWN,
                is_valuable=False,
                rarity=None,
                set_code=None,
                card_number=None,
                edition=None,
                region=None,
                confidence_score=0.0,
                matched_keywords=[],
                ai_analysis={},
                estimated_value={'min': 0.0, 'max': 0.0},
                profit_potential=0.0,
                recommendation=""
            )
            
            # 1. Basic Text Analysis
            title_lower = title.lower()
            description_lower = description.lower() if description else ""
            
            # Extract condition
            card_info.condition = self._determine_condition(title_lower + " " + description_lower)
            
            # Extract rarity
            card_info.rarity = self._determine_rarity(title_lower + " " + description_lower)
            
            # Extract set code and card number
            card_info.set_code, card_info.card_number = self._extract_set_info(title_lower + " " + description_lower)
            
            # Extract edition
            card_info.edition = self._determine_edition(title_lower + " " + description_lower)
            
            # Extract region
            card_info.region = self._determine_region(title_lower + " " + description_lower)
            
            # Check if card is valuable
            card_info.is_valuable = self._is_valuable_card(title_lower, card_info.set_code)
            
            # 2. AI Analysis (if OpenAI client is available)
            if self.openai_client:
                try:
                    ai_analysis = self._perform_ai_analysis(title, description, price)
                    card_info.ai_analysis = ai_analysis
                    
                    # Update card info based on AI analysis
                    if 'value_assessment' in ai_analysis:
                        card_info.estimated_value = {
                            'min': ai_analysis['value_assessment']['min_value'],
                            'max': ai_analysis['value_assessment']['max_value']
                        }
                    
                    if 'profit_potential' in ai_analysis:
                        card_info.profit_potential = ai_analysis['profit_potential']['estimated_profit']
                    
                    if 'recommendation' in ai_analysis:
                        card_info.recommendation = f"{ai_analysis['recommendation']['action']}: {ai_analysis['recommendation']['reasoning']}"
                    
                    # Update confidence score
                    if 'value_assessment' in ai_analysis and 'confidence' in ai_analysis['value_assessment']:
                        card_info.confidence_score = ai_analysis['value_assessment']['confidence']
                    
                except Exception as e:
                    logger.error(f"Error in AI analysis: {str(e)}")
            
            # Calculate final confidence score
            card_info.confidence_score = self._calculate_confidence_score(
                card_info.condition,
                card_info.rarity,
                card_info.set_code,
                card_info.card_number,
                card_info.edition,
                card_info.region
            )
            
            return card_info
            
        except Exception as e:
            logger.error(f"Error analyzing card: {str(e)}")
            raise

    def _extract_price(self, price_text: str) -> float:
        """Extract numeric price from text."""
        try:
            # Remove currency symbols and commas
            cleaned = re.sub(r'[^\d.]', '', price_text)
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0

    def _determine_condition(self, text: str) -> CardCondition:
        """Determine card condition from text."""
        for condition, keywords in self.condition_keywords.items():
            if any(keyword.lower() in text.lower() for keyword in keywords):
                return condition
        return CardCondition.UNKNOWN

    def _determine_rarity(self, text: str) -> Optional[str]:
        """Determine card rarity from text."""
        for rarity, keywords in self.rarity_keywords.items():
            if any(keyword.lower() in text.lower() for keyword in keywords):
                return rarity
        return None

    def _extract_set_info(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract set code and card number from text."""
        match = self.set_code_pattern.search(text)
        if match:
            return match.group(1), match.group(3)
        return None, None

    def _determine_edition(self, text: str) -> Optional[str]:
        """Determine card edition from text."""
        for edition, keywords in self.edition_keywords.items():
            if any(keyword.lower() in text.lower() for keyword in keywords):
                return edition
        return None

    def _determine_region(self, text: str) -> Optional[str]:
        """Determine card region from text."""
        for region, keywords in self.region_keywords.items():
            if any(keyword.lower() in text.lower() for keyword in keywords):
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
                if not set_code or set_code in valid_sets:
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
        """Calculate confidence score based on available information."""
        score = 0.0
        total_factors = 0
        
        # Condition confidence
        if condition != CardCondition.UNKNOWN:
            score += 1.0
        total_factors += 1
        
        # Rarity confidence
        if rarity:
            score += 1.0
        total_factors += 1
        
        # Set code confidence
        if set_code:
            score += 1.0
        total_factors += 1
        
        # Card number confidence
        if card_number:
            score += 1.0
        total_factors += 1
        
        # Edition confidence
        if edition:
            score += 1.0
        total_factors += 1
        
        # Region confidence
        if region:
            score += 1.0
        total_factors += 1
        
        return score / total_factors if total_factors > 0 else 0.0

    def _perform_ai_analysis(self, title: str, description: str, price: float) -> Dict[str, Any]:
        """Perform AI analysis using OpenAI API."""
        if not self.openai_client:
            return {}
        
        try:
            # Prepare analysis prompt
            analysis_prompt = f"""
            Analyze this Yu-Gi-Oh! card listing:
            Title: {title}
            Description: {description}
            Current Price: ¥{price}
            
            Please provide a detailed analysis including:
            1. Card identification (name, set, number if visible)
            2. Condition assessment
            3. Authenticity check
            4. Value assessment based on recent eBay sales
            5. Profit potential analysis
            6. Recommendation (Buy/Pass)
            
            Format your response as JSON with these keys:
            {{
                "card_name": "string",
                "set_code": "string",
                "card_number": "string",
                "condition": "string",
                "authenticity": "string",
                "value_assessment": {{
                    "min_value": float,
                    "max_value": float,
                    "confidence": float
                }},
                "profit_potential": {{
                    "estimated_profit": float,
                    "risk_level": "string",
                    "confidence": float
                }},
                "recommendation": {{
                    "action": "string",
                    "reasoning": "string",
                    "confidence": float
                }}
            }}
            """
            
            # Call OpenAI API
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Yu-Gi-Oh! card evaluator with deep knowledge of card values, conditions, and market trends."
                    },
                    {
                        "role": "user",
                        "content": analysis_prompt
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            # Parse AI response
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Error in AI analysis: {str(e)}")
            return {} 