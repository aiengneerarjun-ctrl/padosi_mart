import uuid

from pydantic import BaseModel, ConfigDict
from typing import Literal

Language = Literal["en", "hi", "bho"]

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    name: str | None
    email: str | None
    language: Language
    roles: list[str]


class UserUpdate(BaseModel):
    name: str | None = None
    language: Language | None = None
    email: str | None = None