from __future__ import annotations
import json,os,signal,subprocess,sys,time
from pathlib import Path
import httpx
from verify_phase3_pdf import create_pdf

URL="http://127.0.0.1:8010"
def start()->subprocess.Popen:
    env=os.environ.copy(); env.update(HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",HF_HUB_DISABLE_TELEMETRY="1",OCR_MODEL_PATH="./data/models/Unlimited-OCR",API_PORT="8010")
    flags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=="nt" else 0
    process=subprocess.Popen([str(Path(".venv/Scripts/python.exe")),"-m","uvicorn","app.main:app","--app-dir","services/api","--host","127.0.0.1","--port","8010"],env=env,creationflags=flags)
    for _ in range(100):
        try:
            if httpx.get(URL+"/api/health",timeout=1).status_code==200:return process
        except Exception: time.sleep(.1)
    raise RuntimeError("server did not start")
def stop(process:subprocess.Popen)->None:
    process.send_signal(signal.CTRL_BREAK_EVENT if os.name=="nt" else signal.SIGINT); process.wait(timeout=40)
def main()->int:
    process=None
    try:
        path=Path("data/uploads/phase4-restart.pdf"); create_pdf(path,5); process=start()
        with httpx.Client(base_url=URL,timeout=30) as client:
            with path.open("rb") as stream: response=client.post("/api/ocr/jobs",files={"file":(path.name,stream,"application/pdf")},data={"ocr_mode":"gundam","pdf_dpi":"200"})
            response.raise_for_status(); job_id=response.json()["id"]
            while True:
                pages=client.get(f"/api/ocr/jobs/{job_id}/pages").json()["pages"]
                if sum(p["status"]=="COMPLETED" for p in pages)>=1: break
                time.sleep(.1)
            completed_before=[p["page_number"] for p in pages if p["status"]=="COMPLETED"]
        stop(process); process=None; process=start()
        with httpx.Client(base_url=URL,timeout=30) as client:
            while True:
                job=client.get(f"/api/ocr/jobs/{job_id}").json()
                if job["status"]=="COMPLETED": break
                time.sleep(.1)
            pages=client.get(f"/api/ocr/jobs/{job_id}/pages").json()["pages"]; integrity=client.get(f"/api/ocr/jobs/{job_id}/integrity").json(); worker=client.get("/api/system/worker").json()
        if not integrity["valid"] or any(p["status"]!="COMPLETED" for p in pages): raise RuntimeError("restart validation failed")
        print(json.dumps({"job_id":job_id,"completed_before_restart":completed_before,"completed_after_restart":[p["page_number"] for p in pages if p["status"]=="COMPLETED"],"worker_state":worker["state"],"integrity":integrity},indent=2)); stop(process); return 0
    except Exception as exc:
        if process and process.poll() is None:
            try: stop(process)
            except Exception: process.kill()
        print(f"PHASE4_RESTART_FAILED: {exc}",file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
