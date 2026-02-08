"""
PDF/Image Simulation (Phase 4 Fix #4)

Simulates PDF and image artifacts from curriculum documents.
Used for testing OCR extraction pipelines.

Dependencies (OPTIONAL - graceful degradation):
- wkhtmltopdf: System binary for HTML->PDF (preferred)
- reportlab: Python PDF library (fallback)
- PIL/Pillow: Image generation

If no PDF backend available, returns markdown-only simulation.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Literal
import tempfile


class PDFBackend(str, Enum):
    """Available PDF generation backends."""
    WKHTMLTOPDF = "wkhtmltopdf"
    REPORTLAB = "reportlab"
    MARKDOWN_ONLY = "markdown_only"  # Fallback


class ImageBackend(str, Enum):
    """Available image generation backends."""
    PILLOW = "pillow"
    NONE = "none"  # Fallback


@dataclass
class PDFSimulatorConfig:
    """Configuration for PDF simulation."""
    output_dir: Path = field(default_factory=lambda: Path(tempfile.gettempdir()) / "synthetic_pdfs")
    dpi: int = 150
    page_width_mm: int = 210  # A4
    page_height_mm: int = 297  # A4
    font_size: int = 12
    add_scan_artifacts: bool = False  # Simulate scanned document
    add_watermarks: bool = False
    pdf_backend: PDFBackend | None = None  # Auto-detect if None


# =============================================================================
# BACKEND AVAILABILITY DETECTION
# =============================================================================

def _check_wkhtmltopdf() -> bool:
    """Check if wkhtmltopdf is available in PATH."""
    import subprocess
    try:
        result = subprocess.run(
            ["wkhtmltopdf", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _check_reportlab() -> bool:
    """Check if reportlab is installed."""
    try:
        import reportlab  # noqa: F401
        return True
    except ImportError:
        return False


def _check_pillow() -> bool:
    """Check if PIL/Pillow is installed."""
    try:
        from PIL import Image  # noqa: F401
        return True
    except ImportError:
        return False


def get_available_pdf_backend() -> PDFBackend:
    """Detect best available PDF backend."""
    if _check_wkhtmltopdf():
        return PDFBackend.WKHTMLTOPDF
    if _check_reportlab():
        return PDFBackend.REPORTLAB
    return PDFBackend.MARKDOWN_ONLY


def get_available_image_backend() -> ImageBackend:
    """Detect best available image backend."""
    if _check_pillow():
        return ImageBackend.PILLOW
    return ImageBackend.NONE


AVAILABLE_PDF_BACKEND = get_available_pdf_backend()
AVAILABLE_IMAGE_BACKEND = get_available_image_backend()


def is_pdf_available() -> bool:
    """Check if full PDF simulation is available."""
    return AVAILABLE_PDF_BACKEND != PDFBackend.MARKDOWN_ONLY


def is_image_available() -> bool:
    """Check if image simulation is available."""
    return AVAILABLE_IMAGE_BACKEND != ImageBackend.NONE


# =============================================================================
# PDF SIMULATOR
# =============================================================================

@dataclass
class SimulatedDocument:
    """Result of document simulation."""
    content_type: Literal["pdf", "image", "markdown"]
    file_path: Path | None
    content_bytes: bytes | None
    original_markdown: str
    backend_used: str


class PDFSimulator:
    """
    Generates simulated PDF documents from curriculum markdown.
    
    Supports multiple backends with graceful degradation.
    """
    
    def __init__(self, config: PDFSimulatorConfig | None = None):
        """Initialize with configuration."""
        self.config = config or PDFSimulatorConfig()
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Auto-detect backend if not specified
        if self.config.pdf_backend is None:
            self.config.pdf_backend = get_available_pdf_backend()
    
    def simulate_pdf(
        self,
        markdown_content: str,
        filename: str = "curriculum",
    ) -> SimulatedDocument:
        """
        Generate a simulated PDF from markdown content.
        
        Args:
            markdown_content: Curriculum content in markdown
            filename: Base filename (without extension)
            
        Returns:
            SimulatedDocument with PDF bytes and path
        """
        if self.config.pdf_backend == PDFBackend.WKHTMLTOPDF:
            return self._simulate_with_wkhtmltopdf(markdown_content, filename)
        elif self.config.pdf_backend == PDFBackend.REPORTLAB:
            return self._simulate_with_reportlab(markdown_content, filename)
        else:
            return self._fallback_markdown_only(markdown_content, filename)
    
    def _simulate_with_wkhtmltopdf(
        self,
        markdown: str,
        filename: str,
    ) -> SimulatedDocument:
        """Generate PDF using wkhtmltopdf."""
        import subprocess
        
        # Convert markdown to simple HTML
        html_content = self._markdown_to_html(markdown)
        
        # Write temp HTML
        html_path = self.config.output_dir / f"{filename}.html"
        pdf_path = self.config.output_dir / f"{filename}.pdf"
        
        html_path.write_text(html_content, encoding="utf-8")
        
        try:
            subprocess.run(
                [
                    "wkhtmltopdf",
                    "--quiet",
                    "--page-size", "A4",
                    "--margin-top", "20mm",
                    "--margin-bottom", "20mm",
                    "--margin-left", "20mm",
                    "--margin-right", "20mm",
                    str(html_path),
                    str(pdf_path),
                ],
                check=True,
                timeout=30,
            )
            
            pdf_bytes = pdf_path.read_bytes()
            
            return SimulatedDocument(
                content_type="pdf",
                file_path=pdf_path,
                content_bytes=pdf_bytes,
                original_markdown=markdown,
                backend_used="wkhtmltopdf",
            )
        except subprocess.CalledProcessError:
            # Fall back to reportlab or markdown
            if _check_reportlab():
                return self._simulate_with_reportlab(markdown, filename)
            return self._fallback_markdown_only(markdown, filename)
    
    def _simulate_with_reportlab(
        self,
        markdown: str,
        filename: str,
    ) -> SimulatedDocument:
        """Generate PDF using reportlab."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.units import mm
        except ImportError:
            return self._fallback_markdown_only(markdown, filename)
        
        pdf_path = self.config.output_dir / f"{filename}.pdf"
        
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            leftMargin=20*mm,
            rightMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm,
        )
        
        styles = getSampleStyleSheet()
        
        # Custom styles for curriculum content
        title_style = ParagraphStyle(
            'CurriculumTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=12,
        )
        heading_style = ParagraphStyle(
            'CurriculumHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=8,
        )
        body_style = styles['Normal']
        
        # Parse markdown into paragraphs
        story = []
        lines = markdown.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 6*mm))
            elif line.startswith('# '):
                story.append(Paragraph(line[2:], title_style))
            elif line.startswith('## '):
                story.append(Paragraph(line[3:], heading_style))
            elif line.startswith('- '):
                story.append(Paragraph(f"• {line[2:]}", body_style))
            else:
                story.append(Paragraph(line, body_style))
        
        doc.build(story)
        pdf_bytes = pdf_path.read_bytes()
        
        return SimulatedDocument(
            content_type="pdf",
            file_path=pdf_path,
            content_bytes=pdf_bytes,
            original_markdown=markdown,
            backend_used="reportlab",
        )
    
    def _fallback_markdown_only(
        self,
        markdown: str,
        filename: str,
    ) -> SimulatedDocument:
        """Fallback when no PDF backend available."""
        md_path = self.config.output_dir / f"{filename}.md"
        md_path.write_text(markdown, encoding="utf-8")
        
        return SimulatedDocument(
            content_type="markdown",
            file_path=md_path,
            content_bytes=markdown.encode("utf-8"),
            original_markdown=markdown,
            backend_used="markdown_only",
        )
    
    def _markdown_to_html(self, markdown: str) -> str:
        """Convert markdown to simple HTML."""
        lines = []
        lines.append("<!DOCTYPE html>")
        lines.append("<html><head><meta charset='utf-8'>")
        lines.append("<style>body{font-family:Arial,sans-serif;margin:2em;}")
        lines.append("h1{color:#333;}h2{color:#555;}</style></head><body>")
        
        for line in markdown.split('\n'):
            line = line.strip()
            if not line:
                lines.append("<br>")
            elif line.startswith('# '):
                lines.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith('## '):
                lines.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith('### '):
                lines.append(f"<h3>{line[4:]}</h3>")
            elif line.startswith('- '):
                lines.append(f"<li>{line[2:]}</li>")
            else:
                lines.append(f"<p>{line}</p>")
        
        lines.append("</body></html>")
        return '\n'.join(lines)


