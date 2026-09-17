from __future__ import annotations

import logging
import os
import re
import sys
import tempfile
import threading
import time
import traceback
import uuid
from collections import deque
from datetime import date
from typing import Any, Deque, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

load_dotenv()

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("avatar-rag")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        log.warning("Invalid int for %s, using default %s", name, default)
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        log.warning("Invalid float for %s, using default %s", name, default)
        return default


def _parse_models(plural_key: str, singular_key: str, default_val: str) -> List[str]:
    """Parse comma-separated model list from .env, falling back to singular or default."""
    raw = os.getenv(plural_key, "").strip() or os.getenv(singular_key, "").strip() or default_val
    return [m.strip() for m in raw.split(",") if m.strip()]


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# 2. Groq — OpenAI-compatible
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODELS     = _parse_models("GROQ_MODELS", "GROQ_MODEL", "openai/gpt-oss-20b,groq/compound-mini,qwen/qwen3.8-27b")
GROQ_BASE_URL  = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()

# 4. OpenRouter — OpenAI-compatible
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODELS    = _parse_models("OPENROUTER_MODELS", "OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()

# 5. Ollama (local/tunnel) — OpenAI-compatible, no key required
OLLAMA_BASE_URL    = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").strip()
OLLAMA_CHAT_MODELS = _parse_models("OLLAMA_CHAT_MODELS", "OLLAMA_CHAT_MODEL", "qwen2.5:1.5b")

# Pinecone / embedding
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "").strip()
PINECONE_INDEX   = os.getenv("PINECONE_INDEX", "avatar-brain").strip()
EMBED_MODEL      = os.getenv("EMBED_MODEL", "nomic-embed-text").strip()

WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "base.en").strip()

MAX_OUTPUT_TOKENS  = _env_int("MAX_OUTPUT_TOKENS", 2048)
TEMPERATURE        = _env_float("TEMPERATURE", 0.1)

TOP_K              = _env_int("TOP_K", 8)
SECTION_TOP_K      = _env_int("SECTION_TOP_K", 10)
MIN_TOP_SCORE      = _env_float("MIN_TOP_SCORE", 0.30)
SCORE_WINDOW       = _env_float("SCORE_WINDOW", 0.28)
GRADUATION_DATE    = os.getenv("GRADUATION_DATE", "2026-06").strip()

MAX_MESSAGE_CHARS  = _env_int("MAX_MESSAGE_CHARS", 1000)
MAX_HISTORY_TURNS  = _env_int("MAX_HISTORY_TURNS", 4)
MAX_AUDIO_BYTES    = _env_int("MAX_AUDIO_BYTES", 25 * 1024 * 1024)

RATE_LIMIT_PER_MIN = _env_int("RATE_LIMIT_PER_MIN", 30)
GEMINI_MAX_RETRIES = _env_int("GEMINI_MAX_RETRIES", 1)
OAI_MAX_RETRIES    = _env_int("OAI_MAX_RETRIES", 1)
DEBUG_TOKEN        = os.getenv("DEBUG_TOKEN", "").strip()

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

OWNER_NAME     = "Arham Mahmood"
OWNER_EMAIL    = "mah.arhamper@gmail.com"
OWNER_GITHUB   = "https://github.com/ArhamMahmood"
OWNER_LINKEDIN = "https://www.linkedin.com/in/arham-mahmood-175b832a1"
OWNER_PHONE    = "+92 315 1547906"
OWNER_LOCATION = "Rawalpindi, Pakistan"

FALLBACK_RESPONSE = (
    f"Sorry! At this moment I can only help you with information related to "
    f"developer {OWNER_NAME}'s resume."
)
NOT_LISTED_RESPONSE = (
    f"That detail isn't listed on {OWNER_NAME}'s resume, so I can't confirm it. "
    f"I can tell you about his skills, projects, work experience, education, or certifications."
)

# --------------------------------------------------------------------------
# Third-party clients
# --------------------------------------------------------------------------

try:
    import ollama as _ollama_embed
except ImportError:
    _ollama_embed = None
    log.error("ollama package not installed — embeddings will fail")

try:
    from pinecone import Pinecone
