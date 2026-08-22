from __future__ import annotations

import html
import io
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


_INK = colors.HexColor("#172033")
_MUTED = colors.HexColor("#5c6980")
_BORDER = colors.HexColor("#d7deea")
_PANEL = colors.HexColor("#f5f7fb")
_ACCENT = colors.HexColor("#4f46e5")

_HE = {
    "Portfolio report": "דוח תיק השקעות",
    "Entire portfolio": "כל התיק",
    "All people": "כל האנשים",
    "All account categories": "כל קטגוריות החשבון",
    "All locations": "כל המיקומים",
    "Generated": "הופק",
    "Report scope": "היקף הדוח",
    "People": "אנשים",
    "Account category": "קטגוריית חשבון",
    "Location": "מיקום",
    "Period": "תקופה",
    "Accounts": "חשבונות",
    "Holdings": "אחזקות",
    "Linked funds": "קופות מקושרות",
    "Accounts included": "חשבונות שנכללו",
    "Account": "חשבון",
    "Owners": "בעלים",
    "Cash": "מזומן",
    "Securities": "ניירות ערך",
    "Total value": "שווי כולל",
    "Profit": "רווח",
    "No accounts match the selected report filters.": "אין חשבונות התואמים למסנני הדוח שנבחרו.",
    "Account details": "פרטי חשבון",
    "No holdings in this account.": "אין אחזקות בחשבון זה.",
    "Symbol": "סמל",
    "Name": "שם",
    "Asset class": "סוג נכס",
    "Quantity": "כמות",
    "Value": "שווי",
    "Long-term funds": "קופות לטווח ארוך",
    "Fund": "קופה",
    "Kind": "סוג",
    "Amount": "סכום",
    "Monthly estimate": "אומדן חודשי",
    "Account history": "היסטוריית חשבון",
    "From": "מתאריך",
    "To": "עד תאריך",
    "Starting value": "שווי התחלתי",
    "Ending value": "שווי סופי",
    "Profit %": "רווח %",
    "No saved history in this period.": "אין היסטוריה שמורה בתקופה זו.",
    "Amounts are shown in each account's native currency.": "הסכומים מוצגים במטבע המקורי של כל חשבון.",
    "Page": "עמוד",
}


def _tr(value: str, language: str) -> str:
    return _HE.get(value, value) if language == "he" else value


def _contains_rtl(value: str) -> bool:
    return any("\u0590" <= char <= "\u08ff" for char in value)


def _display(value: Any) -> str:
    text = str(value if value is not None else "")
    return get_display(text) if _contains_rtl(text) else text


@lru_cache(maxsize=1)
def _register_fonts() -> tuple[str, str]:
    regular_candidates = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansHebrew-Regular.ttf"),
    )
    bold_candidates = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansHebrew-Bold.ttf"),
    )
    regular = next((path for path in regular_candidates if path.exists()), None)
    bold = next((path for path in bold_candidates if path.exists()), None)
    if not regular:
        return "Helvetica", "Helvetica-Bold"
    pdfmetrics.registerFont(TTFont("PortfolioSans", str(regular)))
    pdfmetrics.registerFont(TTFont("PortfolioSansBold", str(bold or regular)))
    return "PortfolioSans", "PortfolioSansBold"


def _paragraph(value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(html.escape(_display(value)).replace("\n", "<br/>"), style)


def _date_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], pattern).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return text


def _number(value: Any, digits: int = 2) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "-"
    return f"{number:,.{digits}f}"


def _money(value: Any, currency: Any) -> str:
    return f"{str(currency or '').upper()} {_number(value)}".strip()


