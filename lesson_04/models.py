"""
Lesson 04 models — persistent state for long-running media generation jobs.
"""

from django.db import models


class VideoGenerationJob(models.Model):
    """
    Tracks an async video-generation request (Kling / Luma API).

    The job is created immediately when the user submits a prompt.
    A background poll (HTMX hx-trigger="every 5s") checks the status
    endpoint until the job reaches "done" or "failed".

    Attributes:
        task_id:    Unique job ID returned by the video generation API.
        prompt:     The original text prompt supplied by the user.
        status:     One of "pending", "processing", "done", "failed".
        result_url: Public URL of the generated video (populated when done).
        created_at: Timestamp of job creation.
    """

    task_id    = models.CharField(max_length=128, unique=True)
    prompt     = models.TextField()
    status     = models.CharField(max_length=32, default="pending")
    result_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"VideoJob({self.task_id[:12]}…) — {self.status}"
