from io import BytesIO

from openpyxl import Workbook
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas

HEADERS = ["Voucher No", "Date", "Current Ledger", "Suggested Ledger", "Confidence", "Reason"]


def _values(row: dict) -> list:
    return [
        row.get("voucher_number", ""), row.get("date", ""), row.get("current_ledger", ""),
        row.get("suggested_ledger", ""), row.get("confidence", ""), row.get("reason", ""),
    ]


def excel_report(rows: list[dict]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Audit Report"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(_values(row))
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = min(max(len(str(cell.value or "")) for cell in column) + 2, 55)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def pdf_report(rows: list[dict]) -> bytes:
    buffer = BytesIO()
    page = landscape(letter)
    document = canvas.Canvas(buffer, pagesize=page)
    width, height = page

    def header() -> float:
        document.setFont("Helvetica-Bold", 16)
        document.drawString(36, height - 36, "Ledger Flash Audit Report")
        document.setFont("Helvetica-Bold", 8)
        document.drawString(36, height - 58, " | ".join(HEADERS))
        return height - 74

    y = header()
    document.setFont("Helvetica", 8)
    for row in rows:
        line = " | ".join(str(value)[:42] for value in _values(row))
        document.drawString(36, y, line[:180])
        y -= 14
        if y < 35:
            document.showPage()
            y = header()
            document.setFont("Helvetica", 8)
    document.save()
    return buffer.getvalue()
