# Frontend Admin (Next.js)

Interface admin live (dashboard, reservations, calls, transcripts, agent, settings, inventory).

## Installation

```bash
cd /workspace/voice-agent-guestflow/frontend
npm install
```

## Lancement dev

```bash
cd /workspace/voice-agent-guestflow
bash scripts/start_frontend.sh
```

Ou manuellement:

```bash
cd /workspace/voice-agent-guestflow/frontend
npm run dev -- --hostname 0.0.0.0 --port 3000
```

## Pages principales

- `/dashboard`
- `/reservations`
- `/calls`
- `/transcripts`
- `/agent`
- `/settings`
- `/inventory`

## Notes

- Le frontend consomme l'API via les rewrites Next (`/admin/live/*`).
- Si erreur runtime webpack en mode dev:

```bash
cd /workspace/voice-agent-guestflow
rm -rf frontend/.next
pkill -f "next dev --hostname 0.0.0.0 --port 3000" || true
nohup npm --prefix frontend run dev -- --hostname 0.0.0.0 --port 3000 > frontend_dev.log 2>&1 &
```
