from __future__ import annotations
import json,sys,time
from pathlib import Path
import httpx
from verify_phase3_pdf import create_pdf

def main()->int:
    try:
        p1=Path("data/uploads/phase4-queue-a.pdf"); p2=Path("data/uploads/phase4-queue-b.pdf"); create_pdf(p1,3); create_pdf(p2,2); image=Path("data/uploads/phase1-sample.png")
        with httpx.Client(base_url="http://127.0.0.1:8000",timeout=30) as client:
            queue_started=time.perf_counter()
            submissions=[]
            for path,mime in ((p1,"application/pdf"),(image,"image/png"),(p2,"application/pdf")):
                before=time.perf_counter()
                with path.open("rb") as stream: response=client.post("/api/ocr/jobs",files={"file":(path.name,stream,mime)},data={"ocr_mode":"gundam","pdf_dpi":"200"})
                response.raise_for_status(); submissions.append({"id":response.json()["id"],"ms":round((time.perf_counter()-before)*1000)})
            order=[]; active=None; health=[]; deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                before=time.perf_counter(); client.get("/api/health").raise_for_status(); health.append(round((time.perf_counter()-before)*1000))
                worker=client.get("/api/system/worker").json()
                if worker["active_job_id"] and worker["active_job_id"]!=active: active=worker["active_job_id"]; order.append(active)
                states=[client.get(f"/api/ocr/jobs/{item['id']}").json()["status"] for item in submissions]
                if all(state=="COMPLETED" for state in states): break
                time.sleep(.05)
            else: raise RuntimeError("queue timed out")
            outputs=[str((Path("data/outputs")/item["id"]).resolve()) for item in submissions]
        expected=[item["id"] for item in submissions]
        if order!=expected or len(set(outputs))!=3: raise RuntimeError(f"queue order mismatch {order} != {expected}")
        print(json.dumps({"submissions":submissions,"total_queue_ms":round((time.perf_counter()-queue_started)*1000),"queue_order":order,"health_max_ms":max(health),"output_directories":outputs},indent=2)); return 0
    except Exception as exc: print(f"PHASE4_QUEUE_FAILED: {exc}",file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
