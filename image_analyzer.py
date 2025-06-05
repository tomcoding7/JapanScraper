import os
import io
import base64
import logging
import requests
import json
from PIL import Image
import openai
import google.generativeai as genai
from typing import Dict, List, Optional, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ImageAnalyzer:
    """Analyzes card images using OpenAI and Gemini Vision APIs."""
    
    def __init__(self):
        # Initialize OpenAI client
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            logger.error("OPENAI_API_KEY environment variable not set.")
            # Depending on severity, you might want to raise an exception here
            # or disable OpenAI functionality. For now, we'll proceed but log.
        self.client = openai.OpenAI(api_key=openai_api_key)
        
        # Initialize Gemini
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            logger.error("GEMINI_API_KEY environment variable not set.")
            # Similar to OpenAI, handle missing key.
        genai.configure(api_key=gemini_api_key)
        self.gemini_model = genai.GenerativeModel('gemini-pro-vision')
        
        # Create a session for image downloads
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Referer': 'https://buyee.jp/', # Keep this specific if images are primarily from buyee.jp
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'same-origin',
            'DNT': '1',
        })
    
    def get_largest_image(self, image_urls: List[str]) -> tuple[Optional[bytes], Optional[str]]:
        """Find and download the largest available image from a list of URLs."""
        largest_size = 0
        largest_image = None
        largest_url = None
        
        if not image_urls:
            logger.warning("No image URLs provided to get_largest_image.")
            return None, None

        logger.info(f"Attempting to download images from {len(image_urls)} URLs.")
        for url in image_urls:
            try:
                # Try HEAD request first to check size
                response = self.session.head(url, timeout=5)
                response.raise_for_status() # Raise an exception for HTTP errors
                content_length = int(response.headers.get('content-length', 0))
                
                if content_length > largest_size:
                    # If this is larger, download the full image
                    img_response = self.session.get(url, timeout=10)
                    img_response.raise_for_status() # Raise an exception for HTTP errors
                    
                    largest_size = content_length
                    largest_image = img_response.content
                    largest_url = url
                    logger.info(f"Found larger image: {url} ({content_length} bytes)")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Network or HTTP error for {url}: {e}")
            except Exception as e:
                logger.warning(f"General error checking image size for {url}: {str(e)}")
            
        if largest_image:
            logger.info(f"Selected largest image: {largest_url} ({largest_size} bytes)")
            return largest_image, largest_url
        logger.error("Failed to download any image from the provided URLs.")
        return None, None
    
    def analyze_with_openai(self, image_content: bytes, image_url: str) -> Optional[Dict[str, Any]]:
        """Analyze image using OpenAI Vision API with detailed prompt and error handling."""
        if not self.client:
            logger.error("OpenAI client is not set. Skipping OpenAI analysis.")
            return None

        try:
            # Convert image to base64
            image = Image.open(io.BytesIO(image_content))
            buffered = io.BytesIO()
            # Ensure image is in RGB mode before saving as JPEG to avoid errors with alpha channel
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            image.save(buffered, format="JPEG", quality=95)  # High quality
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            # Detailed prompt for card condition analysis, requesting JSON output
            prompt = """Analyze this Yu-Gi-Oh card image carefully. Focus on:
1. Surface condition: Are there any visible scratches, scuffs, or surface wear?
2. Edge condition: Is there any edge wear, whitening, or damage?
3. Corner condition: Are the corners sharp or worn?
4. Creases: Are there any visible creases or folds?
5. Overall condition: What is the overall condition of the card?

Based on your analysis, provide a concise summary in the 'condition_analysis' field and a boolean 'is_damaged' field.
If you see *any* damage (scratches, scuffs, wear, creases, folds, whitening, etc.), set 'is_damaged' to true.
If the card appears to be in perfect condition with no visible flaws, set 'is_damaged' to false.

Respond ONLY with a JSON object in the following format:
{
  "condition_analysis": "Your detailed analysis here.",
  "is_damaged": true/false
}
"""

            # Call OpenAI Vision API with timeout
            response = self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_str}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                timeout=30  # 30 second timeout
            )
            
            raw_analysis = response.choices[0].message.content
            logger.info("Successfully received raw analysis from OpenAI.")
            
            # Attempt to parse the JSON response
            try:
                parsed_analysis = json.loads(raw_analysis)
                analysis_text = parsed_analysis.get('condition_analysis', raw_analysis)
                is_damaged = parsed_analysis.get('is_damaged', False) # Default to False if not present
                logger.info("Successfully parsed JSON from OpenAI analysis.")
            except json.JSONDecodeError as e:
                logger.warning(f"OpenAI did not return valid JSON. Falling back to raw text. Error: {e}")
                analysis_text = raw_analysis
                is_damaged = any(term in raw_analysis.lower() for term in [
                    'scratch', 'scuff', 'wear', 'damage', 'crease', 'fold',
                    'edge wear', 'corner wear', 'whitening', 'surface wear'
                ]) # Fallback to keyword matching if JSON parsing fails
            
            return {
                'analysis': analysis_text,
                'is_damaged': is_damaged,
                'source': 'openai'
            }
            
        except openai.error.Timeout:
            logger.warning("OpenAI request timed out.")
            return None
        except openai.error.APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error in OpenAI analysis: {str(e)}")
            return None
    
    def analyze_with_gemini(self, image_content: bytes, image_url: str) -> Optional[Dict[str, Any]]:
        """Analyze image using Google's Gemini Vision API as fallback."""
        if not genai.get_default_retriever(): # Check if Gemini is configured
             logger.error("Gemini API key is not set. Skipping Gemini analysis.")
             return None

        try:
            # Convert image to PIL Image
            image = Image.open(io.BytesIO(image_content))
            # Ensure image is in RGB mode for Gemini if it has an alpha channel
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            
            # Same detailed prompt as OpenAI, requesting JSON output
            prompt = """Analyze this Yu-Gi-Oh card image carefully. Focus on:
1. Surface condition: Are there any visible scratches, scuffs, or surface wear?
2. Edge condition: Is there any edge wear, whitening, or damage?
3. Corner condition: Are the corners sharp or worn?
4. Creases: Are there any visible creases or folds?
5. Overall condition: What is the overall condition of the card?

Based on your analysis, provide a concise summary in the 'condition_analysis' field and a boolean 'is_damaged' field.
If you see *any* damage (scratches, scuffs, wear, creases, folds, whitening, etc.), set 'is_damaged' to true.
If the card appears to be in perfect condition with no visible flaws, set 'is_damaged' to false.

Respond ONLY with a JSON object in the following format:
{
  "condition_analysis": "Your detailed analysis here.",
  "is_damaged": true/false
}
"""
            
            # Call Gemini Vision API
            response = self.gemini_model.generate_content([prompt, image])
            response.resolve() # Ensure the response is fully resolved
            
            raw_analysis = response.text
            logger.info("Successfully received raw analysis from Gemini.")
            
            # Attempt to parse the JSON response
            try:
                parsed_analysis = json.loads(raw_analysis)
                analysis_text = parsed_analysis.get('condition_analysis', raw_analysis)
                is_damaged = parsed_analysis.get('is_damaged', False) # Default to False if not present
                logger.info("Successfully parsed JSON from Gemini analysis.")
            except json.JSONDecodeError as e:
                logger.warning(f"Gemini did not return valid JSON. Falling back to raw text. Error: {e}")
                analysis_text = raw_analysis
                is_damaged = any(term in raw_analysis.lower() for term in [
                    'scratch', 'scuff', 'wear', 'damage', 'crease', 'fold',
                    'edge wear', 'corner wear', 'whitening', 'surface wear'
                ]) # Fallback to keyword matching if JSON parsing fails
            
            return {
                'analysis': analysis_text,
                'is_damaged': is_damaged,
                'source': 'gemini'
            }
            
        except Exception as e:
            logger.error(f"Error in Gemini analysis: {str(e)}")
            return None
    
    def analyze_image(self, image_urls: List[str]) -> Optional[Dict[str, Any]]:
        """Main method to analyze images with proper error handling and fallback."""
        try:
            # Get the largest available image
            image_content, selected_url = self.get_largest_image(image_urls)
            if not image_content:
                logger.error("Failed to download any image for analysis.")
                return None
            
            logger.info("Attempting image analysis with OpenAI...")
            result = self.analyze_with_openai(image_content, selected_url)
            
            # If OpenAI fails, try Gemini
            if not result:
                logger.info("OpenAI analysis failed or returned no result, attempting with Gemini...")
                result = self.analyze_with_gemini(image_content, selected_url)
            
            if result:
                logger.info(f"Successfully analyzed image using {result['source']}")
                return result
            else:
                logger.error("Both OpenAI and Gemini analysis failed or returned no result.")
                return None
                
        except Exception as e:
            logger.error(f"An unexpected error occurred during image analysis: {str(e)}")
            return None

# Example Usage
if __name__ == "__main__":
    # IMPORTANT: Set your API keys as environment variables before running:
    # export OPENAI_API_KEY='your_openai_api_key_here'
    # export GEMINI_API_KEY='your_gemini_api_key_here'

    # Example Yu-Gi-Oh card image URLs (replace with actual URLs for testing)
    # These are placeholder URLs and will likely not work.
    # You need to find actual image URLs of Yu-Gi-Oh cards.
    example_image_urls = [
        "https://example.com/yugioh_card_1_large.jpg",
        "https://example.com/yugioh_card_1_medium.png",
        "https://example.com/yugioh_card_1_small.jpeg",
        "https://upload.wikimedia.org/wikipedia/en/2/2b/Dark_Magician_card.jpg" # A public example
    ]

    analyzer = ImageAnalyzer()
    analysis_result = analyzer.analyze_image(example_image_urls)

    if analysis_result:
        print("\n--- Analysis Result ---")
        print(f"Source: {analysis_result['source']}")
        print(f"Is Damaged: {analysis_result['is_damaged']}")
        print("Condition Analysis:")
        print(analysis_result['analysis'])
    else:
        print("\n--- Analysis Failed ---")
        print("Could not get a successful analysis for the provided image URLs.") 