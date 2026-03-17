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
    """

    TRANSCRIPTION_URL = "https://api.mistral.ai/v1/audio/transcriptions"
    MODEL = "voxtral-mini-2507"

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

    async def transcribe_stream(self, audio_chunk: bytes, sample_rate: int = 8000) -> str:
        if not self.api_key:
            logger.warning("MISTRAL_API_KEY not set - STT disabled.")
            return ""

        if len(audio_chunk) < 320:
            return ""

        wav_bytes = self._mulaw_to_wav(audio_chunk, sample_rate)
        logger.info(f"MistralSTT sending {len(wav_bytes)} bytes WAV to Mistral")

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                data_payload = {
                    "model": self.MODEL,
                    "language": "fr",
                    "prompt": "Transcris fid\u00e8lement en fran\u00e7ais, conserve les accents, et garde les nombres exacts (dates, personnes, nuits).",
                }
                response = await client.post(
                    self.TRANSCRIPTION_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                    data=data_payload,
                )

                # Backward-compat fallback if optional fields are rejected
                if response.status_code == 400:
                    response = await client.post(
                        self.TRANSCRIPTION_URL,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                        data={"model": self.MODEL},
                    )

                if response.status_code == 200:
                    text = response.json().get("text", "").strip()
                    logger.info(f"MistralSTT transcript: '{text}'")
                    return text

                logger.error(
                    f"MistralSTT error {response.status_code}: {response.text}"
                )
                return ""

        except Exception as exc:
            logger.error(f"MistralSTT exception: {exc}", exc_info=True)
            return ""
