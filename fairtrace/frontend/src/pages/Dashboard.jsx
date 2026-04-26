import React, { useMemo, useState } from "react";
import api from "../lib/api";

function riskTone(label) {
  const risk = String(label || "").toUpperCase();
  if (risk.includes("HIGH")) return "red";
  if (risk.includes("MEDIUM")) return "yellow";
  if (risk.includes("LOW")) return "green";
  return "neutral";
}

function toneClasses(tone) {
  return {
    neutral: "bg-white/5 text-slate-100 ring-white/10",
    green: "bg-emerald-500/10 text-emerald-100 ring-emerald-400/20",
    yellow: "bg-amber-500/10 text-amber-100 ring-amber-400/20",
    red: "bg-rose-500/10 text-rose-100 ring-rose-400/20",
  }[tone] || "bg-white/5 text-slate-100 ring-white/10";
}

function SummaryChip({ label, value, tone = "neutral" }) {
  return (
    <div className={`rounded-2xl px-4 py-3 ring-1 ${toneClasses(tone)}`}>
      <div className="text-xs uppercase tracking-[0.2em] opacity-70">{label}</div>
      <div className="mt-2 text-xl font-semibold">{value}</div>
    </div>
  );
}

function FindingCard({ title, risk, dataLabel, dataValue, metricLabel, metricValue, reason, recommendation }) {
  return (
    <article className="glass soft-ring rounded-3xl p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="panel-title">Column</div>
          <h3 className="mt-2 text-xl font-semibold text-white">{title}</h3>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${toneClasses(riskTone(risk))}`}>
          {risk}
        </span>
      </div>

      <div className="mt-5 grid gap-2 text-sm text-slate-300">
        <div className="rounded-2xl bg-white/5 px-4 py-3">
          <span className="text-slate-400">{dataLabel}: </span>
          <span className="text-slate-100">{dataValue}</span>
        </div>
        <div className="rounded-2xl bg-white/5 px-4 py-3">
          <span className="text-slate-400">{metricLabel}: </span>
          <span className="text-slate-100">{metricValue}</span>
        </div>
      </div>

      <div className="mt-5 space-y-4 text-sm leading-6">
        <div className="rounded-2xl bg-white/5 px-4 py-3 text-slate-200">
          <div className="panel-title">Reason</div>
          <p className="mt-2">{reason}</p>
        </div>
        <div className="rounded-2xl bg-emerald-500/10 px-4 py-3 text-emerald-50 ring-1 ring-emerald-400/20">
          <div className="panel-title text-emerald-200">Suggested Correction</div>
          <p className="mt-2">{recommendation}</p>
        </div>
      </div>
    </article>
  );
}

export default function Dashboard() {
  const [analysis, setAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState("");

  const analysisSummary = useMemo(() => {
    if (!analysis) return null;

    return {
      overallRisk: analysis.overall_risk || "LOW RISK",
      biasedCount: analysis.bias_findings?.length || 0,
      proxyCount: analysis.proxy_findings?.length || 0,
      outcomeName: analysis.outcome_column?.display_name || analysis.outcome_column?.column || "Not found",
      recommendationCount: analysis.overall_recommendations?.length || 0,
    };
  }, [analysis]);

  const downloadHref = useMemo(() => {
    if (!analysis?.download_url) return "";
    if (String(analysis.download_url).startsWith("http")) return analysis.download_url;
    return `${String(api.defaults.baseURL || "").replace(/\/$/, "")}${analysis.download_url}`;
  }, [analysis]);

  const uploadDataset = async (file) => {
    if (!file) return;
    setAnalysis(null);
    setAnalysisError("");
    setAnalysisLoading(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await api.post("/analyze-dataset", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setAnalysis(response.data);
    } catch (error) {
      setAnalysis(null);
      setAnalysisError(error?.response?.data?.detail || "Dataset analysis failed. Please try another CSV or Excel file.");
    } finally {
      setAnalysisLoading(false);
    }
  };

  return (
    <div className="grid gap-6">
      <section className="glass soft-ring rounded-3xl p-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold text-white">Upload your dataset</h2>
            <p className="mt-2 text-sm text-slate-300">
              Upload the Excel or CSV file and FairTrace will point out biased columns, affected values, short reasons, and what to change.
            </p>
          </div>
          {analysisSummary ? (
            <span className={`rounded-full px-4 py-2 text-sm font-medium ring-1 ${toneClasses(riskTone(analysisSummary.overallRisk))}`}>
              Overall risk: {analysisSummary.overallRisk}
            </span>
          ) : null}
        </div>

        <input
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={(event) => uploadDataset(event.target.files?.[0])}
          className="mt-5 block w-full cursor-pointer rounded-2xl border border-dashed border-white/15 bg-white/5 px-4 py-6 text-sm text-slate-300 file:mr-4 file:rounded-full file:border-0 file:bg-white file:px-4 file:py-2 file:font-semibold file:text-slate-950"
        />

        {analysisLoading ? (
          <div className="mt-4 rounded-2xl bg-white/5 px-4 py-3 text-sm text-slate-300">
            Analyzing the uploaded file, creating the suggested workbook, and preparing charts...
          </div>
        ) : null}

        {analysisError ? (
          <div className="mt-4 rounded-2xl bg-rose-500/10 px-4 py-3 text-sm text-rose-100 ring-1 ring-rose-400/20">
            {analysisError}
          </div>
        ) : null}

        {analysisSummary ? (
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <SummaryChip label="Rows checked" value={analysis.row_count || 0} />
            <SummaryChip label="Biased columns" value={analysisSummary.biasedCount} tone={analysisSummary.biasedCount ? riskTone(analysisSummary.overallRisk) : "green"} />
            <SummaryChip label="Proxy warnings" value={analysisSummary.proxyCount} tone={analysisSummary.proxyCount ? "yellow" : "green"} />
            <SummaryChip label="Outcome column" value={analysisSummary.outcomeName} tone={analysisSummary.outcomeName === "Not found" ? "neutral" : "green"} />
            <SummaryChip label="Fix suggestions" value={analysisSummary.recommendationCount} tone={analysisSummary.recommendationCount ? "green" : "neutral"} />
          </div>
        ) : null}
      </section>

      {analysis ? (
        <>
          <section className="glass soft-ring rounded-3xl p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="panel-title">Dataset Summary</div>
                <p className="mt-3 text-sm leading-7 text-slate-200">
                  {analysis.dataset_summary || "The uploaded dataset was analyzed successfully."}
                </p>
                {analysis.download_filename ? (
                  <p className="mt-3 text-sm text-slate-400">
                    Generated workbook: <span className="text-slate-200">{analysis.download_filename}</span>
                  </p>
                ) : null}
              </div>
              {downloadHref ? (
                <a
                  href={downloadHref}
                  className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100"
                >
                  Download Excel
                </a>
              ) : null}
            </div>
            <div className="mt-4 rounded-2xl bg-white/5 px-4 py-3 text-sm text-slate-300">
              The download includes a bias report sheet with charts, the original data, and a highlighted suggested-data sheet showing what FairTrace changed.
            </div>
          </section>

          <section className="grid gap-4 xl:grid-cols-2">
            {analysis.bias_findings?.length ? (
              analysis.bias_findings.map((finding) => (
                <FindingCard
                  key={finding.key}
                  title={finding.display_name}
                  risk={finding.risk}
                  dataLabel="Biased data"
                  dataValue={finding.biased_value}
                  metricLabel="Observed gap"
                  metricValue={`${finding.biased_rate}% approval vs ${finding.reference_value} at ${finding.reference_rate}%`}
                  reason={finding.reason}
                  recommendation={finding.recommendation}
                />
              ))
            ) : (
              <div className="glass soft-ring rounded-3xl p-6 text-sm text-slate-300 xl:col-span-2">
                No clear protected-column bias was detected in the uploaded file.
              </div>
            )}
          </section>

          <section className="grid gap-4 xl:grid-cols-2">
            {analysis.proxy_findings?.length ? (
              analysis.proxy_findings.map((finding) => (
                <FindingCard
                  key={finding.key}
                  title={finding.display_name}
                  risk={finding.risk}
                  dataLabel="Flagged value"
                  dataValue={finding.biased_value}
                  metricLabel="Share in dataset"
                  metricValue={`${finding.biased_share}% of rows`}
                  reason={finding.reason}
                  recommendation={finding.recommendation}
                />
              ))
            ) : (
              <div className="glass soft-ring rounded-3xl p-6 text-sm text-slate-300 xl:col-span-2">
                No proxy columns were detected in the uploaded file.
              </div>
            )}
          </section>

          {analysis.overall_recommendations?.length ? (
            <section className="glass soft-ring rounded-3xl p-6">
              <div className="panel-title">What To Change</div>
              <div className="mt-4 grid gap-3">
                {analysis.overall_recommendations.map((item) => (
                  <div key={item} className="rounded-2xl bg-white/5 px-4 py-3 text-sm leading-6 text-slate-200">
                    {item}
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
