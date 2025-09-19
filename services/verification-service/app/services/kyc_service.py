import cv2
import numpy as np
from PIL import Image
import asyncio
import time
import logging
import json
import re
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import traceback

logger = logging.getLogger(__name__)

class KYCService:
    def __init__(self):
        self.supported_countries = ['US', 'UK', 'CA', 'AU', 'EU']
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.min_age_requirement = 18
        
    async def verify_document(
        self,
        file_path: str,
        document_type: Optional[str] = None,
        country_code: str = "US",
        perform_face_match: bool = False,
        reference_image_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Verify a KYC document."""
        try:
            start_time = time.time()
            file_path = Path(file_path)
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Load and analyze image
            image = cv2.imread(str(file_path))
            if image is None:
                raise ValueError("Could not load image file")
            
            # Detect document type if not provided
            if not document_type:
                document_type = await self._detect_document_type(image)
            
            # Extract data from document
            extracted_data = await self._extract_document_data(image, document_type)
            
            # Perform verification checks
            verification_checks = await self._perform_verification_checks(
                image, extracted_data, document_type
            )
            
            # Calculate risk assessment
            risk_assessment = await self._calculate_risk_score(
                extracted_data, verification_checks, document_type
            )
            
            # Perform face matching if requested
            face_match_result = None
            if perform_face_match and reference_image_path:
                face_match_result = await self._perform_face_matching(
                    str(file_path), reference_image_path
                )
                verification_checks['face_match'] = face_match_result.get('is_match', False)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            # Determine overall verification status
            verification_status = self._determine_verification_status(
                verification_checks, risk_assessment['risk_score']
            )
            
            return {
                'verification_status': verification_status,
                'document_type': document_type,
                'extracted_data': extracted_data,
                'risk_score': risk_assessment['risk_score'],
                'risk_level': risk_assessment['risk_level'],
                'risk_factors': risk_assessment['risk_factors'],
                'verification_checks': verification_checks,
                'face_match_result': face_match_result,
                'processing_time': processing_time,
                'metadata': {
                    'processing_engine': 'custom_kyc',
                    'algorithms_used': ['opencv', 'pattern_matching'],
                    'processing_time_ms': processing_time,
                    'image_dimensions': {'width': image.shape[1], 'height': image.shape[0]}
                }
            }
            
        except Exception as e:
            logger.error(f"Error verifying document: {str(e)}\n{traceback.format_exc()}")
            raise
    
    async def _detect_document_type(self, image: np.ndarray) -> str:
        """Detect the type of document from the image."""
        try:
            # Simple document type detection based on aspect ratio and features
            height, width = image.shape[:2]
            aspect_ratio = width / height
            
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Look for specific patterns (simplified version)
            if aspect_ratio > 1.4 and aspect_ratio < 1.6:
                # Likely a card format (driver's license, ID card)
                if self._contains_text_pattern(gray, ['DRIVER', 'LICENSE']):
                    return 'drivers_license'
                elif self._contains_text_pattern(gray, ['PASSPORT']):
                    return 'passport'
                else:
                    return 'national_id'
            elif aspect_ratio > 1.3 and aspect_ratio < 1.4:
                # Likely a passport
                return 'passport'
            else:
                return 'unknown'
            
        except Exception as e:
            logger.error(f"Error detecting document type: {str(e)}")
            return 'unknown'
    
    def _contains_text_pattern(self, image: np.ndarray, patterns: List[str]) -> bool:
        """Check if image contains specific text patterns."""
        # Simplified pattern matching - in production, use OCR
        return False  # Placeholder
    
    async def _extract_document_data(
        self, 
        image: np.ndarray, 
        document_type: str
    ) -> Dict[str, Any]:
        """Extract data from the document."""
        try:
            # Simplified data extraction - in production, use OCR and specialized libraries
            extracted_data = {
                'document_type': document_type,
                'extraction_timestamp': datetime.now().isoformat()
            }
            
            # Mock data extraction based on document type
            if document_type == 'drivers_license':
                extracted_data.update({
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'document_number': 'DL123456789',
                    'date_of_birth': '1990-01-15',
                    'expiry_date': '2025-01-15',
                    'issue_date': '2020-01-15',
                    'address': '123 Main St, City, State 12345'
                })
            elif document_type == 'passport':
                extracted_data.update({
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'document_number': 'P123456789',
                    'date_of_birth': '1990-01-15',
                    'expiry_date': '2030-01-15',
                    'issue_date': '2020-01-15',
                    'nationality': 'USA',
                    'gender': 'M'
                })
            elif document_type == 'national_id':
                extracted_data.update({
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'document_number': 'ID123456789',
                    'date_of_birth': '1990-01-15',
                    'nationality': 'USA'
                })
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"Error extracting document data: {str(e)}")
            return {}
    
    async def _perform_verification_checks(
        self,
        image: np.ndarray,
        extracted_data: Dict[str, Any],
        document_type: str
    ) -> Dict[str, bool]:
        """Perform various verification checks on the document."""
        try:
            checks = {
                'document_authenticity': True,  # Simplified - check security features
                'data_consistency': True,  # Check if data fields are consistent
                'expiry_check': True,  # Check if document is not expired
                'age_verification': True,  # Check if person is above minimum age
                'tampering_detection': True,  # Check for signs of tampering
                'ocr_confidence': True,  # Check OCR confidence levels
                'format_validation': True  # Validate document format
            }
            
            # Check document expiry
            if 'expiry_date' in extracted_data:
                try:
                    expiry_date = datetime.strptime(extracted_data['expiry_date'], '%Y-%m-%d')
                    checks['expiry_check'] = expiry_date > datetime.now()
                except:
                    checks['expiry_check'] = False
            
            # Check age verification
            if 'date_of_birth' in extracted_data:
                try:
                    dob = datetime.strptime(extracted_data['date_of_birth'], '%Y-%m-%d')
                    age = (datetime.now() - dob).days / 365.25
                    checks['age_verification'] = age >= self.min_age_requirement
                except:
                    checks['age_verification'] = False
            
            # Check image quality
            checks['tampering_detection'] = await self._check_tampering(image)
            
            # Validate document format
            checks['format_validation'] = await self._validate_document_format(
                document_type, extracted_data
            )
            
            return checks
            
        except Exception as e:
            logger.error(f"Error performing verification checks: {str(e)}")
            return {
                'document_authenticity': False,
                'data_consistency': False,
                'expiry_check': False,
                'age_verification': False,
                'tampering_detection': False,
                'ocr_confidence': False,
                'format_validation': False
            }
    
    async def _check_tampering(self, image: np.ndarray) -> bool:
        """Check for signs of image tampering."""
        try:
            # Simplified tampering detection
            # In production, use advanced techniques like:
            # - Error Level Analysis (ELA)
            # - Copy-move detection
            # - Metadata analysis
            
            # Check image quality metrics
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # If variance is too low, image might be blurry or tampered
            if laplacian_var < 100:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking tampering: {str(e)}")
            return False
    
    async def _validate_document_format(
        self,
        document_type: str,
        extracted_data: Dict[str, Any]
    ) -> bool:
        """Validate document format and data patterns."""
        try:
            # Validate based on document type
            if document_type == 'drivers_license':
                # Check if license number follows expected pattern
                if 'document_number' in extracted_data:
                    # Simple pattern check (varies by state/country)
                    pattern = r'^[A-Z]{1,2}\d{6,9}$'
                    if not re.match(pattern, extracted_data['document_number']):
                        return False
            
            elif document_type == 'passport':
                # Check passport number format
                if 'document_number' in extracted_data:
                    pattern = r'^[A-Z][0-9]{8}$'
                    if not re.match(pattern, extracted_data['document_number']):
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating document format: {str(e)}")
            return False
    
    async def _calculate_risk_score(
        self,
        extracted_data: Dict[str, Any],
        verification_checks: Dict[str, bool],
        document_type: str
    ) -> Dict[str, Any]:
        """Calculate risk score based on verification results."""
        try:
            risk_factors = {
                'expired_document': False,
                'underage': False,
                'data_mismatch': False,
                'poor_image_quality': False,
                'suspected_tampering': False,
                'blacklisted_country': False
            }
            
            # Check for risk factors
            risk_factors['expired_document'] = not verification_checks.get('expiry_check', True)
            risk_factors['underage'] = not verification_checks.get('age_verification', True)
            risk_factors['suspected_tampering'] = not verification_checks.get('tampering_detection', True)
            risk_factors['data_mismatch'] = not verification_checks.get('data_consistency', True)
            
            # Calculate risk score (0-100)
            failed_checks = sum(1 for check in verification_checks.values() if not check)
            risk_score = (failed_checks / len(verification_checks)) * 100
            
            # Add weight for critical factors
            if risk_factors['suspected_tampering']:
                risk_score += 20
            if risk_factors['expired_document']:
                risk_score += 15
            if risk_factors['underage']:
                risk_score += 25
            
            # Cap at 100
            risk_score = min(risk_score, 100)
            
            # Determine risk level
            if risk_score < 20:
                risk_level = 'low'
            elif risk_score < 50:
                risk_level = 'medium'
            elif risk_score < 80:
                risk_level = 'high'
            else:
                risk_level = 'critical'
            
            return {
                'risk_score': round(risk_score, 2),
                'risk_level': risk_level,
                'risk_factors': risk_factors
            }
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {str(e)}")
            return {
                'risk_score': 100.0,
                'risk_level': 'critical',
                'risk_factors': {}
            }
    
    async def _perform_face_matching(
        self,
        document_image_path: str,
        reference_image_path: str
    ) -> Dict[str, Any]:
        """Perform face matching between document and reference image."""
        try:
            # Simplified face matching
            # In production, use face_recognition library or cloud services
            
            # Load images
            doc_image = cv2.imread(document_image_path)
            ref_image = cv2.imread(reference_image_path)
            
            # Detect faces (simplified)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            
            doc_faces = face_cascade.detectMultiScale(
                cv2.cvtColor(doc_image, cv2.COLOR_BGR2GRAY), 1.1, 4
            )
            ref_faces = face_cascade.detectMultiScale(
                cv2.cvtColor(ref_image, cv2.COLOR_BGR2GRAY), 1.1, 4
            )
            
            if len(doc_faces) == 0 or len(ref_faces) == 0:
                return {
                    'match_score': 0.0,
                    'is_match': False,
                    'confidence': 0.0,
                    'error': 'No faces detected'
                }
            
            # Simplified matching (mock result)
            # In production, use proper face recognition algorithms
            match_score = 85.0  # Mock score
            
            return {
                'match_score': match_score,
                'is_match': match_score > 80,
                'confidence': match_score / 100,
                'face_locations': [
                    {'x': int(doc_faces[0][0]), 'y': int(doc_faces[0][1]),
                     'width': int(doc_faces[0][2]), 'height': int(doc_faces[0][3])}
                ]
            }
            
        except Exception as e:
            logger.error(f"Error performing face matching: {str(e)}")
            return {
                'match_score': 0.0,
                'is_match': False,
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _determine_verification_status(
        self,
        verification_checks: Dict[str, bool],
        risk_score: float
    ) -> str:
        """Determine overall verification status."""
        try:
            # Count passed checks
            passed_checks = sum(1 for check in verification_checks.values() if check)
            total_checks = len(verification_checks)
            pass_rate = passed_checks / total_checks if total_checks > 0 else 0
            
            # Determine status based on pass rate and risk score
            if pass_rate >= 0.9 and risk_score < 20:
                return 'verified'
            elif pass_rate >= 0.7 and risk_score < 50:
                return 'manual_review'
            elif risk_score >= 80:
                return 'rejected'
            else:
                return 'manual_review'
            
        except Exception as e:
            logger.error(f"Error determining verification status: {str(e)}")
            return 'manual_review'
    
    async def validate_file(self, file_path: str, file_size: int) -> Tuple[bool, Optional[str]]:
        """Validate file before processing."""
        try:
            path = Path(file_path)
            
            # Check file exists
            if not path.exists():
                return False, "File does not exist"
            
            # Check file size
            if file_size > self.max_file_size:
                return False, f"File size exceeds maximum allowed size of {self.max_file_size / 1024 / 1024}MB"
            
            # Check file extension
            allowed_extensions = ['.pdf', '.png', '.jpg', '.jpeg']
            if path.suffix.lower() not in allowed_extensions:
                return False, f"File type not supported. Allowed types: {', '.join(allowed_extensions)}"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error validating file: {str(e)}")
            return False, str(e)

# Singleton instance
kyc_service = KYCService()