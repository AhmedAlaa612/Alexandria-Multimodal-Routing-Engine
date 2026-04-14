"""
Pydantic models for the Geocoding API.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class GeocodeQuery(BaseModel):
    address: str = Field(..., description="Address to geocode")
    language: str = Field("en", description="Language for results (e.g. 'en', 'ar')")
    bias: bool = Field(True, description="If true, bias results to Alexandria")
    user_lat: Optional[float] = Field(None, description="User latitude for proximity ranking")
    user_lng: Optional[float] = Field(None, description="User longitude for proximity ranking")


class GeocodeResult(BaseModel):
    latitude: float
    longitude: float
    formatted_address: str


class GeocodeResponse(BaseModel):
    success: bool
    query: str
    language: str
    bias: bool
    count: int = 0
    results: list[GeocodeResult] = []
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
