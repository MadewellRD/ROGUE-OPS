#
# advisory/llm_ollama.py
#
# Minimal, FAIL-SOFT Ollama client (stdlib only).
#
# This is an ADVISORY-layer module. It must NEVER be imported by anything under
# execution/ or capital/. Every failure path returns None / [] / False — it can
# never raise into a caller and can never influence a trading decision. A local
# LLM is non-deterministic and must stay strictly observational in this system.
#
# Config:
#   OLLAMA_HOST   default http://127.0.0.1:11434
#   OLLAMA_MODEL  default llama3.2
#

import json
import os
import urllib.request
from typing import Any, Dict, List, Optional

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2"


def host() -> str:
    return os.getenv("OLLAMA_HOST", DEFAULT_HOST).rstrip("/")


def default_model() -> str:
    return os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)


def available() -> bool:
    """True if the Ollama server answers /api/tags. Fail-soft (never raises)."""
    try:
        with urllib.request.urlopen(host() + "/api/tags", timeout=2) as r:
            return getattr(r, "status", 200) == 200
    except Exception:
        return False


def list_models() -> List[str]:
    try:
        with urllib.request.urlopen(host() + "/api/tags", timeout=3) as r:
            j = json.loads(r.read().decode("utf-8"))
            return [m.get("name") for m in (j.get("models") or []) if m.get("name")]
    except Exception:
        return []


def generate(
    prompt: str,
    *,
    model: Optional[str] = None,
    system: Optional[str] = None,
    json_mode: bool = False,
    timeout: float = 30.0,
    temperature: float = 0.2,
) -> Optional[str]:
    """POST /api/generate (stream=false). Returns the response text, or None on
    ANY failure (server down, timeout, malformed payload). Never raises."""
    body: Dict[str, Any] = {
        "model": model or default_model(),
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system:
        body["system"] = system
    if json_mode:
        body["format"] = "json"
    req = urllib.request.Request(
        host() + "/api/generate",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")).get("response")
    except Exception:
        return None


def generate_json(prompt: str, **kw) -> Optional[Dict[str, Any]]:
    """generate() in JSON mode, parsed to a dict. None on failure / parse error.
    Tolerates models that wrap the JSON object in surrounding prose."""
    txt = generate(prompt, json_mode=True, **kw)
    if not txt:
        return None
    try:
        return json.loads(txt)
    except Exception:
        try:
            i, k = txt.index("{"), txt.rindex("}")
            return json.loads(txt[i : k + 1])
        except Exception:
            return None
