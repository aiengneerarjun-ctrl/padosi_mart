import uuid

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)  # English
    name_hi: str | None = Field(default=None, max_length=100)
    name_bho: str | None = Field(default=None, max_length=100)
    parent_id: uuid.UUID | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    name_hi: str | None = Field(default=None, max_length=100)
    name_bho: str | None = Field(default=None, max_length=100)
    sort_order: int | None = None
    is_active: bool | None = None


class AdminCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    name_hi: str | None
    name_bho: str | None
    sort_order: int
    is_active: bool


class CategoryOut(BaseModel):
    """Customer/seller ko: naam pehle se unki bhasha me."""

    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    sort_order: int


class BrandCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class BrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    is_active: bool | None = None


class BrandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool