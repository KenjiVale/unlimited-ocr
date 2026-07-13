"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Nav } from "../../../components/nav";
import { api, downloadUrl, statusLabel } from "../../../lib/api";

const activeStatuses = new Set(["QUEUED", "LOADING_MODEL", "PROCESSING", "CANCEL_REQUESTED"]);

export default function JobDetail() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<any>();
  const [pages, setPages] = useState<any[]>([]);
  const [result, setResult] = useState<any>();
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    try {
      const value = await api(`/api/ocr/jobs/${jobId}`);
      setJob(value);
      if (value.file_type === "pdf") setPages((await api(`/api/ocr/jobs/${jobId}/pages`)).pages);
      if (value.result_available) setResult(await api(`/api/ocr/jobs/${jobId}/result`));
    } catch (error) { setMessage(String(error)); }
  }, [jobId]);
  useEffect(() => {
    void load();
    if (!job || activeStatuses.has(job.status)) {
      const timer = window.setInterval(() => void load(), 2000);
      return () => window.clearInterval(timer);
    }
  }, [job?.status, load]);
  if (!job) return <main><Nav /><p>Loading… {message}</p></main>;
  const active = activeStatuses.has(job.status);
  const action = (path: string, options?: RequestInit) => api(path, options).then(load).catch(error => setMessage(String(error)));
  const checkIntegrity = async () => {
    try { const value = await api(`/api/ocr/jobs/${jobId}/integrity`); setMessage(value.valid ? "Integrity valid" : value.issues.join(", ")); }
    catch (error) { setMessage(String(error)); }
  };
  return <main><Nav /><h1>{job.original_filename}</h1>
    <p>{statusLabel(job.status)} · {job.progress_percent}% · {job.processed_pages}/{job.total_pages} pages</p>
    <p>Mode {job.ocr_mode} · DPI {job.pdf_dpi ?? "—"} · duration {job.processing_duration_ms ?? "—"} ms</p>
    {job.error && <p role="alert">{job.error.code}: {job.error.message}</p>}
    <section className="actions"><button disabled={!active} onClick={() => action(`/api/ocr/jobs/${jobId}/cancel`, { method: "POST" })}>Cancel</button><button disabled={active || job.status === "COMPLETED"} onClick={() => action(`/api/ocr/jobs/${jobId}/retry`, { method: "POST" })}>Retry job</button><button disabled={active} onClick={() => action(`/api/ocr/jobs/${jobId}`, { method: "DELETE" }).then(() => location.assign("/jobs"))}>Delete</button><button onClick={checkIntegrity}>Integrity</button></section>
    <p aria-live="polite">{message}</p>
    <section><h2>Pages</h2>{pages.map(page => <details key={page.page_number}><summary>Page {page.page_number}: {page.status} · render {page.render_duration_ms ?? "—"} ms · OCR {page.inference_duration_ms ?? "—"} ms</summary>{page.error && <p>{page.error.code}: {page.error.message}</p>}{page.status === "COMPLETED" && <button onClick={() => api(`/api/ocr/jobs/${jobId}/pages/${page.page_number}/result`).then(setResult)}>Load page result</button>}{["FAILED", "SKIPPED"].includes(page.status) && <button onClick={() => action(`/api/ocr/jobs/${jobId}/pages/${page.page_number}/retry`, { method: "POST" })}>Retry page</button>}</details>)}</section>
    {result && <section><h2>Result</h2><p><a href={downloadUrl(jobId, "markdown")}>Download Markdown</a> · <a href={downloadUrl(jobId, "text")}>Download TXT</a> · <a href={downloadUrl(jobId, "json")}>Download JSON</a></p><button onClick={() => navigator.clipboard.writeText(result.markdown ?? "")}>Copy Markdown</button><details open><summary>Rendered Markdown</summary><pre>{result.markdown}</pre></details><details><summary>Plain text</summary><pre>{result.text}</pre></details><details><summary>JSON metadata</summary><pre>{JSON.stringify(result, null, 2)}</pre></details></section>}
  </main>;
}
