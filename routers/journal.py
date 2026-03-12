import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException, status
from groq import GroqError

from app.db import get_journal_collection
from app.middleware.auth import require_user
from app.schemas import (
    JournalAnalysisLookupResponse,
    JournalAnalysisResponse,
    JournalAnalyzeRequest,
    JournalCreate,
    JournalEntry,
    JournalInsightsResponse,
)
from app.services.journal_analysis import analyze_emotion_with_cache
from app.services.rate_limit import ensure_analyze_rate_limit


router = APIRouter(prefix="/api/journal", tags=["journal"])

STOP_WORDS = {
    "the", "and", "that", "have", "with", "this", "from", "were", "what", "when",
    "your", "about", "there", "their", "would", "could", "should", "after", "before",
    "today", "really", "just", "into", "because", "while", "where", "which", "been",
    "being", "them", "they", "felt", "feel", "still", "than", "then", "very", "some",
    "much", "more", "most", "into", "over", "under", "also", "only", "here", "journal",
}


def _serialize_entry_document(entry: dict[str, Any], user_id: str) -> JournalEntry:
    entry_id = entry.get("id") or entry.get("_id") or ObjectId()
    created_at = entry.get("createdAt") or datetime.now(timezone.utc)

    return JournalEntry(
        id=str(entry_id),
        userId=user_id,
        ambience=entry["ambience"],
        text=entry["text"],
        createdAt=created_at,
    )


def _get_grouped_entries(journal_collection: Any, user_id: str) -> list[JournalEntry]:
    bucket = journal_collection.find_one(
        {"userId": user_id, "documentType": "journal_bucket"},
        {"entries": 1},
    )
    if not bucket:
        return []

    entries = bucket.get("entries", [])
    if not isinstance(entries, list):
        return []

    sorted_entries = sorted(
        [entry for entry in entries if isinstance(entry, dict)],
        key=lambda entry: entry.get("createdAt") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return [_serialize_entry_document(entry, user_id) for entry in sorted_entries]


def _get_legacy_entries(journal_collection: Any, user_id: str) -> list[JournalEntry]:
    documents = journal_collection.find(
        {"userId": user_id, "documentType": {"$ne": "journal_bucket"}}
    ).sort("createdAt", -1)
    return [_serialize_entry_document(document, user_id) for document in documents]


def _get_all_entries(journal_collection: Any, user_id: str) -> list[JournalEntry]:
    grouped_entries = _get_grouped_entries(journal_collection, user_id)
    if grouped_entries:
        return grouped_entries

    return _get_legacy_entries(journal_collection, user_id)


def _get_analysis_bucket(journal_collection: Any, user_id: str) -> list[dict[str, Any]]:
    bucket = journal_collection.find_one(
        {"userId": user_id, "documentType": "journal_bucket"},
        {"analysisHistory": 1},
    )
    analysis_history = bucket.get("analysisHistory", []) if bucket else []
    return (
        [record for record in analysis_history if isinstance(record, dict)]
        if isinstance(analysis_history, list)
        else []
    )


def _find_analysis_for_journal(
    journal_collection: Any,
    user_id: str,
    journal_id: str,
) -> Optional[dict[str, Any]]:
    analysis_history = _get_analysis_bucket(journal_collection, user_id)
    for record in reversed(analysis_history):
        if record.get("journalId") == journal_id:
            return record
    return None


def _derive_top_emotion(analysis_history: list[dict[str, Any]]) -> str:
    emotion_counts = Counter[str]()

    for record in analysis_history:
        emotion = record.get("emotion")
        if isinstance(emotion, str) and emotion.strip():
            emotion_counts[emotion.strip().lower()] += 1

    return emotion_counts.most_common(1)[0][0].title() if emotion_counts else "Neutral"


def _derive_recent_keywords(entries: list[JournalEntry]) -> list[str]:
    keyword_counts = Counter[str]()

    for entry in entries[:5]:
        for word in re.findall(r"[a-z]{4,}", entry.text.lower()):
            if word in STOP_WORDS:
                continue
            keyword_counts[word] += 1

    return [word for word, _ in keyword_counts.most_common(5)]


@router.post("", response_model=JournalEntry, status_code=status.HTTP_201_CREATED)
def create_journal_entry(
    payload: JournalCreate,
    user_id: str = Depends(require_user),
) -> JournalEntry:
    if payload.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create journal entries for the logged-in user.",
        )

    journal_collection = get_journal_collection()
    entry = {
        "id": str(ObjectId()),
        "ambience": payload.ambience,
        "text": payload.text,
        "createdAt": datetime.now(timezone.utc),
    }
    journal_collection.update_one(
        {"userId": user_id, "documentType": "journal_bucket"},
        {
            "$setOnInsert": {
                "userId": user_id,
                "documentType": "journal_bucket",
            },
            "$push": {"entries": entry},
            "$set": {"updatedAt": entry["createdAt"]},
        },
        upsert=True,
    )

    return JournalEntry(
        id=entry["id"],
        userId=user_id,
        ambience=entry["ambience"],
        text=entry["text"],
        createdAt=entry["createdAt"],
    )


