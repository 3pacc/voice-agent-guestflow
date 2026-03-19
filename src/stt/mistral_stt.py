import asyncio
import audioop
import io
import logging
import wave

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)


class MistralRealtimeSTT:
    """
    Mistral Voxtral STT via REST API.
    Converts raw mulaw audio (from Twilio) to PCM16 WAV then sends it to Mistral.
    Includes retry with exponential backoff for transient overload/5xx errors.
    """

    TRANSCRIPTION_URL = "https://api.mistral.ai/v1/audio/transcriptions"
    MODEL = "voxtral-mini-2507"
    MAX_RETRIES = 3
    RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    def __init__(self):
        self.api_key = settings.mistral_api_key

    @staticmethod
    def _mulaw_to_wav(mulaw_bytes: bytes, sample_rate: int = 8000) -> bytes:
        pcm16 = audioop.ulaw2lin(mulaw_bytes, 2)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(pcm16)
        return buf.getvalue()

    @staticmethod
    def _is_retryable(status_code: int, body: str) -> bool:
        if status_code in MistralRealtimeSTT.RETRYABLE_STATUS:
            return True
        lower = (body or "").lower()
        return "overflow" in lower or "upstream connect error" in lower or "rate limit" in lower

    async def _request_transcription(
        self,
        client: httpx.AsyncClient,
        wav_bytes: bytes,
        data_payload: dict,
    ) -> httpx.Response:
        return await client.post(
            self.TRANSCRIPTION_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            files={"file": ("audio.wav", wav_bytes, "audio/wav")},
            data=data_payload,
        )

    async def transcribe_stream(self, audio_chunk: bytes, sample_rate: int = 8000) -> str:
        if not self.api_key:
            logger.warning("MISTRAL_API_KEY not set - STT disabled.")
            return ""

        if len(audio_chunk) < 320:
            return ""

        wav_bytes = self._mulaw_to_wav(audio_chunk, sample_rate)
        logger.info("MistralSTT sending %s bytes WAV to Mistral", len(wav_bytes))

        data_payload = {
            "model": self.MODEL,
            "language": "fr",
            "prompt": "Transcris fidelement en francais, conserve les accents, et garde les nombres exacts (dates, personnes, nuits).",
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            for attempt in range(1, self.MAX_RETRIES + 1):
                try:
                    response = await self._request_transcription(client, wav_bytes, data_payload)

                    # Backward-compat fallback if optional fields are rejected
                    if response.status_code == 400:
                        response = await self._request_transcription(
                            client,
                            wav_bytes,
                            {"model": self.MODEL},
                        )

                    if response.status_code == 200:
                        text = response.json().get("text", "").strip()
                        logger.info("MistralSTT transcript: '%s'", text)
                        return text

                    body = response.text
                    retryable = self._is_retryable(response.status_code, body)
                    logger.error(
                        "MistralSTT error %s (attempt %s/%s): %s",
                        response.status_code,
                        attempt,
                        self.MAX_RETRIES,
                        body,
                    )

                    if retryable and attempt < self.MAX_RETRIES:
                        delay = 0.5 * (2 ** (attempt - 1))
                        logger.warning("MistralSTT retrying in %.2fs", delay)
                        await asyncio.sleep(delay)
                        continue
                    return ""

                except Exception as exc:
                    logger.error(
                        "MistralSTT exception (attempt %s/%s): %s",
                        attempt,
                        self.MAX_RETRIES,
                        exc,
                        exc_info=True,
                    )
                    if attempt < self.MAX_RETRIES:
                        delay = 0.5 * (2 ** (attempt - 1))
                        await asyncio.sleep(delay)
                        continue
                    return ""

        return ""
