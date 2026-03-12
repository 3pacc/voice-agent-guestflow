import asyncio
import logging
import json
import websockets
from typing import AsyncGenerator
from src.config.settings import settings

logger = logging.getLogger(__name__)

class MistralRealtimeSTT:
    """
    Client for Mistral Voxtral Realtime STT via WebSocket API.
    Uses wss://api.mistral.ai/v1/speech-to-text endpoint.
    """
    def __init__(self):
        self.api_key = settings.mistral_api_key
        self.ws_url = "wss://api.mistral.ai/v1/speech-to-text"
        
    async def transcribe_stream(self, audio_chunk: bytes, sample_rate: int = 8000) -> str:
        """
        Send audio frames to Mistral via WebSocket and receive transcription.
        In a real infinite stream, we'd maintain the WebSocket connection.
        Here we send the buffered audio from a single turn for simplicity.
        """
        if not self.api_key:
            logger.warning("Mistral API key not set, STT will fail.")
            return ""

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            async with websockets.connect(self.ws_url, additional_headers=headers) as ws:
                # 1. Send configuration/start message (adjust according to exact Mistral WS spec)
                config_msg = {
                    "type": "config",
                    "sample_rate": sample_rate,
                    "encoding": "mulaw" # or "pcm16" if decoded prior
                }
                await ws.send(json.dumps(config_msg))
                
                # 2. Send the binary audio chunk
                # Mistral API might expect raw binary or base64 JSON
                await ws.send(audio_chunk)
                
                # 3. Send end of stream flag if necessary
                await ws.send(json.dumps({"type": "eof"}))
                
                # 4. Await response
                transcription = ""
                async for message in ws:
                    data = json.loads(message)
                    if "text" in data:
                        transcription += data["text"] + " "
                    if data.get("type") == "done":
                        break
                        
                return transcription.strip()
                
        except Exception as e:
            logger.error(f"Mistral STT WebSocket error: {e}")
            return ""
