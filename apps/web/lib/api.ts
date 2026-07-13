const API=process.env.NEXT_PUBLIC_API_URL??"http://127.0.0.1:8000";
export async function api(path:string,init?:RequestInit){const r=await fetch(`${API}${path}`,init);const body=await r.json().catch(()=>null);if(!r.ok)throw new Error(body?.error?.message??`Request failed (${r.status})`);return body;}
export const downloadUrl=(id:string,kind:"markdown"|"text"|"json")=>`${API}/api/ocr/jobs/${id}/download/${kind}`;
export const statusLabel=(status:string)=>({QUEUED:"Waiting in queue",LOADING_MODEL:"Loading local OCR model",PROCESSING:"Processing document",COMPLETED:"Completed",COMPLETED_WITH_ERRORS:"Completed with page errors",FAILED:"Failed",CANCEL_REQUESTED:"Cancelling after current operation",CANCELLED:"Cancelled",INTERRUPTED:"Interrupted and awaiting recovery"}[status]??status);