except ImportError:
    Pinecone = None
    log.error("pinecone package not installed — retrieval will fail")

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None
    log.error("google-genai package not installed — Gemini generation will fail")

try:
    from openai import OpenAI as _OpenAI
except ImportError:
    _OpenAI = None
    log.error("openai package not installed — Groq/SambaNova/OpenRouter/Ollama generation will fail")


class ServiceError(Exception):
    def __init__(self, stage: str, detail: str):
        super().__init__(f"[{stage}] {detail}")
        self.stage = stage
        self.detail = detail


# --------------------------------------------------------------------------
# Provider waterfall state
# --------------------------------------------------------------------------

_PROVIDER_EXHAUSTED: Dict[str, bool] = {
    "gemini":     False,
    "groq":       False,
    "sambanova":  False,
    "openrouter": False,
    "ollama":     False,
}
_EXHAUSTED_LOCK = threading.Lock()
_EXHAUSTED_TTL: Dict[str, float] = {}
PROVIDER_RETRY_AFTER_S = _env_int("PROVIDER_RETRY_AFTER_S", 4 * 3600)


def _mark_exhausted(provider: str) -> None:
    with _EXHAUSTED_LOCK:
        _PROVIDER_EXHAUSTED[provider] = True
        _EXHAUSTED_TTL[provider] = time.time() + PROVIDER_RETRY_AFTER_S
    log.warning("Provider '%s' marked exhausted — will skip for %dh",
                provider, PROVIDER_RETRY_AFTER_S // 3600)


def _is_exhausted(provider: str) -> bool:
    with _EXHAUSTED_LOCK:
        if not _PROVIDER_EXHAUSTED.get(provider):
            return False
        ttl = _EXHAUSTED_TTL.get(provider, 0.0)
        if time.time() > ttl:
            _PROVIDER_EXHAUSTED[provider] = False
            log.info("Provider '%s' cooldown expired — re-enabling", provider)
            return False
        return True


def _is_quota_error(exc: Exception) -> bool:
    blob = str(exc).lower()
    return any(t in blob for t in (
        "429", "402",
        "quota", "rate limit", "resource_exhausted",
        "daily limit", "exceeded", "too many requests",
        "insufficient_quota", "insufficient balance",
        "billing", "payment required", "payment_required",
        "balance", "credits",
    ))


def _is_model_unavailable(exc: Exception) -> bool:
    blob = str(exc).lower()
    return any(t in blob for t in (
        "not_found", "not found", "404", "permission_denied",
        "does not exist", "is not supported", "unsupported model",
    ))


def _is_retryable(exc: Exception) -> bool:
    blob = str(exc).lower()
    return any(t in blob for t in (
        "500", "503", "unavailable", "internal error", "deadline", "timeout",
    ))


# --------------------------------------------------------------------------
# Global clients (initialised in startup)
# --------------------------------------------------------------------------

pinecone_index = None
gemini_client  = None
_groq_client: Optional[Any]       = None
_sambanova_client: Optional[Any]  = None
_openrouter_client: Optional[Any] = None
_ollama_oai_client: Optional[Any] = None

_whisper_model = None
_whisper_lock  = threading.Lock()
_whisper_state = "not_loaded"

app = FastAPI(
    title="Avatar RAG — Arham Mahmood",
    version="2.3.0",
    description="Grounded resume assistant with dynamic multi-model failover per provider.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials="*" not in ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    global pinecone_index, gemini_client
    global _groq_client, _sambanova_client, _openrouter_client, _ollama_oai_client

    if Pinecone and PINECONE_API_KEY:
        try:
            pinecone_index = Pinecone(api_key=PINECONE_API_KEY).Index(PINECONE_INDEX)
            stats = pinecone_index.describe_index_stats()
            count = getattr(stats, "total_vector_count", None)
            if count is None and isinstance(stats, dict):
                count = stats.get("total_vector_count")
            log.info("Pinecone '%s' ready — %s vectors", PINECONE_INDEX, count)
        except Exception:
            log.error("Pinecone init failed:\n%s", traceback.format_exc())

    if _OpenAI and GROQ_API_KEY:
        try:
            _groq_client = _OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
            log.info("Groq ready — configured models: %s @ %s", GROQ_MODELS, GROQ_BASE_URL)
        except Exception:
            log.error("Groq init failed:\n%s", traceback.format_exc())

    if _OpenAI and OPENROUTER_API_KEY:
        try:
            _openrouter_client = _OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
            log.info("OpenRouter ready — configured models: %s @ %s", OPENROUTER_MODELS, OPENROUTER_BASE_URL)
        except Exception:
            log.error("OpenRouter init failed:\n%s", traceback.format_exc())

    if _OpenAI:
        try:
            _ollama_oai_client = _OpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL)
            log.info("Ollama OpenAI-compat ready — configured models: %s @ %s", OLLAMA_CHAT_MODELS, OLLAMA_BASE_URL)
        except Exception:
            log.error("Ollama OpenAI-compat init failed:\n%s", traceback.format_exc())

    threading.Thread(target=_load_whisper, daemon=True).start()


# --------------------------------------------------------------------------
# Rate limiting & Models
# --------------------------------------------------------------------------

_hits: Dict[str, Deque[float]] = {}
_hits_lock = threading.Lock()


def _rate_limited(client_ip: str) -> bool:
    if RATE_LIMIT_PER_MIN <= 0:
        return False
    now = time.time()
    with _hits_lock:
        bucket = _hits.setdefault(client_ip, deque())
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_PER_MIN:
            return True
        bucket.append(now)
    return False


class ChatMessage(BaseModel):
    role: str = Field(default="user", max_length=20)
    content: str = Field(default="", max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=4000)
    history: Optional[List[ChatMessage]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    speech: str
    grounded: bool
    sources: List[str] = Field(default_factory=list)
    latency_ms: int = 0
    provider: str = "unknown"


# --------------------------------------------------------------------------
# Guards & Speech
# --------------------------------------------------------------------------

INJECTION_PATTERNS = [
    re.compile(r"\b(ignore|disregard|forget|override)\b[^.]{0,40}\b(instruction|prompt|rule|guideline)s?\b", re.I),
    re.compile(r"\b(system|developer|initial)\s+(prompt|message|instruction)s?\b", re.I),
    re.compile(r"\b(reveal|print|show|repeat|output)\b[^.]{0,30}\b(your|the)\s+(prompt|instruction)s?\b", re.I),
    re.compile(r"\bpretend\s+(to\s+be|you\s+are)\b", re.I),
    re.compile(r"\brole-?play\s+as\b", re.I),
    re.compile(r"\byou\s+are\s+now\b|\bfrom\s+now\s+on\s+you\b", re.I),
    re.compile(r"\bdo\s+anything\s+now\b", re.I),
    re.compile(r"\bdeveloper\s+mode\b|\bjailbreak\b", re.I),
]

GREETING_RE = re.compile(r"^(hi+|hey+|hello+|salam|assalam[ou]?\s*alaikum|good\s+(morning|afternoon|evening))[\s!.,]*$", re.I)
FAREWELL_RE = re.compile(r"\b(bye|goodbye|good\s*bye|cya|see\s+ya|take\s+care|khuda\s*hafiz)\b", re.I)
THANKS_RE   = re.compile(r"\b(thanks|thank\s*you|thx|shukriya|shukria)\b", re.I)
CONTACT_RE  = re.compile(r"\b(github|linked\s*in|linkedin|contact|email|e-mail|phone|number|reach\s+(him|out)|hire\s+him|cv\s+link|resume\s+link)\b", re.I)
IDENTITY_RE = re.compile(r"\b(who\s+are\s+you|what\s+are\s+you|what\s+can\s+you\s+do|how\s+can\s+you\s+help)\b", re.I)


def _looks_like_injection(text: str) -> bool:
    return any(p.search(text) for p in INJECTION_PATTERNS)


def to_speech(markdown_text: str) -> str:
    text = markdown_text
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)

    lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        item = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", stripped)
        if item and not item.endswith((".", "!", "?", ",", ":", ";")):
            item += "."
        lines.append(item)
    text = " ".join(lines)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*\n]+)\*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


