
from celery import Celery

# Fixed Redis connection to match main.py
celery = Celery(
    'tasks',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0',
    include=["app.main"]  # Include main.py where the task is defined
)

# Configure Celery
celery.conf.update(
    task_track_started=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    result_backend='redis://redis:6379/0'
)

celery.conf.task_routes = {
    "run_plugin_analysis": {"queue": "volatility"}
}
