"use client";

import { useEffect, useState } from "react";

type Reservation = {
  id: number;
  reservation_ref: string;
  call_sid: string;
  room_type: string;
  guests: number;
  check_in_date: string;
  check_out_date: string;
  nights: number;
  sms_sent: boolean;
  sms_status: string;
  created_at: string;
};

export default function ReservationsPage() {
  const [items, setItems] = useState<Reservation[]>([]);
  const [err, setErr] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const json = await fetch('/admin/live/reservations').then(r => r.json());
        setItems(json.items ?? []);
        setErr('');
      } catch {
        setErr('Impossible de charger les reservations.');
      }
    };
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <>
      <h1 className="page-title">Reservations</h1>
      <p className="page-sub">Reservations confirmees apres validation client.</p>
      {err ? <div className="error">{err}</div> : null}
      <div className="card">
        <div className="row"><strong>Historique reservations</strong><span className="badge">{items.length}</span></div>
        <div className="list">
          {items.map((r) => (
            <div key={r.id} className="item">
              <div className="row">
                <div><strong>{r.reservation_ref || '(sans ref)'}</strong> <span className="badge">{r.room_type || 'standard'}</span></div>
                <span className="small">{r.created_at}</span>
              </div>
              <div className="small">{r.check_in_date} {'->'} {r.check_out_date} | {r.nights || 0} nuit(s) | {r.guests || 0} pers.</div>
              <div className="small mono">call: {r.call_sid || '(unknown)'} | sms: {r.sms_sent ? 'envoye' : 'non'} ({r.sms_status || '-'})</div>
            </div>
          ))}
          {items.length === 0 ? <div className="small">Aucune reservation enregistree.</div> : null}
        </div>
      </div>
    </>
  );
}
