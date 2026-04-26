import React from "react";

export default function ReasoningChain({ steps = [] }) {
  return (
    <section className="glass soft-ring rounded-3xl p-5">
      <div className="panel-title">Reasoning Chain</div>
      <ol className="mt-4 space-y-3">
        {steps.length ? (
          steps.map((step, index) => (
            <li key={`${index}-${step}`} className="rounded-2xl bg-white/5 px-4 py-3 text-sm leading-6 text-slate-200">
              <span className="mr-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-emerald-400/15 text-xs font-semibold text-emerald-200">
                {index + 1}
              </span>
              {step}
            </li>
          ))
        ) : (
          <li className="text-sm text-slate-400">No reasoning chain available.</li>
        )}
      </ol>
    </section>
  );
}

