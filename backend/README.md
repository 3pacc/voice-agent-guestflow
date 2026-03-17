# Backend (FastAPI)

Backend principal du projet GuestFlow (API voice + API admin live).

## Lancement rapide (Runpod)

```bash
cd /workspace/voice-agent-guestflow
bash scripts/start_backend.sh
```

## Lancement manuel

```bash
cd /workspace/voice-agent-guestflow
.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## Endpoints importants

- `GET /health`
- `POST /twilio/twiml`
- `WS /twilio/media-stream`
- `GET /admin/live/health`
- `GET /admin/live/calls`
- `GET /admin/live/transcripts`
- `GET /admin/live/reservations`
- `GET /admin/live/inventory/rooms`
- `PUT /admin/live/inventory/rooms`
- `GET /admin/live/inventory/month`

## Verification

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/admin/live/health
```
