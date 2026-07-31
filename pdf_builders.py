
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, List, Sequence
import numpy as np
import squarify
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from pathlib import Path
from reportlab.lib import colors, utils
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, BaseDocTemplate,  \
     Spacer, Table, TableStyle, LongTable, Flowable, PageTemplate, Frame, NextPageTemplate, PageBreak
from reportlab.lib.pagesizes import A4, landscape
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend
from reportlab.lib.validators import Auto
from report_models import (AllocationItem,ClientReportData,)
from itertools import groupby
import datetime


def format_date_ordinal(date_str):
    if not date_str:
        return "-"
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day = dt.day
    suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix} {dt.strftime('%B %Y')}"

def format_date_with_suffix(date_obj):
    day = date_obj.day
    if 11 <= day <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix} {date_obj.strftime('%B %Y')}"

class Card(Flowable):
    def __init__(self, width, height, title, value, subtitle="", accent=colors.HexColor("#3B82F6")):
        super().__init__()
        self.width = width
        self.height = height
        self.title = title
        self.value = value
        self.subtitle = subtitle
        self.accent = accent

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(colors.HexColor("#E5E7EB"))
        c.setFillColor(colors.white)
        c.roundRect(0, 0, self.width, self.height, 10, stroke=1, fill=1)

        c.setFillColor(self.accent)
        c.roundRect(0, self.height - 8, self.width, 8, 10, stroke=0, fill=1)

        c.setFillColor(colors.HexColor("#6B7280"))
        c.setFont("Helvetica", 8)
        c.drawString(10, self.height - 24, self.title)

        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica-Bold", 16)
        c.drawString(10, self.height - 48, str(self.value))

        if self.subtitle:
            c.setFillColor(colors.HexColor("#6B7280"))
            c.setFont("Helvetica", 7)
            c.drawString(10, 10, self.subtitle)

        c.restoreState()

class DetailCard(Flowable):
    def __init__(self, width, height, label, value, icon=None):
        super().__init__()
        self.width = width
        self.height = height
        self.label = label
        self.value = value
        self.icon = icon

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(colors.HexColor("#E5E7EB"))
        c.setFillColor(colors.HexColor("#F9FAFB"))
        c.roundRect(0, 0, self.width, self.height, 8, stroke=1, fill=1)

        c.setFillColor(colors.HexColor("#6B7280"))
        c.setFont("Helvetica", 7)
        c.drawString(10, self.height - 16, self.label)

        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica-Bold", 9)
        text = self.value if self.value else "-"
        c.drawString(10, self.height - 32, text[:50])

        c.restoreState()

class KPIBox(Flowable):
    def __init__(self, width, height, label, value, subtitle="", accent="#24579e"):
        super().__init__()
        self.width = width
        self.height = height
        self.label = label
        self.value = value
        self.subtitle = subtitle
        self.accent = colors.HexColor(accent)

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(colors.HexColor("#E5E7EB"))
        c.setFillColor(colors.HexColor("#F3F4F6"))
        c.roundRect(0, 0, self.width, self.height, 10, stroke=1, fill=1)

        c.setFillColor(colors.HexColor("#6B7280"))
        c.setFont("Helvetica", 8)
        c.drawString(10, self.height - 20, self.label)

        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica-Bold", 16)
        c.drawString(10, self.height - 42, str(self.value))

        if self.subtitle:
            c.setFillColor(colors.HexColor("#6B7280"))
            c.setFont("Helvetica", 7)
            c.drawString(10, 10, self.subtitle)

        c.restoreState()

class CLANBox(Flowable):
    def __init__(self, width, height, label, value, subtitle="", accent="#24579e"):
        super().__init__()
        self.width = width
        self.height = height
        self.label = label
        self.value = value
        self.subtitle = subtitle
        self.accent = colors.HexColor(accent)

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(colors.HexColor("#E5E7EB"))
        c.setFillColor(colors.HexColor("#F3F4F6"))
        c.roundRect(0, 0, self.width, self.height, 10, stroke=1, fill=1)

        c.setFillColor(colors.HexColor("#6B7280"))
        c.setFont("Helvetica", 6.5)
        c.drawString(10, self.height - 20, self.label)

        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica-Bold", 12)
        c.drawString(10, self.height - 42, str(self.value))

        if self.subtitle:
            c.setFillColor(colors.HexColor("#6B7280"))
            c.setFont("Helvetica", 5.5)
            c.drawString(10, 10, self.subtitle)

        c.restoreState()

class DetailBox(Flowable):
    def __init__(self, width, height, label, value):
        super().__init__()
        self.width = width
        self.height = height
        self.label = label
        self.value = value or "-"

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(colors.HexColor("#E5E7EB"))
        c.setFillColor(colors.HexColor("#F9FAFB"))
        c.roundRect(0, 0, self.width, self.height, 8, stroke=1, fill=1)

        c.setFillColor(colors.HexColor("#6B7280"))
        c.setFont("Helvetica", 7)
        c.drawString(10, self.height - 15, self.label)

        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(10, self.height - 30, str(self.value)[:55])

        c.restoreState()

def build_dashboard_report(output_path, report):
    print(type(report))
    print(getattr(report, "perf_strat", None), flush=True)
    print(len(getattr(report, "perf_strat", []) or []), flush=True)
    return SummaryReportBuilder(output_path).build(report)

# Template for Cover page, Internal Pages and Disclaimer Page

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)

class ReportDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, pagesize=landscape(A4), **kwargs)

        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="normal",
            showBoundary=0,
        )

        cover_template = PageTemplate(
            id="Cover",
            frames=[frame],
            onPage=self._cover_page,
        )

        body_template = PageTemplate(
            id="Body",
            frames=[frame],
            onPage=self._body_page,
        )

        last_template = PageTemplate(
            id="Last",
            frames=[frame],
            onPage=self._last_page,
        )

        self.addPageTemplates([cover_template, body_template, last_template])

        # Hooks to be set from builder
        self.cover_page_fn = None
        self.body_page_fn = None
        self.last_page_fn = None

    def _cover_page(self, canvas, doc):
        if self.cover_page_fn:
            self.cover_page_fn(canvas, doc)

    def _body_page(self, canvas, doc):
        if self.body_page_fn:
            self.body_page_fn(canvas, doc)

    def _last_page(self, canvas, doc):
        if self.last_page_fn:
            self.last_page_fn(canvas, doc)

