"""
KYC Microservice - Separate service for AI-based document verification

Best Practices Applied:
1. Image validation with PIL to prevent malicious files
2. Proper error handling and edge case management
3. Exponential backoff for API retries
4. Secure response handling
5. OpenAI vision API best practices
6. Comprehensive logging for audit trail
"""

import json
import logging
import base64
import time
import io
from typing import Dict, Tuple, Optional
from config import Config

logger = logging.getLogger(__name__)

# Optional imports
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None

class ImageValidationError(Exception):
    """Custom exception for image validation errors"""
    pass

class KYCMicroservice:
    """
    Microservice for AI-based KYC document verification
    
    Features:
    - Secure image validation with PIL
    - Edge case handling (corrupted, huge, wrong format)
    - OpenAI vision API best practices
    - Exponential backoff retry logic
    - Comprehensive error handling
    """
    
    # Constants for validation
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB in bytes
    MAX_IMAGE_DIMENSION = 4096  # pixels
    MIN_IMAGE_DIMENSION = 100  # pixels
    ALLOWED_FORMATS = {'JPEG', 'PNG'}
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1.0  # seconds
    
    def __init__(self):
        self.openai_client = None
        self._initialize()
    
    def _initialize(self):
        """Initialize OpenAI client with validation"""
        if not OPENAI_AVAILABLE:
            logger.error("OpenAI package not available - KYC microservice cannot function")
            return
        
        if not PIL_AVAILABLE:
            logger.error("PIL/Pillow not available - image validation disabled")
            return
        
        if not Config.OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY not configured")
            return
        
        try:
            self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
            logger.info("KYC Microservice initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
    
    def is_configured(self) -> bool:
        """Check if microservice is properly configured"""
        return (
            self.openai_client is not None and
            PIL_AVAILABLE and
            OPENAI_AVAILABLE
        )
    
    def validate_image_security(self, image_data: bytes) -> Tuple[bool, Optional[str]]:
        """
        Validate image security using PIL
        
        Checks:
        1. File is actually an image
        2. No malicious content
        3. Format is allowed
        4. Size constraints met
        5. Not corrupted
        
        Returns:
            (is_valid, error_message)
        """
        if not PIL_AVAILABLE:
            return False, "Image validation not available (PIL not installed)"
        
        try:
            # Try to open image with PIL
            img = Image.open(io.BytesIO(image_data))
            
            # Verify the image by loading it (detects corruption)
            img.verify()
            
            # Reopen for further validation (verify() closes the file)
            img = Image.open(io.BytesIO(image_data))
            
            # Check format
            if img.format not in self.ALLOWED_FORMATS:
                return False, f"Invalid image format: {img.format}. Only JPEG and PNG allowed."
            
            # Check dimensions
            width, height = img.size
            if width < self.MIN_IMAGE_DIMENSION or height < self.MIN_IMAGE_DIMENSION:
                return False, f"Image too small: {width}x{height}. Minimum {self.MIN_IMAGE_DIMENSION}x{self.MIN_IMAGE_DIMENSION}."
            
            if width > self.MAX_IMAGE_DIMENSION or height > self.MAX_IMAGE_DIMENSION:
                return False, f"Image too large: {width}x{height}. Maximum {self.MAX_IMAGE_DIMENSION}x{self.MAX_IMAGE_DIMENSION}."
            
            # Check mode (should be RGB or similar)
            if img.mode not in ('RGB', 'RGBA', 'L', 'P'):
                return False, f"Unsupported image mode: {img.mode}"
            
            logger.info(f"Image validation passed: {img.format}, {width}x{height}, {img.mode}")
            return True, None
            
        except Image.DecompressionBombError:
            return False, "Image is too large to process (potential decompression bomb attack)"
        except Exception as e:
            logger.error(f"Image validation failed: {str(e)}")
            return False, f"Invalid or corrupted image file: {str(e)}"
    
    def validate_base64(self, base64_string: str) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """
        Validate and decode base64 string
        
        Returns:
            (is_valid, decoded_bytes, error_message)
        """
        try:
            # Remove data URI prefix if present
            if ',' in base64_string:
                base64_string = base64_string.split(',', 1)[1]
            
            # Remove whitespace
            base64_string = base64_string.strip().replace('\n', '').replace('\r', '')
            
            # Validate base64 format (must be valid base64)
            if len(base64_string) == 0:
                return False, None, "Empty base64 string"
            
            # Decode base64
            try:
                decoded = base64.b64decode(base64_string, validate=True)
            except Exception as e:
                return False, None, f"Invalid base64 encoding: {str(e)}"
            
            # Check size
            if len(decoded) > self.MAX_IMAGE_SIZE:
                size_mb = len(decoded) / (1024 * 1024)
                return False, None, f"Image size {size_mb:.2f}MB exceeds 5MB limit"
            
            if len(decoded) < 100:  # Minimum reasonable image size
                return False, None, "Image data too small to be valid"
            
            return True, decoded, None
            
        except Exception as e:
            logger.error(f"Base64 validation error: {str(e)}")
            return False, None, f"Base64 validation failed: {str(e)}"
    
    def get_system_prompt(self) -> str:
        """
        Get optimized system prompt for OpenAI Vision API
        
        Best practices applied:
        - Clear, specific instructions
        - Structured output format
        - Confidence scoring
        - Edge case handling
        """
        return """You are an expert document verification AI specializing in government-issued identity documents.

**Task**: Analyze the provided image and determine if it is an OFFICIAL government-issued ID document, then extract information.

**Supported Documents**:
- Passport
- Driver's License / Driving Permit
- National ID Card / Citizen Card
- Government-issued photo ID

**Analysis Requirements**:
1. **Authenticity Check**: Determine if this is a REAL, OFFICIAL government document (not screenshot, photocopy, or fake)
2. **Quality Check**: Assess if image is clear enough to read all text
3. **Information Extraction**: Extract data EXACTLY as it appears on document

**Output Format** (strict JSON):
{
    "is_official_document": boolean,
    "document_type": "passport" | "drivers_license" | "national_id" | "other" | "none",
    "full_name": "Full legal name as shown",
    "date_of_birth": "YYYY-MM-DD format",
    "expiry_date": "YYYY-MM-DD format or empty string if not found/not applicable",
    "document_number": "Exact number/ID shown",
    "nationality": "Country name",
    "confidence": "high" | "medium" | "low",
    "verification_notes": "Detailed explanation of your decision"
}

**Confidence Levels**:
- **high**: Clear, official document, all fields readable, no anomalies
- **medium**: Official document but some fields unclear or minor quality issues
- **low**: Image quality poor, suspicious elements, or not an official document

**Edge Cases to Handle**:
- Blurry or low-quality images → confidence: low
- Screenshots of documents → is_official_document: false
- Photocopies/scans → is_official_document: false
- Expired documents → still official, extract expiry_date, note expiration status in verification_notes
- Documents without expiry date (some national IDs) → expiry_date: empty string
- Foreign language documents → extract as shown, provide nationality
- Partial documents → is_official_document: false
- Student IDs, work badges → is_official_document: false

**Critical**: 
- If NOT an official government document, set is_official_document to false
- If image quality prevents extraction, set confidence to low
- Be conservative: when in doubt, use confidence: medium or low
- Provide clear verification_notes explaining your reasoning
"""
    
    def call_openai_vision_with_retry(
        self, 
        base64_image: str,
        max_retries: int = 3
    ) -> Dict:
        """
        Call OpenAI Vision API with exponential backoff retry logic
        
        Best practices:
        - Exponential backoff for rate limits
        - Proper error handling
        - Timeout management
        - Response validation
        """
        retry_delay = self.INITIAL_RETRY_DELAY
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Prepare image URL
                if not base64_image.startswith('data:'):
                    # Determine format from image data (default to JPEG)
                    base64_image = f"data:image/jpeg;base64,{base64_image}"
                
                # Call OpenAI Vision API with best practices
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",  # Cost-efficient model
                    messages=[
                        {
                            "role": "system",
                            "content": self.get_system_prompt()
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Analyze this identity document and extract all information according to the instructions."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": base64_image,
                                        "detail": "high"  # Use "high" for better accuracy on documents
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=800,  # Increased for detailed responses
                    temperature=0,  # Deterministic
                    response_format={"type": "json_object"},  # Force JSON
                    timeout=30.0  # 30 second timeout
                )
                
                # Extract response
                result_text = response.choices[0].message.content
                
                # Parse and validate JSON
                result = json.loads(result_text)
                
                # Validate required fields
                required_fields = [
                    "is_official_document", "document_type", "full_name",
                    "date_of_birth", "expiry_date", "document_number", 
                    "nationality", "confidence", "verification_notes"
                ]
                
                for field in required_fields:
                    if field not in result:
                        logger.warning(f"Missing field in OpenAI response: {field}")
                        result[field] = "" if field not in ["is_official_document"] else False
                
                logger.info(f"OpenAI call successful on attempt {attempt + 1}")
                return result
                
            except json.JSONDecodeError as e:
                last_error = f"Invalid JSON response from OpenAI: {str(e)}"
                logger.error(last_error)
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"OpenAI API call failed (attempt {attempt + 1}/{max_retries}): {last_error}")
                
                # Check if it's a rate limit error
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    if attempt < max_retries - 1:
                        logger.info(f"Rate limited, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                
                # Check if it's a timeout
                if "timeout" in str(e).lower():
                    if attempt < max_retries - 1:
                        logger.info(f"Timeout, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 1.5
                        continue
                
                # Other errors - don't retry
                break
        
        # All retries failed
        return {
            "is_official_document": False,
            "document_type": "none",
            "full_name": "",
            "date_of_birth": "",
            "expiry_date": "",
            "document_number": "",
            "nationality": "",
            "confidence": "low",
            "verification_notes": f"AI verification failed after {max_retries} attempts: {last_error}"
        }
    
    def verify_document(self, image_base64: str) -> Dict:
        """
        Main entry point for document verification
        
        Full validation pipeline:
        1. Validate base64 format
        2. Decode and check size
        3. Validate image security with PIL
        4. Call OpenAI Vision API with retry logic
        5. Return structured result
        
        Returns:
            dict with verification results or error details
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "KYC microservice not properly configured",
                "error_code": "SERVICE_UNAVAILABLE"
            }
        
        try:
            # Step 1: Validate and decode base64
            is_valid, decoded_bytes, error_msg = self.validate_base64(image_base64)
            if not is_valid:
                logger.warning(f"Base64 validation failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "error_code": "INVALID_BASE64"
                }
            
            # Step 2: Validate image security with PIL
            is_valid, error_msg = self.validate_image_security(decoded_bytes)
            if not is_valid:
                logger.warning(f"Image security validation failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "error_code": "INVALID_IMAGE"
                }
            
            # Step 3: Call OpenAI Vision API with retry logic
            result = self.call_openai_vision_with_retry(image_base64)
            
            # Step 4: Return structured response
            return {
                "success": True,
                "data": result
            }
            
        except Exception as e:
            logger.error(f"Unexpected error in verify_document: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": "Internal server error during verification",
                "error_code": "INTERNAL_ERROR",
                "details": str(e)
            }

# Singleton instance
_kyc_microservice = None

def get_kyc_microservice() -> KYCMicroservice:
    """Get singleton KYC microservice instance"""
    global _kyc_microservice
    if _kyc_microservice is None:
        _kyc_microservice = KYCMicroservice()
    return _kyc_microservice

