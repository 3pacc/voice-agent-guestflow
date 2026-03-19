"use client";

import { useEffect, useState } from "react";

type AgentConfig = {
  voice_id: string;
  speaking_rate: number;
  llm_temperature: number;
  greeting_text: string;
  offer_text: string;
  updated_at?: string;
};

const voices = ["Mathieu", "Etienne", "Alex", "Gabriel"];

export default function AgentPage() {
  const [cfg, setCfg] = useState<AgentConfig>({
    voice_id: "Mathieu",
    speaking_rate: 1.2,
    llm_temperature: 0.3,
    greeting_text: "Bonjour et bienvenue chez GuestFlow Hotel, comment puis-je vous aider aujourd'hui ?",
    offer_text: "Offre speciale: petit-dejeuner inclus selon disponibilite.",
  });
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch("/admin/live/agent-config")
      .then((r) => r.json())
      .then((data) => setCfg((prev) => ({ ...prev, ...data })))
      .catch(() => setErr("Impossible de charger la configuration agent."));
  }, []);

  const save = async () => {
    try {
      const res = await fetch("/admin/live/agent-config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cfg),
      });
      const updated = await res.json();
      setCfg((prev) => ({ ...prev, ...updated }));
      setMsg("Configuration enregistree avec succes.");
      setErr("");
    } catch {
      setErr("Echec de sauvegarde de la configuration agent.");
      setMsg("");
    }
  };

  return (
    <>
      <h1 className="page-title">Configuration de l agent vocal</h1>
      <p className="page-sub">Pilotage de la voix, du style de reponse et des messages d accueil/commercial.</p>
      {err ? <div className="error">{err}</div> : null}
      {msg ? <div className="ok small">{msg}</div> : null}

      <div className="grid">
        <div className="card stack">
          <div className="card-title">Parametres conversationnels</div>

          <label className="small">Voix TTS</label>
          <select value={cfg.voice_id} onChange={(e) => setCfg({ ...cfg, voice_id: e.target.value })}>
            {voices.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>

          <label className="small">Vitesse de parole: {cfg.speaking_rate.toFixed(2)}</label>
          <input
            type="range"
            min="0.8"
            max="1.5"
            step="0.05"
            value={cfg.speaking_rate}
            onChange={(e) => setCfg({ ...cfg, speaking_rate: Number(e.target.value) })}
          />

          <label className="small">Temperature LLM: {cfg.llm_temperature.toFixed(2)}</label>
          <input
            type="range"
            min="0.0"
            max="1.2"
            step="0.05"
            value={cfg.llm_temperature}
            onChange={(e) => setCfg({ ...cfg, llm_temperature: Number(e.target.value) })}
          />
          <div className="small">Bas = reponses plus stables. Haut = reponses plus creatives.</div>

          <label className="small">Message d accueil</label>
          <textarea rows={3} value={cfg.greeting_text} onChange={(e) => setCfg({ ...cfg, greeting_text: e.target.value })} />

          <label className="small">Proposition commerciale</label>
          <textarea rows={3} value={cfg.offer_text} onChange={(e) => setCfg({ ...cfg, offer_text: e.target.value })} />

          <button onClick={save}>Enregistrer la configuration</button>
          <div className="small">Derniere mise a jour: {cfg.updated_at || "-"}</div>
        </div>

        <div className="card">
          <div className="card-title">Apercu de comportement</div>
          <p className="small">
            Voix: <strong>{cfg.voice_id}</strong> | Vitesse: <strong>{cfg.speaking_rate.toFixed(2)}</strong> | Temperature: <strong>{cfg.llm_temperature.toFixed(2)}</strong>
          </p>
          <p>
            <span className="badge">Accueil</span> {cfg.greeting_text}
          </p>
          <p>
            <span className="badge">Offre</span> {cfg.offer_text}
          </p>
        </div>
      </div>
    </>
  );
}
