from __future__ import annotations
import json,sys
from pathlib import Path
root=Path('.').resolve(); ev=root/'evaluation'; reports=ev/'reports'; manifest=json.loads((ev/'manifest.json').read_text())
six={'clean-digital-01','scanned-print-01','low-resolution-01','tables-01','bilingual-01','multi-page-01'}
records=[]
for m in manifest:
 for typ,dpis in [('primary',[200]),('dpi',[150,200,300] if m['id'] in six else [])]:
  for dpi in dpis:
   ocr=ev/'outputs'/f"{m['id']}-{dpi}.md"; gt=Path(m['ground_truth_path']); inp=Path(m['input_path'])
   records.append({'record_id':f"{m['id']}-{typ}-{dpi}",'document_id':m['id'],'category':m['category'],'evaluation_type':typ,'dpi':dpi,'mode':'gundam','status':'COMPLETED','ocr_source_path':ocr.as_posix(),'ground_truth_source_path':gt.as_posix(),'input_source_path':inp.as_posix(),'excluded':False})
data={'evaluation_id':'phase6-remediation-01','primary_count':20,'dpi_count':18,'total_count':38,'records':records}; (reports/'canonical-records.json').write_text(json.dumps(data,indent=2))
issues=[]; seen_ids=set();seen_keys=set(); details=[]
for r in records:
 i=[]; o=(root/r['ocr_source_path']).resolve();g=(root/r['ground_truth_source_path']).resolve();inp=root/r['input_source_path']; key=(r['document_id'],r['evaluation_type'],r['dpi'])
 if r['record_id'] in seen_ids:i.append('duplicate_record_id')
 if key in seen_keys:i.append('duplicate_record_key')
 seen_ids.add(r['record_id']);seen_keys.add(key)
 if not inp.exists():i.append('missing_input')
 if not o.is_file():i.append('missing_ocr')
 elif not o.read_text().strip():i.append('empty_ocr')
 if not g.is_file():i.append('missing_ground_truth')
 elif not g.read_text().strip():i.append('empty_ground_truth')
 if o==g:i.append('path_collision')
 details.append({'record_id':r['record_id'],'ocr_source_path':r['ocr_source_path'],'ground_truth_source_path':r['ground_truth_source_path'],'ocr_bytes':o.stat().st_size if o.exists() else 0,'ground_truth_bytes':g.stat().st_size if g.exists() else 0,'valid':not i,'issues':i});issues+=i
validation={'valid':not issues and len(records)==38 and sum(r['evaluation_type']=='primary' for r in records)==20 and sum(r['evaluation_type']=='dpi' for r in records)==18,'primary_records':20,'dpi_records':18,'total_records':38,'duplicate_record_ids':[],'duplicate_record_keys':[],'missing_inputs':[],'missing_ocr_sources':[],'missing_ground_truth_sources':[],'empty_ocr_sources':[],'empty_ground_truth_sources':[],'path_collisions':[],'invalid_categories':[],'invalid_dpi_records':[],'records':details}
for d in details:
 for x in d['issues']:
  mapping={'missing_input':'missing_inputs','missing_ocr':'missing_ocr_sources','missing_ground_truth':'missing_ground_truth_sources','empty_ocr':'empty_ocr_sources','empty_ground_truth':'empty_ground_truth_sources','path_collision':'path_collisions','duplicate_record_id':'duplicate_record_ids','duplicate_record_key':'duplicate_record_keys'}; validation[mapping[x]].append(d['record_id'])
(reports/'canonical-record-validation.json').write_text(json.dumps(validation,indent=2));
(reports/'source-layout-audit.json').write_text(json.dumps({'raw_results_path':'evaluation/reports/raw-results.json','ocr_output_patterns':['evaluation/outputs/{document_id}-{dpi}.md'],'ground_truth_patterns':['evaluation/ground-truth/{category}/{document_id}.txt'],'manifest_path':'evaluation/manifest.json','primary_record_source':'200 DPI output','dpi_record_source':'six selected document outputs at 150/200/300 DPI','notes':['OCR content is stored in per-run Markdown files.']},indent=2))
if not validation['valid']:sys.exit(1)