def _styles(language: str) -> dict[str, ParagraphStyle]:
    regular, bold = _register_fonts()
    base = getSampleStyleSheet()
    alignment = TA_RIGHT if language == "he" else TA_LEFT
    return {
        "title": ParagraphStyle(
            "PortfolioReportTitle",
            parent=base["Title"],
            fontName=bold,
            fontSize=23,
            leading=28,
            textColor=_INK,
            alignment=alignment,
            spaceAfter=5 * mm,
        ),
        "h2": ParagraphStyle(
            "PortfolioReportH2",
            parent=base["Heading2"],
            fontName=bold,
            fontSize=13,
            leading=17,
            textColor=_INK,
            alignment=alignment,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
        ),
        "h3": ParagraphStyle(
            "PortfolioReportH3",
            parent=base["Heading3"],
            fontName=bold,
            fontSize=11,
            leading=14,
            textColor=_INK,
            alignment=alignment,
            spaceBefore=3 * mm,
            spaceAfter=1.5 * mm,
        ),
        "body": ParagraphStyle(
            "PortfolioReportBody",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=8.4,
            leading=11.2,
            textColor=_INK,
            alignment=alignment,
        ),
        "small": ParagraphStyle(
            "PortfolioReportSmall",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=7.3,
            leading=9.5,
            textColor=_MUTED,
            alignment=alignment,
        ),
        "table_header": ParagraphStyle(
            "PortfolioReportTableHeader",
            parent=base["BodyText"],
            fontName=bold,
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
            alignment=alignment,
        ),
        "table": ParagraphStyle(
            "PortfolioReportTable",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=7.2,
            leading=9,
            textColor=_INK,
            alignment=alignment,
        ),
    }


def _table(
    rows: list[list[Any]],
    widths: list[float],
    styles: dict[str, ParagraphStyle],
    *,
    header: bool = True,
) -> Table:
    prepared: list[list[Paragraph]] = []
    for row_index, row in enumerate(rows):
        style = styles["table_header"] if header and row_index == 0 else styles["table"]
        prepared.append([_paragraph(value, style) for value in row])
    table = Table(prepared, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.45, _BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, _PANEL]),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _INK),
                ("LINEBELOW", (0, 0), (-1, 0), 1, _ACCENT),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def _scope_rows(report: dict[str, Any], date_from: str, date_to: str, language: str) -> list[list[str]]:
    scope = report.get("scope") or {}
    account_label = ""
    if scope.get("account_id"):
        account_label = next(
            (str(item.get("label") or "") for item in report.get("account_details") or [] if item.get("id") == scope["account_id"]),
            str(scope["account_id"]),
        )
    return [
        [_tr("Report scope", language), account_label or _tr("Entire portfolio", language)],
        [_tr("People", language), scope.get("person_name") or _tr("All people", language)],
        [_tr("Account category", language), scope.get("account_type") or _tr("All account categories", language)],
        [_tr("Location", language), scope.get("location") or _tr("All locations", language)],
        [_tr("Period", language), f"{_date_text(date_from)} - {_date_text(date_to)}"],
    ]


