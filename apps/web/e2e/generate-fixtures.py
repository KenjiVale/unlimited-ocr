from pathlib import Path
from PIL import Image, ImageDraw
import fitz

root = Path(__file__).parent / "fixtures"
root.mkdir(parents=True, exist_ok=True)
image = Image.new("RGB", (900, 500), "white")
draw = ImageDraw.Draw(image)
draw.text((80, 120), "Browser OCR Test Image", fill="black")
draw.text((80, 190), "Local GPU Offline Verification", fill="black")
image.save(root / "sample-image.png")
doc = fitz.open()
for number, text in enumerate(("Browser OCR Test", "Local GPU Verification", "Offline Processing Complete"), 1):
    page = doc.new_page(width=900, height=1200)
    page.insert_text((90, 180), f"Page {number} - {text}", fontsize=34)
    page.insert_text((90, 260), "Unlimited OCR Local browser acceptance fixture", fontsize=22)
doc.save(root / "sample-three-page.pdf")
doc.close()
