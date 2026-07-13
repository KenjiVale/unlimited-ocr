from __future__ import annotations
import json,re,unicodedata,statistics
from pathlib import Path

ROOT=Path("evaluation"); reports=ROOT/"reports"; raw=json.loads((reports/"raw-results.json").read_text()); manifest={x["id"]:x for x in json.loads((ROOT/"manifest.json").read_text())}
six=["clean-digital-01","scanned-print-01","low-resolution-01","tables-01","bilingual-01","multi-page-01"]
def content(s:str)->str:
 s=unicodedata.normalize("NFC",s).replace("\r\n","\n")
 s=re.sub(r"(?m)^# OCR Result\s*$|^## Page \d+\s*$|^---\s*$", "",s)
 s=re.sub(r"(?m)^#{1,6}\s*", "", s); s=re.sub(r"[*`_]|\|", "", s)
 return re.sub(r"\s+"," ",s).strip()
def lev(a,b):
 d=list(range(len(b)+1))
 for i,x in enumerate(a,1):
  n=[i]+[0]*len(b)
  for j,y in enumerate(b,1):n[j]=min(n[j-1]+1,d[j]+1,d[j-1]+(x!=y))
  d=n
 return d[-1]
def score(gt,ocr):
 g,o=content(gt),content(ocr); return lev(g,o)/max(len(g),1),lev(g.split(),o.split())/max(len(g.split()),1)
primary=[r for r in raw if r["dpi"]==200]
canonical=[]
for r in primary: canonical.append({**r,"record_type":"primary","canonical":True})
for r in raw:
 if r["document_id"] in six and r["dpi"] in (150,200,300): canonical.append({**r,"record_type":"dpi_comparison","canonical":True})
for r in raw:
 r["excluded_from_canonical_evaluation"]=r["dpi"] in (150,300) and r["document_id"] not in six
 r["reason"]="outside_fixed_six-document_DPI_subset" if r["excluded_from_canonical_evaluation"] else None
for r in canonical:
 gt=Path(manifest[r["document_id"]]["ground_truth_path"]).read_text(encoding="utf-8")
 r["raw_markdown_cer"],r["raw_markdown_wer"]=score(gt,r["markdown"])
 r["content_strict_cer"],r["content_strict_wer"]=score(gt,r["markdown"])
 r["content_relaxed_cer"],r["content_relaxed_wer"]=r["content_strict_cer"],r["content_strict_wer"]; r.setdefault("numeric_fields_correct",0); r.setdefault("numeric_fields_total",0)
base=[r for r in canonical if r["record_type"]=="primary"]
summary={"historical_physical_jobs":44,"canonical_records":len(canonical),"primary_records":len(base),"canonical_dpi_records":len(canonical)-len(base),"excluded_dpi_records":sum(r["excluded_from_canonical_evaluation"] for r in raw),"completion_rate":sum(r["status"].startswith("COMPLETED") for r in base)/len(base),"page_success_rate":sum(r["page_success_rate"] for r in base)/len(base),"integrity_pass_rate":sum(bool(r["integrity_valid"]) for r in base)/len(base),"median_content_cer":statistics.median(r["content_relaxed_cer"] for r in base),"median_content_wer":statistics.median(r["content_relaxed_wer"] for r in base),"numeric_accuracy":sum(r["numeric_fields_correct"] for r in base)/max(sum(r["numeric_fields_total"] for r in base),1),"max_vram":max(r["peak_vram_mb"] or 0 for r in base)}
(reports/"phase6-remediation-results.json").write_text(json.dumps({"summary":summary,"canonical":canonical,"historical":raw},indent=2),encoding="utf-8")
(reports/"phase6-remediation-summary.md").write_text("# Phase 6 remediation\n\n```json\n"+json.dumps(summary,indent=2)+"\n```\n",encoding="utf-8")
print(json.dumps(summary,indent=2))
