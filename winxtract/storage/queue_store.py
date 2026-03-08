import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from winxtract.storage.db import QueueTaskORM


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class QueueTask:
    id: int
    task_type: str
    payload: dict[str, Any]
    status: str
    attempts: int
    max_attempts: int
    worker_id: str | None
    message: str
    available_at: datetime
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


def row_to_task(row: QueueTaskORM) -> QueueTask:
    try:
        payload = json.loads(row.payload_json) if row.payload_json else {}
    except Exception:
        payload = {}
    return QueueTask(
        id=int(row.id),
        task_type=row.task_type,
        payload=payload if isinstance(payload, dict) else {},
        status=row.status,
        attempts=int(row.attempts),
        max_attempts=int(row.max_attempts),
        worker_id=row.worker_id,
        message=row.last_error or "",
        available_at=row.available_at,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


class QueueStore:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def enqueue(
        self,
        *,
        task_type: str,
        payload: dict[str, Any],
        max_attempts: int = 3,
        available_at: datetime | None = None,
    ) -> QueueTask:
        row = QueueTaskORM(
            task_type=task_type,
            payload_json=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            status="queued",
            attempts=0,
            max_attempts=max(1, int(max_attempts)),
            available_at=available_at or now_utc(),
        )
        with self.session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return row_to_task(row)

    def claim_next(self, *, worker_id: str) -> QueueTask | None:
        # SQLite has no SKIP LOCKED. We select and then atomically try to switch
        # status to running; on race we retry quickly.
        for _ in range(5):
            with self.session_factory() as session:
                current = now_utc()
                candidate_id = session.scalar(
                    select(QueueTaskORM.id)
                    .where(QueueTaskORM.status == "queued")
                    .where(QueueTaskORM.available_at <= current)
                    .order_by(QueueTaskORM.created_at.asc(), QueueTaskORM.id.asc())
                    .limit(1)
                )
                if candidate_id is None:
                    return None

                result = session.execute(
                    update(QueueTaskORM)
                    .where(QueueTaskORM.id == candidate_id)
                    .where(QueueTaskORM.status == "queued")
                    .values(
                        status="running",
                        worker_id=worker_id,
                        started_at=current,
                        attempts=QueueTaskORM.attempts + 1,
                        last_error=None,
                    )
                )
                if result.rowcount != 1:
                    session.rollback()
                    continue
                session.commit()
                row = session.get(QueueTaskORM, candidate_id)
                if row is None:
                    return None
                return row_to_task(row)
        return None

    def mark_success(self, task_id: int, message: str = "") -> None:
        with self.session_factory() as session:
            row = session.get(QueueTaskORM, task_id)
            if row is None:
                return
            row.status = "success"
            row.last_error = (message or "")[:4000]
            row.finished_at = now_utc()
            session.commit()

    def update_progress(self, task_id: int, progress_message: str) -> None:
        with self.session_factory() as session:
            row = session.get(QueueTaskORM, task_id)
            if row is None:
                return
            if row.status != "running":
                return
            row.last_error = (progress_message or "")[:8000]
            session.commit()

    def mark_failure(self, task_id: int, *, error_message: str, retry_delay_seconds: float) -> None:
        with self.session_factory() as session:
            row = session.get(QueueTaskORM, task_id)
            if row is None:
                return
            terminal = int(row.attempts) >= int(row.max_attempts)
            row.last_error = (error_message or "")[:8000]
            if terminal:
                # Terminal failures are moved to dead-letter status so they can be
                # monitored and replayed explicitly later.
                row.status = "dead"
                row.finished_at = now_utc()
            else:
                row.status = "queued"
                row.available_at = now_utc() + timedelta(seconds=max(0.0, float(retry_delay_seconds)))
            session.commit()

    def mark_dead(self, task_id: int, *, error_message: str) -> None:
        with self.session_factory() as session:
            row = session.get(QueueTaskORM, task_id)
            if row is None:
                return
            row.status = "dead"
            row.last_error = (error_message or "")[:8000]
            row.finished_at = now_utc()
            session.commit()

    def requeue_task(
        self,
        task_id: int,
        *,
        allowed_statuses: Sequence[str] = ("dead", "failed"),
    ) -> QueueTask | None:
        normalized = [s.strip().lower() for s in allowed_statuses if s and s.strip()]
        with self.session_factory() as session:
            row = session.get(QueueTaskORM, task_id)
            if row is None:
                return None
            if normalized and row.status.lower() not in normalized:
                return None
            replay = QueueTaskORM(
                task_type=row.task_type,
                payload_json=row.payload_json,
                status="queued",
                attempts=0,
                max_attempts=max(1, int(row.max_attempts)),
                available_at=now_utc(),
                last_error=f"requeued_from:{row.id}",
            )
            session.add(replay)
            session.commit()
            session.refresh(replay)
            return row_to_task(replay)

    def list_tasks(
        self,
        *,
        status: str | None = None,
        statuses: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[QueueTask]:
        with self.session_factory() as session:
            stmt = select(QueueTaskORM).order_by(QueueTaskORM.id.desc())
            normalized_statuses = [s.strip().lower() for s in (statuses or []) if s and s.strip()]
            if normalized_statuses:
                stmt = stmt.where(QueueTaskORM.status.in_(normalized_statuses))
            elif status:
                stmt = stmt.where(QueueTaskORM.status == status)
            rows = session.scalars(stmt.offset(max(0, offset)).limit(max(1, min(limit, 500)))).all()
            return [row_to_task(row) for row in rows]

    def get_task(self, task_id: int) -> QueueTask | None:
        with self.session_factory() as session:
            row = session.get(QueueTaskORM, task_id)
            if row is None:
                return None
            return row_to_task(row)