@router.post(
    "/analyze",
    response_model=JournalAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
def analyze_journal(
    payload: JournalAnalyzeRequest,
    user_id: str = Depends(require_user),
) -> JournalAnalysisResponse:
    try:
        ensure_analyze_rate_limit(user_id)
        analysis, was_cached = analyze_emotion_with_cache(payload.text)
        analysis.cached = was_cached
        journal_collection = get_journal_collection()
        analysis_record = {
            "id": str(ObjectId()),
            "journalId": payload.journal_id,
            "text": payload.text,
            "emotion": analysis.emotion,
            "keywords": analysis.keywords,
            "summary": analysis.summary,
            "createdAt": datetime.now(timezone.utc),
        }
        journal_collection.update_one(
            {"userId": user_id, "documentType": "journal_bucket"},
            {
                "$setOnInsert": {
                    "userId": user_id,
                    "documentType": "journal_bucket",
                },
                "$push": {"analysisHistory": analysis_record},
                "$set": {"updatedAt": analysis_record["createdAt"]},
            },
            upsert=True,
        )
        return analysis
    except RuntimeError as exc:
        if str(exc).startswith("Rate limit exceeded:"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(exc),
            ) from exc
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except (GroqError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to analyze journal text with Groq.",
        ) from exc


@router.get(
    "/analysis/{user_id}/{journal_id}",
    response_model=JournalAnalysisLookupResponse,
    status_code=status.HTTP_200_OK,
)
def get_journal_analysis(
    user_id: str,
    journal_id: str,
    authenticated_user_id: str = Depends(require_user),
) -> JournalAnalysisLookupResponse:
    if user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view analysis for the logged-in user.",
        )

    journal_collection = get_journal_collection()
    analysis_record = _find_analysis_for_journal(journal_collection, user_id, journal_id)
    if analysis_record is None:
        return JournalAnalysisLookupResponse(
            ok=False,
            message="No analysis found for this journal.",
        )

    return JournalAnalysisLookupResponse(
        ok=True,
        analysis=JournalAnalysisResponse(
            emotion=analysis_record["emotion"],
            keywords=analysis_record["keywords"],
            summary=analysis_record["summary"],
        ),
    )


@router.get(
    "/insights/{user_id}",
    response_model=JournalInsightsResponse,
    status_code=status.HTTP_200_OK,
)
def get_journal_insights(
    user_id: str,
    authenticated_user_id: str = Depends(require_user),
) -> JournalInsightsResponse:
    if user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view insights for the logged-in user.",
        )

    journal_collection = get_journal_collection()
    entries = _get_all_entries(journal_collection, user_id)
    analysis_history = _get_analysis_bucket(journal_collection, user_id)
    ambience_counts = Counter(entry.ambience.strip().lower() for entry in entries if entry.ambience.strip())
    most_used_ambience = ambience_counts.most_common(1)[0][0].title() if ambience_counts else "None"

    return JournalInsightsResponse(
        totalEntries=len(entries),
        topEmotion=_derive_top_emotion(analysis_history),
        mostUsedAmbience=most_used_ambience,
        recentKeywords=_derive_recent_keywords(entries),
    )


@router.get("/{user_id}", response_model=list[JournalEntry], status_code=status.HTTP_200_OK)
def get_journal_entries(
    user_id: str,
    authenticated_user_id: str = Depends(require_user),
) -> list[JournalEntry]:
    if user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view journal entries for the logged-in user.",
        )

    journal_collection = get_journal_collection()
    return _get_all_entries(journal_collection, user_id)
