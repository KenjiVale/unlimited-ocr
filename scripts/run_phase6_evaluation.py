from __future__ import annotations
import json,time,sys
from pathlib import Path
import httpx
M=json.loads(Path("evaluation/manifest.json").read_text()); out=Path("evaluation/outputs"); out.mkdir(exist_ok=True,parents=True)
subset={"clean-digital","scanned-print","low-resolution","tables","bilingual","multi-page"}; rows=[]
def run(doc,dpi):
  with httpx.Client(base_url="http://127.0.0.1:8000",timeout=60) as c:
    start=time.perf_counter()
    with Path(doc["input_path"]).open("rb") as f: r=c.post("/api/ocr/jobs",files={"file":(f.name,f,"application/pdf" if doc["file_type"]=="pdf" else "image/png")},data={"ocr_mode":"gundam","pdf_dpi":str(dpi)}); r.raise_for_status(); jid=r.json()["id"]
    while True:
      j=c.get(f"/api/ocr/jobs/{jid}").json()
      if j["status"] in {"COMPLETED","COMPLETED_WITH_ERRORS","FAILED","CANCELLED"}: break
      time.sleep(.25)
    integrity=c.get(f"/api/ocr/jobs/{jid}/integrity").json(); result=c.get(f"/api/ocr/jobs/{jid}/result").json() if j.get("result_available") else {}
  (out/f"{doc['id']}-{dpi}.md").write_text(result.get("markdown",""),encoding="utf-8")
  return {"evaluation_id":"phase6","document_id":doc["id"],"category":doc["category"],"status":j["status"],"dpi":dpi,"mode":"gundam","markdown":result.get("markdown",""),"duration_ms":j.get("processing_duration_ms"),"peak_vram_mb":result.get("peak_allocated_vram_mb"),"integrity_valid":integrity.get("valid"),"page_success_rate":j.get("successful_pages",0)/max(j.get("total_pages",1),1),"issues":[]}
for d in M: rows.append(run(d,200))
for d in M:
  if d["category"] in subset:
    for dpi in (150,300): rows.append(run(d,dpi))
Path("evaluation/reports/raw-results.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
print(json.dumps({"runs":len(rows)}))
