"""
Transaction runner with automatic retry for transient PostgreSQL failures.

Every write operation in the scheduling services runs as ONE database
transaction: lock -> validate -> write -> commit. If PostgreSQL aborts the
transaction because of a deadlock (40P01) or serialization failure (40001) the
whole operation is rolled back and re-run from the start, which is safe because
operations re-read all state after taking their locks.
"""

import random
import time
from typing import Callable, TypeVar

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

T = TypeVar("T")

_RETRYABLE_PGCODES = {"40P01", "40001"}  # deadlock_detected, serialization_failure


def run_in_transaction(db: Session, operation: Callable[[], T], attempts: int = 4) -> T:
    for attempt in range(1, attempts + 1):
        try:
            result = operation()
            db.commit()
            return result
        except DBAPIError as exc:
            db.rollback()
            pgcode = getattr(exc.orig, "pgcode", None)
            if pgcode in _RETRYABLE_PGCODES and attempt < attempts:
                time.sleep(random.uniform(0.02, 0.08) * attempt)
                continue
            raise
        except Exception:
            db.rollback()
            raise
    raise RuntimeError("unreachable")  # pragma: no cover