def build_portfolio_report_pdf(
    report: dict[str, Any],
    trend: dict[str, Any],
    *,
    date_from: str,
    date_to: str,
    language: str = "en",
) -> bytes:
    language = "he" if language == "he" else "en"
    styles = _styles(language)
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=_tr("Portfolio report", language),
        author="Portfolio Analyzer",
    )
    story: list[Any] = [
        _paragraph(_tr("Portfolio report", language), styles["title"]),
        _table(_scope_rows(report, date_from, date_to, language), [38 * mm, 220 * mm], styles, header=False),
        Spacer(1, 4 * mm),
    ]

    summary_rows = [
        [
            _tr("Accounts", language),
            _tr("Holdings", language),
            _tr("Linked funds", language),
            _tr("Period", language),
        ],
        [
            str(report.get("accounts") or 0),
            str(report.get("holdings") or 0),
            str((report.get("funds") or {}).get("count") or 0),
            f"{_date_text(date_from)} - {_date_text(date_to)}",
        ],
    ]
    story.extend(
        [
            _table(summary_rows, [42 * mm, 42 * mm, 42 * mm, 132 * mm], styles),
            Spacer(1, 2 * mm),
            _paragraph(_tr("Amounts are shown in each account's native currency.", language), styles["small"]),
            _paragraph(_tr("Accounts included", language), styles["h2"]),
        ]
    )

    accounts = report.get("account_details") or []
    if not accounts:
        story.append(_paragraph(_tr("No accounts match the selected report filters.", language), styles["body"]))
    else:
        account_rows = [[
            _tr("Account", language),
            _tr("Account category", language),
            _tr("Owners", language),
            _tr("Cash", language),
            _tr("Securities", language),
            _tr("Total value", language),
            _tr("Profit", language),
        ]]
        for account in accounts:
            owners = ", ".join(str(person.get("name") or "") for person in account.get("persons") or []) or "-"
            currency = account.get("currency") or ""
            account_rows.append(
                [
                    account.get("label") or account.get("id") or "-",
                    account.get("type") or "-",
                    owners,
                    _money(account.get("cash"), currency),
                    _money(account.get("securities_value"), currency),
                    _money(account.get("value"), currency),
                    _money(account.get("profit"), currency),
                ]
            )
        story.append(
            _table(account_rows, [49 * mm, 35 * mm, 42 * mm, 32 * mm, 32 * mm, 34 * mm, 34 * mm], styles)
        )

    trend_by_id = {
        str((item.get("account") or {}).get("id") or ""): item
        for item in trend.get("accounts") or []
    }
    for index, account in enumerate(accounts):
        if index or len(accounts) > 2:
            story.append(PageBreak())
        story.append(_paragraph(f"{_tr('Account details', language)}: {account.get('label') or account.get('id') or '-'}", styles["h2"]))
        owners = ", ".join(str(person.get("name") or "") for person in account.get("persons") or []) or "-"
        meta = " | ".join(
            value
            for value in (
                str(account.get("type") or ""),
                str(account.get("location") or ""),
                str(account.get("currency") or ""),
                f"{_tr('Owners', language)}: {owners}",
            )
            if value
        )
        story.extend([_paragraph(meta, styles["body"]), Spacer(1, 2 * mm)])

        holdings = account.get("holdings") or []
        story.append(_paragraph(_tr("Holdings", language), styles["h3"]))
        if holdings:
            holding_rows = [[
                _tr("Symbol", language),
                _tr("Name", language),
                _tr("Asset class", language),
                _tr("Quantity", language),
                _tr("Value", language),
                _tr("Profit", language),
            ]]
            for holding in holdings:
                currency = holding.get("currency") or account.get("currency") or ""
                holding_rows.append(
                    [
                        holding.get("symbol") or "-",
                        holding.get("name") or "-",
                        holding.get("asset_class") or "-",
                        _number(holding.get("quantity"), 3),
                        _money(holding.get("market_value"), currency),
                        _money(holding.get("profit"), currency),
                    ]
                )
            story.append(_table(holding_rows, [31 * mm, 79 * mm, 40 * mm, 31 * mm, 39 * mm, 38 * mm], styles))
        else:
            story.append(_paragraph(_tr("No holdings in this account.", language), styles["small"]))

        funds = account.get("funds") or []
        if funds:
            story.append(_paragraph(_tr("Long-term funds", language), styles["h3"]))
            fund_rows = [[
                _tr("Fund", language),
                _tr("Kind", language),
                _tr("Amount", language),
                _tr("Monthly estimate", language),
            ]]
            for fund in funds:
                currency = account.get("currency") or ""
                fund_rows.append(
                    [
                        fund.get("fund_name") or fund.get("pension_id") or "-",
                        fund.get("kind") or "-",
                        _money(fund.get("amount"), currency),
                        _money(fund.get("monthly_estimate"), currency) if fund.get("monthly_estimate") is not None else "-",
                    ]
                )
            story.append(_table(fund_rows, [86 * mm, 58 * mm, 57 * mm, 57 * mm], styles))

        trend_item = trend_by_id.get(str(account.get("id") or "")) or {}
        points = trend_item.get("points") or []
        story.append(_paragraph(_tr("Account history", language), styles["h3"]))
        if points:
            start = points[0]
            end = points[-1]
            trend_rows = [[
                _tr("From", language),
                _tr("To", language),
                _tr("Starting value", language),
                _tr("Ending value", language),
                _tr("Profit %", language),
            ], [
                _date_text(start.get("date")),
                _date_text(end.get("date")),
                _money(start.get("value"), account.get("currency")),
                _money(end.get("value"), account.get("currency")),
                f"{_number(end.get('profit_percent'))}%",
            ]]
            story.append(_table(trend_rows, [45 * mm, 45 * mm, 56 * mm, 56 * mm, 56 * mm], styles))
        else:
            story.append(_paragraph(_tr("No saved history in this period.", language), styles["small"]))

    regular, _bold = _register_fonts()

    def footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setStrokeColor(_BORDER)
        canvas.line(doc.leftMargin, 10 * mm, landscape(A4)[0] - doc.rightMargin, 10 * mm)
        canvas.setFillColor(_MUTED)
        canvas.setFont(regular, 7)
        generated = f"{_tr('Generated', language)} {_date_text(date.today().isoformat())}"
        page = f"{_tr('Page', language)} {doc.page}"
        canvas.drawString(doc.leftMargin, 6.5 * mm, _display(generated))
        canvas.drawRightString(landscape(A4)[0] - doc.rightMargin, 6.5 * mm, _display(page))
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
