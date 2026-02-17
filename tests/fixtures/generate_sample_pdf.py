# tests/fixtures/generate_sample_pdf.py
# Run this script to generate tests/fixtures/sample_curriculum.pdf
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from pathlib import Path

out = Path("tests/fixtures")
out.mkdir(parents=True, exist_ok=True)
p = out / "sample_curriculum.pdf"

c = canvas.Canvas(str(p), pagesize=letter)
c.setFont("Helvetica-Bold", 18)
c.drawString(72, 720, "Sample Curriculum - Grade 3 Science")
c.setFont("Helvetica", 12)
c.drawString(72, 690, "1. Life Cycles")
c.drawString(92, 670, "- Describe stages of life cycle of plant and animal")
c.drawString(72, 650, "2. Photosynthesis")
c.drawString(92, 630, "- Understand basic process of photosynthesis")
c.showPage()
c.setFont("Helvetica-Bold", 16)
c.drawString(72, 720, "Session 2 - Genetics")
c.drawString(72, 700, "1. Inheritance basics")
c.drawString(92, 680, "- Recognize traits passed from parents")
c.save()
print("Generated:", p)