class BaseReportBuilder:
    def __init__(self, output_path: str, definitif_logo: str = None, echo_logo: str = None):
        self.output_path = output_path
        self.doc = ReportDocTemplate(
            output_path,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=14 * mm,
            title="Client Report",
            author="Perplexity",
        )
        self.styles = getSampleStyleSheet()
        self._add_styles()

        self.definitif_logo = definitif_logo
        self.echo_logo = echo_logo

        # Connect callbacks
        self.doc.cover_page_fn = self._cover_page
        self.doc.body_page_fn = self._on_page_body
        self.doc.last_page_fn = self._last_page

    def _add_styles(self):
        if "ReportTitle" not in self.styles:
            self.styles.add(
                ParagraphStyle(
                    name="ReportTitle",
                    parent=self.styles["Title"],
                    fontSize=16,
                    leading=20,
                    spaceAfter=8,
                )
            )
        if "SectionTitle" not in self.styles:
            self.styles.add(
                ParagraphStyle(
                    name="SectionTitle",
                    parent=self.styles["Heading2"],
                    fontSize=11,
                    leading=14,
                    spaceBefore=6,
                    spaceAfter=4,
                )
            )
        if "BodySmall" not in self.styles:
            self.styles.add(
                ParagraphStyle(
                    name="BodySmall",
                    parent=self.styles["BodyText"],
                    fontSize=8.5,
                    leading=11,
                )
            )
        if "SmallCenter" not in self.styles:
            self.styles.add(
                ParagraphStyle(
                    name="SmallCenter",
                    parent=self.styles["BodyText"],
                    fontSize=8,
                    leading=10,
                    alignment=TA_CENTER,
                )
            )
        if "SmallRight" not in self.styles:
            self.styles.add(
                ParagraphStyle(
                    name="SmallRight",
                    parent=self.styles["BodyText"],
                    fontSize=8,
                    leading=10,
                    alignment=TA_RIGHT,
                )
            )

    def _on_page(self, canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(doc.leftMargin, 8 * mm, "Client Report")
        canvas.drawRightString(A4[0] - doc.rightMargin, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    def _num(self, v: Any, decimals: int = 2, suffix: str = "") -> str:
        if v is None or v == "":
            return "-"
        try:
            return f"{float(v):,.{decimals}f}{suffix}"
        except Exception:
            return str(v)

    def _pct(self, v: Any, decimals: int = 2) -> str:
        if v is None or v == "":
            return "-"
        try:
            return f"{float(v):,.{decimals}f}%"
        except Exception:
            return str(v)

    def _table_from_rows(
        self,
        rows: Sequence[Any],
        columns: List[tuple],
        title: str,
        col_widths=None,
    ):
        story = [Paragraph(title, self.styles["SectionTitle"])]
        header = [Paragraph(f"<b>{c[0]}</b>", self.styles["BodySmall"]) for c in columns]
        data = [header]

        for row in rows or []:
            if hasattr(row, "__dict__"):
                row = asdict(row)
            data.append([Paragraph(str(row.get(c[1], "-")), self.styles["BodySmall"]) for c in columns])

        if len(data) == 1:
            data.append([Paragraph("-", self.styles["BodySmall"]) for _ in columns])

        t = Table(data, colWidths=col_widths)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story += [t, Spacer(1, 4 * mm)]
        return story

    def _chart_path(self, name: str) -> str:
        out = Path("output")
        out.mkdir(parents=True, exist_ok=True)
        return str(out / name)

    def _pie_chart(self, items: Sequence[AllocationItem], filename: str, title: str) -> str:
        path = self._chart_path(filename)
        labels = []
        values = []
        for item in items or []:
            if item.l and item.v not in (None, 0, 0.0):
                labels.append(item.l)
                values.append(float(item.v))

        fig, ax = plt.subplots(figsize=(6.2, 4.0), dpi=180)
        ax.set_title(title, fontsize=12)

        if values:
            ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90, textprops={"fontsize": 8})
            ax.axis("equal")
        else:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=11)
            ax.set_axis_off()

        fig.tight_layout()
        fig.savefig(path, format="png", bbox_inches="tight")
        plt.close(fig)
        return path

    def _charts_block(self, report):
        perf_isin = getattr(report, "perf_isin", []) or []
        profitbook = getattr(report, "profitbook", []) or []

        left_rows = [["Fund", "ISIN", "Inv", "CV", "Ret"]]
        for x in perf_isin[:3]:
            left_rows.append([
                self._safe(x, "fund_display", "p", default="-"),
                self._safe(x, "isin", default="-"),
                self._fmt(self._safe(x, "inv", default=0.0)),
                self._fmt(self._safe(x, "cv", default=0.0)),
                self._fmt(self._safe(x, "ret", default=0.0)),
            ])

        if len(left_rows) == 1:
            left_rows.append(["-", "-", "-", "-", "-"])

        right_rows = [["Name", "FY", "Cost", "Gain/Loss", "%"]]
        for x in profitbook[:3]:
            right_rows.append([
                self._safe(x, "n", "p", default="-"),
                self._safe(x, "financial_year", default="-"),
                self._fmt(self._safe(x, "total_cost", default=0.0)),
                self._fmt(self._safe(x, "total_gain_loss", default=0.0)),
                self._fmt(self._safe(x, "gain_loss_pct", default=0.0)),
            ])

        if len(right_rows) == 1:
            right_rows.append(["-", "-", "-", "-", "-"])

        left = self._make_table(left_rows, [55 * mm, 35 * mm, 28 * mm, 30 * mm, 20 * mm])
        right = self._make_table(right_rows, [60 * mm, 30 * mm, 30 * mm, 35 * mm, 20 * mm])

        return Table([[left, right]], colWidths=[132 * mm, 132 * mm], style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
    
class SummaryReportDoc(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, pagesize=landscape(A4), **kwargs)

        # Full frame for cover if you like
        cover_frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="cover_frame",
            showBoundary=0,
        )

        # Body frame: start lower to leave room for header
        header_height = 12 * mm  # adjust to match logo + line + title area
        body_frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height - header_height,  # reduce height by header region
            id="body_frame",
            showBoundary=0,  # set to 1 temporarily if you want to see frame border
        )

        cover_template = PageTemplate(
            id="Cover",
            frames=[cover_frame],
            onPage=self._cover_page,
        )

        portfolio_template = PageTemplate(
            id="PortfolioBody",
            frames=[body_frame],
            onPage=self._portfolio_page,
        )

        clanview_template = PageTemplate(
            id="ClanviewBody",
            frames=[body_frame],
            onPage=self._clanview_page,
        )

        performance_template = PageTemplate(
            id="PerformanceBody",
            frames=[body_frame],
            onPage=self._performance_page,
        )

        profitbook_template = PageTemplate(
            id="ProfitbookBody",
            frames=[body_frame],
            onPage=self._profitbook_page,
        )

        last_template = PageTemplate(
            id="Last",
            frames=[cover_frame],
            onPage=self._last_page,
        )

        self.addPageTemplates([
            cover_template,
            portfolio_template,
            clanview_template,
            performance_template,
            profitbook_template,
            last_template,
        ])

        # hooks
        self.cover_page_fn = None
        self.portfolio_page_fn = None
        self.clanview_page_fn = None
        self.performance_page_fn = None
        self.profitbook_page_fn = None
        self.last_page_fn = None

    def _cover_page(self, canvas, doc):
        if self.cover_page_fn:
            self.cover_page_fn(canvas, doc)

    def _portfolio_page(self, canvas, doc):
        if self.portfolio_page_fn:
            self.portfolio_page_fn(canvas, doc)

    def _clanview_page(self, canvas, doc):
            if self.clanview_page_fn:
                self.clanview_page_fn(canvas, doc)

    def _performance_page(self, canvas, doc):
        if self.performance_page_fn:
            self.performance_page_fn(canvas, doc)

    def _profitbook_page(self, canvas, doc):
        if self.profitbook_page_fn:
            self.profitbook_page_fn(canvas, doc)

    def _last_page(self, canvas, doc):
        if self.last_page_fn:
            self.last_page_fn(canvas, doc)

