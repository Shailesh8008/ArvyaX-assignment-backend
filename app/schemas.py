from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., max_length=128)

    model_config = ConfigDict(str_strip_whitespace=True)


class UserLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., max_length=128)

    model_config = ConfigDict(str_strip_whitespace=True)


class AuthUserResponse(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class AuthSuccessResponse(BaseModel):
    ok: bool = True
    user: AuthUserResponse


class UserDetailsResponse(BaseModel):
    ok: bool = True
    user_id: str = Field(..., alias="userId")
    user: AuthUserResponse
    journals: list["JournalEntry"]

    model_config = ConfigDict(populate_by_name=True)


class JournalCreate(BaseModel):
    user_id: str = Field(..., alias="userId", min_length=1, max_length=255)
    ambience: str = Field(..., min_length=1, max_length=100)
    text: str = Field(..., min_length=1, max_length=5000)

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class JournalAnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    journal_id: Optional[str] = Field(default=None, alias="journalId", max_length=255)

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class JournalAnalysisResponse(BaseModel):
    emotion: str
    keywords: list[str]
    summary: str
    cached: bool = False


class JournalInsightsResponse(BaseModel):
    total_entries: int = Field(..., alias="totalEntries")
    top_emotion: str = Field(..., alias="topEmotion")
    most_used_ambience: str = Field(..., alias="mostUsedAmbience")
    recent_keywords: list[str] = Field(..., alias="recentKeywords")

    model_config = ConfigDict(populate_by_name=True)


class JournalAnalysisLookupResponse(BaseModel):
    ok: bool
    analysis: Optional["JournalAnalysisResponse"] = None
    message: Optional[str] = None


class JournalEntry(BaseModel):
    id: str
    user_id: str = Field(..., alias="userId")
    ambience: str
    text: str
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )
