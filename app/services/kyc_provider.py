import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ExternalKYCProvider:
    """
    Mock integration for National Database and AI Facial Recognition.
    In real production, this integrates with SmileIdentity, Dojah, or NIA APIs.
    """
    
    @staticmethod
    async def verify_document_and_background(
        document_type: str, 
        document_number: str, 
        document_image_url: str,
        selfie_image_url: str
    ) -> Dict[str, Any]:
        """
        Simulate a complex background check.
        Returns 'pass' or 'flagged' along with reason strings.
        """
        logger.info(f"Running external KYC on {document_type}: {document_number}")
        
        reasons = []
        is_flagged = False
        
        # Simulated Criminal / Fraud detection based on trailing '999'
        if document_number and document_number.endswith("999"):
            is_flagged = True
            reasons.append("National database returned criminal or prior financial fraud history flag.")
            
        # Simulated Facial Recognition duplicate detection
        if selfie_image_url and "face-match" in selfie_image_url.lower():
            is_flagged = True
            reasons.append("AI Facial Recognition match: Face exists on another banned/criminal account.")
            
        if is_flagged:
            return {
                "status": "flagged",
                "reasons": reasons
            }
            
        return {
            "status": "pass",
            "reasons": []
        }
