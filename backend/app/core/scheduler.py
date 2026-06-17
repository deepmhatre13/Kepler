"""
Built-in Background Scheduler
==============================
Runs periodic jobs directly inside the FastAPI process using asyncio.
No Celery / Redis required — ideal for development and single-server deployments.

Jobs:
 *   • Every 5 min  → Sync Space-Track active satellites & debris
 *   • Every 15 min → Sync space weather
 *   • Every 10 min → Run collision scanning
"""

import asyncio
import datetime
import logging
from typing import Callable, Awaitable

logger = logging.getLogger("app")






async def job_sync_spacetrack():
    """Fetch live GP data from Space-Track and upsert into DB."""
    from app.database.session import SessionLocal
    from app.services.spacetrack import spacetrack_service

    db = SessionLocal()
    try:
        logger.info("🛰  [Scheduler] Starting Space-Track sync...")
        results = spacetrack_service.sync_all_groups(db, limit_per_group=500)
        logger.info(f"✅ [Scheduler] Space-Track sync complete: {results}")
    except Exception as e:
        logger.error(f"❌ [Scheduler] Space-Track sync failed: {e}")
    finally:
        db.close()


async def job_sync_weather():
    """Poll NOAA for space weather Kp index."""
    from app.database.session import SessionLocal
    from app.services.weather_service import weather_service

    db = SessionLocal()
    try:
        logger.info("🌤  [Scheduler] Polling space weather...")
        weather_service.sync_weather(db)
        logger.info("✅ [Scheduler] Space weather updated.")
    except Exception as e:
        logger.error(f"❌ [Scheduler] Space weather sync failed: {e}")
    finally:
        db.close()


async def job_run_collision_scan():
    """Run collision prediction sweep over current TLE catalog."""
    from app.database.session import SessionLocal
    from app.services.collision_engine import collision_engine

    db = SessionLocal()
    try:
        logger.info("💥 [Scheduler] Running collision sweep...")
        preds = collision_engine.predict_collisions(db)
        logger.info(f"✅ [Scheduler] Collision scan done — {len(preds)} conjunctions found.")
    except Exception as e:
        logger.error(f"❌ [Scheduler] Collision scan failed: {e}")
    finally:
        db.close()






class PeriodicTask:
    def __init__(self, name: str, coro_fn: Callable[[], Awaitable], interval_seconds: int, run_immediately: bool = True):
        self.name = name
        self.coro_fn = coro_fn
        self.interval = interval_seconds
        self.run_immediately = run_immediately
        self._task: asyncio.Task | None = None

    async def _run_loop(self):
        if self.run_immediately:
            
            await asyncio.sleep(10)
            await self._safe_run()

        while True:
            await asyncio.sleep(self.interval)
            await self._safe_run()

    async def _safe_run(self):
        try:
            logger.info(f"[Scheduler] ▶  Running job: {self.name}")
            start = datetime.datetime.utcnow()
            await self.coro_fn()
            elapsed = (datetime.datetime.utcnow() - start).total_seconds()
            logger.info(f"[Scheduler] ✓  Job '{self.name}' finished in {elapsed:.1f}s")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[Scheduler] ✗  Job '{self.name}' raised an unhandled error: {e}")

    def start(self):
        self._task = asyncio.create_task(self._run_loop(), name=f"scheduler:{self.name}")
        logger.info(f"[Scheduler] Registered job '{self.name}' every {self.interval}s")

    def cancel(self):
        if self._task and not self._task.done():
            self._task.cancel()


class BackgroundScheduler:
    """Lightweight asyncio-native scheduler."""

    def __init__(self):
        self._jobs: list[PeriodicTask] = []

    def add_job(self, name: str, coro_fn: Callable, interval_seconds: int, run_immediately: bool = True):
        self._jobs.append(PeriodicTask(name, coro_fn, interval_seconds, run_immediately))

    def start_all(self):
        for job in self._jobs:
            job.start()
        logger.info(f"[Scheduler] 🚀 Started {len(self._jobs)} background jobs.")

    def stop_all(self):
        for job in self._jobs:
            job.cancel()
        logger.info("[Scheduler] 🛑 All background jobs stopped.")





scheduler = BackgroundScheduler()

scheduler.add_job(
    name="spacetrack_sync",
    coro_fn=job_sync_spacetrack,
    interval_seconds=5 * 60,   
    run_immediately=True,
)
scheduler.add_job(
    name="space_weather_sync",
    coro_fn=job_sync_weather,
    interval_seconds=15 * 60,  
    run_immediately=True,
)
scheduler.add_job(
    name="collision_scan",
    coro_fn=job_run_collision_scan,
    interval_seconds=10 * 60,  
    run_immediately=False,     
)
