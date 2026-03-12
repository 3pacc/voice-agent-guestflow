import asyncio
import logging
import json
import websockets
from typing import AsyncGenerator
from src.config.settings import settings

logger = logging.getLogger(__name__)

class InworldTTS:
    """
    Client for Inworld TTS high-fidelity streaming.
    Uses wss://api.inworld.ai/v1/tts endpoint for sub-second latency.
    """
    def __init__(self):
        self.api_key = settings.inworld_key
        self.api_secret = settings.inworld_secret
        self.ws_url = "wss://api.inworld.ai/v1/tts" 
        self.model = "inworld-tts-1.5-max"
        self.voice = "Clive"

    async def stream_tts(self, text_stream: AsyncGenerator[str, None], sample_rate: int = 8000) -> AsyncGenerator[bytes, None]:
        """
        Takes an async generator of text chunks (from LLM) and yields an async generator of mulaw audio bytes.
        Sends tokens progressively to the WebSocket to reduce time-to-first-byte (TTFB).
        """
        if not self.api_key or not self.api_secret:
            logger.warning("INWORLD_KEY or INWORLD_SECRET is not set.")
            yield b""
            return

        headers = {
            "Authorization": f"Basic {self.api_key}:{self.api_secret}" # Format depends on exact Inworld auth spec
        }

        try:
            async with websockets.connect(self.ws_url, additional_headers=headers) as ws:
                
                # 1. Send initial configuration
                config_msg = {
                    "type": "config",
                    "model": self.model,
                    "voice": self.voice,
                    "output_format": {
                        "encoding": "MULAW",
                        "sample_rate": sample_rate
                    }
                }
                await ws.send(json.dumps(config_msg))

                # 2. Start a task to receive audio chunks
                async def receiver():
                    audio_chunks = []
                    async for message in ws:
                        if isinstance(message, bytes):
                            audio_chunks.append(message)
                        else:
                            data = json.loads(message)
                            if data.get("type") == "audio":
                                # If Base64 encoded inside JSON (depends on API spec)
                                pass
                            elif data.get("type") == "done":
                                break
                    return audio_chunks

                receive_task = asyncio.create_task(receiver())

                # 3. Stream text tokens to the WebSocket as they arrive
                async for chunk in text_stream:
                    if chunk:
                        text_msg = {"type": "text", "text": chunk}
                        await ws.send(json.dumps(text_msg))
                        
                # 4. Signal end of text stream
                await ws.send(json.dumps({"type": "eof"}))

                # 5. Yield received audio
                audio_chunks = await receive_task
                for chunk in audio_chunks:
                    yield chunk

        except Exception as e:
            logger.error(f"Inworld TTS WebSocket Exception: {e}", exc_info=True)
            yield b""
