from fastapi import APIRouter, Query
from pydantic import BaseModel, EmailStr
from app.services.gmail_client import get_latest_reply_in_thread
from app.services.openai_client import client, parse_availability_prompt, AZURE_OPENAI_DEPLOYMENT

router = APIRouter()

class ReplyParse(BaseModel):
    thread_id: str
    from_email: EmailStr | None = None

@router.get("/check_reply")
async def check_reply(thread_id: str = Query(...), from_email: EmailStr | None = Query(None)):
    text = get_latest_reply_in_thread(thread_id, str(from_email) if from_email else None)
    if not text:
        return {"found": False, "message": "No reply found yet for this thread."}
    prompt = parse_availability_prompt(text)
    resp = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    return {"found": True, "reply_text": text, "parsed_availability": resp.choices[0].message.content}
