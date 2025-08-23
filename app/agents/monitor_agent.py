from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
import asyncio
from app.services.email_monitor import email_monitor, start_email_monitor, stop_email_monitor

router = APIRouter()

class MonitorStatus(BaseModel):
    is_running: bool
    processed_count: int
    check_interval: int

@router.post("/start")
async def start_monitor(background_tasks: BackgroundTasks):
    """Start the email monitoring service"""
    if email_monitor.is_running:
        return {"status": "already_running", "message": "Email monitor is already running"}
    
    # Start the monitor in the background
    background_tasks.add_task(start_email_monitor)
    
    # Give it a moment to start
    await asyncio.sleep(1)
    
    return {
        "status": "started",
        "message": "Email monitor started - watching for candidate responses",
        "check_interval": email_monitor.check_interval
    }

@router.post("/stop")
async def stop_monitor():
    """Stop the email monitoring service"""
    if not email_monitor.is_running:
        return {"status": "not_running", "message": "Email monitor is not running"}
    
    stop_email_monitor()
    return {"status": "stopped", "message": "Email monitor stopped"}

@router.get("/status")
async def get_monitor_status():
    """Get current status of the email monitoring service"""
    return {
        "is_running": email_monitor.is_running,
        "processed_count": len(email_monitor.processed_messages),
        "check_interval": email_monitor.check_interval,
        "total_checks": email_monitor.total_checks,
        "successful_schedules": email_monitor.successful_schedules,
        "failed_schedules": email_monitor.failed_schedules,
        "last_check_time": email_monitor.last_check_time.isoformat() if email_monitor.last_check_time else None,
        "message": "Monitoring candidate email responses" if email_monitor.is_running else "Monitor is stopped"
    }

@router.post("/config")
async def update_config(check_interval: int = 30):
    """Update monitor configuration"""
    if check_interval < 10:
        raise HTTPException(status_code=400, detail="Check interval must be at least 10 seconds")
    
    email_monitor.check_interval = check_interval
    return {
        "status": "updated",
        "check_interval": check_interval,
        "message": f"Monitor will now check emails every {check_interval} seconds"
    }

@router.post("/process-now")
async def process_now():
    """Manually trigger email processing (useful for testing)"""
    if not email_monitor.is_running:
        raise HTTPException(status_code=400, detail="Email monitor is not running")
    
    # Trigger immediate check
    await email_monitor.check_and_process_emails()
    
    return {
        "status": "processed",
        "message": "Manual email check completed",
        "processed_count": len(email_monitor.processed_messages)
    }