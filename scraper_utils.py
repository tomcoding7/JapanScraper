import requests
from bs4 import BeautifulSoup
import logging
import time
import random
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import quote
import statistics
import re
import os
import google.generativeai as genai
from openai import OpenAI

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RequestHandler:
    """Handles HTTP requests with retry logic and bot detection."""
    
    def __init__(self):
        """Initialize the RequestHandler with default headers and retry settings."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        })
        self.retry_delays = [1, 2, 5, 10, 30]  # Exponential backoff delays
        self.max_retries = 3
        self.timeout = 10
        
    def get_page(self, url: str, max_retries: int = None, timeout: int = None) -> Optional[str]:
        """
        Make a request with retry logic and bot detection.
        
        Args:
            url (str): URL to fetch
            max_retries (int): Maximum number of retries
            timeout (int): Request timeout in seconds
            
        Returns:
            Optional[str]: Page content or None if failed
        """
        retries = max_retries if max_retries is not None else self.max_retries
        timeout = timeout if timeout is not None else self.timeout
        
        for retry in range(retries):
            try:
                # Add random delay between requests
                time.sleep(random.uniform(3, 7))
                
                # Make request with timeout
                response = self.session.get(url, timeout=timeout)
                
                # Handle common error cases
                if response.status_code == 404:
                    logger.warning(f"Item not found (404): {url}")
                    return None
                
                if response.status_code in [403, 429]:
                    logger.warning(f"Bot detection triggered (HTTP {response.status_code})")
                    if retry < retries - 1:
                        delay = self.retry_delays[min(retry, len(self.retry_delays) - 1)]
                        logger.info(f"Waiting {delay} seconds before retry...")
                        time.sleep(delay)
                        continue
                    return None
                
                # Check for Japanese-specific error messages
                if 'このサービスは日本国内からのみご利用いただけます' in response.text:
                    logger.error("Access denied. This service is only available from Japan.")
                    return None
                
                if 'アクセスが集中' in response.text or '一時的なアクセス制限' in response.text:
                    logger.warning("Bot challenge page detected")
                    if retry < retries - 1:
                        delay = self.retry_delays[min(retry, len(self.retry_delays) - 1)]
                        logger.info(f"Waiting {delay} seconds before retry...")
                        time.sleep(delay)
                        continue
                    return None
                
                # Raise for any other HTTP errors
                response.raise_for_status()
                
                # Log successful request
                logger.info(f"Successfully fetched page: {url}")
                return response.text
                
            except requests.RequestException as e:
                logger.error(f"Error fetching {url}: {str(e)}")
                if retry < retries - 1:
                    delay = self.retry_delays[min(retry, len(self.retry_delays) - 1)]
                    logger.info(f"Waiting {delay} seconds before retry...")
                    time.sleep(delay)
                else:
                    logger.error("Max retries reached")
                    return None
        return None

class CardInfoExtractor:
    """Extracts and normalizes card information from titles."""
    
    def __init__(self):
        # Initialize OpenAI
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Common set codes and their full names
        self.set_patterns = {
            'SDK': 'Starter Deck Kaiba',
            'LOB': 'Legend of Blue Eyes White Dragon',
            'MRD': 'Metal Raiders',
            'SRL': 'Starter Deck Yugi',
            'PSV': 'Pharaoh\'s Servant',
        }
    
    def translate_to_english(self, japanese_text: str) -> str:
        """Translate Japanese card name to English using OpenAI."""
        try:
            prompt = f"""Translate this Yu-Gi-Oh card name from Japanese to English. 
            Only return the English name, nothing else. If it's a set name or condition, ignore it.
            Japanese text: {japanese_text}"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a Yu-Gi-Oh card name translator. Only return the English name, no explanations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3  # Lower temperature for more consistent translations
            )
            
            english_name = response.choices[0].message.content.strip()
            logger.info(f"Translated '{japanese_text}' to '{english_name}'")
            return english_name
            
        except Exception as e:
            logger.error(f"Error translating card name: {str(e)}")
            return japanese_text
    
    def extract_card_info(self, title: str) -> Tuple[str, Optional[str]]:
        """Extract card name and set from title."""
        try:
            # Try to find set code first
            set_code = None
            for code in self.set_patterns.keys():
                if code in title.upper():
                    set_code = code
                    break
            
            # Extract card name
            card_name = title
            
            # Remove common words and set codes
            common_words = [
                '遊戯王', 'Yu-Gi-Oh', 'カード', 'card', '1st', 'edition', 'limited', 
                'まとめ', 'レア', 'rare', 'セット', 'set', 'パック', 'pack',
                '新品', '未使用', '中古', '使用済み', 'プレイ済み'
            ]
            
            # Remove common words
            for word in common_words:
                card_name = card_name.replace(word, '').strip()
            
            # Remove set code if found
            if set_code:
                card_name = card_name.replace(set_code, '').strip()
            
            # Remove numbers at the end (like "864" in "まとめ 864")
            card_name = re.sub(r'\s*\d+$', '', card_name).strip()
            
            # If the name is too short or just numbers, try to extract from description
            if len(card_name) < 3 or card_name.isdigit():
                logger.warning(f"Card name too short or invalid: {card_name}")
                return None, set_code
            
            # Translate to English if it contains Japanese characters
            if any(ord(c) > 127 for c in card_name):
                card_name = self.translate_to_english(card_name)
            
            return card_name, set_code
            
        except Exception as e:
            logger.error(f"Error extracting card info: {str(e)}")
            return None, None

