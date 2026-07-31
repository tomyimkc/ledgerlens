"""Thread-safe in-memory and durable SQLite idempotency stores."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from .errors import (
    ActionIndeterminateError,
    ActionInProgressError,
    IdempotencyConflictError,
)
from .models import ActionReceipt


class IdempotencyState(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class IdempotencyClaim:
    is_new: bool
    receipt: ActionReceipt | None = None


class IdempotencyStore(Protocol):
    """Atomic claim/complete contract used by all action adapters."""

    def claim(self, key: str, action_digest: str) -> IdempotencyClaim: ...

    def complete(self, key: str, action_digest: str, receipt: ActionReceipt) -> None: ...

    def release(self, key: str, action_digest: str) -> None: ...

    def mark_indeterminate(self, key: str, action_digest: str) -> None: ...


@dataclass
class _Entry:
    action_digest: str
    state: IdempotencyState
    receipt: ActionReceipt | None = None


class InMemoryIdempotencyStore:
    """Process-local store suitable for tests and single-process workers."""

    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}
        self._lock = threading.RLock()

    def claim(self, key: str, action_digest: str) -> IdempotencyClaim:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._entries[key] = _Entry(action_digest, IdempotencyState.PENDING)
                return IdempotencyClaim(is_new=True)
            return _existing_claim(key, action_digest, entry)

    def complete(self, key: str, action_digest: str, receipt: ActionReceipt) -> None:
        with self._lock:
            entry = self._require_matching(key, action_digest)
            entry.state = IdempotencyState.COMPLETED
            entry.receipt = receipt

    def release(self, key: str, action_digest: str) -> None:
        with self._lock:
            entry = self._entries.get(key)
            if (
                entry is not None
                and entry.action_digest == action_digest
                and entry.state is IdempotencyState.PENDING
            ):
                del self._entries[key]

    def mark_indeterminate(self, key: str, action_digest: str) -> None:
        with self._lock:
            entry = self._require_matching(key, action_digest)
            entry.state = IdempotencyState.INDETERMINATE

    def _require_matching(self, key: str, action_digest: str) -> _Entry:
        entry = self._entries.get(key)
        if entry is None or entry.action_digest != action_digest:
            raise IdempotencyConflictError("idempotency state changed unexpectedly")
        return entry


class SQLiteIdempotencyStore:
    """Durable idempotency store for multi-threaded production workers."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS action_idempotency (
                key TEXT PRIMARY KEY,
                action_digest TEXT NOT NULL,
                state TEXT NOT NULL,
                receipt_json TEXT
            )
            """
        )
        self._connection.commit()
        self._lock = threading.RLock()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> SQLiteIdempotencyStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def claim(self, key: str, action_digest: str) -> IdempotencyClaim:
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT action_digest, state, receipt_json FROM action_idempotency WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                self._connection.execute(
                    "INSERT INTO action_idempotency(key, action_digest, state) VALUES (?, ?, ?)",
                    (key, action_digest, IdempotencyState.PENDING.value),
                )
                return IdempotencyClaim(is_new=True)
            entry = _Entry(
                action_digest=str(row[0]),
                state=IdempotencyState(str(row[1])),
                receipt=ActionReceipt.model_validate_json(row[2]) if row[2] else None,
            )
            return _existing_claim(key, action_digest, entry)

    def complete(self, key: str, action_digest: str, receipt: ActionReceipt) -> None:
        with self._lock, self._connection:
            updated = self._connection.execute(
                "UPDATE action_idempotency SET state = ?, receipt_json = ? "
                "WHERE key = ? AND action_digest = ?",
                (
                    IdempotencyState.COMPLETED.value,
                    receipt.model_dump_json(),
                    key,
                    action_digest,
                ),
            )
            if updated.rowcount != 1:
                raise IdempotencyConflictError("idempotency state changed unexpectedly")

    def release(self, key: str, action_digest: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM action_idempotency WHERE key = ? AND action_digest = ? AND state = ?",
                (key, action_digest, IdempotencyState.PENDING.value),
            )

    def mark_indeterminate(self, key: str, action_digest: str) -> None:
        with self._lock, self._connection:
            updated = self._connection.execute(
                "UPDATE action_idempotency SET state = ? WHERE key = ? AND action_digest = ?",
                (IdempotencyState.INDETERMINATE.value, key, action_digest),
            )
            if updated.rowcount != 1:
                raise IdempotencyConflictError("idempotency state changed unexpectedly")


def _existing_claim(
    key: str,
    action_digest: str,
    entry: _Entry,
) -> IdempotencyClaim:
    if entry.action_digest != action_digest:
        raise IdempotencyConflictError(
            f"idempotency key collision in action namespace {key.split(':', 1)[0]!r}"
        )
    if entry.state is IdempotencyState.PENDING:
        raise ActionInProgressError("an identical action is already in progress")
    if entry.state is IdempotencyState.INDETERMINATE:
        raise ActionIndeterminateError(
            "a prior action has an unknown remote outcome; reconcile it before retrying"
        )
    if entry.receipt is None:
        raise IdempotencyConflictError("completed idempotency entry has no receipt")
    return IdempotencyClaim(is_new=False, receipt=entry.receipt)
