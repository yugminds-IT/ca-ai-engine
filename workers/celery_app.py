from celery import Celery
from config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "ca-worker-cluster",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "workers.tasks.tds.extraction_tasks",
        "workers.tasks.tds.generation_tasks",
        "workers.tasks.gst.extraction_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

celery_app.conf.task_routes = {
    "workers.tasks.tds.*": {"queue": "tds"},
    "workers.tasks.gst.*": {"queue": "gst"},
}
