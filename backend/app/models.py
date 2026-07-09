"""
models.py
---------
Exactly three SQLAlchemy 2.0 ORM models:
  - WebhookEndpoint
  - Event
  - Delivery
"""

import datetime
import enum
from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DeliveryStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class WebhookEndpoint(Base):
    """
    Stores registered webhook endpoints.
    A single endpoint listens for one event_type and
    has one target URL where we POST the event payload.
    """
    __tablename__ = "webhook_endpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        nullable=False,
    )

    # One WebhookEndpoint → many Deliveries
    deliveries: Mapped[list["Delivery"]] = relationship(
        "Delivery", back_populates="endpoint"
    )


class Event(Base):
    """
    Represents a domain event (e.g., order.created).
    Stores the raw JSON payload using PostgreSQL JSONB.
    """
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        nullable=False,
    )

    # One Event → many Deliveries
    deliveries: Mapped[list["Delivery"]] = relationship(
        "Delivery", back_populates="event"
    )


class Delivery(Base):
    """
    Tracks the delivery of an Event to a WebhookEndpoint.
    Each delivery starts as PENDING and transitions to
    SUCCESS or FAILED based on the outgoing HTTP result.
    """
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id"), nullable=False, index=True
    )
    endpoint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("webhook_endpoints.id"), nullable=False, index=True
    )
    status: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus, name="delivery_status"),
        default=DeliveryStatus.PENDING,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="deliveries")
    endpoint: Mapped["WebhookEndpoint"] = relationship(
        "WebhookEndpoint", back_populates="deliveries"
    )
