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

function smsLabel(sent: boolean, status?: string) {
  if (!sent) return "SMS non envoye";
  if (!status) return "SMS envoye";
  if (String(status).startsWith("20")) return `SMS envoye (code ${status})`;
  return `SMS en erreur (code ${status})`;
}

export default function ReservationsPage() {
  const [items, setItems] = useState<Reservation[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const json = await fetch("/admin/live/reservations").then((r) => r.json());
        setItems(json.items ?? []);
        setErr("");
      } catch {
        setErr("Impossible de charger les reservations.");
      }
    };
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <>
      <h1 className="page-title">Reservations</h1>
      <p className="page-sub">Historique des reservations confirmees et statut de finalisation SMS.</p>
      {err ? <div className="error">{err}</div> : null}
      <div className="card card-scroll">
        <div className="row"><div className="card-title">Historique reservations</div><span className="badge">{items.length}</span></div>
        <div className="list">
          {items.map((r) => (
            <div key={r.id} className="item reservation-human-card">
              <div className="row">
                <div><strong>{r.reservation_ref || "(sans ref)"}</strong> <span className="badge">{r.room_type || "standard"}</span></div>
                <span className="small">{r.created_at}</span>
              </div>
              <div className="small" style={{ marginTop: 4 }}>
                Sejour: <strong>{r.check_in_date}</strong> au <strong>{r.check_out_date}</strong> - {r.nights || 0} nuit(s) - {r.guests || 0} pers.
              </div>
              <div className="small" style={{ marginTop: 4 }}>
                {smsLabel(r.sms_sent, r.sms_status)}
              </div>
              <div className="small mono" style={{ marginTop: 4 }}>
                Appel: {r.call_sid || "(unknown)"}
              </div>
            </div>
          ))}
          {items.length === 0 ? <div className="small">Aucune reservation enregistree.</div> : null}
        </div>
      </div>
    </>
  );
}
