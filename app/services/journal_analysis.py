import json
import hashlib
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional, Tuple

from groq import Groq

from app.db import get_analysis_cache_collection
from app.schemas import JournalAnalysisResponse
from app.settings import settings


SYSTEM_PROMPT = """You are an emotion analyzer. Respond with valid JSON only.
No markdown, no explanation. Exact format:
{
  "emotion": "string",
  "keywords": ["string", "string"],
  "summary": "string"
}"""


@lru_cache(maxsize=1)
def get_groq_client() -> Groq:
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    return Groq(api_key=settings.GROQ_API_KEY)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _get_text_hash(text: str) -> str:
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


def _get_cached_analysis(text: str) -> Optional[JournalAnalysisResponse]:
    cache_collection = get_analysis_cache_collection()
    document = cache_collection.find_one({"textHash": _get_text_hash(text)})
    if document is None:
        return None

    return JournalAnalysisResponse(
        emotion=document["emotion"],
        keywords=document["keywords"],
        summary=document["summary"],
        cached=True,
    )


def _store_cached_analysis(text: str, analysis: JournalAnalysisResponse) -> None:
    cache_collection = get_analysis_cache_collection()
    cache_collection.update_one(
        {"textHash": _get_text_hash(text)},
        {
            "$set": {
                "normalizedText": _normalize_text(text),
                "emotion": analysis.emotion,
                "keywords": analysis.keywords,
                "summary": analysis.summary,
                "createdAt": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


def analyze_emotion_with_cache(text: str) -> Tuple[JournalAnalysisResponse, bool]:
    cached_analysis = _get_cached_analysis(text)
    if cached_analysis is not None:
        return cached_analysis, True

    client = get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": f"Analyze the emotion in this text: {text}",
            },
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if content is None:
        raise ValueError("Groq returned an empty response.")

    analysis = JournalAnalysisResponse.model_validate(
        json.loads(content)
    )
    analysis.cached = False
    _store_cached_analysis(text, analysis)
    return analysis, False


def analyze_emotion(text: str) -> JournalAnalysisResponse:
    analysis, _ = analyze_emotion_with_cache(text)
    return analysis
