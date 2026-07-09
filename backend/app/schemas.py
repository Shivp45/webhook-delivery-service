"""
schemas.py
----------
Pydantic v2 schemas for request validation and response serialization.
"""

import datetime
from typing import Any
from pydantic import BaseModel, HttpUrl, ConfigDict


# ---------------------------------------------------------------------------
# WebhookEndpoint schemas
# ---------------------------------------------------------------------------

class WebhookEndpointCreate(BaseModel):
    """Request body for POST /webhooks."""
    event_type: str
    target_url: str  # kept as str to avoid Pydantic v2 HttpUrl serialization quirks


class WebhookEndpointResponse(BaseModel):
    """Response schema for a registered webhook endpoint."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    target_url: str
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Event schemas
# ---------------------------------------------------------------------------

class EventCreate(BaseModel):
    """Request body for POST /events."""
    event_type: str
    payload: dict[str, Any]


class EventResponse(BaseModel):
    """Response schema returned immediately after event creation."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime.datetime
    deliveries_queued: int  # how many delivery tasks were enqueued


# ---------------------------------------------------------------------------
# Delivery schemas
# ---------------------------------------------------------------------------

class DeliveryResponse(BaseModel):
    """Full delivery record returned by GET /deliveries and GET /deliveries/{id}."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    endpoint_id: int
    status: str
    attempts: int
    last_error: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
