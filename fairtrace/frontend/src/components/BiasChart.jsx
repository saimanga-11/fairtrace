import React from "react";

export default function BiasChart({ title, rows = [], highlight = false }) {
  const max = Math.max(...rows.map((row) => row.value), 1);
  return (
    <section className={`glass soft-ring rounded-3xl p-5 ${highlight ? "ring-1 ring-rose-400/30" : ""}`}>
      <div className="panel-title">{title}</div>
      <div className="mt-4 space-y-3">
        {rows.length ? (
          rows.map((row) => (
            <div key={row.label} className="space-y-1">
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="text-slate-200">{row.label}</span>
                <span className="text-slate-400">{row.value}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-white/10">
                <div
                  className={`h-full rounded-full ${row.color || "bg-sky-400"}`}
                  style={{ width: `${(row.value / max) * 100}%` }}
                />
              </div>
            </div>
          ))
        ) : (
          <p className="text-sm text-slate-400">No distribution data available.</p>
        )}
      </div>
    </section>
  );
}

