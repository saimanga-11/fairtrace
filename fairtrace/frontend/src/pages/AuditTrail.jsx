import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";

const filters = ["all", "biased", "flagged", "corrected"];

export default function AuditTrail() {
  const navigate = useNavigate();
  const [decisions, setDecisions] = useState([]);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    api.get("/decisions").then((response) => setDecisions(response.data.decisions || []));
  }, []);

  const filtered = useMemo(() => {
    return decisions.filter((decision) => {
      if (filter === "biased") return String(decision.bias_verdict || "").toUpperCase() !== "LOW RISK";
      if (filter === "flagged") return Boolean(decision.flagged);
      if (filter === "corrected") return Boolean(decision.corrected);
      return true;
    });
  }, [decisions, filter]);

  return (
    <section className="glass soft-ring rounded-3xl p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="panel-title">Audit Trail</div>
          <h2 className="mt-2 text-3xl font-semibold text-white">Correctable decision history</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {filters.map((item) => (
            <button
              key={item}
              onClick={() => setFilter(item)}
              className={`rounded-full px-4 py-2 text-sm transition ${
                filter === item
                  ? "bg-emerald-400/15 text-emerald-200 ring-1 ring-emerald-400/30"
                  : "bg-white/5 text-slate-300 hover:bg-white/10"
              }`}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded-3xl border border-white/10">
        <table className="min-w-full divide-y divide-white/10 text-left text-sm">
          <thead className="bg-white/5 text-slate-300">
            <tr>
              <th className="px-4 py-3">ID</th>
              <th className="px-4 py-3">Timestamp</th>
              <th className="px-4 py-3">Outcome</th>
              <th className="px-4 py-3">Bias</th>
              <th className="px-4 py-3">Flagged</th>
              <th className="px-4 py-3">Corrected</th>
              <th className="px-4 py-3">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10 bg-slate-950/45 text-slate-200">
            {filtered.length ? (
              filtered.map((decision) => (
                <tr key={decision.id} className="hover:bg-white/5">
                  <td className="px-4 py-3">{decision.id}</td>
                  <td className="px-4 py-3 text-slate-400">{decision.timestamp}</td>
                  <td className="px-4 py-3">{decision.decision_outcome}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                      String(decision.bias_verdict).toUpperCase() === "HIGH RISK"
                        ? "bg-rose-500/15 text-rose-200"
                        : String(decision.bias_verdict).toUpperCase() === "MEDIUM RISK"
                        ? "bg-amber-500/15 text-amber-200"
                        : "bg-emerald-500/15 text-emerald-200"
                    }`}>
                      {decision.bias_verdict}
                    </span>
                  </td>
                  <td className="px-4 py-3">{decision.flagged ? "Yes" : "No"}</td>
                  <td className="px-4 py-3">{decision.corrected ? "Yes" : "No"}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => navigate(`/decisions/${decision.id}`)}
                      className="rounded-full bg-white/10 px-4 py-2 text-xs font-medium text-slate-100 hover:bg-white/15"
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td className="px-4 py-6 text-slate-400" colSpan={7}>
                  No decisions match the active filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