# =============================================================================
# IMAGE SIMULATOR
# =============================================================================

class ImageSimulator:
    """
    Generates simulated images from curriculum content.
    
    Creates images that look like scanned documents for OCR testing.
    """
    
    def __init__(self, config: PDFSimulatorConfig | None = None):
        """Initialize with configuration."""
        self.config = config or PDFSimulatorConfig()
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
    
    def simulate_scanned_page(
        self,
        markdown_content: str,
        filename: str = "scan",
        add_noise: bool = True,
    ) -> SimulatedDocument:
        """
        Generate a simulated scanned page image.
        
        Args:
            markdown_content: Text content
            filename: Output filename
            add_noise: Add scan artifacts
            
        Returns:
            SimulatedDocument with image
        """
        if not is_image_available():
            return SimulatedDocument(
                content_type="markdown",
                file_path=None,
                content_bytes=markdown_content.encode("utf-8"),
                original_markdown=markdown_content,
                backend_used="none",
            )
        
        from PIL import Image, ImageDraw, ImageFont
        import random
        
        # Create image
        width = int(self.config.page_width_mm * self.config.dpi / 25.4)
        height = int(self.config.page_height_mm * self.config.dpi / 25.4)
        
        # Off-white background (like scanned paper)
        bg_color = (252, 250, 245) if add_noise else (255, 255, 255)
        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Try to use a system font
        try:
            font = ImageFont.truetype("arial.ttf", self.config.font_size * 2)
        except OSError:
            font = ImageFont.load_default()
        
        # Render text
        y_pos = 100
        for line in markdown_content.split('\n'):
            line = line.strip()
            if line.startswith('# '):
                line = line[2:].upper()
            elif line.startswith('## '):
                line = line[3:]
            elif line.startswith('- '):
                line = f"  • {line[2:]}"
            
            if line:
                text_color = (30, 30, 30) if not add_noise else (
                    random.randint(20, 50),
                    random.randint(20, 50),
                    random.randint(20, 50),
                )
                draw.text((80, y_pos), line, fill=text_color, font=font)
            y_pos += 40
            
            if y_pos > height - 100:
                break
        
        # Add scan artifacts if requested
        if add_noise:
            self._add_scan_noise(img)
        
        # Save
        img_path = self.config.output_dir / f"{filename}.png"
        img.save(img_path, "PNG")
        
        img_bytes = img_path.read_bytes()
        
        return SimulatedDocument(
            content_type="image",
            file_path=img_path,
            content_bytes=img_bytes,
            original_markdown=markdown_content,
            backend_used="pillow",
        )
    
    def _add_scan_noise(self, img: "Image.Image"):
        """Add realistic scan noise to image."""
        import random
        from PIL import ImageDraw
        
        draw = ImageDraw.Draw(img)
        width, height = img.size
        
        # Add subtle speckles
        for _ in range(100):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            gray = random.randint(200, 230)
            draw.point((x, y), fill=(gray, gray, gray))
        
        # Add a few larger spots (like paper imperfections)
        for _ in range(5):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            r = random.randint(2, 5)
            gray = random.randint(210, 240)
            draw.ellipse(
                [x - r, y - r, x + r, y + r],
                fill=(gray, gray, gray),
            )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def simulate_curriculum_pdf(
    markdown_content: str,
    filename: str = "curriculum",
    output_dir: Path | None = None,
) -> SimulatedDocument:
    """
    Convenience function to simulate a curriculum PDF.
    
    Uses best available backend automatically.
    """
    config = PDFSimulatorConfig()
    if output_dir:
        config.output_dir = output_dir
    
    simulator = PDFSimulator(config)
    return simulator.simulate_pdf(markdown_content, filename)


def simulate_scanned_document(
    markdown_content: str,
    filename: str = "scan",
    add_noise: bool = True,
    output_dir: Path | None = None,
) -> SimulatedDocument:
    """
    Convenience function to simulate a scanned document image.
    
    Uses Pillow if available.
    """
    config = PDFSimulatorConfig()
    if output_dir:
        config.output_dir = output_dir
    
    simulator = ImageSimulator(config)
    return simulator.simulate_scanned_page(markdown_content, filename, add_noise)
