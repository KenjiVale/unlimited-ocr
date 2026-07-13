"use client";

import { FormEvent, useEffect, useState } from "react";
import { Nav } from "../components/nav";
import { statusLabel } from "../lib/api";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
type System = { health?: string; cuda?: boolean; gpu?: string | null; model?: string; error?: string };
type Job = { id: string; status: string; file_type: string; total_pages: number; processed_pages: number; successful_pages: number; failed_pages: number; progress_percent: number; current_page_number: number | null; result_available: boolean };
type Page = { page_number: number; status: string };
type Worker = { state: string; queued_jobs: number; active_job_id: string | null; active_page_number: number | null };
type Storage = { free_disk_bytes: number; used_disk_bytes: number; accepting_new_jobs: boolean };

export default function Home() {
  const [system, setSystem] = useState<System>({});
  const [file, setFile] = useState<File | null>(null);
  const [dpi, setDpi] = useState("200");
  const [job, setJob] = useState<Job | null>(null);
  const [pages, setPages] = useState<Page[]>([]);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [worker, setWorker] = useState<Worker | null>(null);
  const [storage, setStorage] = useState<Storage | null>(null);
  const [integrity, setIntegrity] = useState<string>("");

  useEffect(() => {
    Promise.all([fetch(`${API}/api/health`).then(r => r.json()), fetch(`${API}/api/system/gpu`).then(r => r.json()), fetch(`${API}/api/system/model`).then(r => r.json()), fetch(`${API}/api/system/worker`).then(r => r.json()), fetch(`${API}/api/system/storage`).then(r => r.json())])
      .then(([health, gpu, model, workerStatus, storageStatus]) => { setSystem({ health: health.status, cuda: gpu.cuda_available, gpu: gpu.device_name, model: model.status }); setWorker(workerStatus); setStorage(storageStatus); })
      .catch(() => setSystem({ error: "Backend unavailable" }));
  }, []);

  useEffect(() => {
    if (!job || ["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED", "CANCELLED"].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      const current = await fetch(`${API}/api/ocr/jobs/${job.id}`).then(r => r.json()); setJob(current);
      if (current.file_type === "pdf") setPages((await fetch(`${API}/api/ocr/jobs/${job.id}/pages`).then(r => r.json())).pages);
      if (current.result_available) setResult((await fetch(`${API}/api/ocr/jobs/${job.id}/result`).then(r => r.json())).markdown);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [job]);

  async function submit(event: FormEvent) {
    event.preventDefault(); if (!file) return;
    setError(""); setResult(""); setPages([]);
    const form = new FormData(); form.append("file", file); form.append("ocr_mode", "gundam"); form.append("pdf_dpi", dpi);
    const response = await fetch(`${API}/api/ocr/jobs`, { method: "POST", body: form });
    const body = await response.json();
    if (!response.ok) { setError(body.error?.message ?? "Upload failed"); return; }
    setJob(body);
  }

  async function checkIntegrity() { if (job) { const value = await fetch(`${API}/api/ocr/jobs/${job.id}/integrity`).then(r => r.json()); setIntegrity(value.valid ? "Valid" : `Issues: ${value.issues.join(", ")}`); } }
  async function previewCleanup() { const value = await fetch(`${API}/api/maintenance/cleanup/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ older_than_days: 30, include_rendered_pages: true, include_source_files: false, include_outputs: false }) }).then(r => r.json()); setIntegrity(`Cleanup preview: ${value.rendered_page_files} rendered files, ${value.rendered_page_bytes} bytes`); }

  return <main>
    <Nav />
    <h1>Unlimited OCR Local</h1>
    <p>Local processing {system.model === "READY" || system.model === "NOT_LOADED" ? "· Offline mode confirmed by backend status when configured" : ""}</p>
    {system.error ? <p>{system.error}</p> : <p>Backend: {system.health ?? "Checking…"} · CUDA: {system.cuda ? "Available" : "Checking…"} · GPU: {system.gpu ?? "—"} · Model: {system.model ?? "Checking…"}</p>}
    {worker && <p>Worker: {worker.state} · queue: {worker.queued_jobs} · active job: {worker.active_job_id ?? "—"} · page: {worker.active_page_number ?? "—"}</p>}
    {storage && <p>Storage: free {storage.free_disk_bytes} bytes · used {storage.used_disk_bytes} bytes · accepting jobs: {storage.accepting_new_jobs ? "yes" : "no"}</p>}
    <form onSubmit={submit}>
      <input type="file" accept="image/png,image/jpeg,image/webp,application/pdf" onChange={event => setFile(event.target.files?.[0] ?? null)} required />
      {file && <p>Selected file: {file.name} ({Math.ceil(file.size / 1024)} KB)</p>}
      <label> Mode <select value="gundam" disabled><option>gundam</option></select></label>
      {file?.type === "application/pdf" && <label> PDF DPI <select value={dpi} onChange={event => setDpi(event.target.value)}><option>150</option><option>200</option><option>300</option></select></label>}
      <button type="submit">Start OCR</button>
    </form>
    {error && <p>{error}</p>}
    {job && <section><h2>Job</h2><p>Status: {statusLabel(job.status)}</p><p>Progress: {job.processed_pages}/{job.total_pages} ({job.progress_percent}%) · successful {job.successful_pages} · failed {job.failed_pages} · current page {job.current_page_number ?? "—"}</p>{pages.length > 0 && <ul>{pages.map(page => <li key={page.page_number}>Page {page.page_number}: {page.status}</li>)}</ul>}<button onClick={checkIntegrity}>Check integrity</button></section>}
    <button onClick={previewCleanup}>Preview rendered-page cleanup</button>{integrity && <p>{integrity}</p>}
    {result && <section><h2>Result</h2><pre>{result}</pre></section>}
  </main>;
}