SPEECH_HINTS = {
    "rate": 0.97, "pitch": 1.0, "volume": 1.0,
    "preferred_voices": ["Google UK English Female", "Samantha"],
}


# --------------------------------------------------------------------------
# Retrieval
# --------------------------------------------------------------------------

def embed_query(question: str) -> List[float]:
    if _ollama_embed is None:
        raise ServiceError("embedding", "ollama package not installed")
    prompt = f"search_query: {OWNER_NAME} resume {question}"
    try:
        response = _ollama_embed.embeddings(model=EMBED_MODEL, prompt=prompt)
    except Exception as exc:
        raise ServiceError("embedding", f"{type(exc).__name__}: {exc}") from exc
    vector = response.get("embedding") if isinstance(response, dict) else getattr(response, "embedding", None)
    if not vector:
        raise ServiceError("embedding", "empty embedding returned")
    return list(vector)


SECTION_INTENTS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("projects",       re.compile(r"\b(projects?|fyp|final\s*year|built|developed)\b", re.I)),
    ("certifications", re.compile(r"\b(certificat\w*|credential\w*|courses?)\b", re.I)),
    ("experience",     re.compile(r"\b(work|job|intern\w*|experience|ncai)\b", re.I)),
    ("education",      re.compile(r"\b(education\w*|degree|university|nutech|cgpa)\b", re.I)),
    ("skills",         re.compile(r"\b(skills?|technolog\w+|tools?|languages?)\b", re.I)),
]


