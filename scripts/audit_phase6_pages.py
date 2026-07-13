import json,sys
from pathlib import Path
sys.path.insert(0,'services/api')
from app.services.phase6_scoring import load_multi_page_ocr
paths=[Path('evaluation/outputs')/x for x in ('multi-page-01-150.md','multi-page-01-200.md','multi-page-01-300.md','multi-page-02-200.md')]
rows=[]
for p in paths:
 try:
  pages=load_multi_page_ocr(p);rows.append({'source_path':p.as_posix(),'pages_detected':len(pages),'page_numbers':[x.page_number for x in pages],'page_character_counts':{str(x.page_number):len(x.markdown) for x in pages},'issues':[]})
 except Exception as e:rows.append({'source_path':p.as_posix(),'pages_detected':0,'page_numbers':[],'page_character_counts':{},'issues':[str(e)]})
out={'valid':all(not x['issues'] for x in rows),'records':rows};Path('evaluation/reports/multi-page-extraction-audit.json').write_text(json.dumps(out,indent=2));sys.exit(0 if out['valid'] else 1)
