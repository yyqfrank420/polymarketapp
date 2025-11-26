"""KYC Service - AI-based document verification using OpenAI Vision"""
import json
import logging
import base64
from config import Config

logger = logging.getLogger(__name__)

# Optional OpenAI import
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

class KYCService:
    """Service for AI-based KYC document verification"""
    
    def __init__(self):
        self.openai_client = None
        self._initialize()
    
    def _initialize(self):
        """Initialize OpenAI client"""
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI not available - install openai package")
            return
        
        if Config.OPENAI_API_KEY:
            try:
                self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
                logger.info("KYC Service initialized with OpenAI")
            except Exception as e:
                logger.error(f"OpenAI initialization error: {e}")
        else:
            logger.warning("OPENAI_API_KEY not configured for KYC")
    
    def is_configured(self):
        """Check if KYC service is configured"""
        return self.openai_client is not None
    
    def get_system_prompt(self):
        """Get system prompt for document verification"""
        return """You are a document verification specialist. Analyze the provided identity document image.

Tasks:
1. Determine if this is an OFFICIAL government-issued identity document (passport, driver's license, national ID, etc.)
2. Extract the following information if official:
   - Full name (as it appears on document)
   - Date of birth (format: YYYY-MM-DD)
   - Document number
   - Nationality
   - Document type (passport/drivers_license/national_id/other)

Response format (JSON only):
{
    "is_official_document": boolean,
    "document_type": "passport" | "drivers_license" | "national_id" | "other" | "none",
    "full_name": "string or empty",
    "date_of_birth": "YYYY-MM-DD or empty",
    "document_number": "string or empty",
    "nationality": "string or empty",
    "confidence": "high" | "medium" | "low",
    "verification_notes": "string explaining verification result"
}

Rules:
- If not an official document, set is_official_document to false and leave other fields empty
- Extract text exactly as it appears
- Use confidence "high" only if all fields are clearly visible and readable
- Use confidence "low" if image is blurry, incomplete, or suspicious
- Provide clear verification_notes explaining your decision
"""
    
    def verify_document(self, image_base64: str) -> dict:
        """
        Analyze identity document using GPT-4o-mini vision
        
        Args:
            image_base64: Base64 encoded image string (with or without data URI prefix)
        
        Returns:
            dict with verification results:
            {
                "is_official_document": bool,
                "document_type": str,
                "full_name": str,
                "date_of_birth": str,
                "document_number": str,
                "nationality": str,
                "confidence": str,
                "verification_notes": str
            }
        """
        if not self.is_configured():
            return {
                "is_official_document": False,
                "document_type": "none",
                "full_name": "",
                "date_of_birth": "",
                "document_number": "",
                "nationality": "",
                "confidence": "low",
                "verification_notes": "KYC service not configured (missing OpenAI API key)"
            }
        
        try:
            # Clean base64 string (remove data URI prefix if present)
            if ',' in image_base64:
                image_base64 = image_base64.split(',', 1)[1]
            
            # Validate base64
            try:
                base64.b64decode(image_base64)
            except Exception as e:
                logger.error(f"Invalid base64 image: {e}")
                return {
                    "is_official_document": False,
                    "document_type": "none",
                    "full_name": "",
                    "date_of_birth": "",
                    "document_number": "",
                    "nationality": "",
                    "confidence": "low",
                    "verification_notes": "Invalid image format"
                }
            
            # Prepare image URL for OpenAI
            image_url = f"data:image/jpeg;base64,{image_base64}"
            
            # Call OpenAI Vision API
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Cheapest model with vision support
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
                                "text": "Please analyze this identity document and extract the information."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                    "detail": "low"  # Faster and cheaper for text extraction
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0,  # Deterministic results
                response_format={"type": "json_object"}  # Force JSON output
            )
            
            # Parse response
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            # Validate result structure
            required_fields = [
                "is_official_document", "document_type", "full_name",
                "date_of_birth", "document_number", "nationality",
                "confidence", "verification_notes"
            ]
            
            for field in required_fields:
                if field not in result:
                    result[field] = "" if field not in ["is_official_document"] else False
            
            logger.info(f"Document verification completed: {result['document_type']}, confidence: {result['confidence']}")
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {e}")
            return {
                "is_official_document": False,
                "document_type": "none",
                "full_name": "",
                "date_of_birth": "",
                "document_number": "",
                "nationality": "",
                "confidence": "low",
                "verification_notes": "AI response parsing error"
            }
        
        except Exception as e:
            logger.error(f"Document verification error: {str(e)}", exc_info=True)
            return {
                "is_official_document": False,
                "document_type": "none",
                "full_name": "",
                "date_of_birth": "",
                "document_number": "",
                "nationality": "",
                "confidence": "low",
                "verification_notes": f"Verification failed: {str(e)}"
            }

# Singleton instance
_kyc_service = None

def get_kyc_service():
    """Get singleton KYC service instance"""
    global _kyc_service
    if _kyc_service is None:
        _kyc_service = KYCService()
    return _kyc_service