def detect_section(question: str) -> Optional[str]:
    for name, pattern in SECTION_INTENTS:
        if pattern.search(question):
            return name
    return None


def _query_pinecone(vector: List[float], top_k: int, section: Optional[str]) -> List[Any]:
    kwargs: Dict[str, Any] = {"vector": vector, "top_k": top_k, "include_metadata": True}
    if section:
        kwargs["filter"] = {"section": {"$eq": section}}
    try:
        result = pinecone_index.query(**kwargs)
    except Exception as exc:
        if section:
            return []
        raise ServiceError("pinecone", f"{type(exc).__name__}: {exc}") from exc
    return list(getattr(result, "matches", None) or (result.get("matches", []) if isinstance(result, dict) else []))


def retrieve(question: str) -> Tuple[str, List[str], List[float]]:
    if pinecone_index is None:
        raise ServiceError("pinecone", "index not initialised")

    vector = embed_query(question)
    section = detect_section(question)

    section_matches = _query_pinecone(vector, SECTION_TOP_K, section) if section else []
    general_matches = _query_pinecone(vector, TOP_K, None)

    def unpack(match: Any) -> Optional[Tuple[str, float, str, str]]:
        metadata = getattr(match, "metadata", None) or {}
        chunk = metadata.get("text") or metadata.get("chunk") or metadata.get("content")
        if not chunk:
            return None
        label = str(metadata.get("title") or metadata.get("section") or "resume")
        return (str(getattr(match, "id", chunk[:40])), float(getattr(match, "score", 0.0) or 0.0), str(chunk), label)

    general = [row for row in (unpack(m) for m in general_matches) if row]
    general.sort(key=lambda row: row[1], reverse=True)
    best = general[0][1] if general else 0.0

    kept: List[Tuple[str, float, str, str]] = []
    seen: set = set()

    for row in (r for r in (unpack(m) for m in section_matches) if r):
        if row[0] not in seen:
            seen.add(row[0])
            kept.append(row)

    for row in general:
        if row[0] not in seen and row[1] >= best - SCORE_WINDOW:
            seen.add(row[0])
            kept.append(row)

    if not kept or (not section_matches and best < MIN_TOP_SCORE):
        return "", [], [r[1] for r in general]

    context = "\n---\n".join(row[2] for row in kept)
    sources = list(dict.fromkeys(row[3] for row in kept))
    return context, sources, [row[1] for row in kept]


# --------------------------------------------------------------------------
# Multi-Model Generation Calls
# --------------------------------------------------------------------------

def _extract_gemini_text(response: Any) -> Tuple[str, str]:
    finish_reason = ""
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return "", "NO_CANDIDATES"
    candidate = candidates[0]
    raw_finish = getattr(candidate, "finish_reason", None)
    if raw_finish is not None:
        finish_reason = getattr(raw_finish, "name", None) or str(raw_finish)
    pieces: List[str] = []
    content = getattr(candidate, "content", None)
    for part in (getattr(content, "parts", None) or []):
        if getattr(part, "thought", False):
            continue
        piece = getattr(part, "text", None)
        if piece:
            pieces.append(piece)
    return "".join(pieces).strip(), finish_reason


