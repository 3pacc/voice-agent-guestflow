import asyncio
import logging
from typing import AsyncGenerator

from openai import AsyncOpenAI

from src.config.settings import settings

logger = logging.getLogger(__name__)


class VllmClient:
    """
    Primary: self-hosted vLLM or any OpenAI-compatible endpoint.
    Fallback: Mistral chat API when primary fails.
    Includes retry for transient 5xx/overflow/rate-limit errors.
    """

    RETRYABLE_HINTS = (
        "429",
        "500",
        "502",
        "503",
        "504",
        "overflow",
        "upstream connect error",
        "rate limit",
        "service unavailable",
        "timed out",
    )

    def __init__(self):
        self.model = settings.llm_model
        self.primary_enabled = settings.llm_primary_enabled
        self.client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )

        self.fallback_enabled = settings.llm_fallback_enabled
        self.fallback_provider = settings.llm_fallback_provider.lower().strip()
        self.fallback_model = settings.llm_fallback_model

        self.fallback_client: AsyncOpenAI | None = None
        if (
            self.fallback_enabled
            and self.fallback_provider == "mistral"
            and settings.mistral_api_key
        ):
            self.fallback_client = AsyncOpenAI(
                base_url="https://api.mistral.ai/v1",
                api_key=settings.mistral_api_key,
            )

    @staticmethod
    def _is_retryable_exception(exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(h in msg for h in VllmClient.RETRYABLE_HINTS)

    async def _stream_once(
        self,
        client: AsyncOpenAI,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        async for chunk in response:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            content = getattr(delta, "content", None) if delta else None
            if content:
                yield content

    async def _stream_with_retry(
        self,
        label: str,
        client: AsyncOpenAI,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        max_attempts: int = 3,
    ) -> AsyncGenerator[str, None]:
        for attempt in range(1, max_attempts + 1):
            try:
                yielded_any = False
                async for token in self._stream_once(
                    client,
                    model,
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    yielded_any = True
                    yield token
                if not yielded_any:
                    logger.warning("%s returned empty stream (attempt %s/%s)", label, attempt, max_attempts)
                return
            except Exception as exc:
                retryable = self._is_retryable_exception(exc)
                logger.error("%s error (attempt %s/%s): %s", label, attempt, max_attempts, exc, exc_info=True)
                if retryable and attempt < max_attempts:
                    delay = 0.5 * (2 ** (attempt - 1))
                    logger.warning("%s retrying in %.2fs", label, delay)
                    await asyncio.sleep(delay)
                    continue
                raise

    @staticmethod
    def _prepare_messages_for_mistral(messages: list[dict]) -> list[dict]:
        """Mistral requires the last role to be user/tool (or assistant with prefix)."""
        prepared = list(messages)
        if not prepared:
            return [{"role": "user", "content": "Bonjour"}]

        last_role = prepared[-1].get("role")
        if last_role in {"assistant", "system"}:
            prepared.append(
                {
                    "role": "user",
                    "content": "Merci. Reponds maintenant au client de facon concise et professionnelle.",
                }
            )
        return prepared

    async def generate_response_stream(self, messages: list[dict], temperature: float | None = None) -> AsyncGenerator[str, None]:
        """
        Streams the response token-by-token.
        Falls back to Mistral if primary fails.
        """
        effective_temp = 0.3 if temperature is None else max(0.0, min(1.5, float(temperature)))

        if self.primary_enabled:
            try:
                async for token in self._stream_with_retry(
                    "Primary LLM",
                    self.client,
                    self.model,
                    messages,
                    temperature=effective_temp,
                    max_tokens=256,
                ):
                    yield token
                return
            except Exception:
                logger.error("Primary LLM failed after retries", exc_info=True)

        if self.fallback_client is not None:
            try:
                logger.warning(
                    "Switching to fallback LLM provider=%s model=%s",
                    self.fallback_provider,
                    self.fallback_model,
                )
                fallback_messages = self._prepare_messages_for_mistral(messages)
                async for token in self._stream_with_retry(
                    "Fallback LLM",
                    self.fallback_client,
                    self.fallback_model,
                    fallback_messages,
                    temperature=min(1.5, effective_temp + 0.1),
                    max_tokens=256,
                ):
                    yield token
                return
            except Exception:
                logger.error("Fallback LLM failed after retries", exc_info=True)

        yield "Je rencontre un ralentissement temporaire. Pouvez-vous repeter votre demande en une phrase courte ?"
