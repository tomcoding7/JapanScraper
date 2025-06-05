from typing import Dict, Any, Optional, List, Tuple
import re
import logging
import os
import json
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai_api_key = os.getenv('OPENAI_API_KEY')

class TextAnalyzer:
    def __init__(self):
        # Initialize OpenAI client
        self.client = openai.OpenAI(api_key=openai_api_key)
        
        # Card name patterns (both English and Japanese)
        self.card_name_patterns = [
            r'Blue-Eyes White Dragon|青眼の白龍',
            r'Dark Magician|ブラック・マジシャン',
            r'Red-Eyes Black Dragon|レッドアイズ・ブラックドラゴン',
            r'Exodia|エクゾディア',
            r'Black Luster Soldier|カオス・ソルジャー',
            r'Chaos Emperor Dragon|カオス・エンペラー・ドラゴン',
            r'Cyber Dragon|サイバー・ドラゴン',
            r'Elemental Hero|エレメンタル・ヒーロー',
            r'Destiny Hero|デステニー・ヒーロー',
            r'Neos|ネオス',
            r'Stardust Dragon|スターダスト・ドラゴン',
            r'Black Rose Dragon|ブラックローズ・ドラゴン',
            r'Arcanite Magician|アーカナイト・マジシャン'
        ]
        
        # Set code pattern (e.g., LOB-001, MRD-060)
        self.set_code_pattern = r'([A-Z]{2,4})-(\d{3})'
        
        # Rarity keywords (both English and Japanese)
        self.rarity_keywords = {
            'common': ['common', 'コモン'],
            'rare': ['rare', 'レア'],
            'super rare': ['super rare', 'sr', 'スーパーレア'],
            'ultra rare': ['ultra rare', 'ur', 'ウルトラレア'],
            'secret rare': ['secret rare', 'scr', 'シークレットレア'],
            'ultimate rare': ['ultimate rare', 'utr', 'アルティメットレア'],
            'ghost rare': ['ghost rare', 'gr', 'ゴーストレア'],
            'platinum rare': ['platinum rare', 'plr', 'プラチナレア'],
            'gold rare': ['gold rare', 'gld', 'ゴールドレア'],
            'parallel rare': ['parallel rare', 'pr', 'パラレルレア'],
            'collector\'s rare': ['collector\'s rare', 'cr', 'コレクターズレア'],
            'quarter century': ['quarter century', 'qc', 'クォーターセンチュリー']
        }
        
        # Edition keywords (both English and Japanese)
        self.edition_keywords = {
            '1st edition': ['1st', 'first edition', '初版'],
            'unlimited': ['unlimited', '無制限', '再版']
        }
        
        # Region keywords (both English and Japanese)
        self.region_keywords = {
            'asia': ['asia', 'asian', 'アジア', 'アジア版'],
            'english': ['english', '英', '英語版'],
            'japanese': ['japanese', '日', '日本語版'],
            'korean': ['korean', '韓', '韓国版']
        }
        
        # Condition keywords (both English and Japanese)
        self.condition_keywords = {
            'mint': ['mint', 'ミント', '未使用'],
            'near mint': ['near mint', 'nm', 'ニアミント', '新品同様'],
            'excellent': ['excellent', 'ex', 'エクセレント', '美品'],
            'good': ['good', 'gd', 'グッド', '良品'],
            'light played': ['light played', 'lp', 'ライトプレイ', '軽度使用'],
            'played': ['played', 'pl', 'プレイ', '使用済み'],
            'poor': ['poor', 'pr', 'プア', '傷あり']
        }
        
        # Special keywords that might indicate value
        self.value_indicators = [
            'limited', '限定', 'promo', '特典', 'tournament', '大会',
            'championship', 'チャンピオンシップ', 'event', 'イベント',
            'sealed', '未開封', 'unopened', '初期', 'shoki', '旧アジア',
            'kyuu-ajia', 'PSA', 'BGS', 'エラーカード', 'error card'
        ]

    def analyze_text(self, title: str, description: Optional[str] = None) -> Dict[str, Any]:
        """Analyze text to extract card information using both rule-based and LLM analysis."""
        # Initialize results dictionary
        results = {
            'card_name_jp': None,
            'card_name_en': None,
            'set_name_jp': None,
            'set_code': None,
            'card_number': None,
            'rarity_jp': None,
            'rarity_en': None,
            'edition_jp': None,
            'edition_en': None,
            'language': None,
            'condition_notes_from_description': [],
            'seller_rank_from_description': None,
            'confidence_score': 0.0
        }
        
        # First, try LLM analysis if we have a description
        if description:
            try:
                llm_results = self._analyze_with_llm(title, description)
                if llm_results:
                    # Update results with LLM findings
                    results.update(llm_results)
                    results['confidence_score'] += 0.6  # LLM analysis provides strong confidence
            except Exception as e:
                logging.error(f"LLM analysis failed: {str(e)}")
        
        # Fall back to rule-based analysis for any missing fields
        rule_based_results = self._analyze_with_rules(title, description or '')
        
        # Update results with rule-based findings for any missing fields
        for key, value in rule_based_results.items():
            if not results.get(key):
                results[key] = value
                results['confidence_score'] += 0.2  # Rule-based analysis provides moderate confidence
        
        # Normalize confidence score
        results['confidence_score'] = min(results['confidence_score'], 1.0)
        
        # Log the analysis results
        logging.info("\nText Analysis Results:")
        for key, value in results.items():
            logging.info(f"{key}: {value}")
        
        return results

    def _analyze_with_llm(self, title: str, description: str) -> Optional[Dict[str, Any]]:
        """Analyze text using OpenAI's GPT model."""
        try:
            # Construct the prompt
            prompt = f"""Given the following Japanese item title and description for a trading card:
Title: "{title}"
Description: "{description}"

Extract the following information into a structured JSON object with these exact keys: "card_name_jp", "card_name_en", "set_name_jp", "set_code", "card_number", "rarity_jp", "rarity_en", "edition_jp", "edition_en", "language", "condition_notes_from_description", "seller_rank_from_description".
If information for a key is not present, use null or an empty string for its value. Focus on information explicitly stated or strongly implied. For "condition_notes_from_description", list all phrases related to condition. For "seller_rank_from_description", extract only the rank (e.g., "A", "S", "B+").

Return ONLY the JSON object, no other text."""

            # Make the API call
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",  # Using the latest GPT-4 model
                messages=[
                    {"role": "system", "content": "You are a specialized parser for Japanese trading card listings. Extract structured information from the given text and return it as a JSON object."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for more consistent results
                max_tokens=500
            )
            
            # Extract and parse the JSON response
            try:
                json_str = response.choices[0].message.content.strip()
                # Remove any markdown code block markers
                json_str = re.sub(r'^```json\s*|\s*```$', '', json_str)
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse LLM response as JSON: {str(e)}")
                return None
            
        except Exception as e:
            logging.error(f"Error in LLM analysis: {str(e)}")
            return None

    def _analyze_with_rules(self, title: str, description: str) -> Dict[str, Any]:
        """Analyze text using rule-based methods."""
        # Combine title and description for analysis
        full_text = f"{title} {description}".lower()
        
        # Extract card name
        card_name = self._extract_card_name(full_text)
        
        # Extract set code and card number
        set_code, card_number = self._extract_set_info(full_text)
        
        # Extract rarity
        rarity = self._extract_rarity(full_text)
        
        # Extract edition
        edition = self._extract_edition(full_text)
        
        # Extract region
        region = self._extract_region(full_text)
        
        # Extract condition keywords
        condition_keywords = self._extract_condition_keywords(full_text)
        
        # Extract value indicators
        value_indicators = self._extract_value_indicators(full_text)
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(
            card_name=card_name,
            set_code=set_code,
            card_number=card_number,
            rarity=rarity,
            edition=edition,
            region=region,
            condition_keywords=condition_keywords,
            value_indicators=value_indicators
        )
        
        return {
            'card_name_jp': card_name,
            'card_name_en': None,  # Rule-based analysis can't reliably extract English names
            'set_name_jp': None,  # Rule-based analysis can't reliably extract Japanese set names
            'set_code': set_code,
            'card_number': card_number,
            'rarity_jp': rarity,
            'rarity_en': rarity,  # For rule-based, we use the same value
            'edition_jp': edition,
            'edition_en': edition,  # For rule-based, we use the same value
            'language': region,
            'condition_notes_from_description': condition_keywords,
            'seller_rank_from_description': None,  # Rule-based analysis can't reliably extract seller rank
            'confidence_score': confidence_score
        }

    def _extract_card_name(self, text: str) -> Optional[str]:
        """Extract card name from text."""
        for pattern in self.card_name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return None

    def _extract_set_info(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract set code and card number from text."""
        match = re.search(self.set_code_pattern, text)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def _extract_rarity(self, text: str) -> Optional[str]:
        """Extract rarity from text."""
        for rarity, keywords in self.rarity_keywords.items():
            if any(keyword.lower() in text.lower() for keyword in keywords):
                return rarity
        return None

    def _extract_edition(self, text: str) -> Optional[str]:
        """Extract edition from text."""
        for edition, keywords in self.edition_keywords.items():
            if any(keyword.lower() in text.lower() for keyword in keywords):
                return edition
        return None

    def _extract_region(self, text: str) -> Optional[str]:
        """Extract region from text."""
        for region, keywords in self.region_keywords.items():
            if any(keyword.lower() in text.lower() for keyword in keywords):
                return region
        return None

    def _extract_condition_keywords(self, text: str) -> List[str]:
        """Extract condition keywords from text."""
        found_keywords = []
        for condition, keywords in self.condition_keywords.items():
            if any(keyword.lower() in text.lower() for keyword in keywords):
                found_keywords.append(condition)
        return found_keywords

    def _extract_value_indicators(self, text: str) -> List[str]:
        """Extract value indicators from text."""
        return [indicator for indicator in self.value_indicators 
                if indicator.lower() in text.lower()]

    def _calculate_confidence_score(self,
                                  card_name: Optional[str],
                                  set_code: Optional[str],
                                  card_number: Optional[str],
                                  rarity: Optional[str],
                                  edition: Optional[str],
                                  region: Optional[str],
                                  condition_keywords: List[str],
                                  value_indicators: List[str]) -> float:
        """Calculate confidence score based on extracted information."""
        score = 0.0
        
        # Card name score
        if card_name:
            score += 0.2
        
        # Set code and card number score
        if set_code and card_number:
            score += 0.15
        
        # Rarity score
        if rarity:
            if rarity.lower() in ['ghost rare', 'ultimate rare', 'starlight rare', 'quarter century']:
                score += 0.15
            elif rarity.lower() in ['secret rare', 'collector\'s rare', 'prismatic secret rare']:
                score += 0.1
            elif rarity.lower() in ['ultra rare', 'gold rare', 'platinum rare']:
                score += 0.08
            elif rarity.lower() in ['super rare', 'parallel rare']:
                score += 0.05
            elif rarity.lower() == 'rare':
                score += 0.03
        
        # Edition score
        if edition == '1st edition':
            score += 0.1
        
        # Region score
        if region:
            if region.lower() in ['japanese', 'asia']:
                score += 0.08
            else:
                score += 0.05
        
        # Condition keywords score
        if len(condition_keywords) >= 2:
            score += 0.1
        elif len(condition_keywords) == 1:
            score += 0.05
        
        # Value indicators score
        if len(value_indicators) >= 2:
            score += 0.1
        elif len(value_indicators) == 1:
            score += 0.05
        
        return min(score, 1.0)  # Cap at 1.0 