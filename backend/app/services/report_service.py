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

    # ------------------------------------------------------------------
    # Structured Markdown report  (POST /reports/markdown)
    # ------------------------------------------------------------------

    def generate_markdown_report(self, req: ReportRequest) -> ReportResponse:
        """
        Build a 6-section business-readable markdown report.
        Uses: enhanced_kpis(), priority_list(), InsightEngine — no new deps.
        """
        from app.decision_engine.insight_engine import InsightEngine

        # ── Gather data ──────────────────────────────────────────────────────
        enhanced = self._ds.enhanced_kpis()
        core = enhanced.core_kpis
        biz  = enhanced.business_metrics

        try:
            insight = InsightEngine.from_kpis(self._ds.kpis(), self._ds.df)
        except Exception:
            insight = None

        top_customers = self._rs.priority_list(top_n=3).customers

        # ── Derived values ───────────────────────────────────────────────────
        exec_summary = (
            insight.executive_summary if insight
            else enhanced.executive_note
            or f"Churn rate is {core.churn_rate_pct:.1f}% across "
               f"{core.total_customers:,} customers, with "
               f"${core.revenue_at_risk:,.0f} revenue at risk."
        )

        key_insights = (
            insight.key_drivers[:3] if insight and insight.key_drivers
            else [
                f"Churn rate: {core.churn_rate_pct:.1f}% — "
                f"classified as {self._risk_label(core.churn_rate_pct)}",
                f"Revenue at risk (churned accounts): ${core.revenue_at_risk:,.0f}",
                f"Avg churn risk score: {core.avg_churn_risk_score:.2f} "
                f"(0 = safe · 1 = certain churn)",
            ]
        )

        actions = [
            f"**{c.recommended_action}** — {c.customer_segment} / "
            f"{c.plan_type} in {c.region} "
            f"(Risk: {c.churn_risk_score:.2f}, CLV: ${c.estimated_clv:,.0f})"
            for c in top_customers
        ] or [
            "Deploy Premium Retention Offers for Critical-priority accounts",
            "Schedule Service Recovery Calls within 48 hours for high-risk accounts",
            "Run monthly check-ins on high-value customers to prevent drift",
        ]

        risk_label     = insight.business_impact.risk_level if insight and insight.business_impact else "High"
        confidence     = insight.confidence_level if insight else "Medium"
        recovery_pct   = 20 if risk_label in ("Critical", "High") else 15
        recoverable    = biz.revenue_at_risk * recovery_pct / 100
        now            = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        title          = req.title or "Customer Retention AI — Executive Report"

        # ── Build markdown ───────────────────────────────────────────────────
        md = "\n".join([
            f"# {title}",
            f"_Generated: {now}_\n",
            "---\n",
            "## 1. Executive Summary\n",
            exec_summary, "",
            "---\n",
            "## 2. Current State\n",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Customers | {core.total_customers:,} |",
            f"| Churn Rate | {core.churn_rate_pct:.1f}% |",
            f"| Avg CLV | ${core.avg_clv:,.0f} |",
            f"| Revenue at Risk (churned) | ${core.revenue_at_risk:,.0f} |",
            f"| Avg Risk Score | {core.avg_churn_risk_score:.2f} |",
            f"| Avg Satisfaction | {core.avg_satisfaction_score:.1f}/10 |",
            "",
            "---\n",
            "## 3. Key Insights\n",
            *[f"- {d}" for d in key_insights],
            "",
            "---\n",
            "## 4. Financial Impact\n",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Revenue at Risk (top-quartile churn risk) | ${biz.revenue_at_risk:,.0f} |",
            f"| High-Value Customers | {biz.high_value_customers:,} "
            f"({biz.high_value_pct:.1f}% of base) |",
            f"| Top Churn Region | {biz.churn_concentration.top_region} "
            f"({biz.churn_concentration.pct_of_total_churned:.1f}% of churned) |",
            "",
            "---\n",
            "## 5. Recommended Actions\n",
            *[f"{i+1}. {a}" for i, a in enumerate(actions)],
            "",
            "---\n",
            "## 6. Expected Outcome\n",
            f"Executing these retention actions targets recovery of approximately "
            f"**{recovery_pct}%** of at-risk revenue — "
            f"**${recoverable:,.0f}** in protected revenue. "
            f"Risk classification: **{risk_label}**.",
            "",
            f"_Confidence level: {confidence}_",
            "",
            "---",
            "_Report generated automatically by the Customer Retention AI Agent._",
        ])

        # ── Save ─────────────────────────────────────────────────────────────
        filename = f"executive_report_{_ts()}.md"
        filepath = os.path.join(_ensure_reports_dir(), filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)

        return ReportResponse(
            report_type="markdown",
            filename=filename,
            download_path=f"/reports/export/{filename}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            size_bytes=os.path.getsize(filepath),
        )


    # ── Static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _risk_label(churn_pct: float) -> str:
        if churn_pct >= 25: return "Critical"
        if churn_pct >= 20: return "High"
        if churn_pct >= 15: return "Elevated"
        return "Moderate"
