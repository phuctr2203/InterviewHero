from fastapi import APIRouter, UploadFile, HTTPException, Form
from app.services.openai_client import client, extract_cv_prompt, AZURE_OPENAI_DEPLOYMENT
from app.utils.pdf_extractor import extract_cv_text_from_pdf
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/extract")
async def extract(file: UploadFile):
    """
    Extract and structure CV data from uploaded file (supports PDF and text files)
    """
    try:
        # Read file content
        raw_content = await file.read()
        
        if not raw_content:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        # Determine file type and extract text accordingly
        filename = file.filename.lower() if file.filename else ""
        cv_text = ""
        extraction_method = ""
        
        if filename.endswith('.pdf'):
            # Handle PDF files
            logger.info(f"📄 Processing PDF file: {file.filename} ({len(raw_content)} bytes)")
            
            pdf_result = extract_cv_text_from_pdf(raw_content)
            
            if not pdf_result["success"]:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Failed to extract text from PDF: {pdf_result.get('error', 'Unknown error')}"
                )
            
            cv_text = pdf_result["text"]
            extraction_method = f"PDF ({pdf_result['method']}, {pdf_result['pdf_info']['pages']} pages)"
            
            if len(cv_text.strip()) < 50:
                raise HTTPException(
                    status_code=400, 
                    detail="PDF contains insufficient text. It may be image-based or corrupted."
                )
                
        else:
            # Handle text files
            try:
                cv_text = raw_content.decode('utf-8', errors="ignore")
                extraction_method = "Text file"
                logger.info(f"📝 Processing text file: {file.filename} ({len(cv_text)} characters)")
            except Exception as e:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Could not read file as text: {str(e)}"
                )
        
        if not cv_text or len(cv_text.strip()) < 20:
            raise HTTPException(
                status_code=400, 
                detail="File contains insufficient text content for CV analysis"
            )
        
        # Use OpenAI to extract structured data
        logger.info(f"🤖 Analyzing CV with GPT-4o ({len(cv_text)} characters)")
        
        prompt = extract_cv_prompt(cv_text)
        resp = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        
        structured_data = resp.choices[0].message.content
        
        logger.info(f"✅ CV extraction completed successfully")
        
        return {
            "cv_structured": structured_data,
            "extraction_method": extraction_method,
            "text_length": len(cv_text),
            "filename": file.filename
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"❌ CV extraction error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/analyze-pdf")
async def analyze_pdf_cv(file: UploadFile, candidate_email: str = Form(...)):
    """
    Analyze PDF CV and create interview questions (integrates with the multi-agent system)
    """
    try:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported for this endpoint")
        
        # Read and extract PDF content
        raw_content = await file.read()
        pdf_result = extract_cv_text_from_pdf(raw_content)
        
        if not pdf_result["success"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to extract text from PDF: {pdf_result.get('error', 'Unknown error')}"
            )
        
        cv_text = pdf_result["text"]
        
        # Import agent manager here to trigger CV analysis
        from app.core.agent_manager import agent_manager, AgentType
        
        # Initialize agent manager if needed
        if not agent_manager.agents:
            await agent_manager.initialize()
        
        # Create a task to analyze the CV
        task_id = await agent_manager.assign_task(
            AgentType.CV_ANALYZER,
            "analyze_cv",
            {
                "candidate_email": candidate_email,
                "cv_text": cv_text,
                "filename": file.filename,
                "extraction_info": {
                    "method": pdf_result["method"],
                    "pages": pdf_result["pdf_info"]["pages"],
                    "char_count": pdf_result["char_count"]
                }
            }
        )
        
        return {
            "status": "success",
            "message": "PDF CV analysis started",
            "task_id": task_id,
            "pdf_info": pdf_result["pdf_info"],
            "text_length": len(cv_text),
            "filename": file.filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ PDF CV analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
