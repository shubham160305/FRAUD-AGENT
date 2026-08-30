"""
Velocity tracker — detects coordinated mandate drain attacks.
Keeps a rolling 10-minute window of agentic transactions per merchant.
Alerts if:
  - Same merchant receives >200 agentic transactions in 10 minutes
  - Same agent session_id appears across >5 different user_ids
These patterns are invisible at the per-user level but obvious in aggregate.
Production: replace with Redis sorted sets for distributed tracking.
"""

from collections import defaultdict
from datetime import datetime, timedelta

WINDOW_MINUTES = 10
MERCHANT_TXN_LIMIT = 200       # transactions per merchant per window
SESSION_USER_LIMIT = 5         # unique users per session_id

# Rolling event log: list of (timestamp, user_id, session_id)
_merchant_events: dict[str, list[tuple[datetime, str, str]]] = defaultdict(list)


def _purge_old(events: list, now: datetime) -> list:
    cutoff = now - timedelta(minutes=WINDOW_MINUTES)
    return [e for e in events if e[0] > cutoff]


def record(merchant_id: str, user_id: str, session_id: str) -> dict:
    """
    Record an agentic transaction event.
    Returns velocity flags immediately — call before executing the transaction.
    """
    now = datetime.utcnow()
    events = _purge_old(_merchant_events[merchant_id], now)
    events.append((now, user_id, session_id))
    _merchant_events[merchant_id] = events

    flags = []

    # Check 1: total transaction volume for this merchant in window
    if len(events) > MERCHANT_TXN_LIMIT:
        flags.append(
            f"Merchant '{merchant_id}' received {len(events)} agentic transactions "
            f"in {WINDOW_MINUTES} minutes — exceeds {MERCHANT_TXN_LIMIT} limit."
        )

    # Check 2: same session across multiple users (stolen mandate token reuse)
    session_users = {e[1] for e in events if e[2] == session_id}
    if len(session_users) > SESSION_USER_LIMIT:
        flags.append(
            f"Session '{session_id}' appeared across {len(session_users)} different users "
            f"in {WINDOW_MINUTES} minutes — possible stolen mandate token."
        )

    return {
        "flagged": len(flags) > 0,
        "flags": flags,
        "window_txn_count": len(events),
        "session_user_count": len(session_users),
    }


def get_stats(merchant_id: str) -> dict:
    now = datetime.utcnow()
    events = _purge_old(_merchant_events.get(merchant_id, []), now)
    return {
        "merchant_id": merchant_id,
        "window_minutes": WINDOW_MINUTES,
        "transaction_count": len(events),
        "unique_users": len({e[1] for e in events}),
        "unique_sessions": len({e[2] for e in events}),
    }
