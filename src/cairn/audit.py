"""A minimal audit chain per workflow thread: append-only entries linked by SHA-256.

Each entry stores the hash of the one before (64 zeros for the first) and its own canonical hash.
`verify_chain` is pure. It detects an edited, deleted, swapped or inserted entry; it does not
stop someone who rewrites the whole chain, and a cut tail shows only against a known head hash.
"""

import json
from dataclasses import dataclass
from typing import Any

from cairn.canonical import canonical_sha256

ZEROS = "0" * 64
TABLE = """CREATE TABLE IF NOT EXISTS audit (
  thread_id TEXT NOT NULL, seq INTEGER NOT NULL, ts TEXT NOT NULL, actor TEXT NOT NULL,
  action TEXT NOT NULL, payload TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL,
  PRIMARY KEY (thread_id, seq))"""
COLUMNS = "seq, ts, actor, action, payload, prev_hash, hash"


@dataclass(frozen=True)
class Check:
    ok: bool
    count: int
    first_broken: int | None = None  # seq of the first entry that fails


def entry_hash(entry: dict[str, Any]) -> str:
    return canonical_sha256({k: v for k, v in entry.items() if k != "hash"})


def make_entry(
    seq: int, ts: str, actor: str, action: str, payload: dict[str, Any], prev_hash: str
) -> dict[str, Any]:
    body = {
        "seq": seq,
        "ts": ts,
        "actor": actor,
        "action": action,
        "payload": payload,
        "prev_hash": prev_hash,
    }
    return {**body, "hash": entry_hash(body)}


def verify_chain(entries: list[dict[str, Any]], head: str | None = None) -> Check:
    """Check order, links and hashes; with `head`, also that the chain ends at that hash."""
    previous = ZEROS
    for position, entry in enumerate(entries, start=1):
        if (
            entry["seq"] != position
            or entry["prev_hash"] != previous
            or entry["hash"] != entry_hash(entry)
        ):
            return Check(False, len(entries), entry["seq"])
        previous = entry["hash"]
    if head is not None and head != previous:
        return Check(False, len(entries), len(entries) + 1)
    return Check(True, len(entries))


async def init(conn: Any) -> None:
    await conn.execute(TABLE)
    await conn.commit()


async def entries(conn: Any, thread_id: str) -> list[dict[str, Any]]:
    cursor = await conn.execute(
        f"SELECT {COLUMNS} FROM audit WHERE thread_id = ? ORDER BY seq", (thread_id,)
    )
    rows = await cursor.fetchall()
    keys = COLUMNS.split(", ")
    return [{**dict(zip(keys, row, strict=True)), "payload": json.loads(row[4])} for row in rows]


async def append(
    conn: Any, thread_id: str, ts: str, actor: str, action: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Add one entry after the last of the thread; call it inside the thread's lock."""
    cursor = await conn.execute(
        "SELECT seq, hash FROM audit WHERE thread_id = ? ORDER BY seq DESC LIMIT 1", (thread_id,)
    )
    last = await cursor.fetchone()
    seq, prev = (last[0] + 1, last[1]) if last else (1, ZEROS)
    entry = make_entry(seq, ts, actor, action, payload, prev)
    await conn.execute(
        f"INSERT INTO audit (thread_id, {COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            thread_id,
            seq,
            ts,
            actor,
            action,
            json.dumps(payload, sort_keys=True),
            prev,
            entry["hash"],
        ),
    )
    await conn.commit()
    return entry
