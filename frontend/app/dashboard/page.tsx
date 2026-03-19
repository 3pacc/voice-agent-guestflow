"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Period = "day" | "week" | "month";

type SummaryCards = {
  period: Period;
  calls_detected: number;
  successful_calls: number;
  events_total: number;
  confirmation_rate: number;
  abandonment_rate: number;
  avg_turns_before_confirmation: number;
  customer_satisfaction_post_call_pct: number;
};

type RevenueData = {
  day_eur: number;
  week_eur: number;
  month_eur: number;
  average_basket_eur: number;
};

type UsageItem = { day: string; calls: number };
type UsageData = { period: Period; items: UsageItem[] };

type MetricBar = { key: string; label: string; value: number; unit: string };
type ConversionData = { period: Period; bars: MetricBar[] };

type AvailabilityItem = { date: string; availability: Record<string, number> };
type AvailabilityData = { year: number; month: number; room_types: string[]; items: AvailabilityItem[] };

type SuccessCallItem = {
  call_sid: string;
  timestamp: string;
  phone_number?: string | null;
  reservation_ref?: string | null;
  room_type?: string | null;
  guests?: number | null;
  nights?: number | null;
  price_total_eur?: number | null;
  status: string;
  sms_status?: string | null;
  satisfaction: "satisfait" | "insatisfait";
};

type SuccessCallsData = { period: Period; items: SuccessCallItem[] };

const PERIOD_OPTIONS: { key: Period; label: string }[] = [
  { key: "day", label: "Jour" },
  { key: "week", label: "Semaine" },
  { key: "month", label: "Mois" },
];

const ROOM_COLORS = ["#69a4ff", "#9b7bff", "#3fd7a3", "#ffb76b", "#5cd0ff", "#ff7aa2"];

function euro(value: number): string {
  return `${Math.round(value)} EUR`;
}

function formatDayLabel(iso: string): string {
  return iso ? iso.slice(5) : "";
}

