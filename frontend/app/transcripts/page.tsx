"use client";

import { useEffect, useState } from "react";

type TranscriptItem = { id: number; call_sid: string; speaker: string; text: string; created_at: string };

export default function TranscriptsPage() {
  const [items, setItems] = useState<TranscriptItem[]>([]);
  const [err, setErr] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const json = await fetch('/admin/live/transcripts').then(r => r.json());
        setItems(json.items ?? []);
        setErr('');
      } catch {
        setErr('Impossible de charger les transcriptions.');
      }
    };
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <>
      <h1 className="page-title">Transcripts Live</h1>
      <p className="page-sub">Lecture chronologique user/agent pendant l'appel.</p>
      {err ? <div className="error">{err}</div> : null}
      <div className="card">
        <div className="row"><strong>Flux transcription</strong><span className="badge">{items.length}</span></div>
        <div className="list">
          {items.map((t) => (
            <div className="item" key={t.id}>
              <div className="small">{t.created_at} - <span className="mono">{t.call_sid || '(unknown)'}</span></div>
              <div style={{ marginTop: 4 }}><span className="badge">{t.speaker}</span> {t.text}</div>
            </div>
          ))}
          {items.length === 0 ? <div className="small">Aucune transcription pour l'instant.</div> : null}
        </div>
      </div>
    </>
  );
}
