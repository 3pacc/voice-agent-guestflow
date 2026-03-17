import logging
from typing import AsyncGenerator

from openai import AsyncOpenAI

from src.config.settings import settings

logger = logging.getLogger(__name__)


class VllmClient:
    """
    Primary: self-hosted vLLM via OpenAI-compatible API.
    Fallback: Mistral chat API when vLLM is unavailable.
    """

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

    async def _stream_from_client(
        self,
        client: AsyncOpenAI,
        model: str,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 256,
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

    async def generate_response_stream(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """
        Streams the response token-by-token.
        Falls back to Mistral if vLLM fails.
        """
        if self.primary_enabled:
            try:
                async for token in self._stream_from_client(
                self.client,
                self.model,
                messages,
                temperature=0.3,
                max_tokens=256,
                ):
                    yield token
                return
            except Exception as exc:
                logger.error(f"vLLM API error: {exc}", exc_info=True)

        if self.fallback_client is not None:
            try:
                logger.warning(
                    "Switching to fallback LLM provider=%s model=%s",
                    self.fallback_provider,
                    self.fallback_model,
                )
                fallback_messages = self._prepare_messages_for_mistral(messages)
                async for token in self._stream_from_client(
                    self.fallback_client,
                    self.fallback_model,
                    fallback_messages,
                    temperature=0.4,
                    max_tokens=256,
                ):
                    yield token
                return
            except Exception as exc:
                logger.error(f"Fallback LLM error: {exc}", exc_info=True)

        yield "Sorry, I am having trouble connecting to my brain right now."
