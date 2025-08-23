import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# Azure OpenAI configuration
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://neith-memu4trw-eastus2.cognitiveservices.azure.com")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

if not AZURE_OPENAI_API_KEY:
    raise RuntimeError("AZURE_OPENAI_API_KEY missing. Put it in .env")

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION
)

def generate_email_prompt(name: str, email: str, position: str, job_title: str):
    return f"""
You are a professional HR assistant. Draft a concise, polite email to {name} ({email})
to schedule a 20–30 minute screening interview for the {job_title} position.
Ask for 2–3 time windows over the next 5 business days, confirm timezone,
and mention the interview will be via Google Meet.
Keep it under 140 words. Use plain text. No need to include information about the company or sender because you are an AI Recruiter.
"""

def parse_availability_prompt(reply_text: str):
    return f"""
Extract interview availability from the following email text.
Return strict JSON with keys: date (YYYY-MM-DD), time (HH:MM), timezone (IANA, if present or infer), flexibility (true/false), notes.
If multiple options exist, return an array in 'options' with the same fields.
Email Reply:
{reply_text}
Output JSON only, no explanation.
"""

def extract_cv_prompt(cv_text: str):
    return f"""
You are an HR data extractor. Read the CV text below and return strict JSON with:
name, email, phone?, position?, years_experience?, skills[] (top 8), summary (1-2 sentences)
CV:
{cv_text}
Output JSON only, no explanation.
"""

def is_candidate_response_prompt(subject: str, body: str):
    return f"""
You are an HR assistant. Analyze this email to determine if it's a candidate responding to an interview scheduling request.

Email Subject: {subject}
Email Body: {body}

Look for:
1. Is this a response to an interview/screening request?
2. Does the candidate provide availability, time preferences, or scheduling information?
3. Is this someone responding about interview timing/scheduling?

Return JSON with:
{{
    "is_candidate_response": true/false,
    "confidence": 0.0-1.0,
    "reason": "brief explanation why",
    "contains_availability": true/false
}}

Output JSON only, no explanation.
"""
