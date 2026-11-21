"""Tiny fail-safe LLM client: any OpenAI-compatible chat-completions API (tested with Gemini; Grok and others work), stdlib urllib only.

NEVER raises. On ANY problem (off, no key, timeout, HTTP error, bad JSON) it returns None and the caller keeps its offline
result. The key is read only from the environment and is never logged, printed or put in an error message.

Environment:
  LLM_API_KEY   the secret (same name as .env.example and backend/render.yaml)
  LLM_MODEL     the model id. Required, no default: a guessed id would only fail. Unset means the LLM is off.
  LLM_BASE_URL  default https://api.x.ai/v1 (https only, so the key is never sent in clear text). SET IT for your provider, e.g. Gemini:
                https://generativelanguage.googleapis.com/v1beta/openai . A key sent to the wrong provider is rejected there and is exposed to it
  AI_USE_LLM    set to 0 to force the offline path (weak-signal demo, quota, debugging)
Only extract_claim uses this module. decide, match_person, classify_message and explain never do.
"""
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional

DEFAULT_BASE_URL = "https://api.x.ai/v1"
TIMEOUT_SECONDS = 8
RETRIES = 2  # extra attempts after a rate limit (429) or a server error (5xx); a TIMEOUT is retried only once (each one costs 8 s)
BACKOFF_SECONDS = (1.0, 2.5)  # pause before retry 1 and 2 (a Retry-After header, capped at MAX_WAIT_SECONDS, wins). An instant retry hits the same limit
MAX_WAIT_SECONDS = 5.0
COOLDOWN_SECONDS = 20.0  # after a burst of failures the LLM is skipped for a while: the offline parser answers at once instead of every claim waiting
MAX_TOKENS = 300
_USER_AGENT = "bharosa-ai/1.0"  # a generic name: some gateways reject the default Python user agent


_STATS = {"calls": 0, "ok": 0, "tokens": 0}  # non-secret usage counters for the evaluation (cost per case)
_COOLDOWN = {"until": 0.0}


def _sleep(seconds: float) -> None:  # a function of its own so tests do not really wait
    time.sleep(seconds)


def _now() -> float:
    return time.monotonic()


def cooling_down() -> bool:
    return _now() < _COOLDOWN["until"]


def stats() -> Dict[str, int]:
    """Calls made, calls answered, and tokens reported by the provider since the last reset. Contains no secret."""
    return dict(_STATS)


def reset_stats() -> None:
    for key in _STATS:
        _STATS[key] = 0
    _COOLDOWN["until"] = 0.0


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _base_url() -> str:
    return (_env("LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def status() -> str:
    """Why the LLM is on or off. Safe to print: it never contains a secret."""
    if _env("AI_USE_LLM") == "0":
        return "off: AI_USE_LLM=0"
    if not _env("LLM_API_KEY"):
        return "off: LLM_API_KEY is not set"
    if not _env("LLM_MODEL"):
        return "off: LLM_MODEL is not set"
    if not _base_url().startswith("https://"):
        return "off: LLM_BASE_URL must start with https://"
    return "on"


def unavailable() -> bool:
    """True when the LLM is wanted but not configured (no key / model / bad URL). False when it is on, or switched off on purpose
    with AI_USE_LLM=0. A key added later needs no code change: restart and this turns False."""
    return _env("AI_USE_LLM") != "0" and status() != "on"


def enabled() -> bool:
    return status() == "on"


def _retry_after(exc: urllib.error.HTTPError) -> Optional[float]:
    try:
        value = float(exc.headers.get("Retry-After", "")) if exc.headers else None
    except (TypeError, ValueError):
        return None
    return value if value is not None and value >= 0 else None


def _post(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    request = urllib.request.Request(
        _base_url() + "/chat/completions", data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + _env("LLM_API_KEY"), "Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": _USER_AGENT})
    if cooling_down():  # the last burst failed: do not make the next claim wait for the same failure
        return None
    timeouts = 0
    for attempt in range(RETRIES + 1):
        wait = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429:  # a bad key or a bad request: retrying cannot help
                return None
            hinted = _retry_after(exc)
            wait = hinted if hinted is not None else wait
        except Exception:  # timeout, DNS, TLS, unreadable body
            timeouts += 1
            if timeouts > 1:  # a second slow answer: give up now
                break
        if attempt < RETRIES:
            _sleep(min(wait, MAX_WAIT_SECONDS))
    _COOLDOWN["until"] = _now() + COOLDOWN_SECONDS
    return None


def _parse_object(text: Any) -> Optional[Dict[str, Any]]:
    """The model's reply as a dict. Tolerates ```json fences and a sentence around the object."""
    if not isinstance(text, str):
        return None
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


_DEFAULT_HINT = "Your last answer was not valid. Answer again with ONLY the JSON object, no other text."


def chat_json(system: str, user: str, validate: Optional[Callable[[Dict[str, Any]], Any]] = None,
              hint: Optional[str] = None) -> Optional[Any]:
    """One chat completion that must answer with a JSON object. Returns the object, or None for any problem.

    With `validate` (for example a Pydantic model's validator) the reply must pass it; an invalid reply (not JSON, or the
    check raises) is retried ONCE, showing the model its bad answer and `hint`, and then gives None: never a guess. A
    network or HTTP failure is not an invalid reply and is not retried here (`_post` already retried it)."""
    try:
        if not enabled():
            return None
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for attempt in (0, 1):
            data = _post({"model": _env("LLM_MODEL"), "temperature": 0, "max_tokens": MAX_TOKENS,
                          "response_format": {"type": "json_object"}, "messages": messages})
            _STATS["calls"] += 1
            if not data:
                return None
            _STATS["ok"] += 1
            usage = data.get("usage")
            if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int):
                _STATS["tokens"] += usage["total_tokens"]
            content = data["choices"][0]["message"]["content"]
            obj = _parse_object(content)
            if validate is None:
                return obj
            try:
                if obj is not None:
                    return validate(obj)
            except Exception:  # the reply does not fit the schema
                pass
            if attempt == 1:
                return None
            messages = messages + [{"role": "assistant", "content": content if isinstance(content, str) else ""},
                                   {"role": "user", "content": hint or _DEFAULT_HINT}]
        return None
    except Exception:
        return None
