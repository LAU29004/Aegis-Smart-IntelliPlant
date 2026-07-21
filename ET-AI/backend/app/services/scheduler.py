"""
Background scheduler for IntelliPlant.

Responsibilities
----------------
Runs maintenance monitoring periodically.

This module NEVER contains business logic.

It simply creates a database session and delegates to
maintenance_monitor.run_maintenance_check_for_all_equipment().

Safe for APScheduler, cron or BackgroundTasks.
"""

from apscheduler.schedulers.background import BackgroundScheduler

from ..database import SessionLocal
from .maintenance_monitor import run_maintenance_check_for_all_equipment

# Global scheduler instance
scheduler = BackgroundScheduler()


def maintenance_job():
    """
    Executed every scheduler interval.
    """

    db = SessionLocal()

    try:
        result = run_maintenance_check_for_all_equipment(db)

        print("\n========== MAINTENANCE SCAN ==========")
        print(result)
        print("======================================\n")

    except Exception as e:
        print("\n========== SCHEDULER ERROR ==========")
        print(e)
        print("=====================================\n")

    finally:
        db.close()


def start_scheduler():
    """
    Starts APScheduler only once.
    """

    if scheduler.running:
        return

    scheduler.add_job(
        maintenance_job,
        trigger="interval",
        seconds=30,
        id="maintenance-monitor",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()

    print("✅ Maintenance Scheduler Started")


def stop_scheduler():
    """
    Shutdown scheduler.
    """

    if scheduler.running:
        scheduler.shutdown(wait=False)