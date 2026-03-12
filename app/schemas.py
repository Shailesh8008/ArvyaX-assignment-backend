from datetime import datetime

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

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )


class JournalAnalysisResponse(BaseModel):
    emotion: str
    keywords: list[str]
    summary: str


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
