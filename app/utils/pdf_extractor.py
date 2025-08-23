"""
PDF text extraction utilities for CV processing
"""
import io
import logging
from typing import Optional, Dict, Any
import pdfplumber
import PyPDF2

logger = logging.getLogger(__name__)

class PDFTextExtractor:
    """Utility class for extracting text from PDF files"""
    
    @staticmethod
    def extract_text_from_pdf(pdf_content: bytes) -> Dict[str, Any]:
        """
        Extract text from PDF content using multiple methods
        
        Args:
            pdf_content: Raw PDF file content as bytes
            
        Returns:
            Dict containing extracted text and metadata
        """
        result = {
            "text": "",
            "method": "",
            "success": False,
            "error": None,
            "pages": 0,
            "char_count": 0
        }
        
        try:
            # Method 1: Try pdfplumber first (better for complex layouts)
            text = PDFTextExtractor._extract_with_pdfplumber(pdf_content)
            if text and len(text.strip()) > 50:  # Minimum text threshold
                result.update({
                    "text": text,
                    "method": "pdfplumber",
                    "success": True,
                    "char_count": len(text)
                })
                logger.info(f"✅ Successfully extracted {len(text)} characters using pdfplumber")
                return result
            
            # Method 2: Fallback to PyPDF2 (simpler but more reliable for basic PDFs)
            text = PDFTextExtractor._extract_with_pypdf2(pdf_content)
            if text and len(text.strip()) > 50:
                result.update({
                    "text": text,
                    "method": "PyPDF2",
                    "success": True,
                    "char_count": len(text)
                })
                logger.info(f"✅ Successfully extracted {len(text)} characters using PyPDF2")
                return result
            
            # If both methods produce minimal text
            if text:
                result.update({
                    "text": text,
                    "method": "PyPDF2_minimal",
                    "success": True,
                    "char_count": len(text),
                    "error": "Extracted text is very short - PDF may be image-based or poorly formatted"
                })
                logger.warning("⚠️ Extracted text is minimal - possible image-based PDF")
                return result
            
            result["error"] = "No text could be extracted from PDF"
            logger.error("❌ Failed to extract any text from PDF")
            
        except Exception as e:
            result["error"] = f"PDF extraction failed: {str(e)}"
            logger.error(f"❌ PDF extraction error: {e}")
        
        return result
    
    @staticmethod
    def _extract_with_pdfplumber(pdf_content: bytes) -> Optional[str]:
        """Extract text using pdfplumber library"""
        try:
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                
                full_text = "\n".join(text_parts)
                return full_text.strip()
                
        except Exception as e:
            logger.warning(f"⚠️ pdfplumber extraction failed: {e}")
            return None
    
    @staticmethod
    def _extract_with_pypdf2(pdf_content: bytes) -> Optional[str]:
        """Extract text using PyPDF2 library"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
            text_parts = []
            
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            full_text = "\n".join(text_parts)
            return full_text.strip()
            
        except Exception as e:
            logger.warning(f"⚠️ PyPDF2 extraction failed: {e}")
            return None
    
    @staticmethod
    def validate_pdf_content(pdf_content: bytes) -> bool:
        """
        Validate that the content is a valid PDF file
        
        Args:
            pdf_content: Raw file content as bytes
            
        Returns:
            bool: True if valid PDF, False otherwise
        """
        if not pdf_content:
            return False
        
        # Check PDF magic number
        if pdf_content.startswith(b'%PDF-'):
            return True
        
        return False
    
    @staticmethod
    def get_pdf_info(pdf_content: bytes) -> Dict[str, Any]:
        """
        Get basic information about the PDF
        
        Args:
            pdf_content: Raw PDF file content as bytes
            
        Returns:
            Dict containing PDF metadata
        """
        info = {
            "valid": False,
            "pages": 0,
            "size_bytes": len(pdf_content),
            "title": None,
            "author": None,
            "creator": None,
            "producer": None
        }
        
        try:
            if not PDFTextExtractor.validate_pdf_content(pdf_content):
                return info
            
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
            info["valid"] = True
            info["pages"] = len(pdf_reader.pages)
            
            # Get metadata if available
            if pdf_reader.metadata:
                info["title"] = pdf_reader.metadata.get('/Title')
                info["author"] = pdf_reader.metadata.get('/Author')
                info["creator"] = pdf_reader.metadata.get('/Creator')
                info["producer"] = pdf_reader.metadata.get('/Producer')
            
        except Exception as e:
            logger.warning(f"⚠️ Could not get PDF info: {e}")
        
        return info

def extract_cv_text_from_pdf(pdf_content: bytes) -> Dict[str, Any]:
    """
    Main function to extract CV text from PDF content
    
    Args:
        pdf_content: Raw PDF file content as bytes
        
    Returns:
        Dict with extraction results and metadata
    """
    extractor = PDFTextExtractor()
    
    # Get PDF info first
    pdf_info = extractor.get_pdf_info(pdf_content)
    
    if not pdf_info["valid"]:
        return {
            "success": False,
            "error": "Invalid PDF file format",
            "text": "",
            "pdf_info": pdf_info
        }
    
    # Extract text
    extraction_result = extractor.extract_text_from_pdf(pdf_content)
    
    # Combine results
    result = {
        **extraction_result,
        "pdf_info": pdf_info
    }
    
    logger.info(f"📄 PDF Processing Summary: {pdf_info['pages']} pages, "
                f"{extraction_result['char_count']} chars extracted using {extraction_result['method']}")
    
    return result