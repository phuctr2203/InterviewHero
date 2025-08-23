from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from app.core.agent_manager import agent_manager, AgentType
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class InterviewAnalysisRequest(BaseModel):
    conversation_text: str
    candidate_name: str
    position: str = "Software Engineer"

class InterviewAnalysisResponse(BaseModel):
    candidate_name: str
    position: str
    questions_answers: List[Dict[str, Any]]
    evaluation: Dict[str, Any]
    processed_at: str

@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_interview_conversation(request: InterviewAnalysisRequest):
    """Analyze an interview conversation and provide detailed evaluation"""
    
    try:
        # Initialize agent manager if needed
        if not agent_manager.agents:
            await agent_manager.initialize()
        
        # Get the interview analyzer agent
        interview_analyzer = agent_manager.agents.get(AgentType.INTERVIEW_ANALYZER)
        
        if not interview_analyzer:
            raise HTTPException(status_code=500, detail="Interview analyzer agent not available")
        
        # Prepare data for analysis
        analysis_data = {
            "conversation_text": request.conversation_text,
            "candidate_name": request.candidate_name,
            "position": request.position
        }
        
        # Analyze the interview
        result = await interview_analyzer.analyze_interview(analysis_data)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "status": "success",
            "analysis": result
        }
        
    except Exception as e:
        logger.error(f"Error analyzing interview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_analyzer_status():
    """Get the status of the interview analyzer agent"""
    
    try:
        # Initialize agent manager if needed
        if not agent_manager.agents:
            await agent_manager.initialize()
        
        interview_analyzer = agent_manager.agents.get(AgentType.INTERVIEW_ANALYZER)
        
        if not interview_analyzer:
            return {
                "status": "error",
                "message": "Interview analyzer agent not available"
            }
        
        return {
            "status": "active",
            "agent_type": "interview_analyzer",
            "is_active": interview_analyzer.is_active,
            "queue_size": interview_analyzer.message_queue.qsize()
        }
        
    except Exception as e:
        logger.error(f"Error getting analyzer status: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@router.post("/task", response_model=Dict[str, Any])
async def create_analysis_task(request: InterviewAnalysisRequest):
    """Create a new interview analysis task"""
    
    try:
        # Initialize agent manager if needed
        if not agent_manager.agents:
            await agent_manager.initialize()
        
        # Create task data
        task_data = {
            "conversation_text": request.conversation_text,
            "candidate_name": request.candidate_name,
            "position": request.position
        }
        
        # Assign task to the interview analyzer agent
        task_id = await agent_manager.assign_task(
            AgentType.INTERVIEW_ANALYZER,
            "analyze_interview",
            task_data
        )
        
        return {
            "status": "success",
            "message": "Interview analysis task created",
            "task_id": task_id
        }
        
    except Exception as e:
        logger.error(f"Error creating analysis task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a specific analysis task"""
    
    try:
        task = agent_manager.tasks.get(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {
            "task_id": task_id,
            "status": task.status,
            "created_at": task.created_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "result": task.result if task.status in ["completed", "failed"] else None
        }
        
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks")
async def list_analysis_tasks():
    """List all interview analysis tasks"""
    
    try:
        interview_tasks = []
        
        for task_id, task in agent_manager.tasks.items():
            if task.agent_type == AgentType.INTERVIEW_ANALYZER:
                interview_tasks.append({
                    "task_id": task_id,
                    "status": task.status,
                    "created_at": task.created_at.isoformat(),
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "candidate_name": task.data.get("candidate_name", "Unknown"),
                    "position": task.data.get("position", "Unknown")
                })
        
        return {
            "status": "success",
            "total_tasks": len(interview_tasks),
            "tasks": interview_tasks
        }
        
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))