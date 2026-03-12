from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
import logging
import json
import base64

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/twiml")
async def twilio_webhook(request: Request):
    """
    Returns TwiML that connects the incoming call to our WebSocket stream.
    Expected to receive the POST request when a Twilio number is called.
    """
    host = request.headers.get("host")
    protocol = "wss" if "localhost" not in host and "127.0.0.1" not in host else "ws"
    # Using ngrok or runpod domain -> default to wss
    stream_url = f"{protocol}://{host}/twilio/media-stream"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}" />
    </Connect>
</Response>"""
    return HTMLResponse(content=twiml, media_type="text/xml")

@router.websocket("/media-stream")
async def twilio_media_stream(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams.
    Handles incoming audio stream from caller, and outgoing TTS back to caller.
    """
    await websocket.accept()
    logger.info("Twilio WebSocket connection accepted.")

    stream_sid = None

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message["event"] == "start":
                stream_sid = message["start"]["streamSid"]
                logger.info(f"Incoming stream started. Stream SID: {stream_sid}")
                
                # Here we would initialize our FastRTC handler
                # to process the incoming audio and respond
                
            elif message["event"] == "media":
                audio_payload = message["media"]["payload"]
                # Decode base64 mulaw audio chunk
                audio_chunk = base64.b64decode(audio_payload)
                
                # Forward to STT/VAD
                
            elif message["event"] == "stop":
                logger.info("Stream stopped by caller.")
                break
                
    except WebSocketDisconnect:
        logger.info("Twilio WebSocket disconnected.")
    except Exception as e:
        logger.error(f"Error in Twilio WebSocket: {e}", exc_info=True)
    finally:
        # Clean up resources
        pass

async def send_audio_to_twilio(websocket: WebSocket, stream_sid: str, audio_chunk_b64: str):
    """
    Helper function to send TTS audio back to Twilio.
    audio_chunk_b64 should be base64 encoded mulaw 8000Hz audio.
    """
    message = {
        "event": "media",
        "streamSid": stream_sid,
        "media": {
            "payload": audio_chunk_b64
        }
    }
    await websocket.send_text(json.dumps(message))

async def send_clear_to_twilio(websocket: WebSocket, stream_sid: str):
    """
    Used to clear Twilio's audio buffer when user interrupts (barge-in).
    """
    message = {
        "event": "clear",
        "streamSid": stream_sid
    }
    await websocket.send_text(json.dumps(message))

