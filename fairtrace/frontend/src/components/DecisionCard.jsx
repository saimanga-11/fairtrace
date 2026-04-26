import React from "react";

const verdictStyles = {
  FAIR: "bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-400/25",
  BIASED: "bg-rose-500/15 text-rose-200 ring-1 ring-rose-400/25",
  "LOW RISK": "bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-400/25",
  "MEDIUM RISK": "bg-amber-500/15 text-amber-200 ring-1 ring-amber-400/25",
  "HIGH RISK": "bg-rose-500/15 text-rose-200 ring-1 ring-rose-400/25",
  UNKNOWN: "bg-slate-500/15 text-slate-200 ring-1 ring-slate-400/25",
};

function formatTimestamp(timestamp) {
  if (!timestamp) return "Unknown time";
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return timestamp;
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
}

export default function DecisionCard({ decision, onView, onFlag }) {
  const verdict = String(decision.bias_verdict || "UNKNOWN").toUpperCase();
  return (
    <article className="glass soft-ring flex h-full flex-col rounded-3xl p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="panel-title">Decision #{decision.id}</div>
          <p className="mt-2 text-lg font-semibold text-white">{decision.decision_outcome}</p>
          <p className="mt-1 text-sm text-slate-400">{formatTimestamp(decision.timestamp)}</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${verdictStyles[verdict] || verdictStyles.UNKNOWN}`}>
          {verdict}
        </span>
      </div>

      <div className="mt-5 flex flex-wrap gap-2 text-sm">
        <span className={`rounded-full px-3 py-2 ${decision.flagged ? "bg-amber-500/15 text-amber-200" : "bg-white/5 text-slate-300"}`}>
          {decision.flagged ? "Flagged" : "Not flagged"}
        </span>
        <span className={`rounded-full px-3 py-2 ${decision.corrected ? "bg-cyan-500/15 text-cyan-200" : "bg-white/5 text-slate-300"}`}>
          {decision.corrected ? "Corrected" : "Not corrected"}
        </span>
      </div>

      <div className="mt-5 flex gap-3">
        <button
          type="button"
          onClick={() => onView?.(decision.id)}
          className="rounded-full bg-white px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-slate-100"
        >
          Open
        </button>
        <button
          type="button"
          onClick={() => onFlag?.(decision.id)}
          className="rounded-full bg-rose-500/15 px-4 py-2 text-sm font-medium text-rose-100 ring-1 ring-rose-400/25 transition hover:bg-rose-500/25"
        >
          Flag
        </button>
      </div>
    </article>
  );
}
