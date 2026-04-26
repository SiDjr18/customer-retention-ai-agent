"""
ReportService — generates PDF, CSV, and PPT (or Markdown) reports.

Dependencies:
  PDF  → reportlab  (pip install reportlab)
  CSV  → pandas (already required)
  PPT  → python-pptx (pip install python-pptx) — graceful markdown fallback
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from typing import List

import pandas as pd

from app.config import settings
from app.schemas.report_schema import ReportRequest, ReportResponse
from app.services.dataset_service import DatasetService
from app.services.recommendation_service import RecommendationService

_TS_FMT = "%Y%m%d_%H%M%S"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime(_TS_FMT)


def _ensure_reports_dir() -> str:
    os.makedirs(settings.REPORTS_DIR, exist_ok=True)
    return settings.REPORTS_DIR


class ReportService:
    def __init__(self) -> None:
        self._ds = DatasetService()
        self._rs = RecommendationService()

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------

    def generate_pdf(self, req: ReportRequest) -> ReportResponse:
        """Generate a PDF executive report using reportlab."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            )
            from reportlab.lib import colors
        except ImportError:
            raise ImportError(
                "reportlab is required for PDF generation. "
                "Install with: pip install reportlab"
            )

        kpis = self._ds.kpis()
        filename = f"executive_report_{_ts()}.pdf"
        filepath = os.path.join(_ensure_reports_dir(), filename)

        doc = SimpleDocTemplate(filepath, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        # Title
        story.append(Paragraph(req.title or "Customer Retention AI — Executive Report", styles["Title"]))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
        story.append(Spacer(1, 0.5 * cm))

        # KPI summary table
        story.append(Paragraph("KPI Snapshot", styles["Heading2"]))
        kpi_data = [
            ["Metric", "Value"],
            ["Total Customers", f"{kpis.total_customers:,}"],
            ["Churn Rate", f"{kpis.churn_rate_pct:.1f}%"],
            ["Avg CLV", f"${kpis.avg_clv:,.2f}"],
            ["Revenue at Risk", f"${kpis.revenue_at_risk:,.2f}"],
            ["Avg Risk Score", f"{kpis.avg_churn_risk_score:.2f}"],
            ["Avg Satisfaction", f"{kpis.avg_satisfaction_score:.2f}"],
        ]
        tbl = Table(kpi_data, colWidths=[8 * cm, 6 * cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c6b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.5 * cm))

        # Churn by region
        story.append(Paragraph("Churn Rate by Region", styles["Heading2"]))
        region_data = [["Region", "Churn Rate"]] + [
            [r, f"{v:.1f}%"] for r, v in sorted(kpis.churn_by_region.items(), key=lambda x: -x[1])
        ]
        if len(region_data) > 1:
            rtbl = Table(region_data, colWidths=[8 * cm, 6 * cm])
            rtbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c6b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
            ]))
            story.append(rtbl)

        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(
            "This report was generated automatically by the Customer Retention AI Agent.",
            styles["Italic"],
        ))

        doc.build(story)
        size = os.path.getsize(filepath)

        return ReportResponse(
            report_type="pdf",
            filename=filename,
            download_path=f"/reports/export/{filename}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            size_bytes=size,
        )

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------

    def generate_csv(self, req: ReportRequest) -> ReportResponse:
        """Export high-risk customer action list as CSV."""
        from app.schemas.dataset import FilterRequest
        from app.schemas.recommendation_schema import CustomerRecommendRequest

        filter_req = FilterRequest(limit=req.top_n_customers or 200)
        result = self._ds.filter_data(filter_req)

        rows = result.records
        # Sort by churn risk descending
        rows_sorted = sorted(
            rows,
            key=lambda r: float(r.get("churn_risk_score") or r.get("risk_score") or 0),
            reverse=True,
        )[: req.top_n_customers]

        # Enrich with NBA recommendation
        enriched = []
        for r in rows_sorted:
            reco_req = CustomerRecommendRequest(
                customer_id=str(r.get("customer_id", "")),
                churn_risk_score=float(r.get("churn_risk_score") or 0),
                estimated_clv=float(r.get("estimated_clv") or 0),
                upsell_probability=float(r.get("upsell_probability") or 0),
                retention_offer_cost=float(r.get("retention_offer_cost") or 0),
                complaints_90d=int(r.get("complaints_90d") or 0),
                payment_failures_12m=int(r.get("payment_failures_12m") or 0),
                satisfaction_score=float(r.get("satisfaction_score") or 5.0),
                contract_type=str(r.get("contract_type") or ""),
                plan_type=str(r.get("plan_type") or ""),
            )
            reco = self._rs.recommend_single(reco_req)
            row_out = dict(r)
            row_out["recommended_action"] = reco.recommendation
            row_out["action_priority"] = reco.priority
            row_out["expected_revenue_protected"] = reco.expected_revenue_protected
            enriched.append(row_out)

        filename = f"customer_action_list_{_ts()}.csv"
        filepath = os.path.join(_ensure_reports_dir(), filename)

        if enriched:
            keys = list(enriched[0].keys())
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(enriched)
        else:
            with open(filepath, "w") as f:
                f.write("No records found.\n")

        return ReportResponse(
            report_type="csv",
            filename=filename,
            download_path=f"/reports/export/{filename}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            size_bytes=os.path.getsize(filepath),
        )

    # ------------------------------------------------------------------
    # PPT / Markdown fallback
    # ------------------------------------------------------------------

    def generate_ppt(self, req: ReportRequest) -> ReportResponse:
        """
        Generate a PowerPoint summary.
        Falls back to a Markdown report if python-pptx is unavailable.
        """
        try:
            return self._generate_pptx(req)
        except ImportError:
            return self._generate_markdown(req)

    def _generate_pptx(self, req: ReportRequest) -> ReportResponse:
        from pptx import Presentation  # type: ignore
        from pptx.util import Inches, Pt  # type: ignore
        from pptx.dml.color import RGBColor  # type: ignore

        kpis = self._ds.kpis()
        prs = Presentation()
        blank_layout = prs.slide_layouts[5]

        def _add_slide(title_text: str, body_lines: List[str]) -> None:
            slide = prs.slides.add_slide(blank_layout)
            txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(1))
            tf = txBox.text_frame
            tf.text = title_text
            tf.paragraphs[0].runs[0].font.bold = True
            tf.paragraphs[0].runs[0].font.size = Pt(28)
            tf.paragraphs[0].runs[0].font.color.rgb = RGBColor(0x1a, 0x3c, 0x6b)

            body_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(9), Inches(5.5))
            btf = body_box.text_frame
            btf.word_wrap = True
            for i, line in enumerate(body_lines):
                if i == 0:
                    btf.text = line
                else:
                    p = btf.add_paragraph()
                    p.text = line
                    p.space_before = Pt(4)

        # Slide 1 — Title
        _add_slide(
            req.title or "Customer Retention AI — Executive Summary",
            [f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"],
        )

        # Slide 2 — KPIs
        _add_slide("KPI Snapshot", [
            f"• Total Customers: {kpis.total_customers:,}",
            f"• Churn Rate: {kpis.churn_rate_pct:.1f}%",
            f"• Average CLV: ${kpis.avg_clv:,.2f}",
            f"• Revenue at Risk: ${kpis.revenue_at_risk:,.2f}",
            f"• Avg Risk Score: {kpis.avg_churn_risk_score:.2f}",
            f"• Avg Satisfaction: {kpis.avg_satisfaction_score:.2f}",
        ])

        # Slide 3 — Regional Churn
        region_lines = ["Regional Churn Breakdown:"] + [
            f"• {r}: {v:.1f}%"
            for r, v in sorted(kpis.churn_by_region.items(), key=lambda x: -x[1])
        ]
        _add_slide("Churn by Region", region_lines)

        # Slide 4 — Recommended Actions
        _add_slide("Recommended Actions", [
            "1. Deploy Premium Retention Offers for Critical-priority accounts.",
            "2. Schedule Service Recovery Calls for complaint-heavy churners.",
            "3. Launch Payment Support Plans for financially stressed customers.",
            "4. Upsell low-risk / high-probability upgrade candidates.",
            "5. Implement CX intervention programme for low-satisfaction cohort.",
        ])

        filename = f"retention_summary_{_ts()}.pptx"
        filepath = os.path.join(_ensure_reports_dir(), filename)
        prs.save(filepath)

        return ReportResponse(
            report_type="pptx",
            filename=filename,
            download_path=f"/reports/export/{filename}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            size_bytes=os.path.getsize(filepath),
        )

    def _generate_markdown(self, req: ReportRequest) -> ReportResponse:
        """Markdown fallback when python-pptx is not installed."""
        kpis = self._ds.kpis()
        lines = [
            f"# {req.title or 'Customer Retention AI — Executive Summary'}",
            f"\n_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}_\n",
            "## KPI Snapshot\n",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Customers | {kpis.total_customers:,} |",
            f"| Churn Rate | {kpis.churn_rate_pct:.1f}% |",
            f"| Avg CLV | ${kpis.avg_clv:,.2f} |",
            f"| Revenue at Risk | ${kpis.revenue_at_risk:,.2f} |",
            f"| Avg Risk Score | {kpis.avg_churn_risk_score:.2f} |",
            f"| Avg Satisfaction | {kpis.avg_satisfaction_score:.2f} |",
            "\n## Churn by Region\n",
        ] + [
            f"- **{r}**: {v:.1f}%"
            for r, v in sorted(kpis.churn_by_region.items(), key=lambda x: -x[1])
        ] + [
            "\n## Recommended Actions\n",
            "1. Deploy Premium Retention Offers for Critical-priority accounts.",
            "2. Schedule Service Recovery Calls for complaint-heavy churners.",
            "3. Launch Payment Support Plans for financially stressed customers.",
            "4. Upsell low-risk / high-probability upgrade candidates.",
            "5. Implement CX intervention programme for low-satisfaction cohort.",
        ]

        filename = f"retention_summary_{_ts()}.md"
        filepath = os.path.join(_ensure_reports_dir(), filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return ReportResponse(
            report_type="markdown",
            filename=filename,
            download_path=f"/reports/export/{filename}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            size_bytes=os.path.getsize(filepath),
        )
