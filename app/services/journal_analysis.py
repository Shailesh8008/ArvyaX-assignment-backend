import json
from functools import lru_cache

from groq import Groq

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


def analyze_emotion(text: str) -> JournalAnalysisResponse:
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

    return JournalAnalysisResponse.model_validate(
        json.loads(response.choices[0].message.content)
    )
