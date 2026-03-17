"use client";

import { useEffect, useMemo, useState } from "react";

type CallItem = { call_sid: string; last_seen: string; events: number };
type TranscriptItem = { id: number; speaker: string; text: string; created_at: string };

function Donut({ value, total, label, tone = "#5ea2ff" }: { value: number; total: number; label: string; tone?: string }) {
  const safeTotal = Math.max(total, 1);
  const pct = Math.max(0, Math.min(100, (value / safeTotal) * 100));
  const style = { background: `conic-gradient(${tone} ${pct}%, #263b75 ${pct}% 100%)` } as React.CSSProperties;
  return (
    <div className="donut-wrap">
      <div className="donut" style={style}>
        <div className="donut-hole">{Math.round(pct)}%</div>
      </div>
      <div className="small">{label}</div>
    </div>
  );
}

function Sparkline({ points }: { points: number[] }) {
  const width = 280;
  const height = 88;
  if (!points.length) return <div className="small">Pas assez de donnees.</div>;
  const max = Math.max(...points, 1);
  const step = points.length > 1 ? width / (points.length - 1) : width;
  const path = points
    .map((p, i) => {
      const x = i * step;
      const y = height - (p / max) * height;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="sparkline" aria-hidden>
      <path d={path} fill="none" stroke="#8ab4ff" strokeWidth="2.5" />
    </svg>
  );
}

export default function DashboardPage() {
  const [calls, setCalls] = useState<CallItem[]>([]);
  const [transcripts, setTranscripts] = useState<TranscriptItem[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const [c, t] = await Promise.all([
          fetch("/admin/live/calls", { cache: "no-store" }).then((r) => r.json()),
          fetch("/admin/live/transcripts", { cache: "no-store" }).then((r) => r.json()),
        ]);
        setCalls(c.items ?? []);
        setTranscripts(t.items ?? []);
        setErr("");
      } catch {
        setErr("Connexion API impossible. Verifie le backend (8000).\n");
      }
    };
    load();
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, []);

  const metrics = useMemo(() => {
    const totalEvents = calls.reduce((a, b) => a + (b.events || 0), 0);
    const userTurns = transcripts.filter((t) => t.speaker === "user").length;
    const agentTurns = transcripts.filter((t) => t.speaker === "agent").length;
    const avgEvents = calls.length ? (totalEvents / calls.length).toFixed(1) : "0.0";

    const positive = ["merci", "parfait", "ok", "super", "bien", "excellent", "convient"];
    const negative = ["non", "probleme", "mauvais", "attendre", "dommage", "annuler"];
    const userTexts = transcripts.filter((t) => t.speaker === "user").map((t) => t.text.toLowerCase());
    const p = userTexts.reduce((acc, txt) => acc + positive.filter((w) => txt.includes(w)).length, 0);
    const n = userTexts.reduce((acc, txt) => acc + negative.filter((w) => txt.includes(w)).length, 0);
    const satisfaction = userTexts.length ? Math.max(30, Math.min(98, Math.round(((p + 1) / (p + n + 2)) * 100))) : 78;

    const eventBars = calls.slice(0, 6).map((c) => ({
      sid: c.call_sid?.slice(-6) || "------",
      events: c.events || 0,
    }));

    const turnSeries = transcripts
      .slice(0, 24)
      .reverse()
      .map((t, i) => (t.speaker === "agent" ? 2 : 1) + (i % 3 === 0 ? 0.1 : 0));

    return { totalEvents, userTurns, agentTurns, avgEvents, satisfaction, eventBars, turnSeries };
  }, [calls, transcripts]);

  const maxBar = Math.max(1, ...metrics.eventBars.map((b) => b.events));

  return (
    <>
      <div className="row" style={{ marginBottom: 8 }}>
        <div>
          <h1 className="page-title">Dashboard Live</h1>
          <p className="page-sub">Pilotage temps reel des appels, qualite conversationnelle et performance agent.</p>
        </div>
        <span className="badge">Live</span>
      </div>

      <div className="grid">
        <div className="card"><div className="kpi-label">Appels detectes</div><div className="kpi-value">{calls.length}</div></div>
        <div className="card"><div className="kpi-label">Evenements total</div><div className="kpi-value">{metrics.totalEvents}</div></div>
        <div className="card"><div className="kpi-label">Tours user / agent</div><div className="kpi-value">{metrics.userTurns} / {metrics.agentTurns}</div></div>
        <div className="card"><div className="kpi-label">Events / appel</div><div className="kpi-value">{metrics.avgEvents}</div></div>
      </div>

      {err ? <div className="error">{err}</div> : null}

      <div className="grid" style={{ marginTop: 14 }}>
        <div className="card">
          <div className="row"><strong>Satisfaction client (estimee)</strong><span className="badge">KPI</span></div>
          <div className="chart-row">
            <Donut value={metrics.satisfaction} total={100} label="Sentiment global" tone="#58d68d" />
            <Donut value={metrics.agentTurns} total={metrics.agentTurns + metrics.userTurns} label="Part de parole agent" tone="#7ea6ff" />
            <Donut value={metrics.userTurns} total={metrics.agentTurns + metrics.userTurns} label="Part de parole client" tone="#a78bfa" />
          </div>
        </div>

        <div className="card">
          <div className="row"><strong>Repartition events par appel</strong><span className="badge">Plot</span></div>
          <div className="bars">
            {metrics.eventBars.map((b) => (
              <div className="bar-row" key={b.sid}>
                <div className="mono small">...{b.sid}</div>
                <div className="bar-track"><div className="bar-fill" style={{ width: `${(b.events / maxBar) * 100}%` }} /></div>
                <div className="small">{b.events}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid" style={{ marginTop: 14 }}>
        <div className="card">
          <div className="row"><strong>Rythme conversationnel</strong><span className="badge">Trend</span></div>
          <Sparkline points={metrics.turnSeries} />
          <div className="small">1 = user, 2 = agent (sequence des derniers tours)</div>
        </div>

        <div className="card">
          <div className="row"><strong>Dernieres transcriptions</strong><span className="badge">Live</span></div>
          <div className="list">
            {transcripts.slice(0, 14).map((t) => (
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
