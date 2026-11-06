"""Render the visible annual-summary snapshot without recalculating financial data."""
from __future__ import annotations

import io
from typing import Any

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Spacer

from .report_pdf import _paragraph, _styles, _table


def build_dividend_summary_pdf(payload: dict[str, Any]) -> bytes:
    language = payload.get("language", "en")
    if language not in {"en", "he"}:
        raise ValueError("Invalid summary language")
    columns = payload.get("columns")
    rows = payload.get("rows")
    title = payload.get("title")
    context = payload.get("context", "")
    if not isinstance(title, str) or not title or len(title) > 200:
        raise ValueError("Invalid summary title")
    if not isinstance(context, str) or len(context) > 2000:
        raise ValueError("Invalid summary context")
    if not isinstance(columns, list) or len(columns) != 6 or not all(isinstance(value, str) and len(value) <= 150 for value in columns):
        raise ValueError("Invalid summary columns")
    if not isinstance(rows, list) or not rows or len(rows) > 2000:
        raise ValueError("Summary export requires between 1 and 2000 rows")
    if any(not isinstance(row, list) or len(row) != 6 or any(not isinstance(value, str) or len(value) > 2000 for value in row) for row in rows):
        raise ValueError("Invalid summary rows")
    styles = _styles(language)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=12*mm, leftMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm, title=title)
    width = landscape(A4)[0] - 24*mm
    all_rows = [columns, *rows]
    weights = [1.45, 1, 1, 1, 1, 1.1]
    if language == "he":
        all_rows = [list(reversed(row)) for row in all_rows]
        weights.reverse()
    table = _table(all_rows, [width * weight / sum(weights) for weight in weights], styles)
    elements = [_paragraph(title, styles["h2"]), _paragraph(context, styles["small"]), Spacer(1, 4*mm), table]
    doc.build(elements)
    return buffer.getvalue()