def _call_gemini(model_name: str, system_instruction: str, question: str, max_tokens: int) -> str:
    if gemini_client is None or genai_types is None:
        raise ServiceError("gemini", "client not initialised")

    for attempt in range(GEMINI_MAX_RETRIES + 1):
        try:
            kwargs: Dict[str, Any] = {
                "system_instruction": system_instruction,
                "temperature": TEMPERATURE,
                "max_output_tokens": max_tokens,
            }
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=question,
                config=genai_types.GenerateContentConfig(**kwargs),
            )
            text, finish = _extract_gemini_text(response)
            if text:
                return text
            raise ServiceError("gemini", f"empty response (finish={finish})")

        except ServiceError:
            raise
        except Exception as exc:
            if _is_quota_error(exc):
                raise ServiceError("quota", f"Gemini quota hit on {model_name}: {exc}") from exc
            if _is_model_unavailable(exc):
                raise ServiceError("gemini", f"model unavailable ({model_name}): {exc}") from exc
            if _is_retryable(exc) and attempt < GEMINI_MAX_RETRIES:
                time.sleep(1.0)
                continue
            raise ServiceError("gemini", f"{type(exc).__name__} on {model_name}: {exc}") from exc

    raise ServiceError("gemini", f"exhausted retries for {model_name}")


def _call_openai_compat(
    client: Any,
    model_name: str,
    provider_name: str,
    system_instruction: str,
    question: str,
) -> str:
    if client is None:
        raise ServiceError(provider_name, f"{provider_name} client not initialised")

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user",   "content": question},
    ]

    for attempt in range(OAI_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_OUTPUT_TOKENS,
            )
            text = (response.choices[0].message.content or "").strip()
            if text:
                return text
            raise ServiceError(provider_name, f"empty response from model {model_name}")

        except ServiceError:
            raise
        except Exception as exc:
            if _is_quota_error(exc):
                raise ServiceError("quota", f"{provider_name} quota hit on {model_name}: {exc}") from exc
            if _is_model_unavailable(exc):
                raise ServiceError(provider_name, f"model unavailable ({model_name}): {exc}") from exc
            if _is_retryable(exc) and attempt < OAI_MAX_RETRIES:
                time.sleep(1.0)
                continue
            raise ServiceError(provider_name, f"{type(exc).__name__} on {model_name}: {exc}") from exc

    raise ServiceError(provider_name, f"exhausted retries for {model_name}")


def _call_ollama_native(model_name: str, system_instruction: str, question: str) -> str:
    if _ollama_embed is None:
        raise ServiceError("ollama", "ollama package not installed")
    try:
        response = _ollama_embed.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user",   "content": question},
            ],
            options={"temperature": TEMPERATURE, "num_predict": MAX_OUTPUT_TOKENS},
        )
        text = ""
        if isinstance(response, dict):
            text = (response.get("message") or {}).get("content") or ""
        else:
            msg = getattr(response, "message", None)
            text = getattr(msg, "content", None) or ""
        text = (text or "").strip()
        if not text:
            raise ServiceError("ollama", f"empty response from native ollama model {model_name}")
        return text
    except ServiceError:
        raise
    except Exception as exc:
        raise ServiceError("ollama", f"{type(exc).__name__} on {model_name}: {exc}") from exc


# --------------------------------------------------------------------------
# Multi-Model Waterfall Routing
# --------------------------------------------------------------------------

