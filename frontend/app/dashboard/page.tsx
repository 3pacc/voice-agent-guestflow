"use client";

import { useEffect, useState } from "react";

type CallItem = { call_sid: string; last_seen: string; events: number };
type TranscriptItem = { id: number; speaker: string; text: string; created_at: string };

export default function DashboardPage() {
  const [calls, setCalls] = useState<CallItem[]>([]);
  const [transcripts, setTranscripts] = useState<TranscriptItem[]>([]);
  const [err, setErr] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const [c, t] = await Promise.all([
          fetch('/admin/live/calls').then(r => r.json()),
          fetch('/admin/live/transcripts').then(r => r.json()),
        ]);
        setCalls(c.items ?? []);
        setTranscripts(t.items ?? []);
        setErr('');
      } catch (e) {
        setErr('Connexion API impossible. Verifie le backend (8000).');
      }
    };
    load();
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, []);

  const totalEvents = calls.reduce((a, b) => a + (b.events || 0), 0);
  const userTurns = transcripts.filter(t => t.speaker === 'user').length;
  const agentTurns = transcripts.filter(t => t.speaker === 'agent').length;

  return (
    <>
      <h1 className="page-title">Dashboard Live</h1>
      <p className="page-sub">Vision temps reel des appels et conversations.</p>

      <div className="grid">
        <div className="card"><div className="kpi-label">Appels detectes</div><div className="kpi-value">{calls.length}</div></div>
        <div className="card"><div className="kpi-label">Evenements total</div><div className="kpi-value">{totalEvents}</div></div>
        <div className="card"><div className="kpi-label">Tours user</div><div className="kpi-value">{userTurns}</div></div>
        <div className="card"><div className="kpi-label">Tours agent</div><div className="kpi-value">{agentTurns}</div></div>
      </div>

      {err ? <div className="error">{err}</div> : null}

      <div className="grid" style={{marginTop: 14}}>
        <div className="card">
          <div className="row"><strong>Derniers appels</strong><span className="badge">live</span></div>
          <div className="list">
            {calls.map(c => (
              <div className="item" key={c.call_sid + c.last_seen}>
                <div className="mono">{c.call_sid || '(unknown)'}</div>
                <div className="small">{c.last_seen} - {c.events} events</div>
              </div>
            ))}
            {calls.length === 0 ? <div className="small">Aucun appel encore.</div> : null}
          </div>
        </div>

        <div className="card">
          <div className="row"><strong>Dernieres transcriptions</strong><span className="badge">live</span></div>
          <div className="list">
            {transcripts.slice(0, 30).map(t => (
              <div className="item" key={t.id}>
                <div><span className="badge">{t.speaker}</span> <span className="small">{t.created_at}</span></div>
                <div>{t.text}</div>
              </div>
            ))}
            {transcripts.length === 0 ? <div className="small">Pas encore de transcript.</div> : null}
          </div>
        </div>
      </div>
    </>
  );
}
