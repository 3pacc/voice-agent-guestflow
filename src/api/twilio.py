import asyncio
import base64
import json
import logging

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.stt.mistral_stt import MistralRealtimeSTT
from src.tts.inworld_tts import InworldTTS
from src.llm.vllm_client import VllmClient
from src.agent.booking_graph import booking_agent, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# TwiML webhook — tells Twilio to open a media WebSocket to our endpoint
# ---------------------------------------------------------------------------

@router.post("/twiml")
async def twilio_webhook(request: Request):
    host = request.headers.get("host", "")
    protocol = "ws" if ("localhost" in host or "127.0.0.1" in host) else "wss"
    stream_url = f"{protocol}://{host}/twilio/media-stream"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}" />
    </Connect>
</Response>"""
    return HTMLResponse(content=twiml, media_type="text/xml")


# ---------------------------------------------------------------------------
# Helpers: send audio / clear buffer back to Twilio
# ---------------------------------------------------------------------------

async def send_audio_to_twilio(websocket: WebSocket, stream_sid: str, audio_chunk_b64: str):
    """Send a base64-encoded mulaw audio chunk back to the Twilio media stream."""
    await websocket.send_text(json.dumps({
        "event": "media",
        "streamSid": stream_sid,
        "media": {"payload": audio_chunk_b64},
    }))


async def send_clear_to_twilio(websocket: WebSocket, stream_sid: str):
    """Clear Twilio's playback buffer (used on barge-in)."""
    await websocket.send_text(json.dumps({
        "event": "clear",
        "streamSid": stream_sid,
    }))


# ---------------------------------------------------------------------------
# Main WebSocket — full Twilio ↔ Agent pipeline
# ---------------------------------------------------------------------------

SILENCE_SECONDS = 1.5   # seconds of quiet before processing the utterance
MAX_BUFFER_BYTES = 160_000  # ~20 s of 8 kHz mulaw — safety cap


@router.websocket("/media-stream")
async def twilio_media_stream(websocket: WebSocket):
    """
    Full pipeline:
      Twilio audio → buffer → silence detection
      → Mistral STT → LangGraph state update
      → vLLM response stream → Inworld TTS → Twilio audio
    """
    await websocket.accept()
    logger.info("Twilio WebSocket connected.")

    # --- Per-call state ---
    stt = MistralRealtimeSTT()
    tts = InworldTTS()
    llm = VllmClient()

    conv_state = {
        "messages": [],
        "stage": "greeting",
        "check_in_date": None,
        "check_out_date": None,
        "guests": None,
        "room_available": None,
    }

    audio_buffer: bytearray = bytearray()
    stream_sid: str | None = None
    is_responding = False
    silence_handle: asyncio.TimerHandle | None = None
    loop = asyncio.get_event_loop()

    # ------------------------------------------------------------------
    async def process_utterance():
        """Called after silence is detected: run the full STT→LLM→TTS pipeline."""
        nonlocal audio_buffer, is_responding

        if not audio_buffer or is_responding:
            return

        captured = bytes(audio_buffer)
        audio_buffer.clear()
        is_responding = True

        try:
            # 1. STT ─────────────────────────────────────────────────────
            user_text = await stt.transcribe_stream(captured)
            if not user_text:
                logger.info("STT returned empty transcript, skipping.")
                return
            logger.info(f"User said: '{user_text}'")

            # 2. LangGraph ────────────────────────────────────────────────
            conv_state["messages"].append(HumanMessage(content=user_text))
            new_state = await booking_agent.ainvoke(conv_state)
            conv_state.update(new_state)

            # 3. Build message list for vLLM (with system prompt)
            messages_for_llm = (
                [{"role": "system", "content": SYSTEM_PROMPT}]
                + [
                    {"role": "user" if isinstance(m, HumanMessage) else "assistant",
                     "content": m.content}
                    for m in conv_state["messages"]
                ]
            )

            # 4. vLLM stream ──────────────────────────────────────────────
            text_stream = llm.generate_response_stream(messages_for_llm)

            # 5. TTS → Twilio ─────────────────────────────────────────────
            full_response = []
            async for audio_chunk in tts.stream_tts(text_stream):
                if not is_responding:
                    # Barge-in happened
                    if stream_sid:
                        await send_clear_to_twilio(websocket, stream_sid)
                    logger.info("Barge-in: audio playback stopped.")
                    return
                if audio_chunk and stream_sid:
                    audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")
                    await send_audio_to_twilio(websocket, stream_sid, audio_b64)

        except Exception as exc:
            logger.error(f"Pipeline error: {exc}", exc_info=True)
        finally:
            is_responding = False

    # ------------------------------------------------------------------
    def schedule_silence_processing():
        """Reset the silence timer each time audio arrives."""
        nonlocal silence_handle
        if silence_handle is not None:
            silence_handle.cancel()
        silence_handle = loop.call_later(
            SILENCE_SECONDS,
            lambda: asyncio.ensure_future(process_utterance()),
        )

    # ------------------------------------------------------------------
    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            event = message.get("event")

            if event == "start":
                stream_sid = message["start"]["streamSid"]
                logger.info(f"Stream started — SID: {stream_sid}")

                # Send greeting immediately
                greeting_text = (
                    "Hello! Welcome to GuestFlow Hotel. "
                    "I'm your virtual receptionist. How can I help you today?"
                )
                conv_state["messages"].append(AIMessage(content=greeting_text))

                async def send_greeting():
                    async def _text_gen():
                        yield greeting_text

                    async for audio_chunk in tts.stream_tts(_text_gen()):
                        if audio_chunk and stream_sid:
                            b64 = base64.b64encode(audio_chunk).decode("utf-8")
                            await send_audio_to_twilio(websocket, stream_sid, b64)

                asyncio.ensure_future(send_greeting())

            elif event == "media":
                audio_payload = message["media"]["payload"]
                audio_chunk = base64.b64decode(audio_payload)

                if is_responding:
                    # User is speaking while agent responds → barge-in
                    logger.info("Barge-in detected.")
                    is_responding = False
                    audio_buffer.clear()

                # Buffer audio (cap at safety limit)
                if len(audio_buffer) < MAX_BUFFER_BYTES:
                    audio_buffer.extend(audio_chunk)

                schedule_silence_processing()

            elif event == "stop":
                logger.info("Twilio stream stopped.")
                break

    except WebSocketDisconnect:
        logger.info("Twilio WebSocket disconnected.")
    except Exception as exc:
        logger.error(f"WebSocket error: {exc}", exc_info=True)
    finally:
        if silence_handle:
            silence_handle.cancel()
        logger.info("Call session ended.")
