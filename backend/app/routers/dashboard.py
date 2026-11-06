from __future__ import annotations

import sqlite3

from fastapi import APIRouter

from app.config import DATABASE_URL
from app.database import engine

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _counts() -> dict:
    with engine.connect() as conn:
        content_by_status = dict(
            conn.exec_driver_sql(
                "SELECT status, COUNT(*) FROM content_items GROUP BY status"
            ).fetchall()
        )
        workflow_by_status = dict(
            conn.exec_driver_sql(
                "SELECT status, COUNT(*) FROM workflows GROUP BY status"
            ).fetchall()
        )
        total_agent_executions = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM agent_executions"
        ).scalar_one()
        failed_agent_executions = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM agent_executions WHERE status = 'FAILED'"
        ).scalar_one()
        completed_agent_executions = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM agent_executions WHERE status = 'COMPLETED'"
        ).scalar_one()
        scheduled_jobs = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM content_items WHERE status = 'Scheduled'"
        ).scalar_one()
        published = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM content_items WHERE published_at IS NOT NULL"
        ).scalar_one()
        pending_approvals = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM content_items WHERE status = 'Awaiting Approval'"
        ).scalar_one()
        total_content = conn.exec_driver_sql("SELECT COUNT(*) FROM content_items").scalar_one()
        total_workflows = conn.exec_driver_sql("SELECT COUNT(*) FROM workflows").scalar_one()

    return {
        "content": {
            "total": total_content,
            "by_status": content_by_status,
            "pending_approvals": pending_approvals,
            "scheduled": scheduled_jobs,
            "published": published,
        },
        "workflows": {
            "total": total_workflows,
            "by_status": workflow_by_status,
        },
        "agent_executions": {
            "total": total_agent_executions,
            "completed": completed_agent_executions,
            "failed": failed_agent_executions,
        },
    }


@router.get("/stats")
def dashboard_stats():
    """Real database counts. No fabricated operational statistics."""
    return _counts()


@router.get("/agent-status")
def agent_status():
    """Latest execution status per agent, derived from agent_executions."""
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(
            """
            SELECT agent_name, status, execution_duration, error_message, completed_at
            FROM agent_executions
            WHERE id IN (
                SELECT MAX(id) FROM agent_executions GROUP BY agent_name
            )
            ORDER BY agent_name
            """
        ).fetchall()

    agents = {}
    for agent_name, status, duration, error, completed_at in rows:
        agents[agent_name] = {
            "status": status,
            "last_duration_ms": duration,
            "last_error": error,
            "completed_at": completed_at,
        }
    return agents
