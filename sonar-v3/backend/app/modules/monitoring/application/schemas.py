from __future__ import annotations

from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class EntityTypeOut(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class AliasOut(BaseModel):
    id: UUID
    alias: str
    model_config = {"from_attributes": True}


class KeywordOut(BaseModel):
    id: UUID
    keyword: str
    language: str
    weight: int
    active: bool
    model_config = {"from_attributes": True}


class EntityCreate(BaseModel):
    name: str
    entity_type_id: int
    country_code: str | None = None
    description: str | None = None
    photo_url: str | None = None
    monitoring_type: str | None = None

    def model_post_init(self, __context):
        if self.country_code == "":
            object.__setattr__(self, "country_code", None)
        if self.description == "":
            object.__setattr__(self, "description", None)
        if self.photo_url == "":
            object.__setattr__(self, "photo_url", None)


class EntityPatch(BaseModel):
    name: str | None = None
    active: bool | None = None
    description: str | None = None
    photo_url: str | None = None
    monitoring_type: str | None = None


class EntityOut(BaseModel):
    id: UUID
    name: str
    entity_type_id: int
    entity_type_name: str | None = None
    country_code: str | None = None
    description: str | None = None
    photo_url: str | None = None
    active: bool
    monitoring_type: str | None = None
    created_at: datetime
    aliases: list[AliasOut] = []
    keywords: list[KeywordOut] = []
    model_config = {"from_attributes": True}


class AliasCreate(BaseModel):
    alias: str


class KeywordCreate(BaseModel):
    keyword: str
    language: str = "es"
    weight: int = 1


class TwitterFeedCreate(BaseModel):
    feed_type: str
    term: str


class TwitterFeedOut(BaseModel):
    id: UUID
    feed_type: str
    term: str
    display_name: str
    entity_id: UUID | None = None
    active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class SocialPlatformOut(BaseModel):
    id: int
    name: str
    code: str
    active: bool
    model_config = {"from_attributes": True}
