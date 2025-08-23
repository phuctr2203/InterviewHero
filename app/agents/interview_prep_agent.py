from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
import json
import PyPDF2
import io
from app.services.openai_client import client, AZURE_OPENAI_DEPLOYMENT

router = APIRouter()

class InterviewPrepRequest(BaseModel):
    candidate_name: str
    cv_text: str
    job_description: str
    position_title: str = "Software Engineer"
    interview_duration: int = 25  # minutes
    focus_areas: Optional[List[str]] = None  # e.g., ["technical_background", "cultural_fit", "motivation"]

class QuestionCategory(BaseModel):
    category: str
    questions: List[str]
    estimated_time: int  # minutes

class InterviewPrepResponse(BaseModel):
    candidate_name: str
    position_title: str
    total_estimated_time: int
    question_categories: List[QuestionCategory]
    key_focus_areas: List[str]
    candidate_highlights: List[str]
    potential_concerns: List[str]

def generate_interview_questions_prompt(candidate_name: str, cv_text: str, job_description: str, 
                                       position_title: str, duration: int, focus_areas: List[str] = None):
    focus_areas_text = ", ".join(focus_areas) if focus_areas else "general HR screening"
    
    return f"""
You are an experienced HR interviewer. Create a comprehensive interview question set for a {duration}-minute screening interview.

CANDIDATE: {candidate_name}
POSITION: {position_title}

CANDIDATE CV:
{cv_text}

JOB DESCRIPTION:
{job_description}

FOCUS AREAS: {focus_areas_text}

Create interview questions that:
1. Fit within {duration} minutes (allow 2-3 minutes per question)
2. Help assess cultural fit, motivation, and basic qualifications
3. Are specific to the candidate's background and the job requirements
4. Include both behavioral and situational questions
5. Avoid deep technical questions (this is HR screening, not technical round)

Return JSON with:
{{
    "total_estimated_time": {duration},
    "question_categories": [
        {{
            "category": "Background & Experience",
            "questions": ["question 1", "question 2", ...],
            "estimated_time": 8
        }},
        {{
            "category": "Motivation & Interest",
            "questions": ["question 1", "question 2", ...],
            "estimated_time": 6
        }},
        {{
            "category": "Cultural Fit & Working Style",
            "questions": ["question 1", "question 2", ...],
            "estimated_time": 7
        }},
        {{
            "category": "Situational & Behavioral",
            "questions": ["question 1", "question 2", ...],
            "estimated_time": 4
        }}
    ],
    "key_focus_areas": ["area1", "area2", "area3"],
    "candidate_highlights": ["highlight1", "highlight2", "highlight3"],
    "potential_concerns": ["concern1", "concern2"]
}}

Make questions:
- Specific to the candidate's experience mentioned in CV
- Relevant to the job requirements
- Open-ended to encourage discussion
- Professional but conversational
- Designed to reveal personality, work style, and motivations

Output JSON only, no explanation.
"""

def extract_text_from_pdf(pdf_file: UploadFile) -> str:
    """Extract text content from PDF file"""
    try:
        # Read the PDF file
        pdf_content = pdf_file.file.read()
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
        
        # Extract text from all pages
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        
        # Reset file pointer for potential reuse
        pdf_file.file.seek(0)
        
        return text.strip()
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract text from PDF: {str(e)}")