class SummaryReportBuilder:
    def __init__(self, output_path):
        self.output_path = output_path
        self.definitif_logo_path = Path("static/websiteLogos/definitif_logo_wb_v2_red.png")
        self.definitif_echo_logo_path = Path("static/websiteLogos/definitif_echo_logo_wb.png")
        self.echo_logo_path = Path("static/dashLogos/powered_by_echo_wb_logo.png")
        self.watermark_path = Path("static/watermarks/watermark_ifinite_two.png")
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        self.styles.add(ParagraphStyle(
            name="DashTitle",
            parent=self.styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=0,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#111827"),
            spaceBefore=4,
            spaceAfter=20,
        ))
        self.styles.add(ParagraphStyle(
            name="DashSub",
            parent=self.styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#6B7280"),
            spaceAfter=10,
        ))
        self.styles.add(ParagraphStyle(
            name="SectionHead",
            parent=self.styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#111827"),
            spaceBefore=6,
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name="ChartTitle",
            parent=self.styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            textColor=colors.HexColor("#111827"),
            spaceBefore=2,
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name="CardValue",
            parent=self.styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#111827"),
        ))
        self.styles.add(ParagraphStyle(
            name="BodySmall",
            parent=self.styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#111827"),
        ))

    def _safe(self, obj, *names, default=""):
        for name in names:
            val = getattr(obj, name, None)
            if val not in (None, ""):
                return val
        return default

    def _fmt(self, v, digits=0):
        if v is None or v == "":
            return "-"
        if isinstance(v, (int, float)):
            return f"{v:,.{digits}f}"
        return str(v)

    def _fmt_three_dec(self, v, digits=3):
            if v is None or v == "":
                return "-"
            if isinstance(v, (int, float)):
                return f"{v:,.{digits}f}"
            return str(v)
    
    def _fmt_pct(self, v):
        try:
            return f"{float(v):.2f}%"
        except Exception:
            return "0.00%"

    def _table_style(self):
        return TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.white),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#111827")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.05, colors.HexColor("#E5E7EB")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])

    def _make_table(self, data, widths):
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(self._table_style())
        return t

    def _make_table_bold(self, data, widths):
        bold_data = []

        for row_idx, row in enumerate(data):
            bold_row = []
            for col_idx, cell in enumerate(row):
                text = cell.text if isinstance(cell, Paragraph) else str(cell)

                if col_idx == 0:
                    style = self.styles["BodySmall"].clone("bold_left")
                    style.fontName = "Helvetica-Bold"
                    style.fontSize = 8
                    style.alignment = 0  # LEFT
                else:
                    style = self.styles["BodySmall"].clone("bold_right")
                    style.fontName = "Helvetica-Bold"
                    style.fontSize = 9
                    style.alignment = 2  # RIGHT

                bold_row.append(Paragraph(f"<b>{text}</b>", style))
            bold_data.append(bold_row)

        t = Table(bold_data, colWidths=widths, repeatRows=1)
        t.setStyle(self._table_style())
        return t
    
    def _perf_table(self, rows, col_widths):
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#e8eef7")),  # header background for first row
            ("GRID", (0, 0), (-1, -1), 0.35, colors.lightgrey),
            ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),  # header font
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return t

    def _perf_category_table(self, rows, col_widths):
        # rows[0] must be the column header row
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            # Header row styling (row 0)
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, 0), "TOP"),

            # All rows
            ("GRID", (0, 0), (-1, -1), 0.35, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return t
    

    def _perf_long_table(self, rows, col_widths, group_row_indices=None):
        wrap_style = ParagraphStyle(
            name="WrapFirstCol",
            fontName="Helvetica",
            fontSize=8,
            leading=9,
            alignment=TA_LEFT,
            wordWrap="CJK",
        )

        def wrap_first_col(v):
            if isinstance(v, Paragraph):
                return v
            return Paragraph(str(v or "-").replace("\n", "<br/>"), wrap_style)

        wrapped_rows = []
        for r_idx, row in enumerate(rows):
            if r_idx == 0:
                wrapped_rows.append(row)
            else:
                new_row = list(row)
                if new_row:
                    new_row[0] = wrap_first_col(new_row[0])
                wrapped_rows.append(new_row)

        t = LongTable(wrapped_rows, colWidths=col_widths, repeatRows=1)

        # Base styles
        style_commands = [
            # Header row (row 0)
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, 0), "TOP"),

            # All rows
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),

            # TOTAL row (row 1, if present)
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#eef6ff")),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ]

        if len(rows) > 1:
            style_commands.extend([
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#eef6ff")),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ])

        if group_row_indices:
            for r in group_row_indices:
                style_commands.append(("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"))

        t.setStyle(TableStyle(style_commands))
        return t

    def _perf_table_family(self, rows, col_widths, group_row_indices=None):
        wrap_style = ParagraphStyle(
            name="WrapCell",
            fontName="Helvetica",
            fontSize=8,
            leading=9,
            alignment=TA_LEFT,
            wordWrap="CJK",
        )

        def wrap_cell(v):
            if isinstance(v, Paragraph):
                return v
            return Paragraph(str(v or "-").replace("\n", "<br/>"), wrap_style)

        wrapped_rows = []
        for r_idx, row in enumerate(rows):
            if r_idx == 0:
                wrapped_rows.append(row)
            else:
                new_row = list(row)
                if len(new_row) > 0:
                    new_row[0] = wrap_cell(new_row[0])   # Fund
                if len(new_row) > 1:
                    new_row[1] = wrap_cell(new_row[1])   # Held by
                wrapped_rows.append(new_row)

        t = LongTable(wrapped_rows, colWidths=col_widths, repeatRows=1)
        
        # Base styles
        style_commands = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, 0), "TOP"),

            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("WRAP", (0, 0), (-1, -1), True),

            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#eef6ff")),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ]

        if len(rows) > 1:
            style_commands.extend([
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#eef6ff")),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ])

        if group_row_indices:
            for r in group_row_indices:
                style_commands.append(("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"))

        t.setStyle(TableStyle(style_commands))
        return t

    def _profit_table(self, rows, col_widths):
        wrap_style = ParagraphStyle(
            name="WrapFirstCol",
            fontName="Helvetica",
            fontSize=8,
            leading=9,
            alignment=TA_LEFT,
            wordWrap="CJK",
        )

        def wrap_first_col(v):
            if isinstance(v, Paragraph):
                return v
            return Paragraph(str(v or "-").replace("\n", "<br/>"), wrap_style)

        wrapped_rows = []
        for r_idx, row in enumerate(rows):
            if r_idx == 0:
                wrapped_rows.append(row)
            else:
                new_row = list(row)
                if new_row:
                    new_row[0] = wrap_first_col(new_row[0])
                wrapped_rows.append(new_row)

        table = Table(wrapped_rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            # Header
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
            ("GRID", (0, 0), (-1, -1), 0.05, colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            # Total row (row 1, if present)
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#eef6ff")),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            # Body rows
            ("FONTNAME", (0, 2), (-1, -1), "Helvetica"),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#111827")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (1, -1), "LEFT"),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return table
    
    def make_pie_chart(title, data, labels, width=180, height=120):
        drawing = Drawing(width, height)
        heading = String(10, height - 12, title, fontSize=11, fillColor=colors.HexColor("#111827"))
        pie = Pie()
        pie.x = 20
        pie.y = 10
        pie.width = 70
        pie.height = 70
        pie.data = data
        pie.labels = labels
        pie.sideLabels = True
        pie.slices.strokeWidth = 0.5

        legend = Legend()
        legend.x = 100
        legend.y = 60
        legend.alignment = "right"
        legend.colorNamePairs = Auto(obj=pie)

        drawing.add(heading)
        drawing.add(pie)
        drawing.add(legend)
        return drawing

    def _chart_path(self, name: str) -> str:
        out = Path("output")
        out.mkdir(parents=True, exist_ok=True)
        return str(out / name)

    def _donut_chart(self, labels, values, title, filename):
        path = self._chart_path(filename)
        fig, ax = plt.subplots(figsize=(6.2, 4.2), dpi=180)
        ax.set_title(title, fontsize=12)

        if values and sum(values) > 0:
            ax.pie(
                values,
                labels=labels,
                startangle=90,
                autopct="%1.1f%%",
                wedgeprops={"width": 0.38, "edgecolor": "white"},
                textprops={"fontsize": 8},
            )
            ax.axis("equal")
        else:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=11)
            ax.set_axis_off()

        fig.tight_layout()
        fig.savefig(path, format="png", bbox_inches="tight")
        plt.close(fig)
        return path
    
    from reportlab.lib import utils

    def _fit_image(self, path, width):
        img = utils.ImageReader(path)
        iw, ih = img.getSize()
        aspect = ih / float(iw)
        return Image(path, width=width, height=width * aspect)

    def _multi_donut_chart(self, sections, filename):
        path = self._chart_path(filename)
        n = len(sections)
        fig, axes = plt.subplots(1, n, figsize=(7.0 * n, 3.5), dpi=300)

        if n == 1:
            axes = [axes]

        box = FancyBboxPatch(
            (0.00, 0.00), 1.00, 1.00,
            boxstyle="round,pad=0.0,rounding_size=0.005",
            transform=fig.transFigure,
            edgecolor="#E5E7EB",
            facecolor="#F3F4F6",
            linewidth=1.0,
            zorder=-1,
        )
        fig.patches.append(box)

        base_colors = [
            "#6f9bfc", "#45a39e", "#59b596", "#b5c265",
            "#d4d26e", "#d4ae6e", "#ae99f0", "#6366F1",
            "#fcbb8d", "#6dc9c0", "#55b1f2", "#cda3f0",
        ]

        for ax, sec in zip(axes, sections):
            labels = sec["labels"]
            values = sec["values"]
            title = sec["title"]

            if values and sum(values) > 0:
                num_slices = len(values)
                colors_list = (base_colors * ((num_slices // len(base_colors)) + 1))[:num_slices]

                wedges, _ = ax.pie(
                    values,
                    labels=None,
                    colors=colors_list,
                    startangle=90,
                    autopct=None,
                    wedgeprops={"width": 0.38, "edgecolor": "white"},
                )

                total = sum(values)
                legend_labels = [
                    f"{label} ({(value / total * 100):.0f}%)"
                    for label, value in zip(labels, values)
                ]

                ax.legend(
                    wedges,
                    legend_labels,
                    loc="center left",
                    bbox_to_anchor=(0.05, 0.5),
                    fontsize=9,
                    frameon=False,
                )

                ax.text(
                    0, 0, title,
                    ha="center", va="center",
                    fontsize=11, fontweight="bold",
                    color="#111827",
                )

                ax.axis("equal")
            else:
                ax.text(0.0, 0.0, "No data", ha="center", va="center", fontsize=9)
                ax.set_axis_off()

            ax.set_facecolor("none")

        fig.subplots_adjust(wspace=0.05, left=0.04, right=0.96, top=0.95, bottom=0.05)
        fig.savefig(path, format="png", dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        return path
    
    def _category_stacked_bar_chart(self, section, filename):
        path = self._chart_path(filename)
        labels = section["labels"]
        values = section["values"]

        fig, ax = plt.subplots(figsize=(9.3, 0.6), dpi=500)
        fig.patch.set_facecolor("#F3F4F6")
        ax.set_facecolor("#F3F4F6")

        if labels and values and sum(values) > 0:
            total = sum(values)
            left = 0
            colors_list = plt.cm.Blues_r(np.linspace(0.35, 0.85, len(values)))

            for lab, val, col in zip(labels, values, colors_list):
                pct = (val / total) * 100
                ax.barh([0], [pct], left=left, height=0.45, color=col, edgecolor="white")
                if pct >= 6:
                    ax.text(
                        left + pct / 2, 0,
                        f"{lab} {pct:.1f}%",
                        ha="center", va="center",
                        fontsize=4,
                        color="white",
                        fontweight="bold"
                    )
                left += pct

            ax.set_xlim(0, 100)
            ax.set_yticks([])
            ax.set_xticks([])
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_visible(False)
            ax.spines["bottom"].set_visible(False)
            
        else:
            ax.text(0.4, 0.4, "No data", ha="left", va="left", fontsize=4)
            ax.set_axis_off()

        fig.tight_layout()
        fig.savefig(path, bbox_inches="tight", dpi=500)
        plt.close(fig)
        return path
    
    def _category_treemap_chart(self, section, filename):
        path = self._chart_path(filename)
        labels = section["labels"]
        values = section["values"]

        fig, ax = plt.subplots(figsize=(16, 0.5), dpi=300)
        fig.patch.set_facecolor("#F3F4F600")
        ax.set_facecolor("#F3F4F600")

        if labels and values and sum(values) > 0:
            total = sum(values)
            norm_vals = squarify.normalize_sizes(values, 100, 10)
            rects = squarify.squarify(norm_vals, 0, 0, 100, 10)

            colors_list = plt.cm.GnBu(np.linspace(0.35, 0.85, len(values)))

            for r, lab, val, col in zip(rects, labels, values, colors_list):
                pct = (val / total) * 100
                ax.add_patch(plt.Rectangle(
                    (r["x"], r["y"]), r["dx"], r["dy"],
                    facecolor=col, edgecolor="white", linewidth=1.0
                ))

                if pct >= 4:
                    txt = f"{lab}\n{pct:.1f}%"
                    ax.text(
                        r["x"] + r["dx"] / 2,
                        r["y"] + r["dy"] / 2,
                        txt,
                        ha="center",
                        va="center",
                        fontsize=6,
                        color="#000000",
                        fontweight="bold",
                        linespacing=1
                    )

            ax.set_xlim(0, 100)
            ax.set_ylim(0, 10)
            ax.axis("off")
        else:
            ax.text(0.3, 0.3, "No data", ha="center", va="center", fontsize=6)
            ax.axis("off")

        fig.savefig(path, bbox_inches="tight", dpi=300, facecolor=fig.get_facecolor())
        plt.close(fig)
        return path
    
    def _build_doc(self):
        doc = SummaryReportDoc(
            self.output_path,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
            title="Summary Report",
            author="Perplexity",
        )
        doc.cover_page_fn = self._cover_page
        doc.portfolio_page_fn = self._portfolio_page_body
        doc.clanview_page_fn = self._clanview_page_body
        doc.performance_page_fn = self._performance_page_body
        doc.profitbook_page_fn = self._profitbook_page_body
        doc.last_page_fn = self._last_page
        return doc

    def _cover_page(self, canvas, doc):
        canvas.saveState()

        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)

        # Watermark in mid-section
        if getattr(self, "watermark_path", None) and self.watermark_path:
            canvas.drawImage(
                str(self.watermark_path),
                PAGE_WIDTH * 0.1,          # left margin-ish
                PAGE_HEIGHT * 0.15,         # mid-section vertically
                width=PAGE_WIDTH * 1.05,     # covers substantial width
                height=PAGE_HEIGHT * 0.65,   # covers substantial height
                preserveAspectRatio=True,
                mask="auto",
            )

        # canvas.setStrokeColor(colors.HexColor("#E6E6E6"))
        # canvas.setLineWidth(0.8)
        # canvas.line(18 * mm, PAGE_HEIGHT - 24 * mm, PAGE_WIDTH - 18 * mm, PAGE_HEIGHT - 24 * mm)


        canvas.setFillColor(colors.black)
        canvas.setFont("Helvetica-Bold", 24)
        canvas.drawString(20 * mm, PAGE_HEIGHT / 2 + 14 * mm, "Portfolio Overview & Statements")

        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#6F6F6F"))
        canvas.drawString(
            20 * mm,
            PAGE_HEIGHT / 2 + 6 * mm,
            "Consolidated view of investments, performance, and profit realization.",
        )

        canvas.setStrokeColor(colors.HexColor("#D50000"))
        canvas.setLineWidth(0.25)
        canvas.line(20 * mm, PAGE_HEIGHT / 2 + 2 * mm, PAGE_WIDTH - 110 * mm, PAGE_HEIGHT / 2 + 2 * mm)

        # You can later pull real client name / valuation date from report
        client = getattr(self, "cover_client_name", "-")
        val_date = getattr(self, "cover_valuation_date", "-")
        canvas.setFont("Helvetica-Bold", 14)
        canvas.setFillColor(colors.HexColor("#444444"))
        canvas.drawString(20 * mm, PAGE_HEIGHT / 2 - 5 * mm, f"{client}")
        canvas.setFont("Helvetica-Bold", 10)
        canvas.setFillColor(colors.HexColor("#444444"))
        canvas.drawString(20 * mm, PAGE_HEIGHT / 2 - 11 * mm, f"{val_date}")

        # definitif logo
        if getattr(self, "definitif_logo_path", None):
            canvas.drawImage(
                self.definitif_logo_path,
                18 * mm,
                18 * mm,
                width=60 * mm,
                height=31 * mm,
                preserveAspectRatio=True,
                mask="auto",
            )

        canvas.setStrokeColor(colors.HexColor("#E6E6E6"))
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, 15 * mm, PAGE_WIDTH - 18 * mm, 15 * mm)

        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(18 * mm, 9 * mm, "Définitif Investments")
        canvas.drawString(18 * mm, 4.5 * mm, "www.definitif.app | definitif.investments@gmail.com")

        canvas.drawString(PAGE_WIDTH - 75 * mm, 9 * mm, "")
        if getattr(self, "echo_logo_path", None):
            canvas.drawImage(
                self.echo_logo_path,
                PAGE_WIDTH - 58 * mm,
                3 * mm,
                width=40 * mm,
                height=10 * mm,
                preserveAspectRatio=True,
                mask="auto",
            )
        canvas.restoreState()

    def _portfolio_page_body(self, canvas, doc):
        self._draw_common_body_chrome(canvas, doc, header_title="Portfolio")

    def _clanview_page_body(self, canvas, doc):
        self._draw_common_body_chrome(canvas, doc, header_title="Clanview")

    def _performance_page_body(self, canvas, doc):
        self._draw_common_body_chrome(canvas, doc, header_title="Performance")

    def _profitbook_page_body(self, canvas, doc):
        self._draw_common_body_chrome(canvas, doc, header_title="Profitbook")

    def _draw_common_body_chrome(self, canvas, doc, header_title: str):
        canvas.saveState()

        # Watermark
        if getattr(self, "watermark_path", None) and self.watermark_path:
            canvas.drawImage(
                str(self.watermark_path),
                PAGE_WIDTH * 0.1,
                PAGE_HEIGHT * 0.15,
                width=PAGE_WIDTH * 1.05,
                height=PAGE_HEIGHT * 0.65,
                preserveAspectRatio=True,
                mask="auto",
            )

        # Logo
        if getattr(self, "definitif_logo_path", None):
            canvas.drawImage(
                self.definitif_logo_path,
                doc.leftMargin,
                PAGE_HEIGHT - 18 * mm,
                width=28 * mm,
                height=10 * mm,
                preserveAspectRatio=True,
                mask="auto",
            )

        # Top separator line
        canvas.setStrokeColor(colors.HexColor("#E6E6E6"))
        canvas.setLineWidth(0.8)
        canvas.line(doc.leftMargin, PAGE_HEIGHT - 20 * mm, PAGE_WIDTH - doc.rightMargin, PAGE_HEIGHT - 20 * mm)

        canvas.setFont("Helvetica-Bold", 12)
        canvas.setFillColor(colors.HexColor("#111827"))
        title_y = PAGE_HEIGHT - 18 * mm
        canvas.drawRightString(
            PAGE_WIDTH - doc.rightMargin,
            title_y,
            header_title,
        )

        # footer line, website, page number...

        canvas.setStrokeColor(colors.HexColor("#DDDDDD"))
        canvas.line(doc.leftMargin, 15 * mm, PAGE_WIDTH - doc.rightMargin, 15 * mm)

        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(doc.leftMargin, 9 * mm, "www.definitif.app | definitif.investments@gmail.com")
        canvas.drawRightString(PAGE_WIDTH - doc.rightMargin, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()


    def _last_page(self, canvas, doc):
        canvas.saveState()

        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)

        # Watermark in mid-section
        if getattr(self, "watermark_path", None) and self.watermark_path:
            canvas.drawImage(
                str(self.watermark_path),
                PAGE_WIDTH * 0.1,          # left margin-ish
                PAGE_HEIGHT * 0.15,         # mid-section vertically
                width=PAGE_WIDTH * 1.05,     # covers substantial width
                height=PAGE_HEIGHT * 0.65,   # covers substantial height
                preserveAspectRatio=True,
                mask="auto",
            )

        # definitif logo
        if getattr(self, "definitif_echo_logo_path", None):
            logo_width = 100 * mm
            logo_height = 23 * mm
            logo_y = 155 * mm  # keep your vertical position

            # Center horizontally: (PAGE_WIDTH - logo_width) / 2
            logo_x = (PAGE_WIDTH - logo_width) / 2.0
            canvas.drawImage(
                self.definitif_echo_logo_path,
                logo_x,
                logo_y,
                width=logo_width,
                height=logo_height,
                preserveAspectRatio=True,
                mask="auto",
            )

        canvas.setStrokeColor(colors.HexColor("#E6E6E6"))
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, 15 * mm, PAGE_WIDTH - 18 * mm, 15 * mm)

        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(18 * mm, 9 * mm, "Définitif Investments")
        canvas.drawString(18 * mm, 4.5 * mm, "www.definitif.app | definitif.investments@gmail.com")

        canvas.drawString(PAGE_WIDTH - 75 * mm, 9 * mm, "")
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(PAGE_WIDTH - 54 * mm,9 * mm,  "B402, Saishakti Symphony")
        canvas.drawString(PAGE_WIDTH - 57 * mm,4.5 * mm, "Suncity, Hyderabad - 500030")
        
        canvas.restoreState()
    
    #################################################################################################
    ### Report Builder ###

    def build(self, report):

        ### Cover Page ###

        kpi = getattr(report, "kpi", None)
        self.cover_client_name = getattr(kpi, "l", None) or "-"
        self.cover_valuation_date = getattr(kpi, "val_date", None) or "-"

        doc = self._build_doc()
        story = []

        story.append(Spacer(1, 100 * mm))
        story.append(NextPageTemplate("PortfolioBody"))
        story.append(PageBreak())

        ### Summary Page ###

        kpi = getattr(report, "kpi", None)
        doc.header_title = "Summary"
        story.append(Spacer(1, 0))
        user_type = str(getattr(kpi, "user_type", "individual")).strip().lower()

        story.append(Paragraph("Overview", self.styles["SectionHead"]))
        story.append(Spacer(1, 8))
        kpi_row = [
            KPIBox(60 * mm, 25 * mm, "Portfolio Value", self._fmt(self._safe(kpi, "pv", default=0.0)), "INR", "#65C1B7"),
            KPIBox(60 * mm, 25 * mm, "Investment Value", self._fmt(self._safe(kpi, "inv", default=0.0)), "INR", "#65C1B7"),
            KPIBox(60 * mm, 25 * mm, "Unrealised Gains", self._fmt(self._safe(kpi, "ugl", default=0.0)), "INR", "#65C1B7"),
            KPIBox(60 * mm, 25 * mm, "Realised Gains", self._fmt(self._safe(kpi, "rgl", default=0.0)), "INR", "#65C1B7"),
        ]
        story.append(Table(
            [[kpi_row[0], kpi_row[1], kpi_row[2], kpi_row[3]]],
            colWidths=[64 * mm, 64 * mm, 64 * mm, 64 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ])
        ))
        story.append(Spacer(1, 8))

        return_row = [
            KPIBox(60 * mm, 25 * mm, "Absolute (Current Holdings)", self._fmt_pct(self._safe(kpi, "ret", default=0.0)), "Simple Return", "#65C1B7"),
            KPIBox(60 * mm, 25 * mm, "XIRR (Current Holdings)", self._fmt_pct(self._safe(kpi, "x1", default=0.0)), "Annualized Return", "#65C1B7"),
            KPIBox(60 * mm, 25 * mm, "XIRR (Since Inception)", self._fmt_pct(self._safe(kpi, "x2", default=0.0)), "Annualized Return", "#65C1B7"),
            KPIBox(60 * mm, 25 * mm, "Valuation", self._safe(kpi, "val_date", default="-"), "Date", "#65C1B7"),
        ]
        story.append(Table(
            [[return_row[0], return_row[1], return_row[2], return_row[3]]],
            colWidths=[64 * mm, 64 * mm, 64 * mm, 64 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ])
        ))
        story.append(Spacer(1, 8))

        # Strategy Chart

        category_alloc = getattr(report, "category_alloc", []) or []

        # Filter to entries that actually have >0 cv (since you already check that for chart data)
        filtered = [
            x for x in category_alloc
            if float(self._safe(x, "cv", default=0.0)) > 0
        ]

        # Sort filtered entries by cv descending
        sorted_alloc = sorted(
            filtered,
            key=lambda x: float(self._safe(x, "cv", default=0.0)),
            reverse=True,
        )

        has_chart_data = bool(sorted_alloc)

        if has_chart_data:
            strategy_section = {
                "title": "Strategy",
                "labels": [
                    f"{self._safe(x, 'c', default='-')}"
                    for x in sorted_alloc
                    if self._safe(x, "g", default="-") != "-" or self._safe(x, "c", default="-") != "-"
                ],
                "values": [
                    float(self._safe(x, "cv", default=0.0))
                    for x in sorted_alloc
                ],
            }
            category_chart = self._category_treemap_chart(strategy_section, "category_alloc.png")
            story.append(Paragraph("Strategy", self.styles["SectionHead"]))
            story.append(Spacer(1, 2))
            story.append(Image(category_chart, width=256 * mm, height=16 * mm))
            story.append(Spacer(1, 2))

        asset_alloc = getattr(report, "asset_alloc", []) or []
        market_cap = getattr(report, "market_cap", []) or []

        has_chart_data = any(float(self._safe(x, "v", default=0.0)) > 0 for x in asset_alloc) or any(float(self._safe(x, "v", default=0.0)) > 0 for x in market_cap)

        if has_chart_data:
            asset_items = sorted(
                [x for x in asset_alloc if self._safe(x, "l", default="-") != "-" and float(self._safe(x, "v", default=0.0)) > 0],
                key=lambda x: float(self._safe(x, "v", default=0.0)),
                reverse=True
            )
            market_cap_items = sorted(
                [x for x in market_cap if self._safe(x, "l", default="-") != "-" and float(self._safe(x, "v", default=0.0)) > 0],
                key=lambda x: float(self._safe(x, "v", default=0.0)),
                reverse=True
            )

            asset_section = {
                "title": "Asset Class",
                "labels": [self._safe(x, "l", default="-") for x in asset_items],
                "values": [float(self._safe(x, "v", default=0.0)) for x in asset_items],
            }
            market_cap_section = {
                "title": "Marketcap",
                "labels": [self._safe(x, "l", default="-") for x in market_cap_items],
                "values": [float(self._safe(x, "v", default=0.0)) for x in market_cap_items],
            }

            sections = [asset_section, market_cap_section]
            chart_path = self._multi_donut_chart(sections, "allocations_donut.png")
            story.append(Paragraph("Allocation", self.styles["SectionHead"]))
            story.append(Spacer(1, 2))
            story.append(Image(chart_path, width=256 * mm, height=64 * mm))
            story.append(Spacer(1, 2))

        ### Family Summary Page ###

        kpi = getattr(report, "kpi", None)
        doc.header_title = "Clanview"
        story.append(Spacer(1, 0))
        user_type = str(getattr(kpi, "user_type", "individual")).strip().lower()

        if user_type == "family":
            
            story.append(NextPageTemplate("ClanviewBody"))
            story.append(PageBreak())
            story.append(Spacer(1, 0))

            pan_summary = getattr(report, "pan_summary", None)
            if pan_summary is None and isinstance(report, dict):
                pan_summary = report.get("pan_summary", [])

            if pan_summary:
                for item in pan_summary:
                    clan_total = sum(float(self._safe(x, "cv", default=0.0)) for x in pan_summary) or 1.0
                    share = (float(self._safe(item, "cv", default=0.0)) / clan_total) * 100

                    story.append(
                        Paragraph(
                            f'{self._safe(item, "n", default="-")} ({share:.2f}%)',
                            self.styles["SectionHead"]
                        )
                    )
                    # story.append(Paragraph(self._safe(item, "n", default="-"), self.styles["SectionHead"]))
                    story.append(Spacer(1, 8))

                    pan_row = [
                        CLANBox(33 * mm, 25 * mm, "Portfolio Value", self._fmt(self._safe(item, "cv", default=0.0)), "INR", "#65C1B7"),
                        CLANBox(33 * mm, 25 * mm, "Investment Value", self._fmt(self._safe(item, "inv", default=0.0)), "INR", "#65C1B7"),
                        CLANBox(33 * mm, 25 * mm, "Unrealised Gains", self._fmt(self._safe(item, "ugl", default=0.0)), "INR", "#65C1B7"),
                        CLANBox(33 * mm, 25 * mm, "Realised Gains", self._fmt(self._safe(item, "rgl", default=0.0)), "INR", "#65C1B7"),
                        CLANBox(33 * mm, 25 * mm, "Absolute (Current Holdings)", self._fmt_pct(self._safe(item, "ret", default=0.0)), "Simple Return", "#65C1B7"),
                        CLANBox(33 * mm, 25 * mm, "XIRR (Current Holdings)", self._fmt_pct(self._safe(item, "x1", default=0.0)), "Annualized Return", "#65C1B7"),
                        CLANBox(35 * mm, 25 * mm, "XIRR (Since Inception)", self._fmt_pct(self._safe(item, "x2", default=0.0)), "Annualized Return", "#65C1B7"),
                    ]

                    story.append(Table(
                        [[pan_row[0], pan_row[1], pan_row[2], pan_row[3], pan_row[4], pan_row[5], pan_row[6]]],
                        colWidths=[36.5 * mm, 36.5 * mm, 36.5 * mm, 36.5 * mm, 36.5 * mm, 36.5 * mm, 36.5 * mm],
                        style=TableStyle([
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 2),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                            ("TOPPADDING", (0, 0), (-1, -1), 0),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                        ])
                    ))
                    story.append(Spacer(1, 8))

        ### Family Performance Page ###

        kpi = getattr(report, "kpi", None)
        user_type = str(getattr(kpi, "user_type", "individual")).strip().lower()

        if user_type == "family":

            ### Family Performance Page ###

            def norm(v):
                return str(v or "").strip().lower()

            def norm_pan(v):
                return str(v or "").strip().upper()

            def get_val(obj, key, default=""):
                if isinstance(obj, dict):
                    return obj.get(key, default)
                return getattr(obj, key, default)

            def unique_preserve(seq):
                seen = set()
                out = []
                for x in seq:
                    x = str(x or "").strip()
                    if x and x not in seen:
                        seen.add(x)
                        out.append(x)
                return out


            perf_isin = sorted(
                getattr(report, "perf_isin", []) or [],
                key=lambda x: (
                    norm(get_val(x, "g", "")),
                    norm(get_val(x, "c", "")),
                    norm(get_val(x, "fund_display", get_val(x, "p", ""))),
                )
            )

            kpi = getattr(report, "kpi", None)
            pv = float(get_val(kpi, "pv", 0.0) or 0.0) if kpi is not None else 0.0
            has_current_holdings = round(pv, 0) != 0

            perf_strat = getattr(report, "perf_strat", None)
            if perf_strat is None and isinstance(report, dict):
                perf_strat = report.get("perf_strat")
            perf_strat = perf_strat or []

            has_perf_data = has_current_holdings and (bool(perf_isin) or bool(perf_strat))

            if has_perf_data:
                story.append(NextPageTemplate("PerformanceBody"))
                story.append(PageBreak())

                doc.header_title = "Performance"
                story.append(Spacer(1, 0))

                perf_strat_map = {}
                for x in perf_strat:
                    key = norm(get_val(x, "g", ""))
                    perf_strat_map[key] = x
                
                perf_colWidth = [78 * mm, 35 * mm, 16 * mm, 24 * mm, 24 * mm, 24 * mm, 24 * mm, 24 * mm, 24 * mm]

                rows = [[
                    "Fund",
                    "Investor Name",
                    "Weight",
                    "Investment",
                    "Current Value",
                    "Gains",
                    "Return(Abs)",
                    "XIRR(Holdings)",
                    "XIRR(SI)",
                ]]

                group_row_indices = []

                pan_source = getattr(report, "pan_summary", None)
                if pan_source is None and isinstance(report, dict):
                    pan_source = report.get("pan_summary", [])

                pan_to_name = {}
                for item in pan_source or []:
                    pan = norm_pan(get_val(item, "p", ""))
                    name = str(get_val(item, "n", "") or get_val(item, "inv_name", "") or "").strip()
                    if pan and name:
                        pan_to_name.setdefault(pan, []).append(name)

                def held_by_for_row(x):
                    pan = norm_pan(get_val(x, "p", ""))
                    names = pan_to_name.get(pan, [])
                    names = unique_preserve(names)
                    return ", ".join(names) if names else "-"

                if not perf_isin:
                    rows.append(["-", "-", "-", "-", "-", "-", "-", "-", "-"])
                else:
                    kpi = getattr(report, "kpi", None)
                    if kpi is None and isinstance(report, dict):
                        kpi = report.get("kpi")
                    kpi_item = (kpi or [None])

                    if kpi_item:
                        rows.append([
                            Paragraph("<b>Portfolio Metrics</b>", self.styles["BodySmall"]),
                            "",
                            self._fmt(get_val(kpi_item, "w", "-")),
                            self._fmt(get_val(kpi_item, "inv", 0.0)),
                            self._fmt(get_val(kpi_item, "pv", 0.0)),
                            self._fmt(get_val(kpi_item, "ugl", 0.0)),
                            self._fmt_pct(get_val(kpi_item, "ret", 0.0)),
                            self._fmt_pct(get_val(kpi_item, "x1", 0.0)),
                            self._fmt_pct(get_val(kpi_item, "x2", 0.0)),
                        ])

                    for group_key, group_iter in groupby(perf_isin, key=lambda x: norm(get_val(x, "g", "")) or "-"):
                        group_items = list(group_iter)
                        group_label = get_val(group_items[0], "g", group_key.title()) if group_items else group_key.title()

                        g = perf_strat_map.get(group_key)
                        if g is None:
                            g = type("G", (), {
                                "w": 0.0, "inv": 0.0, "cv": 0.0, "ugl": 0.0,
                                "ret": 0.0, "x1": 0.0, "x2": 0.0
                            })()

                        group_row_indices.append(len(rows))
                        rows.append([
                            Paragraph(f"<b>{group_label}</b>", self.styles["BodySmall"]),
                            "",
                            self._fmt_pct(get_val(g, "w", 0.0)),
                            self._fmt(get_val(g, "inv", 0.0)),
                            self._fmt(get_val(g, "cv", 0.0)),
                            self._fmt(get_val(g, "ugl", 0.0)),
                            self._fmt_pct(get_val(g, "ret", 0.0)),
                            self._fmt_pct(get_val(g, "x1", 0.0)),
                            self._fmt_pct(get_val(g, "x2", 0.0)),
                        ])

                        for category, cat_iter in groupby(group_items, key=lambda x: norm(get_val(x, "c", "")) or "-"):
                            cat_items = list(cat_iter)
                            category_label = get_val(cat_items[0], "c", category.title()) if cat_items else category.title()

                            rows.append([
                                Paragraph(f'<font color="#24579e"><b>{category_label}</b></font>', self.styles["BodySmall"]),
                                "",
                                "", "", "", "", "", "", "",
                            ])

                            for x in cat_items:
                                rows.append([
                                    get_val(x, "fund_display", get_val(x, "p", "-")),
                                    held_by_for_row(x),
                                    self._fmt(get_val(x, "w", 0.0)),
                                    self._fmt(get_val(x, "inv", 0.0)),
                                    self._fmt(get_val(x, "cv", 0.0)),
                                    self._fmt(get_val(x, "ugl", 0.0)),
                                    self._fmt_pct(get_val(x, "ret", 0.0)),
                                    self._fmt_pct(get_val(x, "x1", 0.0)),
                                    self._fmt_pct(get_val(x, "x2", 0.0)),
                                ])

                story.append(self._perf_table_family(rows, perf_colWidth, group_row_indices))

        else:

        ### Individual Performance Page ###

            def norm(v):
                return str(v or "").strip().lower()

            perf_isin = sorted(
                getattr(report, "perf_isin", []) or [],
                key=lambda x: (
                    norm(getattr(x, "g", "")),
                    norm(getattr(x, "c", "")),
                    norm(getattr(x, "fund_display", getattr(x, "p", ""))),
                )
            )

            kpi = getattr(report, "kpi", None)
            pv = float(getattr(kpi, "pv", 0.0) or 0.0)
            has_current_holdings = round(pv, 0) != 0

            perf_strat = getattr(report, "perf_strat", None)
            if perf_strat is None and isinstance(report, dict):
                perf_strat = report.get("perf_strat")
            perf_strat = perf_strat or []

            has_perf_data = has_current_holdings and (bool(perf_isin) or bool(perf_strat))

            if has_perf_data:
                story.append(NextPageTemplate("PerformanceBody"))
                story.append(PageBreak())

                doc.header_title = "Performance"
                story.append(Spacer(1, 0))

                perf_strat_map = {}
                for x in perf_strat:
                    key = norm(x.get("g", "")) if isinstance(x, dict) else norm(getattr(x, "g", ""))
                    perf_strat_map[key] = x

                perf_colWidth = [85 * mm, 18 * mm, 28 * mm, 28 * mm, 28 * mm, 27 * mm, 32 * mm, 27 * mm]

                rows = [[
                    "Fund",
                    "Weight",
                    "Investment",
                    "Current Value",
                    "Gains",
                    "Return(Abs)",
                    "XIRR(Holdings)",
                    "XIRR(SI)",
                ]]

                group_row_indices = []

                if not perf_isin:
                    rows.append(["-", "-", "-", "-", "-", "-", "-", "-"])
                else:
                    pan_summary = getattr(report, "pan_summary", None)
                    if pan_summary is None and isinstance(report, dict):
                        pan_summary = report.get("pan_summary")
                    pan_item = (pan_summary or [None])[0]

                    if pan_item:
                        rows.append([
                            Paragraph("<b>Portfolio Metrics</b>", self.styles["BodySmall"]),
                            "",
                            self._fmt(getattr(pan_item, "inv", 0.0)),
                            self._fmt(getattr(pan_item, "cv", 0.0)),
                            self._fmt(getattr(pan_item, "ugl", 0.0)),
                            self._fmt_pct(getattr(pan_item, "ret", 0.0)),
                            self._fmt_pct(getattr(pan_item, "x1", 0.0)),
                            self._fmt_pct(getattr(pan_item, "x2", 0.0)),
                        ])

                    for group_key, group_iter in groupby(perf_isin, key=lambda x: norm(getattr(x, "g", "")) or "-"):
                        group_items = list(group_iter)
                        group_label = getattr(group_items[0], "g", group_key.title()) if group_items else group_key.title()

                        g = perf_strat_map.get(group_key)
                        if g is None:
                            g = type("G", (), {
                                "w": 0.0, "inv": 0.0, "cv": 0.0, "ugl": 0.0,
                                "ret": 0.0, "x1": 0.0, "x2": 0.0
                            })()

                        group_row_indices.append(len(rows))
                        rows.append([
                            Paragraph(f"<b>{group_label}</b>", self.styles["BodySmall"]),
                            self._fmt_pct(getattr(g, "w", 0.0)),
                            self._fmt(getattr(g, "inv", 0.0)),
                            self._fmt(getattr(g, "cv", 0.0)),
                            self._fmt(getattr(g, "ugl", 0.0)),
                            self._fmt_pct(getattr(g, "ret", 0.0)),
                            self._fmt_pct(getattr(g, "x1", 0.0)),
                            self._fmt_pct(getattr(g, "x2", 0.0)),
                        ])

                        for category, cat_iter in groupby(group_items, key=lambda x: norm(getattr(x, "c", "")) or "-"):
                            cat_items = list(cat_iter)
                            category_label = getattr(cat_items[0], "c", category.title()) if cat_items else category.title()

                            rows.append([
                                Paragraph(f'<font color="#24579e"><b>{category_label}</b></font>', self.styles["BodySmall"]),
                                "", "", "", "", "", "", "",
                            ])

                            for x in cat_items:
                                rows.append([
                                    getattr(x, "fund_display", getattr(x, "p", "-")),
                                    self._fmt(getattr(x, "w", 0.0)),
                                    self._fmt(getattr(x, "inv", 0.0)),
                                    self._fmt(getattr(x, "cv", 0.0)),
                                    self._fmt(getattr(x, "ugl", 0.0)),
                                    self._fmt_pct(getattr(x, "ret", 0.0)),
                                    self._fmt_pct(getattr(x, "x1", 0.0)),
                                    self._fmt_pct(getattr(x, "x2", 0.0)),
                                ])

                story.append(self._perf_long_table(rows, perf_colWidth, group_row_indices))

        ### Profitbook Page ###

        profitbook = getattr(report, "profitbook_transactions", []) or []

        if profitbook:
            story.append(NextPageTemplate("ProfitbookBody"))
            story.append(PageBreak())

            doc.header_title = "Profitbook"
            story.append(Spacer(1, 0))

            def fy_rank(v):
                s = str(v or "").strip().upper()
                digits = "".join(ch for ch in s if ch.isdigit())
                return int(digits) if digits.isdigit() else -1

            def norm(v):
                return str(v or "").strip().lower()

            def client_key_fn(x):
                return str(
                    getattr(x, "p", None)
                    or getattr(x, "pan", None)
                    or getattr(x, "levelpan", None)
                    or getattr(x, "client_pan", None)
                    or "UNKNOWN"
                ).strip() or "UNKNOWN"

            def client_name_fn(x):
                return str(
                    getattr(x, "n", None)
                    or getattr(x, "name", None)
                    or getattr(x, "client_name", None)
                    or ""
                ).strip()

            kpi = getattr(report, "kpi", None)
            user_type = str(getattr(kpi, "user_type", "individual")).strip().lower()

            profitbook = sorted(
                profitbook,
                key=lambda x: (
                    client_key_fn(x),
                    fy_rank(getattr(x, "financial_year", "")),
                    norm(getattr(x, "g", "")),
                    norm(getattr(x, "fund_display", "")),
                    norm(getattr(x, "folio_no", "")),
                    norm(getattr(x, "dop", "")),
                ),
                reverse=True,
            )

            pb_colWidth = [66 * mm, 23 * mm, 23 * mm, 23 * mm, 23 * mm, 23 * mm, 23 * mm, 23 * mm, 23 * mm, 23 * mm]
            headers = ["Fund", "Folio", "DOP", "DOS", "Units", "Investment", "Sale Value", "Gain", "Return", "Type"]

            if user_type == "family":
                client_groups = []
                for client_key, client_iter in groupby(profitbook, key=client_key_fn):
                    client_groups.append((client_key, list(client_iter)))

                for client_key, client_items in client_groups:
                    client_name = client_name_fn(client_items[0]) if client_items else ""
                    header_text = f"{client_name}" if client_name else f"{client_key}"

                    client_cost = sum(float(getattr(x, "total_cost", 0.0) or 0.0) for x in client_items)
                    client_sale = sum(float(getattr(x, "total_proceeds", 0.0) or 0.0) for x in client_items)
                    client_gain = sum(float(getattr(x, "total_gain_loss", 0.0) or 0.0) for x in client_items)
                    client_pct = (client_gain / client_cost * 100.0) if client_cost else 0.0

                    rows = []
                    rows.append(headers)

                    rows.append([
                        Paragraph(f'<b><font color="#24579e">{header_text}</font></b>', self.styles["BodySmall"]),
                        "", "", "", "",
                        self._fmt(client_cost),
                        self._fmt(client_sale),
                        self._fmt(client_gain),
                        self._fmt_pct(client_pct),
                        ""
                    ])

                    fy_groups = []
                    for fy, items in groupby(client_items, key=lambda x: str(getattr(x, "financial_year", "")).strip()):
                        fy_groups.append((fy, list(items)))

                    latest_fy = fy_groups[0][0] if fy_groups else None

                    for fy, fy_items in fy_groups:
                        summary_cost = sum(float(getattr(x, "total_cost", 0.0) or 0.0) for x in fy_items)
                        summary_sale = sum(float(getattr(x, "total_proceeds", 0.0) or 0.0) for x in fy_items)
                        summary_gain = sum(float(getattr(x, "total_gain_loss", 0.0) or 0.0) for x in fy_items)
                        summary_pct = (summary_gain / summary_cost * 100.0) if summary_cost else 0.0

                        if fy == latest_fy:
                            rows.append([
                                Paragraph(f'<b>{fy} - Total</b>', self.styles["BodySmall"]),
                                "", "", "", "",
                                self._fmt(summary_cost),
                                self._fmt(summary_sale),
                                self._fmt(summary_gain),
                                self._fmt_pct(summary_pct),
                                "",
                            ])

                            fy_items = sorted(
                                fy_items,
                                key=lambda x: (
                                    norm(getattr(x, "g", "")),
                                    norm(getattr(x, "gain_type", "")),
                                    norm(getattr(x, "fund_display", "")),
                                    norm(getattr(x, "folio_no", "")),
                                    norm(getattr(x, "dop", "")),
                                )
                            )

                            for group_key, group_iter in groupby(fy_items, key=lambda x: norm(getattr(x, "g", "")) or "-"):
                                group_items = list(group_iter)
                                group_label = getattr(group_items[0], "g", group_key.upper()) if group_items else group_key.upper()

                                rows.append([
                                    Paragraph(f'<b><font color="#24579e">{group_label}</font></b>', self.styles["BodySmall"]),
                                    "", "", "", "", "", "", "", "", ""
                                ])

                                for x in group_items:
                                    rows.append([
                                        getattr(x, "fund_display", "-"),
                                        getattr(x, "folio_no", "-"),
                                        getattr(x, "dop", "-"),
                                        getattr(x, "dos", "-"),
                                        self._fmt_three_dec(getattr(x, "total_units", 0.0)),
                                        self._fmt(getattr(x, "total_cost", 0.0)),
                                        self._fmt(getattr(x, "total_proceeds", 0.0)),
                                        self._fmt(getattr(x, "total_gain_loss", 0.0)),
                                        self._fmt_pct(getattr(x, "gain_loss_pct", 0.0)),
                                        getattr(x, "gain_type", "-"),
                                    ])
                        else:
                            rows.append([
                                Paragraph(f'<b>{fy} - Total</b>', self.styles["BodySmall"]),
                                "", "", "", "",
                                self._fmt(summary_cost),
                                self._fmt(summary_sale),
                                self._fmt(summary_gain),
                                self._fmt_pct(summary_pct),
                                "",
                            ])

                    table = self._profit_table(rows, pb_colWidth)
                    story.append(table)
                    story.append(Spacer(1, 2))

            else:
                # individual flow: preserve your existing logic, just without grouping by client
                fy_groups = []
                for fy, items in groupby(profitbook, key=lambda x: str(getattr(x, "financial_year", "")).strip()):
                    fy_groups.append((fy, list(items)))

                latest_fy = fy_groups[0][0] if fy_groups else None

                for fy, fy_items in fy_groups:
                    story.append(Spacer(1, 2))

                    summary_cost = sum(float(getattr(x, "total_cost", 0.0) or 0.0) for x in fy_items)
                    summary_sale = sum(float(getattr(x, "total_proceeds", 0.0) or 0.0) for x in fy_items)
                    summary_gain = sum(float(getattr(x, "total_gain_loss", 0.0) or 0.0) for x in fy_items)
                    summary_pct = (summary_gain / summary_cost * 100.0) if summary_cost else 0.0

                    if fy == latest_fy:
                        rows = [headers]
                        rows.append([
                            Paragraph(f'<b>{fy} - Total</b>', self.styles["BodySmall"]),
                            "", "", "", "",
                            self._fmt(summary_cost),
                            self._fmt(summary_sale),
                            self._fmt(summary_gain),
                            self._fmt_pct(summary_pct),
                            "",
                        ])

                        fy_items = sorted(
                            fy_items,
                            key=lambda x: (
                                norm(getattr(x, "g", "")),
                                norm(getattr(x, "gain_type", "")),
                                norm(getattr(x, "fund_display", "")),
                                norm(getattr(x, "folio_no", "")),
                                norm(getattr(x, "dop", "")),
                            )
                        )

                        for group_key, group_iter in groupby(fy_items, key=lambda x: norm(getattr(x, "g", "")) or "-"):
                            group_items = list(group_iter)
                            group_label = getattr(group_items[0], "g", group_key.upper()) if group_items else group_key.upper()

                            rows.append([
                                Paragraph(f'<b><font color="#24579e">{group_label}</font></b>', self.styles["BodySmall"]),
                                "", "", "", "", "", "", "", "", "",
                            ])

                            for x in group_items:
                                rows.append([
                                    getattr(x, "fund_display", "-"),
                                    getattr(x, "folio_no", "-"),
                                    getattr(x, "dop", "-"),
                                    getattr(x, "dos", "-"),
                                    self._fmt_three_dec(getattr(x, "total_units", 0.0)),
                                    self._fmt(getattr(x, "total_cost", 0.0)),
                                    self._fmt(getattr(x, "total_proceeds", 0.0)),
                                    self._fmt(getattr(x, "total_gain_loss", 0.0)),
                                    self._fmt_pct(getattr(x, "gain_loss_pct", 0.0)),
                                    getattr(x, "gain_type", "-"),
                                ])

                        story.append(self._profit_table(rows, pb_colWidth))

                    else:
                        fy_row = [
                            Paragraph(f'<b>{fy} - Total</b>', self.styles["BodySmall"]),
                            "", "", "", "",
                            self._fmt(summary_cost),
                            self._fmt(summary_sale),
                            self._fmt(summary_gain),
                            self._fmt_pct(summary_pct),
                            "",
                        ]

                        fy_table = Table([fy_row], colWidths=pb_colWidth, repeatRows=0)
                        fy_table.setStyle(TableStyle([
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e8eef7")),
                            ("GRID", (0, 0), (-1, -1), 0.05, colors.lightgrey),
                            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                            ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                            ("ALIGN", (0, 0), (1, -1), "LEFT"),
                            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                        ]))
                        story.append(fy_table)
                        story.append(Spacer(1, 2))

        ### Disclaimer ###

        story.append(NextPageTemplate("Last"))
        story.append(PageBreak())

        self.disclaimer_paragraphs = [
            "This portfolio report has been prepared by reporting platform Echo, "
            "solely owned by Definitif Investments, hence forth called as Definitif, "
            "exclusively for the named client based on information available from "
            "custodians/ registrars/ fund houses/ brokers/ and other third-party sources "
            "believed to be reliable. While every effort has been made to ensure the accuracy "
            "and completeness of the information presented, Definitif does not warrant or "
            "guarantee its accuracy, completeness, or timeliness and accepts no liability "
            "for any errors, omissions, or inaccuracies.",
            "The report is intended solely for informational and portfolio review purposes "
            "and should not be construed as investment, legal, tax, accounting, or financial advice, "
            "nor as an offer, solicitation, or recommendation to buy, sell, or hold any "
            "security or financial product. Investment decisions should be made only after considering "
            "individual financial circumstances, investment objectives, risk tolerance, and, "
            "where appropriate, after consulting qualified professional advisors.",
            "Portfolio valuations, returns, gains, losses, and other performance metrics are "
            "based on available market data and valuation methodologies as of the report date. "
            "These values are subject to change due to market movements, corporate actions, "
            "pricing updates, or revised information. Past performance is not indicative of future results, "
            "and all investments are subject to market risks, including the possible loss of principal.",
            "Any projections, estimates, or forward-looking statements contained in this report are "
            "based on current assumptions and market conditions and are inherently subject "
            "to uncertainties. Actual outcomes may differ materially from those expressed or implied.",
            "Clients are advised to carefully review this report and promptly notify Definitif of "
            "any discrepancies or missing information. Definitif shall not be responsible for any "
            "investment decisions or actions taken solely on the basis of this report.",
            "This report is confidential and intended solely for the use of the named recipient. "
            "It may contain proprietary and privileged information and should not be reproduced, "
            "distributed, published, or shared, in whole or in part, without the prior written consent of Definitif.",
            "Mutual Fund investments are subject to market risks. "
            "Please read all scheme-related documents carefully before investing.",
        ]

        disclaimer_head = ParagraphStyle(
            "DisclaimerHead",
            parent=self.styles["SectionHead"],
            leftIndent=6 * mm,
            rightIndent=6 * mm,
            alignment=TA_LEFT,
        )

        body_small_justify = ParagraphStyle(
            "BodySmallJustify",
            parent=self.styles["BodySmall"],
            alignment=TA_JUSTIFY,
            leftIndent=6 * mm,
            rightIndent=6 * mm,
        )

        story.append(Spacer(1, 50 * mm))
        story.append(Paragraph("<b>Disclaimer</b>", disclaimer_head))
        story.append(Spacer(1, 8))

        for para_text in self.disclaimer_paragraphs:
            story.append(Paragraph(para_text, body_small_justify))
            story.append(Spacer(1, 4))


        doc.build(story)

        return {
            "portfolio_stmt_pdf": str(self.output_path),
            "valuation_date": self.cover_valuation_date,
        }