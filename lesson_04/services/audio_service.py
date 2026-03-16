"""
Audio service — Whisper transcription + OpenRouter LLM summarisation.

Flow:
  1. Receive an audio file (Django InMemoryUploadedFile / TemporaryUploadedFile).
  2. Send it to OpenAI Whisper via the official `openai` SDK (OPENAI_API_KEY).
  3. Pass the transcript to an OpenRouter LLM for a concise summary.
  4. Return {transcript, summary}.

Note: Whisper is called through openai.audio.transcriptions, not OpenRouter,
because OpenRouter does not proxy Whisper.  A separate OPENAI_API_KEY is needed.
"""

import openai
from django.conf import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


# =============================================================================
# Transcription
# =============================================================================

def transcribe_audio(file_obj) -> str:
    """
    Transcribe an audio file using OpenAI Whisper.

    Args:
        file_obj: A Django uploaded file object (has .name and .read() / file handle).

    Returns:
        Transcribed text string.

    Raises:
        RuntimeError: If OPENAI_API_KEY is not configured.
    """
    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Whisper requires a direct OpenAI API key "
            "(OpenRouter does not proxy the Whisper endpoint)."
        )

    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    # The openai SDK expects a file-like object with a .name attribute
    response = client.audio.transcriptions.create(
        model="whisper-1",
        file=file_obj,
    )
    return response.text


# =============================================================================
# Summarisation
# =============================================================================

def summarise_transcript(transcript: str) -> str:
    """
    Ask an OpenRouter LLM for a concise summary of the transcript.

    Args:
        transcript: Full text returned by Whisper.

    Returns:
        A short summary string.
    """
    llm = ChatOpenAI(
        model=settings.OPENROUTER_DEFAULT_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )
    messages = [
        SystemMessage(content=(
            "You are a helpful assistant that summarises audio transcripts. "
            "Provide a concise, clear summary in 2-4 sentences."
        )),
        HumanMessage(content=f"Please summarise the following transcript:\n\n{transcript}"),
    ]
    response = llm.invoke(messages)
    return response.content


# =============================================================================
# Public entry point
# =============================================================================

def process_audio(file_obj) -> dict:
    """
    Transcribe and summarise an uploaded audio file.

    Args:
        file_obj: Django uploaded file.

    Returns:
        {"transcript": str, "summary": str}
    """
    transcript = transcribe_audio(file_obj)
    summary    = summarise_transcript(transcript)
    return {"transcript": transcript, "summary": summary}
