import React, { useMemo, useState } from "react";
import api from "../lib/api";

function StatCard({ label, value, tone = "neutral", hint = "" }) {
  const styles = {
    neutral: "bg-white/5 text-slate-100 ring-white/10",
    red: "bg-rose-500/10 text-rose-100 ring-rose-400/20",
    yellow: "bg-amber-500/10 text-amber-100 ring-amber-400/20",
    green: "bg-emerald-500/10 text-emerald-100 ring-emerald-400/20",
  };
  return (
    <div className={`rounded-3xl p-5 ring-1 ${styles[tone] || styles.neutral}`}>
      <div className="text-xs uppercase tracking-[0.24em] opacity-70">{label}</div>
      <div className="mt-3 text-3xl font-semibold">{value}</div>
      {hint ? <div className="mt-2 text-sm opacity-80">{hint}</div> : null}
    </div>
  );
}

function compactDistribution(distribution = {}, maxBars = 6) {
  const entries = Object.entries(distribution).filter(([, value]) => Number(value) > 0);
  if (entries.length <= maxBars) return entries;
  const kept = entries.slice(0, maxBars - 1);
  const other = entries.slice(maxBars - 1).reduce((sum, [, value]) => sum + Number(value || 0), 0);
  return [...kept, ["Other", Number(other.toFixed(2))]];
}

