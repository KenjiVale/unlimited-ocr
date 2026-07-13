from __future__ import annotations
import argparse,json,statistics,sys,time
from pathlib import Path
import httpx
from verify_phase3_pdf import create_pdf

def percentile(values:list[int],p:float)->float:
    ordered=sorted(values); return float(ordered[min(len(ordered)-1,max(0,int((len(ordered)-1)*p)))])

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--url",default="http://127.0.0.1:8000"); parser.add_argument("--pages",type=int,default=12); args=parser.parse_args()
    path=Path("data/uploads/phase4-soak.pdf"); create_pdf(path,args.pages)
    try:
        with httpx.Client(base_url=args.url,timeout=30) as client:
            started=time.perf_counter()
            with path.open("rb") as stream:
                before=time.perf_counter(); response=client.post("/api/ocr/jobs",files={"file":(path.name,stream,"application/pdf")},data={"ocr_mode":"gundam","pdf_dpi":"200"}); upload_ms=round((time.perf_counter()-before)*1000)
            response.raise_for_status(); job_id=response.json()["id"]; health=[]; rss=[]; peak_vram=[]; seen={}
            while True:
                before=time.perf_counter(); client.get("/api/health").raise_for_status(); health.append(round((time.perf_counter()-before)*1000))
                job=client.get(f"/api/ocr/jobs/{job_id}").json(); pages=client.get(f"/api/ocr/jobs/{job_id}/pages").json()["pages"]; worker=client.get("/api/system/worker").json(); rss.append(worker["process_rss_bytes"]); peak_vram.append(worker["allocated_vram_bytes"])
                for page in pages:
                    if page["status"]=="COMPLETED": seen[page["page_number"]]=seen.get(page["page_number"],0)+1
                if job["status"] in {"COMPLETED","FAILED","CANCELLED","COMPLETED_WITH_ERRORS"}: break
                time.sleep(.1)
            total_ms=round((time.perf_counter()-started)*1000); integrity=client.get(f"/api/ocr/jobs/{job_id}/integrity").json()
        if job["status"]!="COMPLETED" or len(pages)!=args.pages or len({p["page_number"] for p in pages})!=args.pages or not integrity["valid"]: raise RuntimeError("soak validation failed")
        result={"job_id":job_id,"pages":args.pages,"upload_ms":upload_ms,"total_ms":total_ms,"render_ms":[p["render_duration_ms"] for p in pages],"inference_ms":[p["inference_duration_ms"] for p in pages],"peak_vram_mb":max(p["peak_allocated_vram_mb"] for p in pages),"peak_rss_bytes":max(rss),"health_p50_ms":statistics.median(health),"health_p95_ms":percentile(health,.95),"health_max_ms":max(health),"completed_page_records":len(seen),"integrity":integrity}; print(json.dumps(result,indent=2)); return 0
    except Exception as exc: print(f"PHASE4_SOAK_FAILED: {exc}",file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
