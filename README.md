# guestFlow-agent

Agent vocal hotelier (Twilio + STT + LLM + TTS) avec dashboard admin live.

Ce README est optimise pour un usage **Runpod via SSH**.

## Structure du projet

- `src/` : backend FastAPI + logique agent vocal
- `frontend/` : dashboard admin Next.js
- `backend/` : manifests/dependances backend
- `scripts/` : scripts d'execution et d'exploitation

## Prerequis

- Runpod actif + acces SSH
- Python 3.11+
- Node.js + npm
- Environnement virtuel Python dans `.venv` (recommande)
- Fichier `.env` configure (Twilio, Mistral, Inworld, etc.)

## Demarrage rapide (Runpod)

Depuis le dossier projet sur le pod:

```bash
cd /workspace/voice-agent-guestflow
```

### 1) Backend API (port 8000)

```bash
bash scripts/start_backend.sh
```

### 2) Frontend Admin (port 3000)

Dans un autre terminal:

```bash
cd /workspace/voice-agent-guestflow
bash scripts/start_frontend.sh
```

### 3) Verification sante

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/admin/live/health
curl http://127.0.0.1:3000/dashboard
```

## Exploitation complete

Consultez le guide detaille:

- `scripts/README.md`

Il contient:

- preparation complete depuis zero
- lancement de chaque service
- usage ngrok
- test d'un appel live + dashboard
- endpoints de verification
- commandes de debug/restart

## Endpoints utiles

- API health: `GET /health`
- Admin live health: `GET /admin/live/health`
- Reservations: `GET /admin/live/reservations`
- Inventaire chambres: `GET /admin/live/inventory/rooms`
- Inventaire mensuel: `GET /admin/live/inventory/month`

## Notes importantes

- Si le frontend affiche une erreur runtime webpack en mode dev, redemarrer le serveur frontend et nettoyer `frontend/.next`.
- Si une nouvelle route backend est ajoutee, redemarrer uvicorn.
- Pour observer les logs backend/vLLM: `bash scripts/logs_services.sh`
