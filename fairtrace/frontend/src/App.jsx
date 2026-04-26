import React from "react";
import { Route, Routes, Navigate } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import DecisionDetail from "./pages/DecisionDetail";

export default function App() {
  return (
    <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-5 sm:px-6 lg:px-8">
      <header className="mb-6 px-1 pt-2">
        <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">Decision Dashboard</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-400">
          Upload your Excel or CSV file, then review the latest decisions in one place.
        </p>
      </header>

      <main className="flex-1 pb-10">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/decisions/:id" element={<DecisionDetail />} />
          <Route path="/dataset-analyzer" element={<Navigate to="/" replace />} />
          <Route path="/audit-trail" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
