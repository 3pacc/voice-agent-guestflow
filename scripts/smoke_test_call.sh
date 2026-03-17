#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV_PY="${VENV_PY:-$ROOT_DIR/.venv/bin/python}"
VENV_UVICORN="${VENV_UVICORN:-$ROOT_DIR/.venv/bin/uvicorn}"
export PATH="$ROOT_DIR/.venv/bin:$PATH"

if [ ! -x "$VENV_PY" ]; then
  echo "[error] Missing venv python: $VENV_PY"
  exit 1
fi

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

LLM_MODEL="${LLM_MODEL:-meta-llama/Llama-3.1-8B-Instruct}"
LLM_API_KEY="${LLM_API_KEY:-EMPTY}"

FAILS=0

ok() { echo "[OK] $1"; }
fail() { echo "[FAIL] $1"; FAILS=$((FAILS+1)); }

maybe_start_services() {
  local api_code
  api_code=$(curl -sS -o /dev/null -w "%{http_code}" "http://localhost:8000/health" || echo "000")
  if [ "$api_code" = "200" ]; then
    return
  fi
  if [ -x "$ROOT_DIR/scripts/start_services.sh" ]; then
    echo "[smoke] services down -> tentative de demarrage automatique"
    "$ROOT_DIR/scripts/start_services.sh" || true
    sleep 2
  fi
}

echo "[smoke] ROOT_DIR=$ROOT_DIR"
maybe_start_services

echo "[smoke] 1) API health"
API_CODE=$(curl -sS -o /tmp/smoke_api_health.json -w "%{http_code}" "http://localhost:8000/health" || echo "000")
if [ "$API_CODE" = "200" ]; then
  ok "API /health = 200"
else
  fail "API /health status=$API_CODE"
fi

echo "[smoke] 2) vLLM models"
VLLM_CODE=$(curl -sS -o /tmp/smoke_vllm_models.json -w "%{http_code}" \
  -H "Authorization: Bearer $LLM_API_KEY" \
  "http://localhost:8002/v1/models" || echo "000")
if [ "$VLLM_CODE" = "200" ]; then
  ok "vLLM /v1/models = 200"
else
  fail "vLLM /v1/models status=$VLLM_CODE"
fi

echo "[smoke] 3) LLM generation"
cat > /tmp/smoke_llm_payload.json <<EOF
{
  "model": "$LLM_MODEL",
  "messages": [
    {"role": "system", "content": "Tu es un assistant utile."},
    {"role": "user", "content": "Dis exactement: test ok"}
  ],
  "max_tokens": 24,
  "temperature": 0.0
}
EOF
LLM_CODE=$(curl -sS -o /tmp/smoke_llm_resp.json -w "%{http_code}" \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d @/tmp/smoke_llm_payload.json \
  "http://localhost:8002/v1/chat/completions" || echo "000")
if [ "$LLM_CODE" = "200" ]; then
  ok "LLM chat completion = 200"
else
  fail "LLM chat completion status=$LLM_CODE"
fi

echo "[smoke] 4) TTS Inworld"
if [ -z "${INWORLD_KEY:-}" ]; then
  fail "TTS: INWORLD_KEY manquant"
else
  AUTH=$("$VENV_PY" - <<'PY2'
import base64, os
key=os.getenv('INWORLD_KEY','')
secret=os.getenv('INWORLD_SECRET','')
if secret:
    raw = f"{key}:{secret}"
    print("Basic " + base64.b64encode(raw.encode()).decode())
else:
    print("Basic " + key)
PY2
)

  INWORLD_VOICE_ID="${INWORLD_VOICE_ID:-Mathieu}"
  cat > /tmp/smoke_tts_payload.json <<EOF
{
  "text": "Bonjour, ceci est un test audio GuestFlow.",
  "modelId": "inworld-tts-1.5-max",
  "voiceId": "$INWORLD_VOICE_ID",
  "audioConfig": {"audioEncoding": "MULAW", "sampleRateHertz": 8000}
}
EOF

  TTS_CODE=$(curl -sS -o /tmp/smoke_tts_resp.json -w "%{http_code}" \
    -H "Authorization: $AUTH" \
    -H "Content-Type: application/json" \
    -d @/tmp/smoke_tts_payload.json \
    "https://api.inworld.ai/tts/v1/voice" || echo "000")

  if [ "$TTS_CODE" = "200" ]; then
    AUDIO_LEN=$("$VENV_PY" - <<'PY3'
import json
from pathlib import Path
p = Path('/tmp/smoke_tts_resp.json')
try:
    data = json.loads(p.read_text(encoding='utf-8'))
    audio = data.get('audioContent') or ''
    print(len(audio))
except Exception:
    print(0)
PY3
)
    if [ "${AUDIO_LEN:-0}" -gt 0 ]; then
      ok "TTS Inworld = 200 (audioContent base64 present)"
    else
      fail "TTS Inworld reponse sans audioContent"
    fi
  else
    fail "TTS Inworld status=$TTS_CODE"
  fi
fi

echo "[smoke] 5) STT Mistral"
if [ -z "${MISTRAL_API_KEY:-}" ]; then
  fail "STT: MISTRAL_API_KEY manquant"
else
  "$VENV_PY" - <<'PY4'
import wave
pcm = b"\x00\x00" * 8000
with wave.open('/tmp/smoke_stt.wav', 'wb') as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(8000)
    w.writeframes(pcm)
PY4

  STT_CODE=$(curl -sS -o /tmp/smoke_stt_resp.json -w "%{http_code}" \
    -H "Authorization: Bearer ${MISTRAL_API_KEY}" \
    -F "file=@/tmp/smoke_stt.wav;type=audio/wav" \
    -F "model=voxtral-mini-2507" \
    "https://api.mistral.ai/v1/audio/transcriptions" || echo "000")

  if [ "$STT_CODE" = "200" ]; then
    ok "STT Mistral = 200"
  else
    fail "STT Mistral status=$STT_CODE"
  fi
fi

echo
echo "[smoke] Resultat final"
if [ "$FAILS" -eq 0 ]; then
  echo "[smoke] RESULT: PASSED"
  exit 0
else
  echo "[smoke] RESULT: FAILED ($FAILS checks en echec)"
  exit 1
fi
