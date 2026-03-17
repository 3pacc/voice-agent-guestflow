import asyncio
import audioop
import base64
import datetime
import html
import json
import logging
import random
import re
import string
import unicodedata

import httpx
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.booking_graph import SYSTEM_PROMPT, booking_agent
from src.config.settings import settings
from src.llm.vllm_client import VllmClient
from src.stt.mistral_stt import MistralRealtimeSTT
from src.tts.inworld_tts import InworldTTS

logger = logging.getLogger(__name__)

router = APIRouter()


def _trace(event: str, **fields):
    """Structured trace logs for long-term observability."""
    try:
        payload = json.dumps(fields, ensure_ascii=False, default=str)
    except Exception:
        payload = str(fields)
    logger.info(f'TRACE {event} | {payload}')


@router.post('/twiml')
async def twilio_webhook(request: Request):
    host = request.headers.get('host', '')
    protocol = 'ws' if ('localhost' in host or '127.0.0.1' in host) else 'wss'
    stream_url = f"{protocol}://{host}/twilio/media-stream"

    form = await request.form()
    caller_number = str(form.get('From', '')).strip()

    stream_param = ''
    if caller_number:
        safe_number = html.escape(caller_number, quote=True)
        stream_param = f'            <Parameter name="caller_number" value="{safe_number}" />\n'

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Response>\n'
        '    <Connect>\n'
        f'        <Stream url="{stream_url}">\n'
        f'{stream_param}'
        '        </Stream>\n'
        '    </Connect>\n'
        '</Response>'
    )
    return HTMLResponse(content=twiml, media_type='text/xml')


async def send_audio_to_twilio(websocket: WebSocket, stream_sid: str, audio_chunk_b64: str):
    await websocket.send_text(
        json.dumps({'event': 'media', 'streamSid': stream_sid, 'media': {'payload': audio_chunk_b64}})
    )


async def send_clear_to_twilio(websocket: WebSocket, stream_sid: str):
    await websocket.send_text(json.dumps({'event': 'clear', 'streamSid': stream_sid}))


def _normalize_text(value: str) -> str:
    base = (value or '').lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', base) if unicodedata.category(c) != 'Mn')


def _is_confirmation_intent(text: str) -> bool:
    low = _normalize_text(text)
    if any(k in low for k in ['annul', 'annule', 'changer', 'modifier', 'alternative', 'autre type', 'non']):
        return False

    patterns = [
        r'\boui\b',
        r'\bouais\b',
        r'\byeah\b',
        r'\byep\b',
        r'\bdaccord\b',
        r'\bje confirme\b',
        r'\bconfirme\b',
        r'\bconfirmer\b',
        r'\bvalider\b',
        r"\bcest bon\b",
        r'\bon y va\b',
    ]
    return any(re.search(p, low) for p in patterns)


def _is_price_or_info_intent(text: str) -> bool:
    low = _normalize_text(text)
    keywords = [
        'prix', 'tarif', 'combien', 'cout', 'coute', 'montant', 'total',
        'offre', 'petit dejeuner', 'petit-dejeuner', 'details', 'detail',
        'pourquoi', 'comment', 'quels services', 'quelle offre',
    ]
    if any(k in low for k in keywords):
        return True
    return '?' in (text or '')


def _sanitize_agent_response(text: str, allow_greeting: bool = False) -> str:
    out = (text or '').strip()
    if not out:
        return out

    if not allow_greeting:
        out = re.sub(r"^(?:bonjour|bonsoir|salut)[\s,!.:-]*", "", out, flags=re.IGNORECASE).strip()

    out = re.sub(r"\s+", " ", out).strip()
    return out


async def _single_text_stream(text: str):
    yield text


def _build_confirmation_question(state: dict) -> str:
    return (
        "Parfait, la chambre est disponible. "
        "Souhaitez-vous confirmer la r\u00e9servation pour recevoir le SMS de finalisation ?"
    )


def _build_reservation_ref() -> str:
    ts = datetime.datetime.utcnow().strftime('%y%m%d%H%M%S')
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f'GF-{ts}-{suffix}'


