"""SQLite database for job queue persistence."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, List, Optional

from arrtheaudio.core.job_models import Job, JobStatus, JobPriority
from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)


class JobDatabase:
    """SQLite database for job persistence."""

    def __init__(self, db_path: Path):
        """Initialize database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    container TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    source TEXT NOT NULL,
                    webhook_id TEXT,
                    batch_id TEXT,
                    selected_track_index INTEGER,
                    selected_track_language TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    success INTEGER,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    tmdb_id INTEGER,
                    original_language TEXT,
                    series_title TEXT,
                    movie_title TEXT
                )
            """
            )

            # Create indexes for common queries
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_priority ON jobs(priority, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_webhook_id ON jobs(webhook_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_batch_id ON jobs(batch_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_created_at ON jobs(created_at)"
            )

            conn.commit()

        logger.info("Job database initialized", db_path=str(self.db_path))

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get database connection context manager."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def add_job(self, job: Job) -> bool:
        """Add job to database.

        Args:
            job: Job to add

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                data = job.to_db_dict()
                columns = ", ".join(data.keys())
                placeholders = ", ".join(["?" for _ in data])
                sql = f"INSERT INTO jobs ({columns}) VALUES ({placeholders})"

                conn.execute(sql, list(data.values()))
                conn.commit()

            logger.debug("Job added to database", job_id=job.job_id)
            return True

        except Exception as e:
            logger.error("Failed to add job", job_id=job.job_id, error=str(e))
            return False

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job if found, None otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
                row = cursor.fetchone()

                if row:
                    return Job.from_db_dict(dict(row))
                return None

        except Exception as e:
            logger.error("Failed to get job", job_id=job_id, error=str(e))
            return None

    def update_job(self, job: Job) -> bool:
        """Update job in database.

        Args:
            job: Job with updated data

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                data = job.to_db_dict()
                # Remove job_id from update data
                job_id = data.pop("job_id")

                set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
                sql = f"UPDATE jobs SET {set_clause} WHERE job_id = ?"

                conn.execute(sql, list(data.values()) + [job_id])
                conn.commit()

            logger.debug("Job updated in database", job_id=job.job_id)
            return True

        except Exception as e:
            logger.error("Failed to update job", job_id=job.job_id, error=str(e))
            return False

    def get_next_job(self) -> Optional[Job]:
        """Get next job from queue (highest priority, oldest first).

        Returns:
            Next job to process, or None if queue is empty
        """
        try:
            with self._get_connection() as conn:
                # Order by priority (high > normal > low) then by created_at
                cursor = conn.execute(
                    """
                    SELECT * FROM jobs
                    WHERE status = ?
                    ORDER BY
                        CASE priority
                            WHEN 'high' THEN 1
                            WHEN 'normal' THEN 2
                            WHEN 'low' THEN 3
                        END,
                        created_at ASC
                    LIMIT 1
                """,
                    (JobStatus.QUEUED.value,),
                )
                row = cursor.fetchone()

                if row:
                    return Job.from_db_dict(dict(row))
                return None

        except Exception as e:
            logger.error("Failed to get next job", error=str(e))
            return None

    def get_jobs_by_status(self, status: JobStatus) -> List[Job]:
        """Get all jobs with given status.

        Args:
            status: Job status

        Returns:
            List of jobs
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC",
                    (status.value,),
                )
                rows = cursor.fetchall()

                return [Job.from_db_dict(dict(row)) for row in rows]

        except Exception as e:
            logger.error("Failed to get jobs by status", status=status, error=str(e))
            return []

    def get_jobs_by_webhook(self, webhook_id: str) -> List[Job]:
        """Get all jobs from same webhook.

        Args:
            webhook_id: Webhook ID

        Returns:
            List of jobs
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM jobs WHERE webhook_id = ? ORDER BY created_at ASC",
                    (webhook_id,),
                )
                rows = cursor.fetchall()

                return [Job.from_db_dict(dict(row)) for row in rows]

        except Exception as e:
            logger.error(
                "Failed to get jobs by webhook", webhook_id=webhook_id, error=str(e)
            )
            return []

    def get_jobs_by_batch(self, batch_id: str) -> List[Job]:
        """Get all jobs from same batch.

        Args:
            batch_id: Batch ID

        Returns:
            List of jobs
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM jobs WHERE batch_id = ? ORDER BY created_at ASC",
                    (batch_id,),
                )
                rows = cursor.fetchall()

                return [Job.from_db_dict(dict(row)) for row in rows]

        except Exception as e:
            logger.error(
                "Failed to get jobs by batch", batch_id=batch_id, error=str(e)
            )
            return []

    def get_queue_stats(self) -> dict:
        """Get queue statistics.

        Returns:
            Dictionary with status counts
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM jobs
                    GROUP BY status
                """
                )
                rows = cursor.fetchall()

                stats = {
                    "total": 0,
                    "queued": 0,
                    "running": 0,
                    "completed": 0,
                    "failed": 0,
                    "cancelled": 0,
                }

                for row in rows:
                    status = row["status"]
                    count = row["count"]
                    stats[status] = count
                    stats["total"] += count

                return stats

        except Exception as e:
            logger.error("Failed to get queue stats", error=str(e))
            return {
                "total": 0,
                "queued": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
            }

    def count_running_by_container(self, container: str) -> int:
        """Count running jobs for specific container type.

        Args:
            container: Container type (mkv, mp4)

        Returns:
            Number of running jobs
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM jobs
                    WHERE status = ? AND container = ?
                """,
                    (JobStatus.RUNNING.value, container),
                )
                row = cursor.fetchone()
                return row["count"] if row else 0

        except Exception as e:
            logger.error(
                "Failed to count running jobs", container=container, error=str(e)
            )
            return 0

    def cleanup_old_jobs(self, days: int = 30) -> int:
        """Remove completed/failed jobs older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of jobs deleted
        """
        try:
            cutoff = datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            cutoff_str = cutoff.isoformat()

            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM jobs
                    WHERE status IN (?, ?, ?)
                    AND completed_at < datetime(?, '-' || ? || ' days')
                """,
                    (
                        JobStatus.COMPLETED.value,
                        JobStatus.FAILED.value,
                        JobStatus.CANCELLED.value,
                        cutoff_str,
                        days,
                    ),
                )
                deleted = cursor.rowcount
                conn.commit()

            if deleted > 0:
                logger.info("Cleaned up old jobs", deleted=deleted, days=days)

            return deleted

        except Exception as e:
            logger.error("Failed to cleanup old jobs", error=str(e))
            return 0

    def delete_job(self, job_id: str) -> bool:
        """Delete job from database.

        Args:
            job_id: Job ID

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
                conn.commit()

            logger.debug("Job deleted from database", job_id=job_id)
            return True

        except Exception as e:
            logger.error("Failed to delete job", job_id=job_id, error=str(e))
            return False
