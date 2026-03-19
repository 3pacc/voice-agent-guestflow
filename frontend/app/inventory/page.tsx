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

type InventoryCard = {
  roomType: string;
  availableNow: number;
  averageMonth: number;
  minMonth: number;
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
        setErr("Impossible de charger l inventaire.");
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

  const deleteCategory = async (roomType: string) => {
    if (!confirm(`Supprimer la categorie "${roomType}" ? Les donnees de stock restent mais elle ne sera plus proposee.`)) return;
    try {
      const res = await fetch(`/admin/live/inventory/rooms/${encodeURIComponent(roomType)}`, { method: "DELETE" });
      const data = await res.json();
      if (data.items) setRooms(data.items);
      setMsg("Categorie supprimee.");
      setErr("");
      await loadMonth();
    } catch {
      setErr("Echec suppression.");
    }
  };

  const toggleBlock = async (r: RoomConf) => {
    const nextActive = !r.is_active;
    try {
      const res = await fetch(`/admin/live/inventory/rooms/${encodeURIComponent(r.room_type)}?is_active=${nextActive}`, { method: "PATCH" });
      const data = await res.json();
      if (data.items) setRooms(data.items);
      setMsg(nextActive ? "Categorie reactivee." : "Categorie bloquee (indisponible).");
      setErr("");
      await loadMonth();
    } catch {
      setErr("Echec mise a jour statut.");
    }
  };

  const inventoryCards = useMemo<InventoryCard[]>(() => {
    if (!roomTypes.length || !monthRows.length) return [];

    const todayIso = new Date().toISOString().slice(0, 10);
    const targetRow = monthRows.find((row) => row.date >= todayIso) ?? monthRows[monthRows.length - 1];

    return roomTypes.map((rt) => {
      const values = monthRows.map((row) => Number(row.availability?.[rt] ?? 0));
      const sum = values.reduce((acc, n) => acc + n, 0);
      return {
        roomType: rt,
        availableNow: Number(targetRow?.availability?.[rt] ?? 0),
        averageMonth: Math.round((sum / Math.max(1, values.length)) * 10) / 10,
        minMonth: values.length ? Math.min(...values) : 0,
      };
    });
  }, [monthRows, roomTypes]);

  return (
    <>
      <h1 className="page-title">Gestion de l inventaire hotelier</h1>
      <p className="page-sub">Configuration des categories de chambres et supervision des disponibilites par categorie.</p>

      {msg ? <div className="ok small">{msg}</div> : null}
      {err ? <div className="error">{err}</div> : null}

      <div className="grid" style={{ marginBottom: 14 }}>
        <div className="card stack">
          <div className="card-title">Configuration des categories</div>
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
            <button onClick={saveRoom}>Enregistrer</button>
            <button onClick={seedHorizon}>Recharger horizon</button>
          </div>
        </div>

        <div className="card card-scroll">
          <div className="row"><div className="card-title">Catalogue des categories</div><span className="badge">{rooms.length}</span></div>
          <div className="list">
            {rooms.map((r) => (
              <div key={r.room_type} className="item inventory-catalog-item">
                <div className="row" style={{ alignItems: "flex-start" }}>
                  <div style={{ flex: 1, cursor: "pointer" }} onClick={() => setForm(r)}>
                    <strong>{r.room_type}</strong>
                    <span className="badge" style={{ marginLeft: 8 }}>{r.is_active ? "actif" : "bloque"}</span>
                    <div className="small" style={{ marginTop: 4 }}>Capacite: {r.capacity} - Prix: {r.price_eur} EUR - Stock/jour: {r.rooms_per_day}</div>
                  </div>
                  <div className="inventory-item-actions" onClick={(e) => e.stopPropagation()}>
                    <button type="button" className="btn-small" onClick={() => toggleBlock(r)} title={r.is_active ? "Bloquer (indisponible)" : "Activer"}>
                      {r.is_active ? "Bloquer" : "Activer"}
                    </button>
                    <button type="button" className="btn-small btn-danger" onClick={() => deleteCategory(r.room_type)} title="Supprimer la categorie">
                      Supprimer
                    </button>
                  </div>
                </div>
              </div>
            ))}
            {rooms.length === 0 ? <div className="small">Aucune categorie configuree.</div> : null}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ marginBottom: 10 }}>
          <div className="card-title">Disponibilite actuelle par categorie</div>
          <div style={{ display: "flex", gap: 8 }}>
            <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} style={{ width: 90 }} />
            <input type="number" min={1} max={12} value={month} onChange={(e) => setMonth(Number(e.target.value))} style={{ width: 70 }} />
          </div>
        </div>

        <div className="inventory-kpi-grid">
          {inventoryCards.map((c) => (
            <div key={c.roomType} className="inventory-kpi-card">
              <div className="inventory-kpi-title">{c.roomType}</div>
              <div className="inventory-kpi-value">{c.availableNow}</div>
              <div className="small">chambres disponibles (date cible)</div>
              <div className="small" style={{ marginTop: 6 }}>Moyenne mois: {c.averageMonth} - Min mois: {c.minMonth}</div>
            </div>
          ))}
          {inventoryCards.length === 0 ? <div className="small">Aucune donnee de disponibilite pour la periode selectionnee.</div> : null}
        </div>
      </div>
    </>
  );
}
