import os
import tempfile
from openai import OpenAI
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
import markdown
import re


async def generate_meeting_summary(transcription_file_path: str) -> str:
    """
    Generate a meeting summary using OpenAI API from a transcription file.
    
    :param transcription_file_path: Path to the transcription log file
    :return: Markdown formatted summary
    """
    # Read the transcription file
    try:
        with open(transcription_file_path, 'r', encoding='utf-8') as f:
            transcription_text = f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Transcription file not found: {transcription_file_path}")
    
    if not transcription_text:
        raise ValueError("Transcription file is empty")
    
    # Get OpenAI client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("MODEL_SUMMARY", "gpt-4o")
    
    # System prompt for meeting summarization
    system_prompt = """You are a professional meeting summarizer. Your task is to analyze meeting transcriptions and create comprehensive, well-structured summaries.

Create a summary in markdown format with the following sections:

# Meeting Summary

## Key Discussion Points
- List the main topics discussed with brief explanations

## Decisions Made
- Document any decisions that were reached during the meeting

## Action Items
- List specific tasks, assignments, or follow-ups mentioned
- Include responsible parties if mentioned

## Important Questions Raised
- Document significant questions that were discussed
- Note if they were resolved or need follow-up

## Next Steps
- Outline any planned future actions or meetings

## Additional Notes
- Include any other relevant information, insights, or context

Guidelines:
- Be concise but comprehensive
- Use professional language
- Focus on actionable content
- Maintain the logical flow of the discussion
- Use bullet points and clear formatting
- If speakers can be identified, include relevant attributions"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Please summarize this meeting transcription:\n\n{transcription_text}"}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        raise Exception(f"Failed to generate summary: {str(e)}")


async def markdown_to_pdf(markdown_content: str, output_filename: str = None) -> str:
    """
    Convert markdown content to a professional PDF report.
    
    :param markdown_content: Markdown formatted content
    :param output_filename: Optional custom filename
    :return: Path to generated PDF file
    """
    # Ensure the logs directory exists
    logs_dir = "./.logs/pdfs"
    os.makedirs(logs_dir, exist_ok=True)

    # Create output file
    if output_filename:
        pdf_file_path = os.path.join(logs_dir, output_filename)
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=logs_dir) as tmp_file:
            pdf_file_path = tmp_file.name

    # Set up the PDF document
    doc = SimpleDocTemplate(pdf_file_path, pagesize=A4,
                            leftMargin=1 * inch, rightMargin=1 * inch, 
                            topMargin=1 * inch, bottomMargin=1 * inch)
    elements = []

    # Define styles
    styles = {
        'title': ParagraphStyle(
            name="Title",
            fontName="Helvetica-Bold",
            fontSize=18,
            alignment=1,  # Center
            textColor=colors.black,
            spaceAfter=24,
        ),
        'heading': ParagraphStyle(
            name="Heading",
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=colors.black,
            spaceAfter=12,
            spaceBefore=12,
        ),
        'subheading': ParagraphStyle(
            name="SubHeading",
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=colors.black,
            spaceAfter=8,
            spaceBefore=8,
        ),
        'body': ParagraphStyle(
            name="Body",
            fontName="Times-Roman",
            fontSize=11,
            leading=14,
            spaceAfter=6,
        ),
        'bullet': ParagraphStyle(
            name="Bullet",
            fontName="Times-Roman",
            fontSize=11,
            leading=14,
            spaceAfter=4,
            leftIndent=20,
        ),
    }

    def process_markdown_text(text):
        """Convert markdown formatting to ReportLab markup"""
        # Bold text: **text** -> <b>text</b>
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        # Italic text: *text* -> <i>text</i>
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        # Code: `text` -> <font name="Courier">text</font>
        text = re.sub(r'`(.*?)`', r'<font name="Courier">\1</font>', text)
        return text
    
    # Parse markdown content
    lines = markdown_content.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            elements.append(Spacer(1, 6))
            continue
            
        # Handle headers
        if line.startswith('# '):
            text = process_markdown_text(line[2:].strip())
            elements.append(Paragraph(text, styles['title']))
        elif line.startswith('## '):
            text = process_markdown_text(line[3:].strip())
            elements.append(Paragraph(text, styles['heading']))
        elif line.startswith('### '):
            text = process_markdown_text(line[4:].strip())
            elements.append(Paragraph(text, styles['subheading']))
        # Handle bullet points
        elif line.startswith('- '):
            text = process_markdown_text(line[2:].strip())
            elements.append(Paragraph(f"• {text}", styles['bullet']))
        # Handle regular text
        else:
            if line:
                text = process_markdown_text(line)
                elements.append(Paragraph(text, styles['body']))

    # Build the PDF
    doc.build(elements)
    
    return pdf_file_path