async def validate_pdf_file(file: UploadFile):
    """Validate that the uploaded file is a PDF"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    if file.content_type != 'application/pdf':
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a PDF file")
    
    # Check file size (limit to 10MB)
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB")

@router.post("/generate-questions", response_model=InterviewPrepResponse)
async def generate_interview_questions(req: InterviewPrepRequest):
    """Generate targeted interview questions based on CV and job description"""
    try:
        # Generate interview questions using AI
        prompt = generate_interview_questions_prompt(
            candidate_name=req.candidate_name,
            cv_text=req.cv_text,
            job_description=req.job_description,
            position_title=req.position_title,
            duration=req.interview_duration,
            focus_areas=req.focus_areas
        )
        
        resp = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # Slight creativity for varied questions
        )
        
        # Parse AI response
        ai_response = resp.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if ai_response.startswith('```json'):
            ai_response = ai_response.replace('```json', '').replace('```', '').strip()
        elif ai_response.startswith('```'):
            ai_response = ai_response.replace('```', '').strip()
        
        questions_data = json.loads(ai_response)
        
        # Structure the response
        return InterviewPrepResponse(
            candidate_name=req.candidate_name,
            position_title=req.position_title,
            total_estimated_time=questions_data.get('total_estimated_time', req.interview_duration),
            question_categories=[
                QuestionCategory(**category) for category in questions_data.get('question_categories', [])
            ],
            key_focus_areas=questions_data.get('key_focus_areas', []),
            candidate_highlights=questions_data.get('candidate_highlights', []),
            potential_concerns=questions_data.get('potential_concerns', [])
        )
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate interview questions: {str(e)}")

@router.post("/generate-from-pdf", response_model=InterviewPrepResponse)
async def generate_questions_from_pdf(
    cv_file: UploadFile = File(..., description="PDF file containing candidate's CV"),
    candidate_name: str = Form(..., description="Candidate's full name"),
    job_description: str = Form(..., description="Job description text"),
    position_title: str = Form(default="Software Engineer", description="Position title"),
    interview_duration: int = Form(default=25, description="Interview duration in minutes"),
    focus_areas: Optional[str] = Form(default=None, description="Comma-separated focus areas (e.g., 'technical_background,cultural_fit')")
):
    """Generate interview questions from PDF CV and job description text"""
    
    # Validate PDF file
    await validate_pdf_file(cv_file)
    
    try:
        # Extract text from PDF
        cv_text = extract_text_from_pdf(cv_file)
        
        if not cv_text or len(cv_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="Could not extract sufficient text from PDF. Please ensure the PDF contains readable text.")
        
        # Parse focus areas
        focus_areas_list = None
        if focus_areas:
            focus_areas_list = [area.strip() for area in focus_areas.split(',') if area.strip()]
        
        # Create request object
        req = InterviewPrepRequest(
            candidate_name=candidate_name,
            cv_text=cv_text,
            job_description=job_description,
            position_title=position_title,
            interview_duration=interview_duration,
            focus_areas=focus_areas_list
        )
        
        # Generate questions using the existing logic
        return await generate_interview_questions(req)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF and generate questions: {str(e)}")

@router.post("/quick-prep")
async def quick_interview_prep(
    candidate_name: str,
    cv_text: str,
    job_title: str = "Software Engineer",
    company_info: str = "Tech startup focused on innovation"
):
    """Quick interview prep with minimal job description"""
    
    # Create a basic job description if not provided
    basic_job_description = f"""
Position: {job_title}
Company: {company_info}

We are looking for a motivated {job_title} to join our team. 
Key requirements:
- Relevant experience in the field
- Strong communication skills
- Ability to work in a team environment
- Problem-solving mindset
- Willingness to learn and grow

This is an exciting opportunity to contribute to innovative projects and grow your career.
"""
    
    req = InterviewPrepRequest(
        candidate_name=candidate_name,
        cv_text=cv_text,
        job_description=basic_job_description,
        position_title=job_title,
        interview_duration=25,
        focus_areas=["background_check", "motivation", "cultural_fit"]
    )
    
    return await generate_interview_questions(req)

@router.get("/sample-questions/{position}")
async def get_sample_questions(position: str):
    """Get sample interview questions for a specific position"""
    
    sample_questions = {
        "software_engineer": {
            "Background & Experience": [
                "Walk me through your experience with [specific technology from CV]",
                "What project are you most proud of and why?",
                "How do you stay updated with new technologies?"
            ],
            "Motivation & Interest": [
                "What interests you about this position?",
                "Where do you see yourself in 3-5 years?",
                "What motivates you in your work?"
            ],
            "Cultural Fit": [
                "How do you handle working in a team?",
                "Describe a time you had to learn something quickly",
                "How do you manage competing priorities?"
            ]
        },
        "product_manager": {
            "Background & Experience": [
                "Tell me about a product you've managed from start to finish",
                "How do you prioritize features?",
                "Describe your experience with stakeholder management"
            ],
            "Motivation & Interest": [
                "What draws you to product management?",
                "How do you define product success?",
                "What's your approach to user research?"
            ],
            "Cultural Fit": [
                "How do you handle conflicting feedback from stakeholders?",
                "Describe a time you had to make a difficult product decision",
                "How do you work with engineering teams?"
            ]
        }
    }
    
    position_key = position.lower().replace(" ", "_")
    if position_key not in sample_questions:
        position_key = "software_engineer"  # Default fallback
    
    return {
        "position": position,
        "sample_questions": sample_questions[position_key],
        "estimated_time": "20-30 minutes",
        "note": "These are general questions. Use /generate-questions for personalized questions based on specific CV and job description."
    }