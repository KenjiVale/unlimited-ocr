from __future__ import annotations
import json
from pathlib import Path
import fitz
from PIL import Image, ImageDraw

ROOT=Path("evaluation"); fixtures=ROOT/"fixtures"; truth=ROOT/"ground-truth"
categories=[("clean-digital","Clean Digital Heading\nThis document verifies clear digital text."),("scanned-print","Scanned Printed Document\nPrinted paragraph with stable spacing."),("low-resolution","Low Resolution Sample\nSmall text 12345."),("rotated","Slight Rotation Sample\nRotate this printed page two degrees."),("multi-column","Left Column A\nLeft Column B\nRight Column A\nRight Column B"),("tables","Item Quantity Price\nPaper 2 15000\nInk 1 45000"),("invoice-receipt","INVOICE 2026-001\nDate 12 July 2026\nTotal Rp 125000"),("bilingual","Halo world\nDokumen Indonesian and English."),("numeric","Order 98765\nDate 2026-07-12\nAmount Rp 1,250,000\nTax 11%"),("multi-page","Multi Page One\nSecond page follows\nThird page ends.")]
manifest=[]
for cat,text in categories:
  (fixtures/cat).mkdir(parents=True,exist_ok=True); (truth/cat).mkdir(parents=True,exist_ok=True)
  for n in (1,2):
    docid=f"{cat}-{n:02d}"; content=text+f"\nSample {n}."
    gt=truth/cat/f"{docid}.txt"; gt.write_text(content,encoding="utf-8")
    if cat in {"low-resolution","rotated"}:
      im=Image.new("RGB",(900,500),"white"); d=ImageDraw.Draw(im); d.text((60,80),content,fill="black",spacing=12)
      if cat=="low-resolution": im.resize((300,167)).save(fixtures/cat/f"{docid}.png")
      else: im.rotate(2,expand=True,fillcolor="white").save(fixtures/cat/f"{docid}.png")
      ftype="image"; pages=1
    else:
      pdf=fitz.open(); count=3 if cat=="multi-page" else 1
      for p in range(count):
        page=pdf.new_page(width=800,height=1000); page.insert_text((70,120),content if count==1 else f"{content}\nPage {p+1}",fontsize=20)
      path=fixtures/cat/f"{docid}.pdf"; pdf.save(path); pdf.close(); ftype="pdf"; pages=count
    manifest.append({"id":docid,"category":cat,"input_path":str((fixtures/cat/(f"{docid}.png" if ftype=="image" else f"{docid}.pdf")).as_posix()),"ground_truth_path":str(gt.as_posix()),"file_type":ftype,"page_count":pages,"language":["id","en"],"contains_table":cat=="tables","contains_columns":cat=="multi-column","expected_difficulty":"hard" if cat in {"low-resolution","rotated","multi-column"} else "easy"})
(ROOT/"outputs").mkdir(parents=True,exist_ok=True); (ROOT/"reports").mkdir(parents=True,exist_ok=True)
(ROOT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
