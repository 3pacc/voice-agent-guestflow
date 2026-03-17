"use client";

import { useEffect, useState } from "react";

type CallItem = { call_sid: string; last_seen: string; events: number };
type EventItem = { id: number; call_sid: string; event_type: string; created_at: string; payload: Record<string, unknown> };

export default function CallsPage() {
  const [calls, setCalls] = useState<CallItem[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [selected, setSelected] = useState('');
  const [err, setErr] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const callsJson = await fetch('/admin/live/calls').then(r => r.json());
        const items: CallItem[] = callsJson.items ?? [];
        setCalls(items);
        const sid = selected || items[0]?.call_sid || '';
        if (sid && sid !== selected) setSelected(sid);
        const q = sid ? `?call_sid=${encodeURIComponent(sid)}` : '';
        const eventsJson = await fetch(`/admin/live/events${q}`).then(r => r.json());
        setEvents(eventsJson.items ?? []);
        setErr('');
      } catch {
        setErr('Impossible de charger les donnees live.');
      }
    };
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [selected]);

  return (
    <>
      <h1 className="page-title">Calls Live</h1>
      <p className="page-sub">Suivi de session et timeline d'evenements en direct.</p>
      {err ? <div className="error">{err}</div> : null}

      <div className="grid">
        <div className="card">
          <div className="row"><strong>Sessions</strong><span className="badge">{calls.length}</span></div>
          <div className="list">
            {calls.map((c) => (
              <div className="item" key={c.call_sid + c.last_seen} onClick={() => setSelected(c.call_sid)} style={{cursor: 'pointer'}}>
                <div className="mono">{c.call_sid || '(unknown)'}</div>
                <div className="small">{c.last_seen}</div>
                <span className="badge">{c.events} events</span>
              </div>
            ))}
            {calls.length === 0 ? <div className="small">Aucune session pour le moment.</div> : null}
          </div>
        </div>

        <div className="card">
          <div className="row"><strong>Events {selected ? `(${selected})` : ''}</strong><span className="badge">{events.length}</span></div>
          <div className="list">
            {events.map((e) => (
              <div className="item" key={e.id}>
                <div className="row"><span className="badge">{e.event_type}</span><span className="small">{e.created_at}</span></div>
                <pre className="mono" style={{ whiteSpace: 'pre-wrap', margin: '8px 0 0' }}>{JSON.stringify(e.payload, null, 2)}</pre>
              </div>
            ))}
            {events.length === 0 ? <div className="small">Aucun event encore.</div> : null}
          </div>
        </div>
      </div>
    </>
  );
}
