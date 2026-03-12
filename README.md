# 🛎️ guestFlow-agent

**guestFlow-agent** est un Agent Vocal IA de réservation hôtelière 100% Cloud, conçu pour offrir une expérience conversationnelle téléphonique avec une latence quasi-nulle. Il est capable de gérer les réservations de bout en bout, de vérifier la disponibilité des chambres et de répondre aux questions sur les politiques de l'hôtel.

## 🌟 Fonctionnalités Clés

- **Téléphonie Temps Réel** : Intégration via Twilio WebSockets pour du streaming audio bidirectionnel (Mulaw 8KHz).
- **Transcription Ultra-Rapide (STT)** : Utilisation de l'API Mistral Voxtral Realtime pour une transcription précise et immédiate.
- **Synthèse Vocale Haute Fidélité (TTS)** : Intégration de Cartesia Sonic pour une voix naturelle, expressive et fluide.
- **Cerveau LLM Performant** : Propulsé par Llama 3.1 (8B/70B) via une instance vLLM auto-hébergée.
- **Logique de Réservation par Graphe** : Orchestration robuste du flux conversationnel (Salutations > Dates > Disponibilité > Confirmation) grâce à LangGraph.
- **Interruption Native (Barge-in)** : Gestion de l'interruption vocale (VAD) via FastRTC, permettant à l'utilisateur de couper la parole à l'agent naturellement.
- **RAG & Données** : Intégration (mock) avec Superlinked pour les politiques de l'hôtel et SQLAlchemy pour la gestion de l'inventaire des chambres en temps réel.
- **Déploiement Optimisé GPU** : Prêt pour la production sur RunPod avec des configurations Docker adaptées pour vLLM.

## 🏗️ Architecture Technique

Le projet suit une architecture modulaire :

```text
guestFlow-agent/
├── src/
│   ├── main.py                # Point d'entrée FastAPI
│   ├── api/twilio.py          # WebSocket Twilio pour le flux audio
│   ├── agent/                 # LangGraph & FastRTC Orchestrator
│   │   ├── booking_graph.py   # Flux de réservation (Check-in, Check-out, etc.)
│   │   └── orchestrator.py    # Gestion STT -> LLM -> TTS + VAD
│   ├── llm/vllm_client.py     # Client Llama 3.1 vLLM
│   ├── stt/mistral_stt.py     # Client Mistral Voxtral STT
│   ├── tts/cartesia_tts.py    # Client Cartesia Sonic TTS
│   ├── db/                    # Base de données & RAG
│   │   ├── sql_stock.py       # SQL (Stocks de chambres)
│   │   └── policy_rag.py      # Base de connaissances Superlinked
│   └── config/settings.py     # Gestion des variables d'environnement
├── scripts/
│   └── deploy_runpod.py       # Script de déploiement d'instance
├── docker-compose.yml         # Stack RunPod (vLLM + FastAPI)
└── pyproject.toml             # Dépendances (FastAPI, LangGraph, vLLM, etc.)
```

## 🚀 Prérequis

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommandé) ou `pip` pour l'installation des dépendances.
- Un numéro de téléphone [Twilio](https://www.twilio.com/).
- Des clés API pour les services suivants :
  - **Mistral AI** (STT)
  - **Cartesia** (TTS)
  - **RunPod** (Pour le déploiement)

## 🛠️ Installation et Exécution Locale

1. **Cloner le projet ou se placer dans le répertoire :**
   ```bash
   cd guestFlow-agent
   ```

2. **Installer les dépendances :**
   ```bash
   # Utilisation de uv (très rapide)
   uv pip install -e .
   ```

3. **Configurer les variables d'environnement :**
   Copiez `.env.example` en `.env` et remplissez vos clés API.
   ```bash
   cp .env.example .env
   ```

4. **Initialiser la base de données (Mock) :**
   ```bash
   python src/db/sql_stock.py
   ```

5. **Lancer le serveur FastAPI :**
   ```bash
   fastapi run src/main.py
   ```

6. **Exposer le serveur local (pour Twilio) :**
   Utilisez [ngrok](https://ngrok.com/) pour exposer le port 8000.
   ```bash
   ngrok http 8000
   ```
   *Mettez ensuite à jour l'URL du Webhook Twilio avec l'adresse fournie par ngrok (`https://<votre-ngrok>/twilio/twiml`).*

## 🐳 Déploiement en Production (RunPod)

L'agent est conçu pour tourner sur une instance GPU pour garantir d'excellentes performances d'inférence (vLLM).

1. Vérifiez que votre `.env` contient la clé `RUNPOD_API_KEY`.
2. Lancez le script de déploiement automatisé :
   ```bash
   python scripts/deploy_runpod.py
   ```
   Ce script créera un Pod utilisant le `docker-compose.yml` fourni (ou l'image Docker spécifiée) avec l'allocation GPU (ex: RTX 4090).

## 🧪 Tests

Lancez les tests unitaires pour valider la logique du graphe conversationnel LangGraph :

```bash
pytest tests/
```

## 📄 Licence

Ce projet a été généré dans le cadre d'un PoC d'Agent Vocal IA Cloud.