class PriceAnalyzer:
    """Analyzes card prices from 130point.com."""
    
    def __init__(self):
        self.request_handler = RequestHandler()
    
    def get_130point_prices(self, card_name: str, set_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get price data from 130point.com."""
        try:
            search_term = f"{card_name} {set_code}" if set_code else card_name
            search_term = quote(search_term)
            url = f"https://130point.com/sales/?item={search_term}"
            
            time.sleep(random.uniform(2, 4))
            html_content = self.request_handler.get_page(url)
            if not html_content:
                return None
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            raw_prices = []
            psa_9_prices = []
            psa_10_prices = []
            
            sales = soup.find_all('div', class_='sale-item')
            for sale in sales:
                try:
                    price_elem = sale.find('span', class_='price')
                    if not price_elem:
                        continue
                    price = float(price_elem.text.strip().replace('$', '').replace(',', ''))
                    
                    condition_elem = sale.find('span', class_='condition')
                    if not condition_elem:
                        continue
                    condition = condition_elem.text.strip().lower()
                    
                    if 'psa 10' in condition:
                        psa_10_prices.append(price)
                    elif 'psa 9' in condition:
                        psa_9_prices.append(price)
                    else:
                        raw_prices.append(price)
                        
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Error parsing sale entry: {str(e)}")
                    continue
            
            return {
                'raw_avg': statistics.mean(raw_prices) if raw_prices else None,
                'psa_9_avg': statistics.mean(psa_9_prices) if psa_9_prices else None,
                'psa_10_avg': statistics.mean(psa_10_prices) if psa_10_prices else None,
                'raw_count': len(raw_prices),
                'psa_9_count': len(psa_9_prices),
                'psa_10_count': len(psa_10_prices)
            }
            
        except Exception as e:
            logger.error(f"Error getting 130point prices: {str(e)}")
            return None

class ConditionAnalyzer:
    """Analyzes card condition from text and images."""
    
    def __init__(self):
        self.japanese_grade_patterns = {
            'SS': r'SSランク|新品未使用|完全美品',
            'S': r'Sランク|未使用.*初期傷.*微妙',
            'A': r'Aランク|未使用.*凹み.*初期傷.*目立つレベルではない',
            'B+': r'B\+ランク|未使用品.*凹み.*初期傷.*目立つ傷',
            'B': r'Bランク|中古品.*使用感あり.*初期傷.*プレイ時の傷',
            'C': r'Cランク|中古品.*使用感あり.*目立つレベルの傷',
            'D': r'Dランク|中古品.*ボロボロ',
            'E': r'Eランク|ジャンク品'
        }
        
        self.condition_terms = {
            'new': [
                '新品', '未使用', 'SSランク', 'Sランク', '完全美品',
                'new', 'mint', 'unused', 'sealed'
            ],
            'used': [
                '中古', '使用済み', '使用感あり', 'プレイ済み',
                'used', 'played', 'second-hand'
            ],
            'damaged': [
                '傷あり', '凹み', '白欠け', 'スレ', '初期傷',
                'damaged', 'scratched', 'dented', 'wear'
            ]
        }
    
    def analyze_condition(self, title: str, description: str, image_analysis: Optional[Dict] = None) -> Dict[str, Any]:
        """Analyze the condition of an item based on title, description, and optional image analysis."""
        # Combine title and description for analysis
        full_text = f"{title} {description}"
        
        # Initialize condition info
        condition_info = {
            'is_new': False,
            'is_used': False,
            'is_unopened': False,
            'is_played': False,
            'is_scratched': False,
            'is_damaged': False,
            'condition_notes': [],
            'condition_summary': 'Unknown',
            'damage_flags': [],
            'image_text_discrepancy': False,
            'japanese_grade': None
        }
        
        # Check for Japanese grading system
        for grade, pattern in self.japanese_grade_patterns.items():
            if re.search(pattern, full_text, re.IGNORECASE):
                condition_info['japanese_grade'] = grade
                condition_info['condition_summary'] = f"Grade {grade}"
                
                # Set condition flags based on grade
                if grade in ['SS', 'S']:
                    condition_info['is_new'] = True
                    condition_info['is_unopened'] = True
                elif grade in ['A', 'B+']:
                    condition_info['is_new'] = True
                    condition_info['is_scratched'] = True
                elif grade in ['B', 'C']:
                    condition_info['is_used'] = True
                    condition_info['is_played'] = True
                    condition_info['is_scratched'] = True
                elif grade in ['D', 'E']:
                    condition_info['is_used'] = True
                    condition_info['is_damaged'] = True
                
                break
        
        # If no Japanese grade found, fall back to standard analysis
        if not condition_info['japanese_grade']:
            # Check for condition terms
            for condition_type, terms in self.condition_terms.items():
                for term in terms:
                    if term.lower() in full_text.lower():
                        if condition_type == 'new':
                            condition_info['is_new'] = True
                            condition_info['is_unopened'] = True
                        elif condition_type == 'used':
                            condition_info['is_used'] = True
                            condition_info['is_played'] = True
                        elif condition_type == 'damaged':
                            condition_info['is_damaged'] = True
                            condition_info['is_scratched'] = True
                        
                        condition_info['condition_notes'].append(f"Found {condition_type} indicator: {term}")
            
            # Set condition summary
            if condition_info['is_new']:
                condition_info['condition_summary'] = 'New'
            elif condition_info['is_used']:
                if condition_info['is_damaged']:
                    condition_info['condition_summary'] = 'Used - Damaged'
                elif condition_info['is_scratched']:
                    condition_info['condition_summary'] = 'Used - Scratched'
                else:
                    condition_info['condition_summary'] = 'Used'
        
        # Add image analysis if available
        if image_analysis:
            image_condition = image_analysis.get('condition', {}).get('summary', '').lower()
            
            # Check for discrepancies between text and image analysis
            if condition_info['is_new'] and 'damaged' in image_condition:
                condition_info['image_text_discrepancy'] = True
                condition_info['damage_flags'].append('Image shows damage but listed as new')
            elif condition_info['is_used'] and 'mint' in image_condition:
                condition_info['image_text_discrepancy'] = True
                condition_info['damage_flags'].append('Image shows mint condition but listed as used')
        
        return condition_info 