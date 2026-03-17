import asyncio
import base64
import logging
import httpx
from typing import AsyncGenerator

from src.config.settings import settings

logger = logging.getLogger(__name__)


class InworldTTS:
    """
    Inworld TTS client.
    Uses REST API (POST /tts/v1/voice) and returns mulaw audio.
    """

    def __init__(self):
        self.api_key = settings.inworld_key
        self.api_secret = settings.inworld_secret
        self.model = "inworld-tts-1.5-max"
        self.voice = settings.inworld_voice_id or "default-ojjf5gdfr1kpiardizji5a__design-voice-c40d242e"
        self.base_url = "https://api.inworld.ai"
        self.temperature = settings.inworld_tts_temperature
        self.speaking_rate = settings.inworld_tts_speaking_rate

    def _auth_header(self) -> str:
        if self.api_secret:
            raw = f"{self.api_key}:{self.api_secret}"
            encoded = base64.b64encode(raw.encode()).decode()
            return f"Basic {encoded}"
        return f"Basic {self.api_key}"

    def _voice_candidates(self) -> list[str]:
        """Return ordered voice fallback list for FR quality and robustness."""
        preferred = (self.voice or "").strip()
        candidates = []
        if preferred:
            candidates.append(preferred)
            if preferred.lower() == "etienne":
                candidates.append("?tienne")
            if preferred.lower() == "h?l?ne":
                candidates.append("Helene")
            if preferred.lower() == "helene":
                candidates.append("H?l?ne")

        # French voice fallbacks available on this account
        for v in ["Mathieu", "Alain", "H?l?ne", "?tienne", "Clive"]:
            if v not in candidates:
                candidates.append(v)
        return candidates

    async def stream_tts(
        self,
        text_stream: AsyncGenerator[str, None],
        sample_rate: int = 8000,
    ) -> AsyncGenerator[bytes, None]:
        if not self.api_key:
            logger.warning("INWORLD_KEY not set - skipping TTS.")
            yield b""
            return

        full_text = ""
        async for chunk in text_stream:
            if chunk:
                full_text += chunk

        if not full_text.strip():
            yield b""
            return

        logger.info(f"InworldTTS synthesizing: '{full_text[:80]}...'")

        headers = {
            "Authorization": self._auth_header(),
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                last_error = None
                for voice_id in self._voice_candidates():
                    payload = {
                        "text": full_text,
                        "modelId": self.model,
                        "voiceId": voice_id,
                        "audioConfig": {
                            "audioEncoding": "MULAW",
                            "sampleRateHertz": sample_rate,
                            "speakingRate": self.speaking_rate,
                        },
                        "temperature": self.temperature,
                    }

                    response = await client.post(
                        f"{self.base_url}/tts/v1/voice",
                        headers=headers,
                        json=payload,
                    )

                    # Fallback: retry with minimal payload if optional controls are rejected
                    if response.status_code >= 400 and response.status_code < 500:
                        minimal_payload = {
                            "text": full_text,
                            "modelId": self.model,
                            "voiceId": voice_id,
                            "audioConfig": {
                                "audioEncoding": "MULAW",
                                "sampleRateHertz": sample_rate,
                            },
                        }
                        response = await client.post(
                            f"{self.base_url}/tts/v1/voice",
                            headers=headers,
                            json=minimal_payload,
                        )

                    if response.status_code == 200:
                        body = response.json()
                        audio_b64 = body.get("audioContent", "")
                        if not audio_b64:
                            last_error = "InworldTTS response missing audioContent"
                            continue

                        chunk_size = 320
                        audio = base64.b64decode(audio_b64)
                        logger.info(
                            f"InworldTTS voice={voice_id} received {len(audio)} bytes of audio"
                        )
                        for i in range(0, len(audio), chunk_size):
                            yield audio[i : i + chunk_size]
                            await asyncio.sleep(0)
                        return

                    last_error = f"voice={voice_id} status={response.status_code} body={response.text[:220]}"

                logger.error(f"InworldTTS failed on all voice candidates: {last_error}")
                yield b""

        except Exception as exc:
            logger.error(f"InworldTTS exception: {exc}", exc_info=True)
            yield b""
