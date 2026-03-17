# Scripts d'exploitation (Runpod SSH)

Ce guide explique comment lancer et maitriser le projet de A a Z sur Runpod.

## 0) Se connecter au pod

Depuis votre machine locale:

```bash
ssh <user>@ssh.runpod.io -i ~/.ssh/id_ed25519
```

Puis:

```bash
cd /workspace/voice-agent-guestflow
```

## 1) Preparation initiale (premier lancement)

### 1.1 Python venv + dependances

```bash
cd /workspace/voice-agent-guestflow
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 1.2 Frontend dependances

```bash
cd /workspace/voice-agent-guestflow/frontend
npm install
```

### 1.3 Variables d'environnement

Verifier/editer `.env` a la racine:

```bash
cd /workspace/voice-agent-guestflow
nano .env
```

Variables importantes (exemples):

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`
- `MISTRAL_API_KEY`
- `INWORLD_KEY`
- `INWORLD_SECRET`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `DATABASE_URL`

## 2) Lancer les services

## 2.1 Backend FastAPI (8000)

```bash
cd /workspace/voice-agent-guestflow
bash scripts/start_backend.sh
```

## 2.2 Frontend Next.js (3000)

Dans un second terminal:

```bash
cd /workspace/voice-agent-guestflow
bash scripts/start_frontend.sh
```

## 2.3 (Optionnel) vLLM local

Si vous utilisez le LLM local sur GPU, lancez votre commande vLLM dans un troisieme terminal.

## 2.4 Logs live

```bash
cd /workspace/voice-agent-guestflow
bash scripts/logs_services.sh
```


## 2.5 Lancement en une seule commande (backend + frontend)

```bash
cd /workspace/voice-agent-guestflow
bash scripts/start_all.sh
```

Ce script:
- verifie `.venv` et `npm`
- redemarre proprement backend + frontend
- nettoie `frontend/.next`
- verifie `:8000/health` et `:3000/dashboard`

## 2.6 Arreter tous les services

```bash
cd /workspace/voice-agent-guestflow
bash scripts/stop_all.sh
```

## 2.7 Redemarrer tous les services

```bash
cd /workspace/voice-agent-guestflow
bash scripts/restart_all.sh
```

## 2.8 Diagnostic complet

```bash
cd /workspace/voice-agent-guestflow
bash scripts/doctor.sh
```

Le diagnostic verifie:
- prerequis (`.venv`, `node`, `npm`)
- presence des scripts
- process actifs (backend/frontend/vllm/ngrok)
- endpoints HTTP critiques
- ports ecoutes

## 3) Exposer en public (ngrok)

Si vous devez tester via Twilio depuis l'exterieur:

```bash
cd /workspace/voice-agent-guestflow
./ngrok start --all --config /root/.config/ngrok/ngrok.yml
```

Utiliser:

- URL frontend ngrok -> dashboard admin
- URL backend ngrok -> webhook Twilio

## 4) Verification fonctionnelle

## 4.1 API

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/admin/live/health
curl http://127.0.0.1:8000/admin/live/settings
curl http://127.0.0.1:8000/admin/live/inventory/rooms
```

## 4.2 Frontend

```bash
curl http://127.0.0.1:3000/dashboard
curl http://127.0.0.1:3000/settings
curl http://127.0.0.1:3000/inventory
```

## 4.3 Test appel voice

1. Verifier que webhook Twilio pointe vers `/twilio/twiml`.
2. Appeler le numero Twilio.
3. Observer en live:
   - `Calls`
   - `Transcripts`
   - `Reservations`
   - `Inventory` (coherence stock/prix)

## 5) Operations courantes

## 5.1 Redemarrer backend

```bash
pkill -f "uvicorn src.main:app" || true
cd /workspace/voice-agent-guestflow
nohup .venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &
```

## 5.2 Redemarrer frontend (corriger erreur webpack dev)

```bash
pkill -f "next dev --hostname 0.0.0.0 --port 3000" || true
cd /workspace/voice-agent-guestflow
rm -rf frontend/.next
nohup npm --prefix frontend run dev -- --hostname 0.0.0.0 --port 3000 > frontend_dev.log 2>&1 &
```

## 5.3 Verifier les processus

```bash
ps -ww -ef | grep -E "uvicorn|next dev|vllm" | grep -v grep
```

## 5.4 Verifier l'inventaire

```bash
curl http://127.0.0.1:8000/admin/live/inventory/rooms
curl "http://127.0.0.1:8000/admin/live/inventory/month?year=2026&month=3"
```

## 6) Depannage rapide

- Backend 404 sur nouvelle route -> redemarrer uvicorn.
- Frontend runtime error webpack -> nettoyer `frontend/.next` + restart frontend.
- Dashboard vide -> verifier backend `8000` et rewrites Next.
- Twilio sans son -> verifier credentials TTS/STT + logs backend.
- Reponses incoherentes prix/dispo -> verifier routes inventory et DB (`/admin/live/inventory/*`).

## 7) Sequence de lancement recommandee (resume)

```bash
# Terminal 1
cd /workspace/voice-agent-guestflow && bash scripts/start_backend.sh

# Terminal 2
cd /workspace/voice-agent-guestflow && bash scripts/start_frontend.sh

# Terminal 3 (optionnel)
cd /workspace/voice-agent-guestflow && bash scripts/logs_services.sh
```