def _payment_link_for_ref(reference: str) -> str:
    base = (settings.booking_payment_test_url or '').strip() or 'https://example.com/payment-test'
    sep = '&' if '?' in base else '?'
    return f'{base}{sep}booking_ref={reference}'


def _build_final_confirmation_text(
    state: dict,
    reservation_ref: str,
    sms_sent: bool,
    target_number: str | None,
    payment_link: str,
) -> str:
    if sms_sent:
        return (
            "Parfait, votre r\u00e9servation est enregistr\u00e9e. "
            "Un SMS vous a \u00e9t\u00e9 envoy\u00e9 pour finaliser la r\u00e9servation. "
            "Merci pour votre confiance et \u00e0 bient\u00f4t."
        )

    return (
            "Parfait, votre r\u00e9servation est enregistr\u00e9e. "
        f"Le lien de paiement est : {payment_link}. "
        "Merci pour votre confiance et \u00e0 bient\u00f4t."
    )


def _build_sms_body(state: dict, reference: str, payment_link: str) -> str:
    check_in = state.get('check_in_date') or 'N/A'
    check_out = state.get('check_out_date') or 'N/A'
    nights = state.get('nights') or 'N/A'
    guests = state.get('guests') or 'N/A'
    room_type = state.get('room_type') or 'standard'

    return (
        f'GuestFlow - Reservation confirmee\n'
        f'Ref: {reference}\n'
        f'Sejour: {check_in} au {check_out} ({nights} nuit(s))\n'
        f'Chambre: {room_type} - {guests} personne(s)\n'
        f'Paiement test: {payment_link}'
    )


async def _send_booking_sms(to_number: str, body: str) -> dict:
    sid = (settings.twilio_account_sid or '').strip()
    token = (settings.twilio_auth_token or '').strip()
    sender = (settings.twilio_phone_number or '').strip()

    if not sid or not token or not sender:
        logger.warning('SMS not sent: Twilio credentials/From number are missing.')
        return {'ok': False, 'sid': None, 'status': None, 'error': 'missing_twilio_credentials'}

    if not to_number:
        logger.warning('SMS not sent: target phone number is empty.')
        return {'ok': False, 'sid': None, 'status': None, 'error': 'missing_target_number'}

    url = f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json'
    data = {'From': sender, 'To': to_number, 'Body': body}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, data=data, auth=(sid, token))

        if response.status_code in (200, 201):
            msg_sid = response.json().get('sid', 'unknown')
            logger.info(f'Booking SMS sent successfully to {to_number}, sid={msg_sid}')
            return {'ok': True, 'sid': msg_sid, 'status': response.status_code, 'error': None}

        error_msg = response.text[:400]
        logger.error(f'Booking SMS failed [{response.status_code}]: {error_msg}')
        return {'ok': False, 'sid': None, 'status': response.status_code, 'error': error_msg}

    except Exception as exc:
        logger.error(f'Booking SMS exception: {exc}', exc_info=True)
        return {'ok': False, 'sid': None, 'status': None, 'error': str(exc)}


async def _hangup_twilio_call(call_sid: str | None) -> bool:
    if not call_sid:
        logger.warning('Hangup skipped: call_sid is missing.')
        return False

    account_sid = (settings.twilio_account_sid or '').strip()
    auth_token = (settings.twilio_auth_token or '').strip()
    if not account_sid or not auth_token:
        logger.warning('Hangup skipped: Twilio credentials are missing.')
        return False

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls/{call_sid}.json"
    data = {'Twiml': '<Response><Hangup/></Response>'}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, data=data, auth=(account_sid, auth_token))
        ok = response.status_code in (200, 201)
        if ok:
            logger.info(f'Twilio hangup requested successfully for call_sid={call_sid}')
        else:
            logger.error(f'Twilio hangup failed [{response.status_code}] for call_sid={call_sid}: {response.text[:300]}')
        return ok
    except Exception as exc:
        logger.error(f'Twilio hangup exception: {exc}', exc_info=True)
        return False


