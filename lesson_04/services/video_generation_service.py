"""
Video generation service — simulate or call an external video-gen API.

In a real integration this would call Kling or Luma AI.  Since those APIs
require paid keys and have complex webhook flows, this demo uses a **mock**
implementation that pretends to generate a video and resolves after a few
status-poll cycles.  The HTMX polling pattern is fully exercised either way.

Real integration points are marked with # REAL: comments.
"""

import time
import uuid

from django.conf import settings

from lesson_04.models import VideoGenerationJob


# =============================================================================
# Job creation
# =============================================================================

def create_video_job(prompt: str) -> VideoGenerationJob:
    """
    Submit a new video-generation job and return the persisted model instance.

    In the mock implementation a unique task_id is generated locally.
    A real integration would POST to the Kling/Luma API here and store the
    API-assigned job ID.

    Args:
        prompt: User-supplied text description of the video to generate.

    Returns:
        A newly created VideoGenerationJob with status="pending".
    """
    # REAL: response = httpx.post(KLING_API_URL, json={"prompt": prompt}, ...)
    #       task_id  = response.json()["task_id"]
    task_id = str(uuid.uuid4())

    job = VideoGenerationJob.objects.create(
        task_id=task_id,
        prompt=prompt,
        status="pending",
    )
    return job


# =============================================================================
# Status polling
# =============================================================================

def _mock_progress(job: VideoGenerationJob) -> str:
    """
    Simulate job progression: pending → processing → done.

    Uses elapsed seconds since creation to decide the mock state.
    This lets students see the HTMX polling pattern in action without
    a real video API.
    """
    elapsed = time.time() - job.created_at.timestamp()
    if elapsed < 5:
        return "pending"
    if elapsed < 15:
        return "processing"
    return "done"


def poll_video_job(task_id: str) -> VideoGenerationJob:
    """
    Check and update the status of a video generation job.

    Fetches the current job, advances the mock state, persists and returns it.

    Args:
        task_id: The unique identifier stored in VideoGenerationJob.

    Returns:
        Updated VideoGenerationJob instance.

    Raises:
        VideoGenerationJob.DoesNotExist: If task_id is unknown.
    """
    job = VideoGenerationJob.objects.get(task_id=task_id)

    if job.status in ("done", "failed"):
        # Job is terminal — no need to poll the external API again
        return job

    # REAL: response = httpx.get(f"{KLING_STATUS_URL}/{task_id}", ...)
    #       new_status  = response.json()["status"]
    #       result_url  = response.json().get("video_url", "")
    new_status = _mock_progress(job)

    if new_status == "done":
        # Mock result URL — replace with real URL from API response
        job.result_url = "https://www.w3schools.com/html/mov_bbb.mp4"

    job.status = new_status
    job.save(update_fields=["status", "result_url"])
    return job