function ProtectedCard({ item }) {
  const bars = Object.entries(item.distribution || {}).filter(([, value]) => Number(value) > 0);
  const max = Math.max(...bars.map(([, value]) => Number(value)), 1);
  const riskLabel = (item.bias_risk || item.verdict || (item.imbalanced ? "HIGH" : "LOW")).toString();
  const banner = item.gap !== undefined
    ? `⚠ ${item.verdict || (item.imbalanced ? "Imbalanced" : "Balanced")} — ${item.dominant_group} has the lowest approval rate at ${item.dominant_percentage}%`
    : null;
  return (
    <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-2xl font-semibold text-white">{item.display_name || item.column}</h3>
          <p className="mt-1 text-sm text-slate-400">{item.reason}</p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${
            riskLabel.includes("HIGH")
              ? "bg-rose-500/15 text-rose-200"
              : riskLabel.includes("MEDIUM")
              ? "bg-amber-500/15 text-amber-200"
              : "bg-emerald-500/15 text-emerald-200"
          }`}
        >
          {riskLabel}
        </span>
      </div>

      {banner ? (
        <div className="mt-4 rounded-2xl bg-rose-500/10 px-4 py-3 text-sm font-medium text-rose-100 ring-1 ring-rose-400/20">
          {banner}
        </div>
      ) : null}

      <div className="mt-4 space-y-3">
        {bars.map(([label, value]) => (
          <div key={label} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-200">{label}</span>
              <span className="text-slate-400">{value}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/10">
              <div
                className={`h-full rounded-full ${label === item.dominant_group ? "bg-rose-400" : "bg-sky-400"}`}
                style={{ width: `${(Number(value) / max) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 text-sm text-slate-300">
        Bias Risk: <span className="font-semibold">{riskLabel}</span>
      </div>
    </div>
  );
}

function ProxyCard({ item }) {
  const distributionText = Object.entries(item.distribution || {})
    .map(([key, value]) => `${key} ${value}%`)
    .join(" • ");
  return (
    <div className="rounded-3xl border border-amber-400/20 bg-amber-500/10 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-xl font-semibold text-white">{item.display_name || item.column}</h3>
          <p className="mt-1 text-sm leading-6 text-amber-50/90">{item.reason}</p>
        </div>
        <span className="rounded-full bg-amber-400/15 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-amber-100">
          Proxy
        </span>
      </div>
      <p className="mt-4 text-sm text-amber-50/80">{distributionText || "No distribution available."}</p>
    </div>
  );
}

function OutcomePanel({ outcome }) {
  const entries = Object.entries(outcome?.distribution || {}).filter(([, value]) => Number(value) > 0);
  const positiveLabel = entries.find(([label]) => ["high", "approved", "yes", "hired", "accepted", "granted", "selected"].includes(String(label).trim().toLowerCase()))?.[0] || entries[0]?.[0];
  return (
    <div className="rounded-3xl border border-emerald-400/15 bg-emerald-500/10 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-emerald-100/70">Outcome Distribution</div>
          <h3 className="mt-2 text-2xl font-semibold text-white">{outcome?.display_name || outcome?.column || "Outcome"}</h3>
        </div>
        <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-slate-100">
          {outcome?.column ? "Detected" : "Unavailable"}
        </span>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {entries.length ? (
          entries.map(([label, value]) => (
            <div key={label} className="rounded-2xl bg-slate-950/40 p-4 ring-1 ring-white/5">
              <div className="text-sm text-slate-300">{label}</div>
              <div className={`mt-2 text-3xl font-semibold ${String(label).trim().toLowerCase() === String(positiveLabel).trim().toLowerCase() ? "text-emerald-300" : "text-rose-300"}`}>
                {value}%
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-2xl bg-slate-950/40 p-4 text-sm text-slate-300 ring-1 ring-white/5">
            No outcome distribution available.
          </div>
        )}
      </div>
    </div>
  );
}

export default function DatasetAnalyzer() {
  const [file, setFile] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const analyze = async () => {
    if (!file) return;
    setError("");
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await api.post("/analyze-dataset", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setProfile(response.data);
    } catch (requestError) {
      setProfile(null);
      setError(requestError?.response?.data?.detail || "Unable to analyze the selected file.");
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = async (event) => {
    const selected = event.target.files?.[0] || null;
    setFile(selected);
    setProfile(null);
  };

  const summary = useMemo(() => {
    if (!profile) return { protectedCount: 0, proxyCount: 0, outcomeText: "No outcome yet" };
    const protectedCount = profile.protected_columns?.length || 0;
    const proxyCount = profile.proxy_columns?.length || 0;
    const maxGap = Math.max(
      0,
      ...(profile.protected_columns || []).map((item) => {
        const values = Object.values(item.distribution || {}).map((value) => Number(value) || 0);
        return values.length ? Math.max(...values) - Math.min(...values) : 0;
      })
    );
    const outcome = profile.outcome_column?.distribution || profile.outcome_distribution || {};
    const outcomeText = Object.entries(outcome)
      .map(([label, value]) => `${label} ${value}%`)
      .join(" • ");
    const risk = maxGap < 5 ? "LOW" : maxGap < 15 ? "MEDIUM" : "HIGH";
    return { protectedCount, proxyCount, outcomeText: outcomeText || "No outcome distribution", maxGap, risk };
  }, [profile]);

  return (
    <div className="grid gap-6">
      <section className="glass soft-ring rounded-3xl p-6">
        <div className="panel-title">Dataset Analyzer</div>
        <h2 className="mt-2 text-3xl font-semibold text-white">Upload CSV or Excel to inspect bias before decisions</h2>
        <p className="mt-2 max-w-3xl text-sm text-slate-300">
          FairTrace detects protected columns, proxy variables, and outcome distributions using Mistral-powered classification.
        </p>
        <div className="mt-5 flex flex-col gap-4 md:flex-row md:items-end">
          <input
            type="file"
            accept=".csv,.xlsx,.xls"
            onChange={handleFileChange}
            className="block w-full cursor-pointer rounded-2xl border border-dashed border-white/15 bg-white/5 px-4 py-4 text-sm text-slate-300 file:mr-4 file:rounded-full file:border-0 file:bg-white file:px-4 file:py-2 file:font-semibold file:text-slate-950"
          />
          <button
            type="button"
            onClick={analyze}
            disabled={!file || loading}
            className="rounded-full bg-emerald-400 px-5 py-3 font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:opacity-50"
          >
            {loading ? "Analyzing..." : "Analyze Dataset"}
          </button>
        </div>
        {error ? (
          <div className="mt-4 rounded-2xl bg-rose-500/10 px-4 py-3 text-sm text-rose-100 ring-1 ring-rose-400/20">
            {error}
          </div>
        ) : null}
      </section>

      {profile ? (
        <>
          <section className="grid gap-4 md:grid-cols-3">
            <StatCard
              label="Protected Columns Found"
              value={`${summary.protectedCount}`}
              tone={summary.risk === "HIGH" ? "red" : summary.risk === "MEDIUM" ? "yellow" : "green"}
              hint={summary.risk === "HIGH" ? "Bias detected - review required" : summary.risk === "MEDIUM" ? "Moderate bias risk detected" : "No protected bias risk detected."}
            />
            <StatCard
              label="Proxy Variables Detected"
              value={`${summary.proxyCount}`}
              tone={summary.proxyCount > 0 ? "yellow" : "green"}
              hint={summary.proxyCount > 0 ? "Review proxy signals carefully." : "No proxy variables detected."}
            />
            <StatCard label="Outcome Distribution" value={summary.outcomeText} tone="neutral" hint="Approved vs rejected or similar target outcome." />
          </section>

          <section className="grid gap-6">
            <div>
              <div className="mb-3 flex items-center justify-between gap-3">
                <h3 className="text-2xl font-semibold text-white">Protected Columns</h3>
                <span className="text-sm text-slate-400">{profile.detection_method}</span>
              </div>
              {profile.protected_columns?.length ? (
                <div className="grid gap-4 xl:grid-cols-2">
                  {profile.protected_columns.map((item) => (
                    <ProtectedCard key={item.original_column || item.column} item={item} />
                  ))}
                </div>
              ) : (
                <div className="rounded-3xl border border-white/10 bg-white/5 p-6 text-sm text-slate-400">
                  No protected columns detected.
                </div>
              )}
            </div>

            <div>
              <h3 className="mb-3 text-2xl font-semibold text-white">Proxy Variables</h3>
              {profile.proxy_columns?.length ? (
                <div className="grid gap-4 xl:grid-cols-2">
                  {profile.proxy_columns.map((item) => (
                    <ProxyCard key={item.original_column || item.column} item={item} />
                  ))}
                </div>
              ) : (
                <div className="rounded-3xl border border-white/10 bg-white/5 p-6 text-sm text-slate-400">
                  No proxy variables detected.
                </div>
              )}
            </div>

            <div>
              <h3 className="mb-3 text-2xl font-semibold text-white">Outcome Distribution</h3>
              <OutcomePanel outcome={profile.outcome_column} />
            </div>
          </section>
        </>
      ) : (
        <section className="glass soft-ring rounded-3xl p-6 text-sm text-slate-400">
          Upload a CSV or Excel file to see protected columns, proxy warnings, and the outcome distribution.
        </section>
      )}
    </div>
  );
}
