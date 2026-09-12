"""LLM layer for translation, register, and nuance.

Three deliberate choices:

1. **Batch per scene, not per line.** One request covers the whole clip so the
   model sees context. 大丈夫 means "I'm fine" or "no thanks" depending on what
   came before.
2. **Cache by content hash.** Re-importing the same clip costs nothing, and two
   users importing the same episode only pay once.
3. **Offline-safe stub.** With no API key configured the stub engine returns
   dictionary-shaped output so the whole pipeline still runs in CI and in
   local development.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from functools import lru_cache

from app.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You translate Japanese dialogue for language learners.
For each numbered line return JSON with:
  english  - natural spoken English, not literal word order
  register - one of: casual, polite, formal, rough, childish, keigo
  nuance   - at most 20 words on why it was said this way, or "" if obvious
Return only a JSON array, one object per input line, same order.
Use the surrounding lines for context: pronouns and subjects are often omitted.
"""


@dataclass(slots=True)
class SceneGloss:
    english: str = ""
    register: str = ""
    nuance: str = ""


class LlmClient:
    name = "base"

    def gloss_scene(self, lines: list[str]) -> list[SceneGloss]:  # pragma: no cover
        raise NotImplementedError


class StubLlmClient(LlmClient):
    """Deterministic placeholder used when no API key is set.

    It does not invent translations. It reports the register it can detect from
    surface markers and leaves English empty, so the UI can show "translation
    unavailable" rather than something wrong.
    """

    name = "stub"

    _POLITE_MARKERS = ("です", "ます", "ません", "でした", "ました", "ください")
    _KEIGO_MARKERS = ("いたしま", "ございま", "なさいま", "おりま")

    def gloss_scene(self, lines: list[str]) -> list[SceneGloss]:
        out: list[SceneGloss] = []
        for line in lines:
            if any(marker in line for marker in self._KEIGO_MARKERS):
                register = "keigo"
            elif any(marker in line for marker in self._POLITE_MARKERS):
                register = "polite"
            else:
                register = "casual"
            out.append(SceneGloss(english="", register=register, nuance=""))
        return out


class OpenAiLlmClient(LlmClient):
    """Real engine. Batches one request per scene and caches by content hash."""

    name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._cache: dict[str, list[SceneGloss]] = {}

    def gloss_scene(self, lines: list[str]) -> list[SceneGloss]:
        if not lines:
            return []

        key = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
        if key in self._cache:
            return self._cache[key]

        try:
            result = self._request(lines)
        except Exception:  # noqa: BLE001 - never fail a lesson because of the LLM
            logger.exception("LLM request failed, falling back to stub glosses")
            return StubLlmClient().gloss_scene(lines)

        self._cache[key] = result
        return result

    def _request(self, lines: list[str]) -> list[SceneGloss]:
        import httpx  # noqa: PLC0415 - keep the import cost off the hot path

        numbered = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(lines))
        response = httpx.post(
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": numbered},
                ],
            },
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(payload)
        items = parsed if isinstance(parsed, list) else parsed.get("lines", [])

        glosses = [
            SceneGloss(
                english=str(item.get("english", "")),
                register=str(item.get("register", "")),
                nuance=str(item.get("nuance", "")),
            )
            for item in items
        ]
        # Never return fewer glosses than lines; pad so zip stays aligned.
        while len(glosses) < len(lines):
            glosses.append(SceneGloss())
        return glosses


@lru_cache(maxsize=1)
def get_llm_client() -> LlmClient:
    if settings.llm_api_key:
        return OpenAiLlmClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
        )
    logger.warning("LLM_API_KEY not set; using stub glosses")
    return StubLlmClient()
