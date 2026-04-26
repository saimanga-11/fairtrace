import React from "react";

export default function CounterfactualPanel({ result }) {
  if (!result) {
    return (
      <section className="glass soft-ring rounded-3xl p-5">
        <div className="panel-title">Counterfactual</div>
        <p className="mt-3 text-sm text-slate-400">No counterfactual data available.</p>
      </section>
    );
  }

  const scenarios = result.scenarios || [];
  const primary = scenarios[0] || result;

  return (
    <section className="glass soft-ring rounded-3xl p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="panel-title">Counterfactual Panel</div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${result.would_change ? "bg-amber-500/15 text-amber-200" : "bg-slate-500/15 text-slate-200"}`}>
          {result.would_change ? "Outcome changes" : "Outcome stable"}
        </span>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl bg-white/5 p-4">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Original</p>
          <p className="mt-2 text-xl font-semibold text-white">{result.original_outcome}</p>
          <p className="mt-3 text-sm text-slate-300">{primary.explanation || "Original outcome context loaded."}</p>
        </div>
        <div className="rounded-2xl bg-emerald-500/10 p-4 ring-1 ring-emerald-400/20">
          <p className="text-xs uppercase tracking-[0.2em] text-emerald-200">What if</p>
          <p className="mt-2 text-xl font-semibold text-white">{primary.flipped_outcome || "unknown"}</p>
          <p className="mt-3 text-sm text-slate-300">
            Flip <span className="font-semibold text-emerald-200">{primary.flipped_attribute}</span>
            {primary.flipped_value !== undefined ? ` to ${primary.flipped_value}` : ""}.
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {scenarios.map((scenario) => (
          <div key={scenario.flipped_attribute} className="rounded-2xl bg-white/5 px-4 py-3 text-sm text-slate-300">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-sky-500/15 px-3 py-1 text-xs font-semibold text-sky-200">
                {scenario.flipped_attribute}
              </span>
              <span>Changed to {String(scenario.flipped_value)}</span>
              <span className="text-slate-500">|</span>
              <span>{scenario.original_outcome} -&gt; {scenario.flipped_outcome}</span>
              <span className="text-slate-500">|</span>
              <span className={scenario.would_change ? "text-amber-300" : "text-emerald-300"}>
                {scenario.would_change ? "changed" : "stable"}
              </span>
            </div>
            <p className="mt-2 text-slate-400">{scenario.explanation}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
