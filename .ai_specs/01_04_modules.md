# Coding Agent Instructions: Lesson 04 Modules (Media, Visual, Audio)

**Goal Requirement**: Implement processing of rich media. Given OpenRouter is strictly text/image-in and text-out, specific external API services or Hugging Face models will need to be configured for native audio/video tasks. 

## 1. Modules `01_04_audio` & `01_04_video`
**Objective**: A/V Transcription and generation.
*   **Backend Details**:
    1.  Since OpenRouter does not broadly support native audio file uploads like the raw Gemini File API, the Django backend should utilize the standard OpenAI SDK (e.g., `client.audio.transcriptions.create`) targeting a Whisper model for transcription.
    2.  Extract the transcription string, and pass it to OpenRouter for summarization/analysis.
*   **Frontend (HTMX)**:
    1.  An upload form `<form enctype="multipart/form-data" hx-post="..." hx-encoding="multipart/form-data">`. Wait for transcription and swap the resulting text block into the UI.

## 2. Module `01_04_video_generation`
**Objective**: Request video generation via text.
*   **Backend Details**: 
    1.  Use `requests` or `httpx` to trigger a specific generation API (like Kling API, Luma, or Replicate).
    2.  Because generation takes minutes, building a Celery backend is too complex. Simply start the generation hook and save the `task_id` in a Django DB record.
*   **Frontend (HTMX Polling)**:
    1.  The browser UI receives the `task_id`.
    2.  Utilize HTMX's polling feature: `<div hx-get="/video/status/{{ job_id }}/" hx-trigger="every 5s">Loading...</div>`. 
    3.  When the Django view detects the external job is `SUCCESS`, it returns a `<video>` tag instead, stopping the poll.

## 3. Modules `01_04_image_guidance`, `json_image`, `image_editing`
**Objective**: Image generation variations.
*   **Backend Details**:
    1.  Utilize standard `openai` library targeting DALL-E 3 (or an equivalent provider) for base generation from JSON or prompts.
    2.  For "Guidance" (ControlNet) and "Editing" (Inpainting), if OpenRouter does not provide these natively, explicitly direct the instruction to use local Python libraries containing Replicate API SDKs for execution.

## 4. Module `01_04_reports`
**Objective**: Construct stylized PDF documents.
*   **Backend Details**:
    1.  Gather data from the database or an LLM summary.
    2.  Render a standard Django HTML template (using `django.template.loader.render_to_string`).
    3.  Use the `WeasyPrint` Python package: `weasyprint.HTML(string=html).write_pdf(target)`. Do not use complex headless instances. Provide download links to the generated static file.
