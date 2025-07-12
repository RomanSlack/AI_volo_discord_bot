import os
import tempfile

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def add_parchment_background(c, doc):
    """Draw the parchment background on each page."""
    background_path = os.path.join('assets', 'parchment_background.jpg')
    c.drawImage(background_path, 0, 0, width=A4[0], height=A4[1], mask='auto')

async def pdf_generator(transcriptions, logo_path=None):
    """
    Generates a clean PDF with transcribed text, one line per utterance.
    
    :param transcriptions: List of transcription strings.
    :param logo_path: Optional path to a logo image to include in the PDF.
    :return: Path to the generated PDF file.
    """
    # Ensure the logs directory exists
    logs_dir = "./.logs/pdfs"
    os.makedirs(logs_dir, exist_ok=True)

    # Create a temporary file in the logs directory
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=logs_dir) as tmp_file:
        pdf_file_path = tmp_file.name

    # Set up the PDF document with standard margins
    doc = SimpleDocTemplate(pdf_file_path, pagesize=A4,
                            leftMargin=1 * inch, rightMargin=1 * inch, topMargin=1 * inch, bottomMargin=1 * inch)
    elements = []

    # Professional title style
    title_style = ParagraphStyle(
        name="Title",
        fontName="Helvetica-Bold",
        fontSize=20,
        alignment=1,  # Center the title
        textColor=colors.black,
        spaceAfter=24,
    )

    # Content text style
    content_style = ParagraphStyle(
        name="Content",
        fontName="Times-Roman",
        fontSize=11,
        leading=16,
        spaceAfter=8,
    )

    # Title of the document
    title = Paragraph("Meeting Transcription", title_style)
    elements.append(title)
    elements.append(Spacer(1, 24))

    # Add the transcriptions - simple text lines
    for transcription in transcriptions:
        if transcription and transcription.strip():
            # Each transcription is just a line of text
            line = Paragraph(transcription.strip(), content_style)
            elements.append(line)

    # Build the PDF without background
    doc.build(elements)

    return pdf_file_path
