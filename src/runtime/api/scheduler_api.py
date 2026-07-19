"""定时任务API——Agent定时检查调度"""

from fastapi import APIRouter
from pydantic import BaseModel

from src.runtime.core.scheduler import scheduler

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


# 调度器启动由Runtime lifespan管理
def ensure_scheduler():
    if not scheduler.scheduler.running:
        scheduler.start()


class ScheduleRequest(BaseModel):
    goal: str
    bom_id: str = "BOM-NPI-007"
    interval_hours: int = 2


@router.post("/supply-check")
async def schedule_supply_check(req: ScheduleRequest):
    """注册定时齐套检查"""
    ensure_scheduler()
    job_id = f"auto-check-{req.bom_id.lower().replace(' ', '-')}"
    scheduler.schedule_supply_check(
        job_id=job_id,
        goal=req.goal,
        bom_id=req.bom_id,
        interval_hours=req.interval_hours,
    )
    return {
        "status": "scheduled",
        "job_id": job_id,
        "interval_hours": req.interval_hours,
    }


@router.delete("/{job_id}")
async def remove_schedule(job_id: str):
    """取消定时任务"""
    scheduler.remove_job(job_id)
    return {"status": "removed", "job_id": job_id}


@router.get("/jobs")
async def list_schedules():
    """列出所有定时任务"""
    jobs = scheduler.list_jobs()
    return {"jobs": jobs, "total": len(jobs)}