def generate(system_instruction: str, question: str) -> Tuple[str, str]:
    """
    Waterfall across Providers, with sub-loops iterating through each configured Model.
    """

    def _try_groq() -> Optional[Tuple[str, str]]:
        if _is_exhausted("groq") or not GROQ_API_KEY or _groq_client is None:
            return None
        for model in GROQ_MODELS:
            try:
                log.info("Attempting Groq model: %s", model)
                ans = _call_openai_compat(_groq_client, model, "groq", system_instruction, question)
                return ans, f"groq ({model})"
            except ServiceError as exc:
                log.warning("Groq model '%s' failed: %s", model, exc.detail)
                if exc.stage == "quota":
                    _mark_exhausted("groq")
                    break
        return None


    def _try_openrouter() -> Optional[Tuple[str, str]]:
        if _is_exhausted("openrouter") or not OPENROUTER_API_KEY or _openrouter_client is None:
            return None
        for model in OPENROUTER_MODELS:
            try:
                log.info("Attempting OpenRouter model: %s", model)
                ans = _call_openai_compat(_openrouter_client, model, "openrouter", system_instruction, question)
                return ans, f"openrouter ({model})"
            except ServiceError as exc:
                log.warning("OpenRouter model '%s' failed: %s", model, exc.detail)
                if exc.stage == "quota":
                    _mark_exhausted("openrouter")
                    break
        return None

    def _try_ollama() -> Optional[Tuple[str, str]]:
        for model in OLLAMA_CHAT_MODELS:
            if _ollama_oai_client is not None:
                try:
                    log.info("Attempting Ollama model (OpenAI-compat): %s", model)
                    ans = _call_openai_compat(_ollama_oai_client, model, "ollama", system_instruction, question)
                    return ans, f"ollama ({model})"
                except ServiceError as exc:
                    log.warning("Ollama model '%s' failed via OpenAI-compat: %s", model, exc.detail)

            if _ollama_embed is not None:
                try:
                    log.info("Attempting Ollama model (native): %s", model)
                    ans = _call_ollama_native(model, system_instruction, question)
                    return ans, f"ollama ({model})"
                except ServiceError as exc:
                    log.warning("Ollama model '%s' failed via native API: %s", model, exc.detail)
        return None

    for attempt_fn in (_try_groq, _try_openrouter, _try_ollama):
        result = attempt_fn()
        if result is not None:
            return result

    raise ServiceError(
        "all_providers",
        "Every provider and model in the fallback chain failed or is exhausted."
    )


# --------------------------------------------------------------------------
# Prompt & System Instructions
# --------------------------------------------------------------------------

_METRIC_CLAIM_RE = re.compile(
    r"\b(cgpa|gpa|grade\s*point|percentage|percentile|marks|salary|stipend|"
    r"years?\s+of\s+experience|ranked|top\s+\d+\s*%)\b", re.I)


def drop_unsupported_claims(answer: str, context: str) -> str:
    if not _METRIC_CLAIM_RE.search(answer):
        return answer
    if _METRIC_CLAIM_RE.search(context):
        return answer
    kept_lines: List[str] = []
    for line in answer.splitlines():
        sentences = re.split(r"(?<=[.!?])\s+", line)
        surviving = " ".join(s for s in sentences if not _METRIC_CLAIM_RE.search(s)).strip()
        if surviving:
            kept_lines.append(surviving)
    cleaned = "\n".join(kept_lines).strip()
    return cleaned or NOT_LISTED_RESPONSE


def _graduation_fact() -> str:
    try:
        year, month = (int(p) for p in GRADUATION_DATE.split("-")[:2])
    except (ValueError, TypeError):
        return ""
    today = date.today()
    month_name = date(year, month, 1).strftime("%B %Y")
    if (today.year, today.month) > (year, month):
        return (
            f"DERIVED FACT: {OWNER_NAME} has ALREADY GRADUATED. He completed his BS in Artificial Intelligence at "
            f"NUTECH in {month_name}. Describe his degree in the past tense."
        )
    return (
        f"DERIVED FACT: {OWNER_NAME} is completing his BS in Artificial Intelligence at "
        f"NUTECH and is expected to graduate in {month_name}."
    )


def build_system_instruction(context: str, history_text: str) -> str:
    return f"""You are the AI assistant on developer {OWNER_NAME}'s portfolio site.
Speak concisely to recruiters/interviewers about his resume.

Today's date is {date.today().strftime("%d %B %Y")}.
{_graduation_fact()}

<resume_context>
{context}
</resume_context>

<recent_conversation>
{history_text or "(none)"}
</recent_conversation>

GROUNDING RULES
1. Every fact in your answer MUST appear verbatim in <resume_context>.
2. If context does not answer the question, reply with: "{NOT_LISTED_RESPONSE}"
3. If irrelevant to {OWNER_NAME}'s resume, reply with: "{FALLBACK_RESPONSE}"
"""


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@app.get("/")
def home() -> Dict[str, Any]:
    return {
        "status": "Avatar RAG backend running",
        "version": app.version,
        "index": PINECONE_INDEX,
    }


