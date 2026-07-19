"""Agent定时任务调度器

允许Agent注册周期执行的检查任务，实现"每2小时自动检查"能力。
基于APScheduler实现。
"""

import logging
from datetime import datetime
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class AgentScheduler:
    """Agent定时任务调度器"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._jobs: dict[str, str] = {}  # job_id -> job_name

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("⏰ AgentScheduler started")

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("⏰ AgentScheduler stopped")

    def schedule_supply_check(
        self,
        job_id: str,
        goal: str,
        bom_id: str,
        interval_hours: int = 2,
        callback: Callable | None = None,
    ) -> str:
        """
        注册定时齐套检查任务

        Args:
            job_id: 任务唯一ID
            goal: 检查目标描述
            bom_id: BOM编号
            interval_hours: 检查间隔（小时）
            callback: 执行完成后的回调

        Returns:
            job_id: 任务ID
        """
        trigger = IntervalTrigger(hours=interval_hours)

        async def check_job():
            try:
                from src.agents.supply_chain.agent import supply_chain_agent
                logger.info(f"⏰ [Scheduled] Running supply check: {bom_id}")
                plan = await supply_chain_agent.analyze_goal(goal)
                result = await supply_chain_agent.execute(goal, plan)

                # 记录到审计
                from src.meta_agent.audit import audit_logger
                audit_logger.log(
                    session_id=f"scheduled-{bom_id}",
                    event_type="scheduled_check",
                    actor="agent_scheduler",
                    detail={
                        "goal": goal[:80],
                        "completeness": result.get("completeness_pct"),
                        "warning_count": len(result.get("warning", [])),
                    },
                )

                # 如果有回调
                if callback:
                    await callback(result)

                logger.info(f"⏰ [Scheduled] Check complete: {result.get('completeness_pct')}%")

            except Exception as e:
                logger.error(f"⏰ [Scheduled] Check failed: {e}")

        self.scheduler.add_job(check_job, trigger, id=job_id, replace_existing=True)
        self._jobs[job_id] = f"SupplyCheck({bom_id}, every {interval_hours}h)"
        logger.info(f"⏰ Scheduled: {self._jobs[job_id]} (id={job_id})")
        return job_id

    def remove_job(self, job_id: str):
        """取消定时任务"""
        if job_id in self._jobs:
            self.scheduler.remove_job(job_id)
            del self._jobs[job_id]
            logger.info(f"⏰ Removed scheduled job: {job_id}")

    def list_jobs(self) -> list[dict]:
        """列出所有定时任务"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": self._jobs.get(job.id, job.id),
                "next_run": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return jobs


# 全局单例
scheduler = AgentScheduler()
