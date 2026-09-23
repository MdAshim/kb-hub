"""
Django settings for config project.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-r7g9#*43%zux5&(5*5=h^@p!8i9qeiqxtqs8j3ssdft00wc@-k",
)

DEBUG = _env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "huey.contrib.djhuey",
    "harvest",
    "knowledge",
    "search",
    "api",
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

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Data directory: SQLite db, FAISS index and Huey's queue db all live here.
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Application settings (all tunables come from .env; see .env.example)
# ---------------------------------------------------------------------------

# Embeddings
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIM = _env_int("EMBEDDING_DIM", 384)
FAISS_INDEX_PATH = BASE_DIR / os.environ.get("FAISS_INDEX_PATH", "data/faiss.index")

# Chunking
CHUNK_SIZE_TOKENS = _env_int("CHUNK_SIZE_TOKENS", 450)
CHUNK_OVERLAP_TOKENS = _env_int("CHUNK_OVERLAP_TOKENS", 50)

# Retrieval
SEARCH_TOP_K = _env_int("SEARCH_TOP_K", 20)
SEARCH_CONTEXT_CHUNKS = _env_int("SEARCH_CONTEXT_CHUNKS", 8)
PERSON_BOOST = _env_float("PERSON_BOOST", 0.10)

# LLM
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")
LLM_TIMEOUT_SECONDS = _env_int("LLM_TIMEOUT_SECONDS", 60)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

# Fetching
FETCH_TIMEOUT_SECONDS = _env_int("FETCH_TIMEOUT_SECONDS", 20)
FETCH_MAX_RETRIES = _env_int("FETCH_MAX_RETRIES", 2)
PLAYWRIGHT_FALLBACK = _env_bool("PLAYWRIGHT_FALLBACK", True)
MIN_TEXT_CHARS = _env_int("MIN_TEXT_CHARS", 500)


# ---------------------------------------------------------------------------
# Huey (background worker). SqliteHuey, no Redis/Celery.
# Thread workers, not process workers: process mode is unreliable on Windows.
# Worker count stays at 1 by default (HUEY_WORKERS) so FAISS writes stay serialized.
# ---------------------------------------------------------------------------

HUEY_WORKERS = _env_int("HUEY_WORKERS", 1)

HUEY = {
    "huey_class": "huey.SqliteHuey",
    "name": "kb_hub",
    "filename": str(DATA_DIR / "huey.db"),
    "results": True,
    "store_none": False,
    "immediate": False,
    "utc": True,
    "consumer": {
        "workers": HUEY_WORKERS,
        "worker_type": "thread",
    },
}

# Under pytest, tasks are enqueued (never run, since immediate stays False)
# but must never land in the real dev queue file -- Django's test-DB
# rollback doesn't cover Huey's separate SQLite store, so without this a
# stray enqueued task from a test run would sit in data/huey.db and could
# later be picked up by a real `run_huey` consumer.
if "pytest" in sys.modules:
    HUEY["filename"] = str(DATA_DIR / "huey-test.db")


# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}
