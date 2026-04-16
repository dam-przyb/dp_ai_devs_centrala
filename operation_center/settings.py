from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-key-change-in-production-please",
)

DEBUG = os.getenv("DEBUG", "True") == "True"

ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".ag3nts.org"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # project apps
    "core",
    "lesson_01",
    "lesson_02",
    "lesson_03",
    "lesson_04",
    "lesson_05",
    # Season 2
    "module_02_01",
    "module_02_02",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "operation_center.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "operation_center.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Session engine (uses DB by default — fine for SQLite)
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# ── Project-specific directories ──────────────────────────────────────────────
SANDBOX_DIR = BASE_DIR / "sandbox"
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"

# Ensure runtime directories exist
SANDBOX_DIR.mkdir(exist_ok=True)
KNOWLEDGE_BASE_DIR.mkdir(exist_ok=True)
(BASE_DIR / "media").mkdir(exist_ok=True)

# ── LLM / OpenRouter ──────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTERKEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "google/gemini-3-flash-preview" #"openai/gpt-4o-mini"

# OpenAI key (Whisper, lesson 04 — optional)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# MCP server command (lesson 03 — optional)
MCP_SERVER_SCRIPT = os.getenv("MCP_SERVER_SCRIPT", "")

# AI Devs API Key (Quest task)
AIDEVS_API_KEY = os.getenv("AIDEVSKEY", "")

# Model used specifically for the findhim investigation agent.
# Can be overridden via FINDHIM_MODEL env var to use a stronger model when
# gpt-4o-mini makes reasoning errors on the multi-step distance-comparison task.
FINDHIM_MODEL = os.getenv("FINDHIM_MODEL", "openai/gpt-5.4-mini")

# ── Season 2 models & paths ───────────────────────────────────────────────────
# Model for the Agentic RAG agent (module 02_01). Override via env var.
RAG_02_01_MODEL = os.getenv("RAG_02_01_MODEL", "openai/gpt-5-mini")

# Document root searched by the RAG file tools. Override via env var.
LESSONS_TEXTS_DIR = BASE_DIR / os.getenv("LESSONS_TEXTS_DIR", "_lessons_texts")

# Model for module_02_02 (Chunking, Embeddings, Hybrid RAG).
RAG_02_02_MODEL = os.getenv("RAG_02_02_MODEL", "openai/gpt-4o-mini")