SAMPLE_RATE = 8000
CHUNK_MS = 20
RMS_SPEECH_THRESHOLD = 250
REQUIRED_SILENCE_MS = 800
MIN_UTTERANCE_MS = 300
MAX_BUFFER_BYTES = 160_000

BARGE_IN_RMS_THRESHOLD = 500
BARGE_IN_MIN_FRAMES = 5


@router.websocket('/media-stream')
async def twilio_media_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info('Twilio WebSocket connected.')

    stt = MistralRealtimeSTT()
    tts = InworldTTS()
    llm = VllmClient()

    conv_state = {
        'messages': [],
        'turn_count': 0,
        'stage': 'greeting',
        'check_in_date': None,
        'check_out_date': None,
        'guests': None,
        'room_type': None,
        'nights': None,
        'room_available': None,
        'reservation_confirmed': False,
        'reservation_ref': None,
        'sms_sent': False,
    }

    caller_number: str | None = None
    call_sid: str | None = None

    audio_buffer: bytearray = bytearray()
    stream_sid: str | None = None
    is_responding = False

    in_speech = False
    silence_ms = 0
    process_task: asyncio.Task | None = None
    barge_in_voice_frames = 0
    should_hangup_after_response = False
    final_response_override: str | None = None

    async def process_utterance(captured: bytes):
        nonlocal is_responding, barge_in_voice_frames, caller_number, call_sid, should_hangup_after_response, final_response_override

        if not captured or is_responding:
            return

        is_responding = True
        barge_in_voice_frames = 0
        try:
            user_text = await stt.transcribe_stream(captured)
            if not user_text:
                logger.info('STT returned empty transcript, skipping.')
                return

            logger.info(f"User said: '{user_text}'")

            conv_state['turn_count'] = int(conv_state.get('turn_count', 0)) + 1
            final_response_override = None
            conv_state['messages'].append(HumanMessage(content=user_text))
            new_state = await booking_agent.ainvoke(conv_state)
            conv_state.update(new_state)

            has_booking_fields = (
                bool(conv_state.get('check_in_date'))
                and bool(conv_state.get('check_out_date'))
                and bool(conv_state.get('guests'))
                and bool(conv_state.get('room_type'))
            )
            can_finalize = (
                has_booking_fields
                and not conv_state.get('reservation_confirmed')
                and _is_confirmation_intent(user_text)
                and (
                    conv_state.get('room_available') is True
                    or conv_state.get('stage') == 'confirmation'
                )
            )
            _trace(
                'finalization_gate',
                user_text=user_text,
                stage=conv_state.get('stage'),
                room_available=conv_state.get('room_available'),
                has_booking_fields=has_booking_fields,
                is_confirmation_intent=_is_confirmation_intent(user_text),
                can_finalize=can_finalize,
            )

            if can_finalize:
                reservation_ref = _build_reservation_ref()
                payment_link = _payment_link_for_ref(reservation_ref)
                target_number = caller_number or (settings.booking_sms_fallback_to or '').strip()

                sms_result = {'ok': False, 'sid': None, 'status': None, 'error': 'not_attempted'}
                if settings.booking_sms_enabled and target_number:
                    sms_body = _build_sms_body(conv_state, reservation_ref, payment_link)
                    sms_result = await _send_booking_sms(target_number, sms_body)
                elif settings.booking_sms_enabled:
                    logger.warning('SMS enabled but no caller/fallback number available for booking confirmation.')
                    sms_result = {'ok': False, 'sid': None, 'status': None, 'error': 'missing_caller_and_fallback'}

                sms_sent = bool(sms_result.get('ok'))
                conv_state['reservation_confirmed'] = True
                conv_state['reservation_ref'] = reservation_ref
                conv_state['sms_sent'] = sms_sent
                conv_state['stage'] = 'done'
                should_hangup_after_response = True

                _trace(
                    'booking_finalized',
                    reservation_ref=reservation_ref,
                    stream_sid=stream_sid,
                    caller_number=caller_number,
                    target_number=target_number,
                    sms_enabled=settings.booking_sms_enabled,
                    sms_sent=sms_sent,
                    sms_sid=sms_result.get('sid'),
                    sms_status=sms_result.get('status'),
                    sms_error=sms_result.get('error'),
                    check_in_date=conv_state.get('check_in_date'),
                    check_out_date=conv_state.get('check_out_date'),
                    nights=conv_state.get('nights'),
                    guests=conv_state.get('guests'),
                    room_type=conv_state.get('room_type'),
                )

                if sms_sent:
                    tool_msg = AIMessage(
                        content=(
                            f'[System] Reservation finalisee. Reference: {reservation_ref}. '
                            f'Un SMS recapitulatif avec lien de paiement test a ete envoye au {target_number}. '
                            'Confirme brievement la reservation au client et invite-le a finaliser le paiement via le lien SMS.'
                        )
                    )
                else:
                    tool_msg = AIMessage(
                        content=(
                            f'[System] Reservation finalisee. Reference: {reservation_ref}. '
                            f'Lien de paiement test: {payment_link}. '
                            "Le SMS n'a pas pu etre envoye automatiquement. Donne la reference au client et indique qu'un lien sera envoye."
                        )
                    )

                conv_state['messages'].append(tool_msg)
                final_response_override = _build_final_confirmation_text(
                    conv_state,
                    reservation_ref,
                    sms_sent,
                    target_number,
                    payment_link,
                )
            elif conv_state.get('room_available') is True and not conv_state.get('reservation_confirmed'):
                if _is_price_or_info_intent(user_text):
                    _trace('confirmation_deferred_for_question', user_text=user_text)
                else:
                    final_response_override = _build_confirmation_question(conv_state)

            messages_for_llm = (
                [{'role': 'system', 'content': SYSTEM_PROMPT}]
                + [
                    {
                        'role': 'user' if isinstance(m, HumanMessage) else 'assistant',
                        'content': m.content,
                    }
                    for m in conv_state['messages']
                ]
            )

            if final_response_override:
                response_text = final_response_override
            else:
                generated_parts = []
                async for token in llm.generate_response_stream(messages_for_llm):
                    generated_parts.append(token)
                response_text = ''.join(generated_parts).strip()

            # Never re-greet after initial welcome; keep responses concise.
            response_text = _sanitize_agent_response(response_text, allow_greeting=False)
            if not response_text:
                response_text = "Je vous \u00e9coute."

            sent_chunks = 0
            async for audio_chunk in tts.stream_tts(_single_text_stream(response_text)):
                if not is_responding:
                    if stream_sid:
                        await send_clear_to_twilio(websocket, stream_sid)
                    logger.info('Barge-in: audio playback stopped.')
                    return

                if audio_chunk and stream_sid:
                    audio_b64 = base64.b64encode(audio_chunk).decode('utf-8')
                    await send_audio_to_twilio(websocket, stream_sid, audio_b64)
                    sent_chunks += 1

            logger.info(f'Agent response sent ({sent_chunks} chunks).')

            if should_hangup_after_response and conv_state.get('reservation_confirmed'):
                playback_drain_s = max((sent_chunks * CHUNK_MS) / 1000.0 + 1.6, 2.2)
                _trace(
                    'call_hangup_scheduled',
                    call_sid=call_sid,
                    reservation_ref=conv_state.get('reservation_ref'),
                    sent_chunks=sent_chunks,
                    delay_seconds=round(playback_drain_s, 2),
                )
                await asyncio.sleep(playback_drain_s)
                _trace('call_hangup_requested', call_sid=call_sid, reservation_ref=conv_state.get('reservation_ref'))
                await _hangup_twilio_call(call_sid)
                should_hangup_after_response = False

        except Exception as exc:
            logger.error(f'Pipeline error: {exc}', exc_info=True)
        finally:
            is_responding = False
            barge_in_voice_frames = 0

    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            event = message.get('event')

            if event == 'start':
                start_payload = message.get('start', {})
                stream_sid = start_payload.get('streamSid')
                call_sid = start_payload.get('callSid')
                custom = start_payload.get('customParameters') or {}
                caller_number = (custom.get('caller_number') or '').strip() or None
                if not caller_number:
                    fallback = (settings.booking_sms_fallback_to or '').strip()
                    caller_number = fallback or None

                logger.info(f'Stream started - SID: {stream_sid}')
                if caller_number:
                    logger.info(f'Caller number available for SMS: {caller_number}')
                _trace('call_started', stream_sid=stream_sid, call_sid=call_sid, caller_number=caller_number)

                greeting_text = (
                    'Bonjour et bienvenue chez GuestFlow Hotel. '
                    "Je suis votre receptionniste virtuelle, comment puis-je vous aider aujourd'hui ?"
                )
                conv_state['messages'].append(AIMessage(content=greeting_text))

                async def send_greeting():
                    nonlocal is_responding, barge_in_voice_frames
                    is_responding = True
                    barge_in_voice_frames = 0

                    async def _text_gen():
                        yield greeting_text

                    sent_chunks = 0
                    try:
                        async for audio_chunk in tts.stream_tts(_text_gen()):
                            if not is_responding:
                                if stream_sid:
                                    await send_clear_to_twilio(websocket, stream_sid)
                                logger.info('Greeting interrupted by barge-in.')
                                return
                            if audio_chunk and stream_sid:
                                b64 = base64.b64encode(audio_chunk).decode('utf-8')
                                await send_audio_to_twilio(websocket, stream_sid, b64)
                                sent_chunks += 1
                    finally:
                        is_responding = False
                        barge_in_voice_frames = 0

                    logger.info(f'Greeting sent ({sent_chunks} chunks).')
                    if sent_chunks == 0:
                        logger.error('Greeting produced no audio chunks. Check TTS credentials/response.')

                asyncio.create_task(send_greeting())

            elif event == 'media':
                audio_payload = message['media']['payload']
                audio_chunk = base64.b64decode(audio_payload)

                pcm16 = audioop.ulaw2lin(audio_chunk, 2)
                rms = audioop.rms(pcm16, 2)
                is_voice = rms >= RMS_SPEECH_THRESHOLD
                is_barge_voice = rms >= BARGE_IN_RMS_THRESHOLD

                if is_responding:
                    if is_barge_voice:
                        barge_in_voice_frames += 1
                    else:
                        barge_in_voice_frames = 0

                    if barge_in_voice_frames >= BARGE_IN_MIN_FRAMES:
                        logger.info(f'Barge-in detected (rms={rms}, frames={barge_in_voice_frames}).')
                        is_responding = False
                        barge_in_voice_frames = 0
                        audio_buffer.clear()
                        in_speech = False
                        silence_ms = 0
                        if stream_sid:
                            await send_clear_to_twilio(websocket, stream_sid)
                    continue

                if is_voice:
                    if not in_speech:
                        in_speech = True
                        silence_ms = 0
                        audio_buffer.clear()
                        logger.info(f'Speech start (rms={rms}).')

                    if len(audio_buffer) < MAX_BUFFER_BYTES:
                        audio_buffer.extend(audio_chunk)
                    silence_ms = 0

                elif in_speech:
                    if len(audio_buffer) < MAX_BUFFER_BYTES:
                        audio_buffer.extend(audio_chunk)

                    silence_ms += CHUNK_MS
                    if silence_ms >= REQUIRED_SILENCE_MS:
                        captured = bytes(audio_buffer)
                        audio_buffer.clear()
                        in_speech = False
                        silence_ms = 0

                        min_bytes = int(SAMPLE_RATE * (MIN_UTTERANCE_MS / 1000.0))
                        if len(captured) >= min_bytes:
                            logger.info(f'Speech end detected, captured={len(captured)} bytes -> STT')
                            if process_task and not process_task.done():
                                logger.info('Previous processing still running, dropping overlap.')
                            else:
                                process_task = asyncio.create_task(process_utterance(captured))
                        else:
                            logger.info('Discarding too-short utterance.')

            elif event == 'stop':
                logger.info('Twilio stream stopped.')
                break

    except WebSocketDisconnect:
        logger.info('Twilio WebSocket disconnected.')
    except Exception as exc:
        logger.error(f'WebSocket error: {exc}', exc_info=True)
    finally:
        if process_task and not process_task.done():
            process_task.cancel()
        logger.info('Call session ended.')