export default function DashboardPage() {
  const [period, setPeriod] = useState<Period>("week");
  const [summary, setSummary] = useState<SummaryCards | null>(null);
  const [revenue, setRevenue] = useState<RevenueData | null>(null);
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [conversion, setConversion] = useState<ConversionData | null>(null);
  const [availability, setAvailability] = useState<AvailabilityData | null>(null);
  const [successCalls, setSuccessCalls] = useState<SuccessCallsData | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const now = new Date();
        const year = now.getFullYear();
        const month = now.getMonth() + 1;

        const [s, r, u, c, av, sc] = await Promise.all([
          fetch(`/admin/live/dashboard/summary-cards?period=${period}`, { cache: "no-store" }).then((x) => x.json()),
          fetch(`/admin/live/dashboard/revenue`, { cache: "no-store" }).then((x) => x.json()),
          fetch(`/admin/live/dashboard/usage?period=${period}`, { cache: "no-store" }).then((x) => x.json()),
          fetch(`/admin/live/dashboard/conversion-metrics?period=${period}`, { cache: "no-store" }).then((x) => x.json()),
          fetch(`/admin/live/inventory/month?year=${year}&month=${month}`, { cache: "no-store" }).then((x) => x.json()),
          fetch(`/admin/live/dashboard/success-calls?period=${period}&limit=20`, { cache: "no-store" }).then((x) => x.json()),
        ]);

        setSummary(s);
        setRevenue(r);
        setUsage(u);
        setConversion(c);
        setAvailability(av);
        setSuccessCalls(sc);
        setErr("");
      } catch {
        setErr("Connexion API impossible. Verifie le backend (8000).");
      }
    };

    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [period]);

  const selectedRevenue = useMemo(() => {
    if (!revenue) return 0;
    if (period === "day") return revenue.day_eur;
    if (period === "week") return revenue.week_eur;
    return revenue.month_eur;
  }, [period, revenue]);

  const usageData = useMemo(() => {
    return (usage?.items ?? []).map((it) => ({
      label: formatDayLabel(it.day),
      fullDate: it.day,
      calls: it.calls,
    }));
  }, [usage]);

  const availabilityDonutData = useMemo(() => {
    if (!availability) return [];
    const todayIso = new Date().toISOString().slice(0, 10);
    const upcoming = (availability.items ?? []).filter((it) => it.date >= todayIso);

    let sliced = upcoming;
    if (period === "day") sliced = upcoming.slice(0, 1);
    if (period === "week") sliced = upcoming.slice(0, 7);

    if (!sliced.length) return [];

    const days = Math.max(1, sliced.length);
    return (availability.room_types ?? []).map((roomType) => {
      const total = sliced.reduce((acc, day) => acc + Number(day.availability?.[roomType] ?? 0), 0);
      return {
        name: roomType,
        value: Math.round((total / days) * 10) / 10,
      };
    });
  }, [availability, period]);

  const smsRate = useMemo(() => {
    const sms = (conversion?.bars ?? []).find((b) => b.key === "sms_success_rate");
    return Number(sms?.value ?? 0);
  }, [conversion]);

  const centralKpiData = useMemo(
    () => [
      { name: "Confirmation", value: Number(summary?.confirmation_rate ?? 0), fill: "#69a4ff" },
      { name: "Satisfaction post-appel", value: Number(summary?.customer_satisfaction_post_call_pct ?? 0), fill: "#3fd7a3" },
      { name: "SMS delivres", value: smsRate, fill: "#5cd0ff" },
      { name: "Abandon", value: Number(summary?.abandonment_rate ?? 0), fill: "#9b7bff" },
    ],
    [summary, smsRate],
  );

  return (
    <>
      <div className="row" style={{ marginBottom: 8 }}>
        <div>
          <h1 className="page-title">Centre de pilotage hotelier</h1>
          <p className="page-sub">Suivi en temps reel des appels, de la conversion commerciale et de la performance de reservation.</p>
        </div>
        <span className="badge">Live</span>
      </div>

      <div className="period-filter-row">
        {PERIOD_OPTIONS.map((opt) => (
          <button
            key={opt.key}
            type="button"
            className={`period-btn ${period === opt.key ? "period-btn-active" : ""}`}
            onClick={() => setPeriod(opt.key)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {err ? <div className="error">{err}</div> : null}

      <div className="grid">
        <div className="card"><div className="kpi-label">Appels detectes</div><div className="kpi-value">{summary?.calls_detected ?? 0}</div></div>
        <div className="card"><div className="kpi-label">Reservations confirmees + SMS</div><div className="kpi-value">{summary?.successful_calls ?? 0}</div></div>
        <div className="card"><div className="kpi-label">Taux de confirmation</div><div className="kpi-value">{summary?.confirmation_rate ?? 0}%</div></div>
        <div className="card"><div className="kpi-label">Revenu confirme</div><div className="kpi-value">{euro(selectedRevenue)}</div></div>
      </div>

      <div className="card usage-chart-card" style={{ marginTop: 14 }}>
        <div className="row"><div className="card-title">Activite quotidienne de l agent</div><span className="badge">{period}</span></div>
        <div className="small" style={{ marginBottom: 8 }}>Survol pour afficher la date precise et le volume d appels.</div>
        <div className="chart-box-horizontal" style={{ height: 280 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={usageData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="usageFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#69a4ff" stopOpacity={0.6} />
                  <stop offset="100%" stopColor="#69a4ff" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
              <XAxis dataKey="label" tick={{ fill: "var(--muted)", fontSize: 11 }} minTickGap={16} />
              <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }} allowDecimals={false} width={28} />
              <Tooltip
                contentStyle={{ background: "var(--tooltip-bg)", border: "1px solid var(--tooltip-border)", borderRadius: 10, color: "var(--tooltip-text)" }}
                labelStyle={{ color: "var(--tooltip-text)", fontWeight: 600 }}
                itemStyle={{ color: "var(--tooltip-text)" }}
                formatter={(v) => [`${Number(v ?? 0)} appel(s)`, "Activite"]}
                labelFormatter={(_, payload) => {
                  const entry = payload?.[0]?.payload as { fullDate?: string } | undefined;
                  return entry?.fullDate ? `Date: ${entry.fullDate}` : "Date";
                }}
              />
              <Area type="monotone" dataKey="calls" stroke="#86b5ff" fill="url(#usageFill)" strokeWidth={2.4} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid" style={{ marginTop: 14 }}>
        <div className="card usage-chart-card">
          <div className="row"><div className="card-title">Disponibilite moyenne par categorie</div><span className="badge">{period}</span></div>
          <div className="small" style={{ marginBottom: 8 }}>Moyenne des chambres disponibles sur la periode selectionnee.</div>
          <div className="chart-box-horizontal">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Tooltip
                  contentStyle={{ background: "var(--tooltip-bg)", border: "1px solid var(--tooltip-border)", borderRadius: 10, color: "var(--tooltip-text)" }}
                  labelStyle={{ color: "var(--tooltip-text)", fontWeight: 600 }}
                  itemStyle={{ color: "var(--tooltip-text)" }}
                  formatter={(v, n) => [`${Number(v ?? 0)} chambres`, String(n)]}
                />
                <Pie
                  data={availabilityDonutData}
                  dataKey="value"
                  nameKey="name"
                  cx="35%"
                  cy="50%"
                  innerRadius={58}
                  outerRadius={98}
                  paddingAngle={2}
                  label={({ name, value }) => `${name}: ${value}`}
                  labelLine={false}
                >
                  {availabilityDonutData.map((entry, idx) => (
                    <Cell key={entry.name} fill={ROOM_COLORS[idx % ROOM_COLORS.length]} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card kpi-central-card">
          <div className="row"><div className="card-title">Indicateurs de performance consolides</div><span className="badge">{period}</span></div>
          <div className="small" style={{ marginBottom: 8 }}>
            Vue centralisee des KPI conversion et qualite. Tours moyens avant confirmation: <strong>{summary?.avg_turns_before_confirmation ?? 0}</strong>
          </div>
          <div className="chart-box-horizontal" style={{ height: 250 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={centralKpiData} margin={{ top: 8, right: 18, left: 8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                <XAxis dataKey="name" tick={{ fill: "var(--text)", fontSize: 12 }} />
                <YAxis type="number" domain={[0, 100]} tick={{ fill: "var(--muted)", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "var(--tooltip-bg)", border: "1px solid var(--tooltip-border)", borderRadius: 10, color: "var(--tooltip-text)" }}
                  labelStyle={{ color: "var(--tooltip-text)", fontWeight: 600 }}
                  itemStyle={{ color: "var(--tooltip-text)" }}
                  formatter={(v) => [`${Number(v ?? 0)}%`, "Valeur"]}
                />
                <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                  {centralKpiData.map((entry) => (
                    <Cell key={entry.name} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="card card-scroll dashboard-success-card" style={{ marginTop: 14 }}>
        <div className="row"><div className="card-title">Synthese des appels aboutis</div><span className="badge">Reservations</span></div>
        <div className="list dashboard-success-list">
          {(successCalls?.items ?? []).map((it) => (
            <div className="item" key={`${it.call_sid}-${it.timestamp}`}>
              <div className="row">
                <div className="small"><span className="mono">{it.phone_number || "numero inconnu"}</span> - {it.timestamp}</div>
                <span className="badge">{it.status}</span>
              </div>
              <div style={{ marginTop: 6 }}>
                <strong>{it.room_type || "standard"}</strong> - {it.guests ?? "?"} pers - {it.nights ?? "?"} nuit(s) - {euro(Number(it.price_total_eur ?? 0))}
              </div>
              <div className="small" style={{ marginTop: 4 }}>
                Ref: {it.reservation_ref || "N/A"} - SMS: {it.sms_status || "N/A"} - Satisfaction: {it.satisfaction}
              </div>
            </div>
          ))}
          {(successCalls?.items ?? []).length === 0 ? <div className="small">Aucun appel confirme + SMS sur cette periode.</div> : null}
        </div>
      </div>
    </>
  );
}
