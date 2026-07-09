"""
main.py
-------
FastAPI application entry point.

Exposes exactly five endpoints:
  POST /webhooks          — register a webhook endpoint
  GET  /webhooks          — list all registered endpoints
  POST /events            — create an event and queue deliveries
  GET  /deliveries        — list all delivery records
  GET  /deliveries/{id}   — get one delivery by ID
"""

import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.database import engine, get_db, Base
from app.models import WebhookEndpoint, Event, Delivery, DeliveryStatus
from app.schemas import (
    WebhookEndpointCreate,
    WebhookEndpointResponse,
    EventCreate,
    EventResponse,
    DeliveryResponse,
)
from app.tasks import deliver_webhook

logger = logging.getLogger(__name__)


def create_tables_with_retry(retries: int = 10, delay: int = 3) -> None:
    """
    Try to create all tables, retrying if PostgreSQL isn't ready yet.
    This handles the race condition that occurs when Docker Compose starts
    the database and the API container at nearly the same time.
    """
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully.")
            return
        except OperationalError as exc:
            if attempt == retries:
                raise
            logger.warning(
                "Database not ready (attempt %d/%d). Retrying in %ds… (%s)",
                attempt,
                retries,
                delay,
                exc,
            )
            time.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup logic (table creation) before accepting requests."""
    create_tables_with_retry()
    yield


app = FastAPI(
    title="Webhook Delivery Service",
    description=(
        "A learning project demonstrating webhook registration, "
        "event creation, async delivery via Celery, retry logic, "
        "and delivery status tracking."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Feature 1: Register a webhook endpoint
# ---------------------------------------------------------------------------

@app.post("/webhooks", response_model=WebhookEndpointResponse, status_code=201)
def register_webhook(
    body: WebhookEndpointCreate,
    db: Session = Depends(get_db),
):
    """
    Register a new webhook endpoint.

    The endpoint will receive POST requests whenever an event
    matching its event_type is created.
    """
    endpoint = WebhookEndpoint(
        event_type=body.event_type,
        target_url=body.target_url,
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint


@app.get("/webhooks", response_model=list[WebhookEndpointResponse])
def list_webhooks(db: Session = Depends(get_db)):
    """Return all registered webhook endpoints."""
    return db.query(WebhookEndpoint).all()


# ---------------------------------------------------------------------------
# Feature 2: Create an event
# ---------------------------------------------------------------------------

@app.post("/events", response_model=EventResponse, status_code=201)
def create_event(
    body: EventCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new event and immediately queue async deliveries.

    Steps:
    1. Persist the event.
    2. Find all endpoints registered for this event_type.
    3. Create a PENDING Delivery for each endpoint.
    4. Enqueue a Celery task for each delivery.
    5. Return immediately — HTTP requests happen inside the worker.
    """
    # 1. Persist event
    event = Event(event_type=body.event_type, payload=body.payload)
    db.add(event)
    db.commit()
    db.refresh(event)

    # 2. Find matching endpoints
    endpoints = (
        db.query(WebhookEndpoint)
        .filter(WebhookEndpoint.event_type == body.event_type)
        .all()
    )

    # 3. Create PENDING deliveries
    deliveries_queued = 0
    for endpoint in endpoints:
        delivery = Delivery(
            event_id=event.id,
            endpoint_id=endpoint.id,
            status=DeliveryStatus.PENDING,
        )
        db.add(delivery)
        db.flush()  # get delivery.id before commit

        # 4. Enqueue Celery task
        deliver_webhook.delay(delivery.id)
        deliveries_queued += 1

    db.commit()

    return EventResponse(
        id=event.id,
        event_type=event.event_type,
        payload=event.payload,
        created_at=event.created_at,
        deliveries_queued=deliveries_queued,
    )


# ---------------------------------------------------------------------------
# Feature 5: Track delivery status
# ---------------------------------------------------------------------------

@app.get("/deliveries", response_model=list[DeliveryResponse])
def list_deliveries(db: Session = Depends(get_db)):
    """Return all delivery records."""
    return db.query(Delivery).all()


@app.get("/deliveries/{delivery_id}", response_model=DeliveryResponse)
def get_delivery(delivery_id: int, db: Session = Depends(get_db)):
    """
    Return a single delivery by ID.
    Returns HTTP 404 if the delivery does not exist.
    """
    delivery = db.get(Delivery, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return delivery
