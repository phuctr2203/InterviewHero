"""
Agent System API - Controls the multi-agent system
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import asyncio
from app.core.agent_manager import agent_manager, AgentType, MessageType

router = APIRouter()

class TaskRequest(BaseModel):
    agent_type: str
    task_type: str
    data: Dict[str, Any]

class MessageRequest(BaseModel):
    from_agent: str
    to_agent: str
    message_type: str
    content: Dict[str, Any]
    priority: int = 1

class CandidateWorkflowRequest(BaseModel):
    candidate_name: str
    candidate_email: str
    cv_text: Optional[str] = None
    job_description: Optional[str] = None
    position_title: str = "Software Engineer"

@router.post("/start")
async def start_agent_system(background_tasks: BackgroundTasks):
    """Start the multi-agent system"""
    if agent_manager.is_running:
        return {"status": "already_running", "message": "Agent system is already running"}
    
    # Initialize agents if not done
    if not agent_manager.agents:
        await agent_manager.initialize()
    
    # Start all agents in background
    background_tasks.add_task(agent_manager.start_all_agents)
    
    # Give agents time to start
    await asyncio.sleep(1)
    
    return {
        "status": "started",
        "message": "Multi-agent system started",
        "agents": list(agent_manager.agents.keys())
    }

@router.post("/stop")
async def stop_agent_system():
    """Stop the multi-agent system"""
    if not agent_manager.is_running:
        return {"status": "not_running", "message": "Agent system is not running"}
    
    await agent_manager.stop_all_agents()
    
    return {"status": "stopped", "message": "Multi-agent system stopped"}

@router.get("/status")
async def get_system_status():
    """Get status of the agent system"""
    return {
        "system_status": agent_manager.get_agent_status(),
        "agent_types": [agent_type.value for agent_type in AgentType],
        "message_types": [msg_type.value for msg_type in MessageType]
    }

@router.get("/messages")
async def get_message_history(limit: int = 10):
    """Get recent message history between agents"""
    return {
        "messages": agent_manager.get_message_history(limit),
        "total_messages": len(agent_manager.message_history)
    }

@router.post("/assign-task")
async def assign_task(task_request: TaskRequest):
    """Assign a task to a specific agent"""
    try:
        agent_type = AgentType(task_request.agent_type)
        
        task_id = await agent_manager.assign_task(
            agent_type=agent_type,
            task_type=task_request.task_type,
            data=task_request.data
        )
        
        return {
            "status": "task_assigned",
            "task_id": task_id,
            "agent": agent_type.value,
            "task_type": task_request.task_type
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid agent type: {task_request.agent_type}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to assign task: {str(e)}")

@router.post("/send-message")
async def send_message(message_request: MessageRequest):
    """Send a message between agents"""
    try:
        from_agent = AgentType(message_request.from_agent)
        to_agent = AgentType(message_request.to_agent)
        message_type = MessageType(message_request.message_type)
        
        # Get the source agent and send message
        source_agent = agent_manager.agents.get(from_agent)
        if not source_agent:
            raise HTTPException(status_code=404, detail=f"Source agent {from_agent.value} not found")
        
        await source_agent.send_message(
            to_agent=to_agent,
            message_type=message_type,
            content=message_request.content,
            priority=message_request.priority
        )
        
        return {
            "status": "message_sent",
            "from": from_agent.value,
            "to": to_agent.value,
            "type": message_type.value
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid enum value: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

@router.post("/workflows/candidate-screening")
async def start_candidate_screening_workflow(request: CandidateWorkflowRequest):
    """Start a complete candidate screening workflow"""
    if not agent_manager.is_running:
        raise HTTPException(status_code=400, detail="Agent system is not running. Start it first with /start")
    
    try:
        # Step 1: Assign recruiter to send availability request
        task_id = await agent_manager.assign_task(
            agent_type=AgentType.RECRUITER,
            task_type="send_availability_request",
            data={
                "candidate_name": request.candidate_name,
                "candidate_email": request.candidate_email,
                "position_title": request.position_title
            }
        )
        
        # Step 2: If CV provided, analyze it
        cv_analysis_task = None
        if request.cv_text:
            cv_analysis_task = await agent_manager.assign_task(
                agent_type=AgentType.CV_ANALYZER,
                task_type="analyze_cv",
                data={
                    "candidate_email": request.candidate_email,
                    "cv_text": request.cv_text,
                    "job_description": request.job_description
                }
            )
        
        return {
            "status": "workflow_started",
            "workflow_type": "candidate_screening",
            "candidate": {
                "name": request.candidate_name,
                "email": request.candidate_email,
                "position": request.position_title
            },
            "tasks": {
                "availability_request": task_id,
                "cv_analysis": cv_analysis_task
            },
            "next_steps": [
                "Recruiter will send availability request",
                "Email monitor will watch for candidate response",
                "Scheduler will process availability and confirm meeting",
                "Interviewer will prepare questions based on CV analysis"
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")

@router.get("/workflows/active")
async def get_active_workflows():
    """Get information about active workflows"""
    active_tasks = [
        {
            "task_id": task.id,
            "agent": task.agent_type.value,
            "type": task.task_type,
            "status": task.status,
            "created_at": task.created_at.isoformat() if task.created_at else None
        }
        for task in agent_manager.tasks.values()
        if task.status in ["pending", "in_progress"]
    ]
    
    return {
        "active_workflows": len(active_tasks),
        "tasks": active_tasks,
        "total_tasks": len(agent_manager.tasks)
    }

@router.get("/agents/{agent_type}")
async def get_agent_info(agent_type: str):
    """Get detailed information about a specific agent"""
    try:
        agent_enum = AgentType(agent_type)
        agent = agent_manager.agents.get(agent_enum)
        
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_type} not found")
        
        # Get agent-specific tasks
        agent_tasks = [
            {
                "task_id": task.id,
                "type": task.task_type,
                "status": task.status,
                "created_at": task.created_at.isoformat() if task.created_at else None
            }
            for task in agent_manager.tasks.values()
            if task.agent_type == agent_enum
        ]
        
        return {
            "agent_type": agent_type,
            "is_active": agent.is_active,
            "queue_size": agent.message_queue.qsize(),
            "tasks": {
                "total": len(agent_tasks),
                "pending": len([t for t in agent_tasks if t["status"] == "pending"]),
                "in_progress": len([t for t in agent_tasks if t["status"] == "in_progress"]),
                "completed": len([t for t in agent_tasks if t["status"] == "completed"])
            },
            "recent_tasks": agent_tasks[-5:]  # Last 5 tasks
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid agent type: {agent_type}")

@router.get("/tasks/{task_id}")
async def get_task_details(task_id: str):
    """Get detailed information about a specific task"""
    task = agent_manager.tasks.get(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return {
        "task_id": task.id,
        "agent_type": task.agent_type.value,
        "task_type": task.task_type,
        "status": task.status,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "data": task.data,
        "result": task.result
    }

@router.get("/tasks/{task_id}/interview-questions")
async def get_interview_questions(task_id: str):
    """Get interview questions generated from CV analysis task"""
    task = agent_manager.tasks.get(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    if task.task_type != "analyze_cv":
        raise HTTPException(status_code=400, detail="This endpoint is only for CV analysis tasks")
    
    if task.status != "completed":
        return {"status": task.status, "message": "Task not yet completed"}
    
    if not task.result or "interview_questions" not in task.result:
        raise HTTPException(status_code=404, detail="No interview questions found for this task")
    
    return {
        "task_id": task_id,
        "candidate_name": task.result.get("candidate_name"),
        "candidate_email": task.result.get("candidate_email"),
        "estimated_duration": task.result.get("estimated_duration", "30 minutes"),
        "interview_focus_areas": task.result.get("interview_focus_areas", []),
        "interview_questions": task.result.get("interview_questions", []),
        "cv_summary": {
            "key_skills": task.result.get("key_skills", []),
            "experience_years": task.result.get("experience_years", 0),
            "education": task.result.get("education", ""),
            "highlights": task.result.get("highlights", []),
            "match_score": task.result.get("match_score", 0),
            "summary": task.result.get("summary", "")
        }
    }

@router.get("/interview-questions/{candidate_email}")
async def get_interview_questions_by_email(candidate_email: str):
    """Get interview questions for a candidate by email"""
    # Find CV analysis task for this candidate
    cv_task = None
    for task in agent_manager.tasks.values():
        if (task.task_type == "analyze_cv" and 
            task.data.get("candidate_email") == candidate_email and
            task.status == "completed"):
            cv_task = task
            break
    
    if not cv_task:
        raise HTTPException(status_code=404, detail=f"No completed CV analysis found for {candidate_email}")
    
    if not cv_task.result or "interview_questions" not in cv_task.result:
        raise HTTPException(status_code=404, detail="No interview questions found for this candidate")
    
    return {
        "candidate_email": candidate_email,
        "candidate_name": cv_task.result.get("candidate_name"),
        "task_id": cv_task.id,
        "estimated_duration": cv_task.result.get("estimated_duration", "30 minutes"),
        "interview_focus_areas": cv_task.result.get("interview_focus_areas", []),
        "interview_questions": cv_task.result.get("interview_questions", []),
        "cv_analysis": {
            "key_skills": cv_task.result.get("key_skills", []),
            "experience_years": cv_task.result.get("experience_years", 0),
            "education": cv_task.result.get("education", ""),
            "highlights": cv_task.result.get("highlights", []),
            "match_score": cv_task.result.get("match_score", 0),
            "summary": cv_task.result.get("summary", "")
        }
    }

@router.get("/email-monitor/status")
async def get_email_monitor_status():
    """Get email monitor status and monitored threads"""
    email_monitor = agent_manager.agents.get(AgentType.EMAIL_MONITOR)
    
    if not email_monitor:
        raise HTTPException(status_code=404, detail="Email monitor agent not found")
    
    return {
        "is_active": email_monitor.is_active,
        "is_monitoring": email_monitor.monitoring,
        "monitored_threads": {
            thread_id: candidate_email 
            for thread_id, candidate_email in email_monitor.monitored_threads.items()
        },
        "total_monitored": len(email_monitor.monitored_threads),
        "queue_size": email_monitor.message_queue.qsize()
    }

@router.post("/test/simulate-email-response")
async def simulate_candidate_email_response(
    candidate_email: str,
    availability_text: str = "I'm available Monday at 2 PM UTC for the interview"
):
    """Simulate a candidate email response for testing"""
    if not agent_manager.is_running:
        raise HTTPException(status_code=400, detail="Agent system is not running")
    
    # Simulate email monitor detecting a response
    email_monitor = agent_manager.agents.get(AgentType.EMAIL_MONITOR)
    if not email_monitor:
        raise HTTPException(status_code=404, detail="Email monitor agent not found")
    
    # Simulate processing the email
    await email_monitor.process_candidate_email({
        "from": candidate_email,
        "body": availability_text,
        "parsed_availability": {
            "date": "2024-08-26",
            "time": "14:00",
            "timezone": "UTC"
        }
    })
    
    return {
        "status": "email_simulated",
        "candidate_email": candidate_email,
        "availability_text": availability_text,
        "message": "Simulated candidate email response processed by agent system"
    }