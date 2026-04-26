import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api from "../lib/api";
import ReasoningChain from "../components/ReasoningChain";
import CounterfactualPanel from "../components/CounterfactualPanel";

function FeatureBars({ features = [], className = "" }) {
  const max = Math.max(...features.map((item) => item.score), 1);
  return (
    <div className={`glass soft-ring rounded-3xl p-5 ${className}`}>
      <div className="panel-title">Feature Importance</div>
      <div className="mt-4 space-y-3">
        {features.length ? (
          features.map((item) => (
            <div key={item.feature} className="space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-200">{item.feature}</span>
                <span className="text-slate-400">{item.score}</span>
              </div>
              <div className="h-2 rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-emerald-400"
                  style={{ width: `${(item.score / max) * 100}%` }}
                />
              </div>
            </div>
          ))
        ) : (
          <p className="text-sm text-slate-400">No feature importance data available.</p>
        )}
      </div>
    </div>
  );
}

function BiasAnalysisPanel({ analysis = {} }) {
  const attributes = analysis.attributes || [];
  if (!attributes.length) {
    return (
      <section className="glass soft-ring rounded-3xl p-5">
        <div className="panel-title">Approval Rate Bias</div>
        <p className="mt-3 text-sm text-slate-400">No approval-rate analysis available.</p>
      </section>
    );
  }

  const risk = String(analysis.overall_verdict || "LOW RISK").toUpperCase();
  const badgeClass =
    risk === "HIGH RISK"
      ? "bg-rose-500/15 text-rose-200"
      : risk === "MEDIUM RISK"
      ? "bg-amber-500/15 text-amber-200"
      : "bg-emerald-500/15 text-emerald-200";

  return (
    <section className="glass soft-ring rounded-3xl p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="panel-title">Approval Rate Bias</div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${badgeClass}`}>{risk}</span>
      </div>

      <div className="mt-4 grid gap-4">
        {attributes.map((item) => {
          const rates = Object.entries(item.group_rates || {});
          const max = Math.max(...rates.map(([, value]) => Number(value)), 1);
          const min = Math.min(...rates.map(([, value]) => Number(value)), 0);
          const lowGroup = item.dominant_group || rates.reduce((best, current) => (Number(current[1]) < Number(best[1]) ? current : best), rates[0] || []);
          return (
            <div key={item.attribute} className="rounded-3xl bg-white/5 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h4 className="text-lg font-semibold text-white">{item.attribute === "age" ? "Age" : item.attribute === "race" ? "Race / Ethnicity" : "Gender"}</h4>
                  <p className="mt-1 text-sm text-slate-400">Gap: {item.gap}% between highest and lowest approved group</p>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${badgeClass}`}>{item.verdict}</span>
              </div>
              <div className="mt-4 space-y-3">
                {rates.map(([group, value]) => (
                  <div key={group} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-200">{group}</span>
                      <span className="text-slate-400">{value}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-white/10">
                      <div
                        className={`h-full rounded-full ${group === lowGroup ? "bg-rose-400" : "bg-sky-400"}`}
                        style={{ width: `${(Number(value) / max) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-sm text-slate-300">
                Flagged group: <span className="font-semibold text-white">{lowGroup}</span>
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function DecisionDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [decision, setDecision] = useState(null);

  const loadDecision = async () => {
    const response = await api.get(`/decisions/${id}`);
    setDecision(response.data);
  };

  useEffect(() => {
    loadDecision().catch(() => setDecision(null));
  }, [id]);

  const reasoning = decision?.reasoning_chain || {};
  const counterfactual = decision?.counterfactual_result || {};
  const biasAnalysis = decision?.bias_analysis || {};

  const handleFlag = async () => {
    await api.post(`/flag/${id}`);
    await loadDecision();
  };

  const handleCorrect = async () => {
    const nextOutcome = window.prompt("Enter the corrected outcome", decision?.decision_outcome || "approved");
    if (!nextOutcome) return;
    await api.post(`/correct/${id}`, { new_outcome: nextOutcome });
    await loadDecision();
  };

  if (!decision) {
    return <div className="glass soft-ring rounded-3xl p-6 text-slate-300">Loading decision details...</div>;
  }

  const verdict = String(decision.bias_verdict || "UNKNOWN").toUpperCase();

  return (
    <div className="grid gap-6">
      <section className="glass soft-ring rounded-3xl p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="panel-title">Decision #{decision.id}</div>
            <h2 className="mt-2 text-3xl font-semibold text-white">{decision.decision_outcome}</h2>
            <p className="mt-1 text-sm text-slate-400">{decision.timestamp}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${verdict === "BIASED" ? "bg-rose-500/15 text-rose-200" : "bg-emerald-500/15 text-emerald-200"}`}>
              {verdict}
            </span>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${decision.flagged ? "bg-amber-500/15 text-amber-200" : "bg-slate-500/15 text-slate-200"}`}>
              {decision.flagged ? "Flagged" : "Not flagged"}
            </span>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${decision.corrected ? "bg-cyan-500/15 text-cyan-200" : "bg-slate-500/15 text-slate-200"}`}>
              {decision.corrected ? "Corrected" : "Uncorrected"}
            </span>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <button onClick={handleFlag} className="rounded-full bg-rose-500/15 px-4 py-2 text-sm text-rose-100 ring-1 ring-rose-400/25">
            Flag decision
          </button>
          <button onClick={handleCorrect} className="rounded-full bg-cyan-500/15 px-4 py-2 text-sm text-cyan-100 ring-1 ring-cyan-400/25">
            Correct decision
          </button>
          <button onClick={() => navigate(-1)} className="rounded-full bg-white/10 px-4 py-2 text-sm text-slate-100">
            Back
          </button>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <ReasoningChain steps={reasoning.reasoning_steps || []} />
        <FeatureBars features={reasoning.feature_importance || []} />
      </section>

      <BiasAnalysisPanel analysis={biasAnalysis} />

      <section className="glass soft-ring rounded-3xl p-5">
        <div className="panel-title">AI Summary</div>
        <p className="mt-3 text-sm leading-7 text-slate-200">{reasoning.summary || "No summary available."}</p>
        <p className="mt-4 text-sm leading-7 text-slate-400">{reasoning.bias_explanation || "No bias explanation available."}</p>
      </section>

      <CounterfactualPanel result={counterfactual} />
    </div>
  );
}

