from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class CreatorCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    brand_name: str = Field(..., min_length=2, max_length=120)
    niche: str = Field(..., min_length=2, max_length=80)
    email: EmailStr
    platform_focus: str = Field(default="Instagram", min_length=2, max_length=120)
    bio: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=250)
    approved_for_publication: bool = False
    authorized_for_avatar_use: bool = False

    @field_validator("website")
    @classmethod
    def validate_website(cls, value):
        if value is None:
            return value
        cleaned = value.strip()
        if cleaned and not (cleaned.startswith("http://") or cleaned.startswith("https://")):
            raise ValueError("Website must start with http:// or https://")
        return cleaned


class CreatorRead(BaseModel):
    id: int
    name: str
    brand_name: str
    niche: str
    email: EmailStr
    platform_focus: str
    bio: str | None
    website: str | None
    approved_for_publication: bool
    authorized_for_avatar_use: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
