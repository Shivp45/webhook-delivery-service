"""
tasks.py
--------
Celery task: deliver a webhook and retry on failure.

Retry logic (satisfies Feature 3 & 4):
  - max_retries=2 means Celery will call the task at most 3 times total
    (1 initial attempt + 2 retries = 3 total attempts).
  - Every actual HTTP attempt increments delivery.attempts by 1.
  - On success  → status = SUCCESS
  - On final failure → status = FAILED, last_error is stored
"""

import httpx
from celery import Task
from celery.exceptions import MaxRetriesExceededError

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Delivery, DeliveryStatus

# Fixed delay between retries (seconds)
RETRY_DELAY_SECONDS = 10

# Maximum number of retries (so total attempts = max_retries + 1 = 3)
MAX_RETRIES = 2


@celery_app.task(
    bind=True,
    max_retries=MAX_RETRIES,
    default_retry_delay=RETRY_DELAY_SECONDS,
    acks_late=True,
)
def deliver_webhook(self: Task, delivery_id: int) -> dict:
    """
    Attempt to deliver a webhook payload to the registered target URL.

    Parameters
    ----------
    delivery_id : int
        Primary key of the Delivery row to process.

    Returns
    -------
    dict
        Simple status dict for the Celery result backend.
    """
    db = SessionLocal()
    try:
        # ------------------------------------------------------------------
        # 1. Load the Delivery (and its related Event + Endpoint)
        # ------------------------------------------------------------------
        delivery = db.get(Delivery, delivery_id)
        if delivery is None:
            # Nothing we can do — row doesn't exist
            return {"status": "error", "reason": f"Delivery {delivery_id} not found"}

        event = delivery.event
        endpoint = delivery.endpoint

        # ------------------------------------------------------------------
        # 2. Increment attempt counter BEFORE making the HTTP request
        # ------------------------------------------------------------------
        delivery.attempts += 1
        db.commit()

        # ------------------------------------------------------------------
        # 3. Send the HTTP POST to the target URL
        # ------------------------------------------------------------------
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    endpoint.target_url,
                    json={
                        "event_id": event.id,
                        "event_type": event.event_type,
                        "payload": event.payload,
                    },
                    headers={"Content-Type": "application/json"},
                )
            response.raise_for_status()  # raises HTTPStatusError for 4xx / 5xx

        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            # ------------------------------------------------------------------
            # 4. Handle failure: retry or mark as FAILED
            # ------------------------------------------------------------------
            error_message = str(exc)

            try:
                # raise self.retry() schedules the next attempt and raises
                # Retry so Celery knows not to mark the task as done yet.
                raise self.retry(exc=exc)

            except MaxRetriesExceededError:
                # All three attempts exhausted — mark delivery as FAILED
                delivery.status = DeliveryStatus.FAILED
                delivery.last_error = error_message
                db.commit()
                return {
                    "status": "failed",
                    "delivery_id": delivery_id,
                    "error": error_message,
                }

        # ------------------------------------------------------------------
        # 5. Success path
        # ------------------------------------------------------------------
        delivery.status = DeliveryStatus.SUCCESS
        delivery.last_error = None
        db.commit()
        return {"status": "success", "delivery_id": delivery_id}

    finally:
        db.close()
