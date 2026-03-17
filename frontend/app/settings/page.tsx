"use client";

import { useEffect, useState } from "react";

type SettingsSummary = {
  voice_api_enabled: boolean;
  dashboard_enabled: boolean;
  sms_enabled: boolean;
  calls_events_count: number;
  transcripts_count: number;
  reservations_count: number;
  llm_model: string;
  updated_at: string;
};

export default function SettingsPage() {
  const [s, setS] = useState<SettingsSummary | null>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const json = await fetch('/admin/live/settings').then(r => r.json());
        setS(json);
        setErr('');
      } catch {
        setErr('Impossible de charger les settings.');
      }
    };
    load();
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, []);

  return (
    <>
      <h1 className="page-title">Settings</h1>
      <p className="page-sub">Sante plateforme, canaux actifs, et compteurs systeme.</p>
      {err ? <div className="error">{err}</div> : null}
      <div className="grid">
        <div className="card"><div className="kpi-label">Voice API</div><div className="kpi-value">{s?.voice_api_enabled ? 'ON' : 'OFF'}</div></div>
        <div className="card"><div className="kpi-label">Dashboard</div><div className="kpi-value">{s?.dashboard_enabled ? 'ON' : 'OFF'}</div></div>
        <div className="card"><div className="kpi-label">SMS</div><div className="kpi-value">{s?.sms_enabled ? 'ON' : 'OFF'}</div></div>
      </div>
      <div className="card" style={{marginTop:14}}>
        <div className="row"><strong>System Overview</strong><span className="badge">live</span></div>
        <div className="small">LLM model: <span className="mono">{s?.llm_model || '-'}</span></div>
        <div className="small">Events: {s?.calls_events_count ?? 0}</div>
        <div className="small">Transcripts: {s?.transcripts_count ?? 0}</div>
        <div className="small">Reservations: {s?.reservations_count ?? 0}</div>
        <div className="small">Updated: {s?.updated_at || '-'}</div>
      </div>
    </>
  );
}
