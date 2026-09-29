"""Common schema models and generic response wrappers."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ResponseEnvelope(BaseModel, Generic[T]):
    """Generic response wrapper."""

    model_config = ConfigDict(from_attributes=True)
    data: T
