"use client";

import { useEffect, useState } from "react";

type AgentConfig = {
  voice_id: string;
  speaking_rate: number;
  greeting_text: string;
  offer_text: string;
  updated_at?: string;
};

const voices = ['Mathieu', '?tienne', 'Alex', 'Gabriel'];

export default function AgentPage() {
  const [cfg, setCfg] = useState<AgentConfig>({
    voice_id: 'Mathieu',
    speaking_rate: 1.2,
    greeting_text: "Bonjour et bienvenue chez GuestFlow Hotel, comment puis-je vous aider aujourd'hui ?",
    offer_text: 'Offre speciale: petit-dejeuner inclus selon disponibilite.',
  });
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  useEffect(() => {
    fetch('/admin/live/agent-config')
      .then(r => r.json())
      .then(data => setCfg(data))
      .catch(() => setErr('Impossible de charger la configuration agent.'));
  }, []);

  const save = async () => {
    try {
      const res = await fetch('/admin/live/agent-config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cfg),
      });
      const updated = await res.json();
      setCfg(updated);
      setMsg('Configuration sauvegardee.');
      setErr('');
    } catch {
      setErr('Echec sauvegarde configuration agent.');
      setMsg('');
    }
  };

  return (
    <>
      <h1 className="page-title">Agent Config</h1>
      <p className="page-sub">Configuration non technique: voix, vitesse, accroche, offre.</p>
      {err ? <div className="error">{err}</div> : null}
      {msg ? <div className="ok small">{msg}</div> : null}

      <div className="grid">
        <div className="card stack">
          <label className="small">Voix Inworld</label>
          <select value={cfg.voice_id} onChange={(e) => setCfg({ ...cfg, voice_id: e.target.value })}>
            {voices.map(v => <option key={v} value={v}>{v}</option>)}
          </select>

          <label className="small">Vitesse de parole: {cfg.speaking_rate}</label>
          <input type="range" min="0.8" max="1.5" step="0.05" value={cfg.speaking_rate}
            onChange={(e) => setCfg({ ...cfg, speaking_rate: Number(e.target.value) })} />

          <label className="small">Phrase d'accroche</label>
          <textarea rows={3} value={cfg.greeting_text} onChange={(e) => setCfg({ ...cfg, greeting_text: e.target.value })} />

          <label className="small">Proposition d'offre</label>
          <textarea rows={3} value={cfg.offer_text} onChange={(e) => setCfg({ ...cfg, offer_text: e.target.value })} />

          <button onClick={save}>Sauvegarder</button>
          <div className="small">Maj: {cfg.updated_at || '-'}</div>
        </div>

        <div className="card">
          <h3>Apercu agent</h3>
          <p className="small">Voix: <strong>{cfg.voice_id}</strong> | Vitesse: <strong>{cfg.speaking_rate}</strong></p>
          <p><span className="badge">Accroche</span> {cfg.greeting_text}</p>
          <p><span className="badge">Offre</span> {cfg.offer_text}</p>
        </div>
      </div>
    </>
  );
}
