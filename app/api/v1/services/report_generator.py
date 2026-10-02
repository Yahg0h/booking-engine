"""
Generates PDF and CSV reports from report data.
"""

from io import BytesIO, StringIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


def generate_pdf_report(report_data: dict) -> BytesIO:
    """
    Generates a PDF report from report data with metadata and summary.

    Args:
        report_data: dict with metadata, summary, and data DataFrame

    Returns:
        BytesIO object containing PDF
    """
    metadata = report_data["metadata"]
    summary = report_data["summary"]

    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=12,
        alignment=1  # Center
    )

    # Title
    elements.append(Paragraph(metadata["report_title"], title_style))
    elements.append(Spacer(1, 0.2*inch))

    # Metadata section
    metadata_lines = [
        f"<b>Generated:</b> {metadata['generated_at'].strftime('%Y-%m-%d %H:%M:%S')}",
        f"<b>Organization ID:</b> {metadata['organization_id'] or 'Global'}",
        f"<b>Period:</b> {metadata['period']['start_date'].strftime('%Y-%m-%d')} to {metadata['period']['end_date'].strftime('%Y-%m-%d')}"
    ]

    # Add applied filters to metadata
    if metadata.get('filters_applied'):
        filters_applied = metadata['filters_applied']
        for key, value in filters_applied.items():
            if value is not None:
                filter_name = key.replace('_', ' ').title()
                metadata_lines.append(f"<b>{filter_name}:</b> {value}")

    metadata_text = "<br/>".join(metadata_lines)
    elements.append(Paragraph(metadata_text, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))

    # Summary section
    elements.append(Paragraph("<b>Summary</b>", styles['Heading2']))
    summary_text = "<br/>".join([f"<b>{k.replace('_', ' ').title()}:</b> {v}" for k, v in summary.items()])
    elements.append(Paragraph(summary_text, styles['Normal']))

    doc.build(elements)
    pdf_buffer.seek(0)
    return pdf_buffer


def generate_csv_report(report_data: dict) -> StringIO:
    """
    Generates a CSV report from report data.

    Args:
        report_data: dict with metadata, summary, and data DataFrame

    Returns:
        StringIO object containing CSV
    """
    metadata = report_data["metadata"]
    summary = report_data["summary"]
    df = report_data["data"]

    csv_buffer = StringIO()

    # Write metadata
    csv_buffer.write(f"Report: {metadata['report_title']}\n")
    csv_buffer.write(f"Generated: {metadata['generated_at'].strftime('%Y-%m-%d %H:%M:%S')}\n")
    csv_buffer.write(f"Organization ID: {metadata['organization_id'] or 'Global'}\n")
    csv_buffer.write(f"Period: {metadata['period']['start_date'].strftime('%Y-%m-%d')} to {metadata['period']['end_date'].strftime('%Y-%m-%d')}\n")

    # Write applied filters
    if metadata.get('filters_applied'):
        filters_applied = metadata['filters_applied']
        for key, value in filters_applied.items():
            if value is not None:
                filter_name = key.replace('_', ' ').title()
                csv_buffer.write(f"{filter_name}: {value}\n")

    csv_buffer.write("\n")

    # Write summary
    csv_buffer.write("Summary\n")
    for key, value in summary.items():
        csv_buffer.write(f"{key.replace('_', ' ').title()},{value}\n")
    csv_buffer.write("\n")

    # Write data
    csv_buffer.write("Detailed Data\n")
    df.to_csv(csv_buffer, index=False)

    csv_buffer.seek(0)
    return csv_buffer