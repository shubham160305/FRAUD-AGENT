"""
Detector 3 — Agent Identity + Velocity
Two sub-checks:

A) JWT verification — prove which AI platform is making the request.
   Production: verify signature against Anthropic/OpenAI public keys.
   For internal testing: simulate token structure validation.

B) Velocity detection — cross-user mandate drain.
   Uses velocity_tracker to catch coordinated attacks invisible per-user.

Token format expected:
{
  "platform": "claude",
  "version": "sonnet-4-6",
  "session_id": "abc123",
  "user_id_hash": "sha256(user_id)",
  "issued_at": 1234567890,    ← unix timestamp, must be <5 min old
  "signature": "..."           ← in prod: verified against platform public key
}
"""

import json
import time
import hashlib
from app.models.schemas import DetectorResult
from app.services.velocity_tracker import record as record_velocity

KNOWN_PLATFORMS = {"claude", "gemini", "chatgpt", "copilot"}
TOKEN_MAX_AGE_SECONDS = 300   # 5 minutes

BLOCK_THRESHOLD = 60.0
NUDGE_THRESHOLD = 30.0


def _parse_token(token_str: str) -> tuple[dict | None, str | None]:
    """Parse the agent token. Returns (payload, error)."""
    try:
        payload = json.loads(token_str)
        return payload, None
    except Exception:
        return None, "Token is not valid JSON"


def _validate_token(payload: dict, user_id: str) -> tuple[float, list[str]]:
    """Validate token fields. Returns (risk_score, issues)."""
    score = 0.0
    issues = []

    platform = payload.get("platform", "").lower()
    if platform not in KNOWN_PLATFORMS:
        score += 40
        issues.append(f"Unknown platform '{platform}'")

    issued_at = payload.get("issued_at")
    if not issued_at:
        score += 20
        issues.append("Missing issued_at timestamp")
    else:
        age = time.time() - issued_at
        if age > TOKEN_MAX_AGE_SECONDS:
            score += 30
            issues.append(f"Token expired — {age:.0f}s old (max {TOKEN_MAX_AGE_SECONDS}s)")

    session_id = payload.get("session_id")
    if not session_id:
        score += 20
        issues.append("Missing session_id")

    # In production: verify signature against platform's public key
    # For now: flag if signature field is entirely absent
    if "signature" not in payload:
        score += 30
        issues.append("No signature field — cannot verify platform identity")

    return min(100.0, score), issues


def run(
    agent_token: str | None,
    user_id: str,
    merchant_id: str,
) -> DetectorResult:

    score = 0.0
    issues = []
    session_id = "unknown"

    # ── A) Token validation ───────────────────────────────────────────────────
    if not agent_token:
        score += 50
        issues.append("No agent identity token provided — cannot verify platform")
    else:
        payload, parse_error = _parse_token(agent_token)
        if parse_error:
            score += 60
            issues.append(f"Token parse failed: {parse_error}")
        else:
            token_score, token_issues = _validate_token(payload, user_id)
            score += token_score
            issues.extend(token_issues)
            session_id = payload.get("session_id", "unknown")

    score = min(100.0, score)

    # ── B) Velocity detection ─────────────────────────────────────────────────
    velocity = record_velocity(merchant_id, user_id, session_id)
    if velocity["flagged"]:
        score = min(100.0, score + 40)
        issues.extend(velocity["flags"])

    passed = score < BLOCK_THRESHOLD

    if score >= BLOCK_THRESHOLD:
        reason = "agent_identity_failed"
    elif score >= NUDGE_THRESHOLD:
        reason = "agent_identity_unverified"
    else:
        reason = "agent_identity_acceptable"

    return DetectorResult(
        passed=passed,
        score=round(score, 1),
        reason=reason,
        detail=" | ".join(issues) if issues else "Agent identity verified."
    )