@app.get("/providers")
def provider_status() -> Dict[str, Any]:
    return {
        "groq":       {"enabled": bool(GROQ_API_KEY),       "exhausted": _is_exhausted("groq"),       "models": GROQ_MODELS},
        "openrouter": {"enabled": bool(OPENROUTER_API_KEY), "exhausted": _is_exhausted("openrouter"), "models": OPENROUTER_MODELS},
        "ollama":     {"enabled": True,                     "exhausted": False,                       "models": OLLAMA_CHAT_MODELS},
    }


@app.post("/chat", response_model=ChatResponse)
def chat_with_avatar(request: ChatRequest, http_request: Request) -> ChatResponse:
    started = time.perf_counter()
    request_id = uuid.uuid4().hex[:8]
    client_ip = (http_request.client.host if http_request.client else "unknown")

    if _rate_limited(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

    question = (request.message or "").strip()[:MAX_MESSAGE_CHARS]
    lowered = question.lower()

    def reply(text: str, grounded: bool = False, sources: Optional[List[str]] = None,
              provider: str = "static") -> ChatResponse:
        return ChatResponse(
            reply=text,
            speech=to_speech(text),
            grounded=grounded,
            sources=sources or [],
            latency_ms=int((time.perf_counter() - started) * 1000),
            provider=provider,
        )

    if not re.search(r"[A-Za-z\u0600-\u06FF]", question):
        return reply(FALLBACK_RESPONSE)

    if _looks_like_injection(question):
        return reply(FALLBACK_RESPONSE)

    if GREETING_RE.match(question):
        return reply(f"Hello! I'm the AI assistant for developer {OWNER_NAME}. "
                     f"Ask me about his skills, projects, experience, or education.")

    try:
        context, sources, scores = retrieve(question)
    except ServiceError as exc:
        raise HTTPException(status_code=503, detail=f"Retrieval unavailable ({exc.stage}).") from exc

    if not context:
        return reply(FALLBACK_RESPONSE)

    history_text = ""
    if request.history:
        recent = request.history[-MAX_HISTORY_TURNS:]
        history_text = "\n".join(
            f"{(m.role or 'user').strip()[:12]}: {(m.content or '').strip()[:500]}"
            for m in recent if (m.content or "").strip()
        )

    try:
        answer, provider_used = generate(build_system_instruction(context, history_text), question)
    except ServiceError as exc:
        raise HTTPException(status_code=503, detail="Assistant temporarily unavailable. All providers exhausted.") from exc

    answer = drop_unsupported_claims(answer, context)
    grounded = (FALLBACK_RESPONSE.lower() not in answer.lower()
                and NOT_LISTED_RESPONSE.lower() not in answer.lower())
    return reply(answer, grounded=grounded, sources=sources if grounded else [], provider=provider_used)


# --------------------------------------------------------------------------
# Whisper STT Load & Transcribe
# --------------------------------------------------------------------------

def _load_whisper() -> None:
    global _whisper_model, _whisper_state
    with _whisper_lock:
        if _whisper_model is not None:
            return
        try:
            import whisper
            _whisper_state = "loading"
            _whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
            _whisper_state = f"ok: {WHISPER_MODEL_NAME}"
        except Exception as exc:
            _whisper_state = f"unavailable: {exc}"


def _transcribe_sync(path: str) -> str:
    result = _whisper_model.transcribe(
        path, language="en", fp16=False, temperature=0.0,
    )
    return str(result.get("text", "")).strip()


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)) -> Dict[str, str]:
    if _whisper_model is None:
        _load_whisper()
    if _whisper_model is None:
        raise HTTPException(status_code=503, detail="Speech-to-text unavailable.")

    suffix = os.path.splitext(file.filename or "")[1] or ".webm"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
            chunk = await file.read()
            tmp.write(chunk)
        text = await run_in_threadpool(_transcribe_sync, temp_path)
        return {"text": text}
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=_env_int("PORT", 8000), reload=False)