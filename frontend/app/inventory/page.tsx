"use client";

import { useEffect, useMemo, useState } from "react";

type RoomConf = {
  room_type: string;
  capacity: number;
  price_eur: number;
  rooms_per_day: number;
  is_active: boolean;
  updated_at?: string | null;
};

type MonthRow = {
  date: string;
  availability: Record<string, number>;
};

export default function InventoryPage() {
  const today = new Date();
  const [rooms, setRooms] = useState<RoomConf[]>([]);
  const [monthRows, setMonthRows] = useState<MonthRow[]>([]);
  const [roomTypes, setRoomTypes] = useState<string[]>([]);
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [form, setForm] = useState<RoomConf>({
    room_type: "standard",
    capacity: 2,
    price_eur: 80,
    rooms_per_day: 10,
    is_active: true,
  });
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const monthKey = useMemo(() => `${year}-${month}`, [year, month]);

  const loadRooms = async () => {
    const json = await fetch("/admin/live/inventory/rooms").then((r) => r.json());
    setRooms(json.items ?? []);
  };

  const loadMonth = async () => {
    const json = await fetch(`/admin/live/inventory/month?year=${year}&month=${month}`).then((r) => r.json());
    setMonthRows(json.items ?? []);
    setRoomTypes(json.room_types ?? []);
  };

  useEffect(() => {
    const load = async () => {
      try {
        await Promise.all([loadRooms(), loadMonth()]);
        setErr("");
      } catch {
        setErr("Impossible de charger l'inventaire.");
      }
    };
    load();
  }, [monthKey]);

  const saveRoom = async () => {
    try {
      await fetch("/admin/live/inventory/rooms", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setMsg("Configuration chambre sauvegardee.");
      setErr("");
      await Promise.all([loadRooms(), loadMonth()]);
    } catch {
      setErr("Echec de sauvegarde.");
    }
  };

  const seedHorizon = async () => {
    try {
      await fetch("/admin/live/inventory/seed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days: 180 }),
      });
      setMsg("Stock recharge sur 180 jours.");
      await loadMonth();
    } catch {
      setErr("Echec de recharge du stock.");
    }
  };

  return (
    <>
      <h1 className="page-title">Inventaire Hotel</h1>
      <p className="page-sub">Types de chambres, capacite, prix, et disponibilite mensuelle.</p>

      {msg ? <div className="ok small">{msg}</div> : null}
      {err ? <div className="error">{err}</div> : null}

      <div className="grid" style={{ marginBottom: 14 }}>
        <div className="card stack">
          <div className="row"><strong>Configurer un type</strong><span className="badge">DB</span></div>
          <label className="small">Type de chambre</label>
          <input value={form.room_type} onChange={(e) => setForm({ ...form, room_type: e.target.value.toLowerCase().trim() })} />

          <label className="small">Capacite (personnes)</label>
          <input type="number" min={1} value={form.capacity} onChange={(e) => setForm({ ...form, capacity: Number(e.target.value) })} />

          <label className="small">Prix par nuit (EUR)</label>
          <input type="number" min={1} value={form.price_eur} onChange={(e) => setForm({ ...form, price_eur: Number(e.target.value) })} />

          <label className="small">Stock par jour (nombre de chambres)</label>
          <input type="number" min={0} value={form.rooms_per_day} onChange={(e) => setForm({ ...form, rooms_per_day: Number(e.target.value) })} />

          <label className="small" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            Actif
          </label>

          <div className="row" style={{ gap: 8 }}>
            <button onClick={saveRoom}>Sauvegarder</button>
            <button onClick={seedHorizon}>Recharger horizon</button>
          </div>
        </div>

        <div className="card">
          <div className="row"><strong>Catalogue actuel</strong><span className="badge">{rooms.length}</span></div>
          <div className="list">
            {rooms.map((r) => (
              <div className="item" key={r.room_type} style={{ cursor: "pointer" }} onClick={() => setForm(r)}>
                <div className="row">
                  <strong>{r.room_type}</strong>
                  <span className="badge">{r.is_active ? "actif" : "off"}</span>
                </div>
                <div className="small">Cap: {r.capacity} - Prix: {r.price_eur} EUR - Stock/jour: {r.rooms_per_day}</div>
              </div>
            ))}
            {rooms.length === 0 ? <div className="small">Aucun type configure.</div> : null}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ marginBottom: 10 }}>
          <strong>Disponibilite mensuelle</strong>
          <div style={{ display: "flex", gap: 8 }}>
            <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} style={{ width: 90 }} />
            <input type="number" min={1} max={12} value={month} onChange={(e) => setMonth(Number(e.target.value))} style={{ width: 70 }} />
          </div>
        </div>

        <div style={{ overflow: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                {roomTypes.map((rt) => <th key={rt}>{rt}</th>)}
              </tr>
            </thead>
            <tbody>
              {monthRows.map((row) => (
                <tr key={row.date}>
                  <td className="mono">{row.date}</td>
                  {roomTypes.map((rt) => <td key={`${row.date}-${rt}`}>{row.availability?.[rt] ?? 0}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
