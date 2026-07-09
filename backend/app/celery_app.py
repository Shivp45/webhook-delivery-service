"""
celery_app.py
-------------
Creates and configures the Celery application instance.
Both the FastAPI app (for .delay()) and the Celery worker import this module.
"""

import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "webhook_delivery",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"],  # auto-discover task module
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Use a single default queue — no custom routing needed
    task_default_queue="default",
)
