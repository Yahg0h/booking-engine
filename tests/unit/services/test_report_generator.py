"""Unit tests for PDF and CSV report generation."""

from datetime import datetime, timezone
from io import BytesIO, StringIO

import pandas as pd

from app.api.v1.services.report_generator import generate_csv_report, generate_pdf_report


def _report_data() -> dict:
    return {
        "metadata": {
            "report_title": "Appointments Report",
            "generated_at": datetime(2025, 2, 1, 12, 30, tzinfo=timezone.utc),
            "organization_id": 23,
            "period": {
                "start_date": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "end_date": datetime(2025, 2, 1, tzinfo=timezone.utc),
            },
            "filters_applied": {"professional_id": 7, "customer_id": None},
        },
        "summary": {"total_appointments": 2, "total_revenue": 175.5},
        "data": pd.DataFrame([
            {"appointment_id": 1, "customer_email": "one@example.com", "procedure_price": 100.0},
            {"appointment_id": 2, "customer_email": "two@example.com", "procedure_price": 75.5},
        ]),
    }


def test_generate_pdf_report_returns_valid_pdf_buffer():
    result = generate_pdf_report(_report_data())

    assert isinstance(result, BytesIO)
    assert result.tell() == 0
    assert result.read().startswith(b"%PDF-")


def test_generate_csv_report_includes_metadata_summary_and_data():
    result = generate_csv_report(_report_data())

    assert isinstance(result, StringIO)
    assert result.tell() == 0
    content = result.read()

    assert "Report: Appointments Report" in content
    assert "Organization ID: 23" in content
    assert "Period: 2025-01-01 to 2025-02-01" in content
    assert "Professional Id: 7" in content
    assert "Customer Id" not in content
    assert "Total Appointments,2" in content
    assert "Total Revenue,175.5" in content
    assert "appointment_id,customer_email,procedure_price" in content
    assert "1,one@example.com,100.0" in content
    assert "2,two@example.com,75.5" in content
