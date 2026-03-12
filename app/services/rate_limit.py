from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument

from app.db import get_rate_limit_collection


ANALYZE_MINUTE_LIMIT = 5
ANALYZE_DAY_LIMIT = 100


def _floor_to_minute(current_time: datetime) -> datetime:
    return current_time.replace(second=0, microsecond=0)


def _floor_to_day(current_time: datetime) -> datetime:
    return current_time.replace(hour=0, minute=0, second=0, microsecond=0)


def _increment_window(user_id: str, scope: str, window_start: datetime, expires_at: datetime) -> int:
    rate_limit_collection = get_rate_limit_collection()
    record = rate_limit_collection.find_one_and_update(
        {
            "userId": user_id,
            "scope": scope,
            "windowStart": window_start,
        },
        {
            "$inc": {"count": 1},
            "$setOnInsert": {
                "expiresAt": expires_at,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(record["count"])


def ensure_analyze_rate_limit(user_id: str) -> None:
    current_time = datetime.now(timezone.utc)

    minute_window_start = _floor_to_minute(current_time)
    minute_count = _increment_window(
        user_id=user_id,
        scope="journal_analyze_minute",
        window_start=minute_window_start,
        expires_at=minute_window_start + timedelta(minutes=1, seconds=5),
    )
    if minute_count > ANALYZE_MINUTE_LIMIT:
        raise RuntimeError("Rate limit exceeded: max 5 analysis requests per minute.")

    day_window_start = _floor_to_day(current_time)
    day_count = _increment_window(
        user_id=user_id,
        scope="journal_analyze_day",
        window_start=day_window_start,
        expires_at=day_window_start + timedelta(days=1, minutes=5),
    )
    if day_count > ANALYZE_DAY_LIMIT:
        raise RuntimeError("Rate limit exceeded: max 100 analysis requests per day.")
