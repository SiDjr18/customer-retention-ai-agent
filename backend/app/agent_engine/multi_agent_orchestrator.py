"""
Multi-Agent Orchestrator — fully question-aware, no paid APIs required.

Architecture:
  Intent detector  → parse question → extract entities (region, segment, budget…)
  Router           → intent + keyword scoring → pick best agent
  Agent            → compute a SPECIFIC answer for the detected intent

5 specialist agents:
  DataAnalystAgent         — KPIs, churn rate, revenue, region/segment breakdowns
  RetentionStrategistAgent — priority lists, outreach, segment-specific strategy
  ScenarioPlannerAgent     — what-if, budget ROI, simulation
  ExecutiveBriefingAgent   — narrative executive summaries for leadership
  UploadedDataAgent        — questions about the currently uploaded file / dataset
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class MultiChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


class RecommendedAction(BaseModel):
    priority: str
    action:   str
    rationale: str


class BusinessImpact(BaseModel):
    revenue_at_risk:     Optional[str] = None
    affected_customers:  Optional[int] = None
    risk_level:          str = "Moderate"


class MultiChatResponse(BaseModel):
    agent_used:          str
    executive_summary:   str
    key_insights:        List[str]
    business_impact:     Optional[BusinessImpact] = None
    recommended_actions: List[RecommendedAction]
    confidence_level:    str


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt(v: float) -> str:
    if v >= 1e7:  return f"₹{v/1e7:.2f} Cr"
    if v >= 1e5:  return f"₹{v/1e5:.2f} Lakh"
    return f"₹{v:,.0f}"

def _risk_level(churn_pct: float) -> str:
    if churn_pct >= 25: return "Critical"
    if churn_pct >= 20: return "High"
    if churn_pct >= 15: return "Elevated"
    return "Moderate"

def _rank_dict(d: dict, top_n: int = 20) -> List[Tuple[str, float]]:
    return sorted(d.items(), key=lambda x: x[1], reverse=True)[:top_n]


# ─────────────────────────────────────────────────────────────────────────────
# Intent detection — returns (intent_name, extracted_params)
# ─────────────────────────────────────────────────────────────────────────────

def _detect_intent(message: str) -> Tuple[str, Dict[str, Any]]:
    msg    = message.lower()
    params: Dict[str, Any] = {}

    # Extract budget
    m = re.search(r'\$([\d,]+(?:\.\d+)?)\s*([km]?)', msg)
    if m:
        v = float(m.group(1).replace(',', ''))
        sfx = m.group(2).lower()
        if sfx == 'k': v *= 1_000
        elif sfx == 'm': v *= 1_000_000
        params['budget'] = v

    # Extract discount
    m = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:off|discount|offer)', msg)
    if m: params['discount'] = float(m.group(1))

    # Extract top-N
    m = re.search(r'top\s*(\d+)', msg)
    if m: params['top_n'] = int(m.group(1))

    # Extract segment mentions
    for seg in ['premium', 'standard', 'enterprise', 'basic', 'platinum',
                'gold', 'silver', 'sme', 'smb', 'corporate', 'retail', 'consumer']:
        if seg in msg:
            params['segment'] = seg.title()
            break

    # Extract region mentions (Indian cities + generic directions)
    for reg in ['mumbai', 'delhi', 'bangalore', 'bengaluru', 'chennai', 'kolkata',
                'hyderabad', 'pune', 'ahmedabad', 'jaipur', 'surat', 'lucknow',
                'kanpur', 'nagpur', 'indore', 'thane', 'bhopal', 'visakhapatnam',
                'north', 'south', 'east', 'west', 'central']:
        if reg in msg:
            params['region'] = reg.title()
            break

    # ── Intent classification ──────────────────────────────────────────────

    if re.search(r'upload|my\s+file|this\s+file|this\s+data(?:set)?|the\s+file|'
                 r'what\s+did\s+i\s+upload|what.?s\s+in\s+the\s+file|'
                 r'what\s+(?:data|file)\s+do\s+(?:i|we)\s+have', msg):
        return 'upload_info', params

    # Named region/segment checks come BEFORE generic churn_rate so
    # "what is churn in Mumbai?" → specific_region, not churn_rate
    if 'region' in params and re.search(r'what|how|tell|show|give|analyse|analyze|churn|rate|perform', msg):
        return 'specific_region', params

    if 'segment' in params and re.search(r'what|how|tell|show|give|analyse|analyze|strateg|retain|churn|rate', msg):
        return 'specific_segment', params

    if re.search(r'churn\s*rate|how\s+(?:many|much).*churn|what\s+(?:is|was|.?s)\s+(?:the\s+)?churn|'
                 r'overall\s+churn|total\s+churn|churn\s+percent', msg):
        return 'churn_rate', params

    if re.search(r'revenue\s+at\s+risk|revenue.*risk|risk.*revenue|'
                 r'money\s+at\s+risk|financial\s+(?:risk|exposure)|how\s+much.*(?:risk|lose|loss)', msg):
        return 'revenue_risk', params

    if re.search(r'which\s+region|region.*(?:highest|most|worst|best)|'
                 r'top\s+region|by\s+region|region(?:al)?\s+(?:breakdown|analysis|churn)', msg):
        return 'region_breakdown', params

    if re.search(r'which\s+segment|segment.*(?:highest|most|worst|best)|'
                 r'top\s+segment|by\s+segment|segment(?:al)?\s+(?:breakdown|analysis|churn)', msg):
        return 'segment_breakdown', params

    if re.search(r'satisf|csat|nps|customer\s+(?:experience|cx)|happiness|sentiment', msg):
        return 'satisfaction', params

    if re.search(r'top\s*(?:\d+\s*)?(?:priority\s+)?customers?|priority\s+(?:customer|list|queue)|'
                 r'who\s+(?:should|to)\s+(?:we\s+)?(?:contact|call|reach|target)|'
                 r'outreach\s+(?:list|priority)|at.risk\s+customers?', msg):
        return 'top_customers', params

    if re.search(r'simulat|what.?if|budget|roi|return\s+on|scenario|'
                 r'forecast|spend|retention\s+campaign|campaign\s+(?:cost|budget|roi)', msg):
        return 'scenario', params

    if re.search(r'strateg|recommend|how\s+to\s+retain|retention\s+(?:strategy|plan|approach)|'
                 r'best\s+(?:action|approach|way)\s+to\s+retain', msg):
        return 'strategy', params

    if re.search(r'summar|executive|overview|brief(?:ing)?|report|'
                 r'(?:tell|give)\s+me\s+(?:everything|all)|status\s+report', msg):
        return 'executive', params

    return 'general_analysis', params


# ─────────────────────────────────────────────────────────────────────────────
# Agent 1 — Data Analyst
# ─────────────────────────────────────────────────────────────────────────────

class DataAnalystAgent:
    NAME = "DataAnalystAgent"

    def run(self, message: str, context: dict) -> MultiChatResponse:
        from app.services.dataset_service import DatasetService
        intent, params = _detect_intent(message)
        svc  = DatasetService()
        kpis = svc.kpis()
        rl   = _risk_level(kpis.churn_rate_pct)

        if intent == 'churn_rate':
            return self._churn_rate(kpis, rl)
        if intent == 'revenue_risk':
            return self._revenue_risk(kpis, svc.enhanced_kpis(), rl)
        if intent == 'region_breakdown':
            return self._region_breakdown(kpis, rl)
        if intent == 'segment_breakdown':
            return self._segment_breakdown(kpis, rl)
        if intent == 'specific_region':
            return self._specific_region(kpis, rl, params.get('region', ''))
        if intent == 'specific_segment':
            return self._specific_segment(kpis, rl, params.get('segment', ''))
        if intent == 'satisfaction':
            return self._satisfaction(kpis, rl)
        return self._general(kpis, svc.enhanced_kpis(), rl)

    # ── Sub-handlers ──────────────────────────────────────────────────────────

    def _churn_rate(self, kpis, rl) -> MultiChatResponse:
        churned  = int(kpis.total_customers * kpis.churn_rate_pct / 100)
        retained = kpis.total_customers - churned
        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=(
                f"Current churn rate: {kpis.churn_rate_pct:.1f}% — classified as {rl} risk. "
                f"Out of {kpis.total_customers:,} customers, {churned:,} have churned "
                f"and {retained:,} are retained ({100-kpis.churn_rate_pct:.1f}% retention rate)."
            ),
            key_insights=[
                f"Churn rate: {kpis.churn_rate_pct:.1f}% → {rl} risk level",
                f"Churned customers: {churned:,} | Retained: {retained:,}",
                f"Revenue lost to churn: {_fmt(kpis.revenue_at_risk)}",
                f"Avg CLV per customer: {_fmt(kpis.avg_clv)}",
                f"Avg churn risk score: {kpis.avg_churn_risk_score:.3f} (0 = safe, 1 = certain churn)",
                f"Avg satisfaction score: {kpis.avg_satisfaction_score:.1f}/10",
                "Industry benchmark: < 15% healthy | 15–25% high | > 25% critical",
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt(kpis.revenue_at_risk),
                affected_customers=churned,
                risk_level=rl,
            ),
            recommended_actions=[
                RecommendedAction(priority="High",
                    action="Immediate intervention for customers with risk score > 0.7",
                    rationale=f"Churn at {kpis.churn_rate_pct:.1f}% is a {rl} risk classification"),
                RecommendedAction(priority="Medium",
                    action="Deploy monthly churn risk scoring across all customers",
                    rationale="Proactive scoring enables intervention before churn, not after"),
                RecommendedAction(priority="Low",
                    action="Set up real-time alert when satisfaction score drops below 6",
                    rationale="Satisfaction decline is the strongest leading indicator of churn"),
            ],
            confidence_level="High",
        )

    def _revenue_risk(self, kpis, enh, rl) -> MultiChatResponse:
        biz = enh.business_metrics
        combined = kpis.revenue_at_risk + biz.revenue_at_risk
        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=(
                f"Revenue at risk (churned CLV): {_fmt(kpis.revenue_at_risk)}. "
                f"Additional forward exposure from the top-quartile risk cohort: {_fmt(biz.revenue_at_risk)}. "
                f"Combined total exposure: {_fmt(combined)}."
            ),
            key_insights=[
                f"Realised revenue loss (churned CLV): {_fmt(kpis.revenue_at_risk)}",
                f"Forward risk (top-25% risk cohort, not yet churned): {_fmt(biz.revenue_at_risk)}",
                f"Total combined exposure: {_fmt(combined)}",
                f"Average CLV per customer: {_fmt(kpis.avg_clv)}",
                f"High-value customers at risk: {biz.high_value_customers:,} ({biz.high_value_pct:.1f}% of base)",
                f"Region with highest churn concentration: {biz.churn_concentration.top_region} "
                f"({biz.churn_concentration.pct_of_total_churned:.1f}% of all churned customers)",
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt(combined),
                affected_customers=int(kpis.total_customers * kpis.churn_rate_pct / 100),
                risk_level=rl,
            ),
            recommended_actions=[
                RecommendedAction(priority="High",
                    action="Protect top-CLV customers with priority retention programme",
                    rationale=f"{biz.high_value_customers:,} high-value customers hold disproportionate revenue"),
                RecommendedAction(priority="High",
                    action=f"Emergency retention blitz in {biz.churn_concentration.top_region}",
                    rationale=f"Region accounts for {biz.churn_concentration.pct_of_total_churned:.1f}% of churned revenue"),
                RecommendedAction(priority="Medium",
                    action="Model revenue recovery from a 5% churn reduction scenario",
                    rationale="Even small churn reduction at high CLV yields outsized revenue return"),
            ],
            confidence_level="High",
        )

    def _region_breakdown(self, kpis, rl) -> MultiChatResponse:
        ranked = _rank_dict(kpis.churn_by_region)
        if not ranked:
            return self._general(kpis, None, rl)
        top, avg = ranked[0], kpis.churn_rate_pct
        insights = []
        for i, (reg, pct) in enumerate(ranked[:10], 1):
            diff = pct - avg
            flag = " ▲ above avg" if diff > 2 else (" ▼ below avg" if diff < -2 else "")
            insights.append(f"#{i}  {reg}: {pct:.1f}%{flag}")
        insights.append(f"Portfolio average: {avg:.1f}%")
        if len(ranked) > 1:
            insights.append(f"Spread (worst–best): {ranked[0][1]-ranked[-1][1]:.1f} percentage points")
        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=(
                f"{top[0]} has the highest regional churn at {top[1]:.1f}% — "
                f"{top[1]-avg:.1f}pp above the {avg:.1f}% portfolio average. "
                f"Full ranking of {len(ranked)} regions:"
            ),
            key_insights=insights,
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt(kpis.revenue_at_risk),
                affected_customers=int(kpis.total_customers * kpis.churn_rate_pct / 100),
                risk_level=rl,
            ),
            recommended_actions=[
                RecommendedAction(priority="High",
                    action=f"Targeted retention campaign in {ranked[0][0]}",
                    rationale=f"Highest regional churn at {ranked[0][1]:.1f}%"),
                RecommendedAction(priority="High" if len(ranked) > 1 else "Medium",
                    action=f"Root-cause investigation in {ranked[1][0] if len(ranked)>1 else 'second region'}",
                    rationale=f"{ranked[1][1]:.1f}% churn — second highest" if len(ranked)>1 else ""),
                RecommendedAction(priority="Medium",
                    action=f"Replicate playbook from {ranked[-1][0]} (lowest churn) to high-churn regions",
                    rationale="Best-in-class region provides a proven retention model"),
            ],
            confidence_level="High",
        )

    def _segment_breakdown(self, kpis, rl) -> MultiChatResponse:
        ranked = _rank_dict(kpis.churn_by_segment)
        if not ranked:
            return self._general(kpis, None, rl)
        top, avg = ranked[0], kpis.churn_rate_pct
        insights = []
        for i, (seg, pct) in enumerate(ranked[:10], 1):
            diff = pct - avg
            flag = " ▲ above avg" if diff > 2 else (" ▼ below avg" if diff < -2 else "")
            insights.append(f"#{i}  {seg}: {pct:.1f}%{flag}")
        insights.append(f"Portfolio average: {avg:.1f}%")
        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=(
                f"{top[0]} is the highest-churning segment at {top[1]:.1f}% — "
                f"{top[1]-avg:.1f}pp above the {avg:.1f}% portfolio average. "
                f"Segment churn ranking ({len(ranked)} segments):"
            ),
            key_insights=insights,
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt(kpis.revenue_at_risk),
                affected_customers=int(kpis.total_customers * kpis.churn_rate_pct / 100),
                risk_level=rl,
            ),
            recommended_actions=[
                RecommendedAction(priority="High",
                    action=f"Priority retention offer for {ranked[0][0]} segment",
                    rationale=f"Highest churn at {ranked[0][1]:.1f}%"),
                RecommendedAction(priority="Medium",
                    action=f"Qualitative exit interviews for churned {ranked[0][0]} customers",
                    rationale="Identify fixable product/service/pricing gaps"),
                RecommendedAction(priority="Low",
                    action=f"Upsell programme targeting stable {ranked[-1][0]} segment",
                    rationale="Low-churn segments represent expansion revenue opportunity"),
            ],
            confidence_level="High",
        )

    def _specific_region(self, kpis, rl, region: str) -> MultiChatResponse:
        if not region: return self._region_breakdown(kpis, rl)
        rl_lower = region.lower()
        match_key = match_val = None
        for k, v in kpis.churn_by_region.items():
            if rl_lower in k.lower() or k.lower() in rl_lower:
                match_key, match_val = k, v; break
        if match_key is None: return self._region_breakdown(kpis, rl)
        all_ranked = _rank_dict(kpis.churn_by_region)
        rank = next((i+1 for i,(k,_) in enumerate(all_ranked) if k==match_key), len(all_ranked))
        avg  = kpis.churn_rate_pct
        diff_txt = f"{match_val-avg:+.1f}pp {'above' if match_val>avg else 'below'} portfolio average"
        est_customers = int(kpis.total_customers * match_val / 100 / max(len(all_ranked),1))
        est_revenue   = kpis.revenue_at_risk * match_val / max(kpis.churn_rate_pct, 0.001) / max(len(all_ranked),1)
        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=(
                f"{match_key} churn rate: {match_val:.1f}% — ranked #{rank} of {len(all_ranked)} regions. "
                f"{diff_txt} ({avg:.1f}%)."
            ),
            key_insights=[
                f"{match_key} churn: {match_val:.1f}%",
                f"Portfolio average: {avg:.1f}% | Deviation: {match_val-avg:+.1f}pp",
                f"Regional rank: #{rank} of {len(all_ranked)}",
                f"Estimated churned customers in {match_key}: ~{est_customers:,}",
                f"Estimated revenue at risk from {match_key}: ~{_fmt(est_revenue)}",
                f"Risk classification: {'CRITICAL — above 25%' if match_val>=25 else 'High — above 20%' if match_val>=20 else 'Elevated — above 15%' if match_val>=15 else 'Moderate'}",
            ],
            business_impact=BusinessImpact(
                risk_level="Critical" if match_val>=25 else ("High" if match_val>=20 else "Moderate"),
                affected_customers=est_customers,
                revenue_at_risk=_fmt(est_revenue),
            ),
            recommended_actions=[
                RecommendedAction(
                    priority="High" if match_val > avg+5 else "Medium",
                    action=f"Regional retention campaign in {match_key}",
                    rationale=f"{match_val:.1f}% churn vs {avg:.1f}% average = {match_val-avg:+.1f}pp gap"),
                RecommendedAction(priority="Medium",
                    action=f"High-touch customer success check-in for enterprise accounts in {match_key}",
                    rationale="High-CLV customers in underperforming regions need personalised intervention"),
            ],
            confidence_level="High",
        )

    def _specific_segment(self, kpis, rl, segment: str) -> MultiChatResponse:
        if not segment: return self._segment_breakdown(kpis, rl)
        s_lower = segment.lower()
        match_key = match_val = None
        for k, v in kpis.churn_by_segment.items():
            if s_lower in k.lower() or k.lower() in s_lower:
                match_key, match_val = k, v; break
        if match_key is None: return self._segment_breakdown(kpis, rl)
        all_ranked = _rank_dict(kpis.churn_by_segment)
        rank = next((i+1 for i,(k,_) in enumerate(all_ranked) if k==match_key), len(all_ranked))
        avg  = kpis.churn_rate_pct
        est  = int(kpis.total_customers * match_val / 100 / max(len(all_ranked),1))
        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=(
                f"{match_key} segment churn: {match_val:.1f}% — ranked #{rank} of {len(all_ranked)} segments. "
                f"{match_val-avg:+.1f}pp {'above' if match_val>avg else 'below'} the {avg:.1f}% portfolio average."
            ),
            key_insights=[
                f"{match_key} churn: {match_val:.1f}% | Portfolio avg: {avg:.1f}%",
                f"Deviation: {match_val-avg:+.1f}pp | Rank: #{rank} of {len(all_ranked)}",
                f"Estimated churned in {match_key}: ~{est:,} customers",
                f"Estimated revenue at risk: ~{_fmt(kpis.revenue_at_risk * match_val / max(kpis.churn_rate_pct,0.001) / max(len(all_ranked),1))}",
            ],
            business_impact=BusinessImpact(
                risk_level="Critical" if match_val>=25 else ("High" if match_val>=20 else "Moderate"),
                affected_customers=est,
            ),
            recommended_actions=[
                RecommendedAction(priority="High" if match_val>avg+5 else "Medium",
                    action=f"Personalised retention offer for high-risk {match_key} customers",
                    rationale=f"Churn at {match_val:.1f}% — {'significantly above' if match_val>avg+5 else 'above'} average"),
                RecommendedAction(priority="Medium",
                    action=f"Exit interviews for churned {match_key} customers",
                    rationale="Qualitative data identifies fixable drivers specific to this segment"),
                RecommendedAction(priority="Low",
                    action=f"Win-back campaign targeting churned {match_key} customers",
                    rationale="Reactivating churned high-CLV accounts is 5× cheaper than new acquisition"),
            ],
            confidence_level="High",
        )

    def _satisfaction(self, kpis, rl) -> MultiChatResponse:
        sat = kpis.avg_satisfaction_score
        label = ("Excellent" if sat>=8 else "Good" if sat>=7 else "Fair" if sat>=6 else "Poor" if sat>=5 else "Critical")
        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=(
                f"Average customer satisfaction: {sat:.1f}/10 — rated {label}. "
                f"Customers scoring ≤ 5 are 3× more likely to churn. "
                f"Portfolio churn rate is {kpis.churn_rate_pct:.1f}% ({rl} risk)."
            ),
            key_insights=[
                f"Avg satisfaction score: {sat:.1f}/10 ({label})",
                "Score ≤ 5 → 3× higher churn likelihood (strong leading indicator)",
                "Score 6–7 → moderate risk | Score 8+ → low churn risk zone",
                f"Portfolio churn: {kpis.churn_rate_pct:.1f}% | Avg risk score: {kpis.avg_churn_risk_score:.3f}",
                "Top satisfaction drivers: support resolution speed, product reliability, onboarding quality",
                "Target: score ≥ 8.0 to achieve promoter-zone customer advocacy",
            ],
            business_impact=BusinessImpact(
                affected_customers=int(kpis.total_customers * kpis.churn_rate_pct / 100),
                risk_level=rl,
            ),
            recommended_actions=[
                RecommendedAction(priority="High",
                    action="Identify and contact all customers with satisfaction ≤ 5 within 48 hours",
                    rationale="Below-5 scores are the #1 predictive signal of imminent churn"),
                RecommendedAction(priority="Medium",
                    action="Proactive support outreach for customers with > 2 tickets / 90 days",
                    rationale="High ticket volume correlates with low satisfaction and elevated churn risk"),
                RecommendedAction(priority="Low",
                    action="Launch quarterly CSAT pulse survey across all segments",
                    rationale="Regular measurement enables early detection of satisfaction decline"),
            ],
            confidence_level="High",
        )

    def _general(self, kpis, enh, rl) -> MultiChatResponse:
        top_seg = max(kpis.churn_by_segment.items(), key=lambda x: x[1], default=("N/A", 0))
        top_reg = max(kpis.churn_by_region.items(),  key=lambda x: x[1], default=("N/A", 0))
        biz     = enh.business_metrics if enh else None
        churned = int(kpis.total_customers * kpis.churn_rate_pct / 100)
        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=(
                f"Portfolio: {kpis.total_customers:,} customers | Churn: {kpis.churn_rate_pct:.1f}% ({rl} risk) | "
                f"Revenue at risk: {_fmt(kpis.revenue_at_risk)}. "
                f"Worst churn in {top_seg[0]} segment ({top_seg[1]:.1f}%) and {top_reg[0]} region ({top_reg[1]:.1f}%)."
            ),
            key_insights=[
                f"Total customers: {kpis.total_customers:,} | Churned: {churned:,}",
                f"Churn rate: {kpis.churn_rate_pct:.1f}% — {rl} risk level",
                f"Revenue at risk (churned CLV): {_fmt(kpis.revenue_at_risk)}",
                f"Avg CLV: {_fmt(kpis.avg_clv)} | Avg risk score: {kpis.avg_churn_risk_score:.3f}",
                f"Avg satisfaction: {kpis.avg_satisfaction_score:.1f}/10",
                f"Worst segment: {top_seg[0]} ({top_seg[1]:.1f}% churn)",
                f"Worst region: {top_reg[0]} ({top_reg[1]:.1f}% churn)",
                (f"High-value customers: {biz.high_value_customers:,} ({biz.high_value_pct:.1f}% of base)" if biz else ""),
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt(kpis.revenue_at_risk),
                affected_customers=churned,
                risk_level=rl,
            ),
            recommended_actions=[
                RecommendedAction(priority="High",
                    action=f"Retention blitz in {top_seg[0]} segment",
                    rationale=f"Highest churn at {top_seg[1]:.1f}%"),
                RecommendedAction(priority="High",
                    action=f"Regional campaign in {top_reg[0]}",
                    rationale=f"Highest regional churn at {top_reg[1]:.1f}%"),
                RecommendedAction(priority="Medium",
                    action="Satisfaction recovery programme for all customers scoring < 6",
                    rationale=f"Avg satisfaction {kpis.avg_satisfaction_score:.1f}/10 — below 7 is high churn risk"),
            ],
            confidence_level="High",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Agent 2 — Retention Strategist
# ─────────────────────────────────────────────────────────────────────────────

class RetentionStrategistAgent:
    NAME = "RetentionStrategistAgent"

    def run(self, message: str, context: dict) -> MultiChatResponse:
        intent, params = _detect_intent(message)
        if intent == 'top_customers':
            return self._top_customers(params.get('top_n', 10), params.get('segment'), params.get('region'))
        if intent in ('strategy', 'specific_segment') and params.get('segment'):
            return self._segment_strategy(params['segment'])
        return self._general_strategy()

    def _top_customers(self, top_n: int, segment: Optional[str], region: Optional[str]) -> MultiChatResponse:
        from app.services.recommendation_service import RecommendationService
        from app.services.dataset_service import DatasetService
        rs   = RecommendationService()
        pl   = rs.priority_list(top_n=min(max(top_n, 10), 50))
        kpis = DatasetService().kpis()
        rl   = _risk_level(kpis.churn_rate_pct)
        custs = pl.customers
        if segment:
            custs = [c for c in custs if segment.lower() in (c.customer_segment or '').lower()]
        if region:
            custs = [c for c in custs if region.lower() in (c.region or '').lower()]
        display = custs[:top_n]
        filter_note = ""
        if segment: filter_note += f" | Segment filter: {segment}"
        if region:  filter_note += f" | Region filter: {region}"
        actions = []
        for c in display[:10]:
            actions.append(RecommendedAction(
                priority=c.priority_class,
                action=f"{c.recommended_action} → {c.customer_id}",
                rationale=(
                    f"{c.customer_segment}/{c.plan_type} in {c.region} | "
                    f"CLV: {_fmt(c.estimated_clv)} | Risk: {c.churn_risk_score:.2f} | "
                    f"Priority score: {c.priority_score:.2f}"
                ),
            ))
        if not actions:
            actions = [RecommendedAction(priority="High",
                action="No customers match the filter — broaden criteria",
                rationale="Try removing segment or region restrictions")]
        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=(
                f"Top {len(display)} priority customers for immediate outreach{filter_note}. "
                f"Priority formula: 50% churn risk + 30% CLV + 20% complaint volume. "
                f"Full queue: {pl.high_priority_count} High | {pl.medium_priority_count} Medium | {pl.low_priority_count} Low."
            ),
            key_insights=[
                f"High Priority (immediate action required): {pl.high_priority_count}",
                f"Medium Priority (proactive outreach within 2 weeks): {pl.medium_priority_count}",
                f"Low Priority (monitor quarterly): {pl.low_priority_count}",
                f"Displaying top {len(display)} ranked by priority score",
                "Sorted by: churn risk score × CLV weight × complaint frequency",
            ],
            business_impact=BusinessImpact(
                affected_customers=pl.high_priority_count,
                risk_level=rl,
            ),
            recommended_actions=actions,
            confidence_level="High",
        )

    def _segment_strategy(self, segment: str) -> MultiChatResponse:
        from app.services.dataset_service import DatasetService
        from app.services.recommendation_service import RecommendationService
        svc  = DatasetService()
        kpis = svc.kpis()
        pl   = RecommendationService().priority_list(top_n=50)
        seg_churn = None
        for k, v in kpis.churn_by_segment.items():
            if segment.lower() in k.lower() or k.lower() in segment.lower():
                seg_churn = (k, v); break
        avg       = kpis.churn_rate_pct
        seg_custs = [c for c in pl.customers if segment.lower() in (c.customer_segment or '').lower()]
        churn_note = (
            f"{seg_churn[0]} segment churn: {seg_churn[1]:.1f}% "
            f"({'ABOVE' if seg_churn[1]>avg else 'below'} portfolio avg of {avg:.1f}%)"
        ) if seg_churn else f"Segment '{segment}' not found — showing general strategy"
        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=(
                f"Retention strategy for {segment} customers. {churn_note}. "
                f"{len(seg_custs)} {segment} customers in the priority outreach queue."
            ),
            key_insights=[
                churn_note,
                f"Priority customers in {segment} segment: {len(seg_custs)}",
                f"Portfolio churn average: {avg:.1f}%",
                f"{segment} churn vs average: {seg_churn[1]-avg:+.1f}pp" if seg_churn else "",
                "Best retention window: contact within 30 days of first churn signal",
                "Personalised offers outperform generic discounts by 2–3× (industry benchmark)",
            ],
            business_impact=BusinessImpact(
                affected_customers=len(seg_custs),
                risk_level="High" if (seg_churn and seg_churn[1]>avg+5) else "Moderate",
            ),
            recommended_actions=[
                RecommendedAction(priority="High",
                    action=f"Personalised loyalty offer for high-risk {segment} customers",
                    rationale="Segment-specific value proposition reduces churn 2–3× vs generic outreach"),
                RecommendedAction(priority="High",
                    action=f"Dedicated {segment} customer success manager assignment",
                    rationale="High-touch model reduces churn in premium/enterprise tiers by up to 40%"),
                RecommendedAction(priority="Medium",
                    action=f"Upgrade path / feature unlock specifically for {segment} plan",
                    rationale="Increasing product stickiness reduces voluntary churn substantially"),
                RecommendedAction(priority="Medium",
                    action=f"Quarterly business review cadence for top-CLV {segment} accounts",
                    rationale="QBRs reinforce value and surface issues before they cause churn"),
                RecommendedAction(priority="Low",
                    action=f"Referral programme targeting satisfied {segment} customers",
                    rationale="Satisfied customers in stable segments become advocates — leverage them"),
            ],
            confidence_level="High",
        )

    def _general_strategy(self) -> MultiChatResponse:
        from app.services.recommendation_service import RecommendationService
        from app.services.dataset_service import DatasetService
        rs   = RecommendationService()
        pl   = rs.priority_list(top_n=10)
        kpis = DatasetService().kpis()
        rl   = _risk_level(kpis.churn_rate_pct)
        top_seg = max(kpis.churn_by_segment.items(), key=lambda x: x[1], default=("N/A", 0))
        actions = []
        for c in pl.customers[:5]:
            actions.append(RecommendedAction(
                priority=c.priority_class,
                action=f"{c.recommended_action} — {c.customer_id}",
                rationale=(
                    f"{c.customer_segment}/{c.plan_type} in {c.region}. "
                    f"CLV {_fmt(c.estimated_clv)}, risk {c.churn_risk_score:.2f}"
                ),
            ))
        if not actions:
            actions = [RecommendedAction(priority="High",
                action="Deploy personalised retention offers to high-risk cohort",
                rationale="Top priority action for immediate churn reduction")]
        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=(
                f"Retention overview: {pl.high_priority_count} customers need immediate action, "
                f"{pl.medium_priority_count} need proactive outreach. "
                f"Primary focus: {top_seg[0]} segment ({top_seg[1]:.1f}% churn — highest in portfolio)."
            ),
            key_insights=[
                f"High Priority — immediate retention offer required: {pl.high_priority_count} customers",
                f"Medium Priority — proactive outreach within 2 weeks: {pl.medium_priority_count} customers",
                f"Low Priority — monitor quarterly: {pl.low_priority_count} customers",
                f"Highest churn segment: {top_seg[0]} ({top_seg[1]:.1f}%)",
                "Priority score: 50% churn risk + 30% CLV + 20% complaint volume",
                "Best practice: contact within 30 days of first churn signal for 2–3× better outcomes",
            ],
            business_impact=BusinessImpact(
                affected_customers=pl.high_priority_count + pl.medium_priority_count,
                risk_level=rl,
            ),
            recommended_actions=actions,
            confidence_level="High",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Agent 3 — Scenario Planner
# ─────────────────────────────────────────────────────────────────────────────

class ScenarioPlannerAgent:
    NAME = "ScenarioPlannerAgent"

    @staticmethod
    def _extract(pattern: str, text: str, default: float) -> float:
        m = re.search(pattern, text, re.IGNORECASE)
        return float(m.group(1).replace(",", "")) if m else default

    def run(self, message: str, context: dict) -> MultiChatResponse:
        from app.decision_engine.scenario_service import ScenarioService, SimulationRequest
        _, params = _detect_intent(message)
        budget   = params.get('budget') or self._extract(r'\$?([\d,]+(?:\.\d+)?)\s*(?:k|thousand)?.*?budget', message, 500_000)
        discount = params.get('discount') or self._extract(r'(\d+(?:\.\d+)?)\s*%\s*(?:off|discount|offer)', message, 10.0)
        threshold = self._extract(r'risk\s*(?:threshold|score)?\s*[>=of]*\s*(0\.\d+)', message, 0.6)
        success  = self._extract(r'(\d+(?:\.\d+)?)\s*%\s*success', message, 18.0) / 100.0
        if re.search(r'[\d,]+k\b', message, re.IGNORECASE) and budget < 10_000:
            budget *= 1000
        sim_req = SimulationRequest(
            target_segment="All",
            risk_threshold=threshold,
            retention_budget=budget,
            offer_discount_pct=discount,
            expected_success_rate=success,
        )
        result = ScenarioService().simulate(sim_req)
        sim, base = result.simulation, result.baseline
        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=result.scenario_summary,
            key_insights=[
                f"Budget: {_fmt(budget)} | Discount: {discount:.0f}% | Risk threshold: {threshold:.1f}",
                f"At-risk cohort: {base.affected_customers:,} customers | Revenue at risk: {_fmt(base.current_revenue_at_risk)}",
                f"Budget covers: {sim.customers_reachable:,} customers (avg offer cost: {_fmt(sim.avg_offer_cost)} each)",
                f"Expected saved: {sim.expected_customers_saved:,} customers → {_fmt(sim.expected_revenue_saved)} recovered",
                f"Estimated ROI: {sim.estimated_roi:.2f}× ({sim.roi_label}) — breakeven at 1.0×",
                f"Success rate assumed: {success*100:.0f}% of reached customers accept offer",
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt(base.current_revenue_at_risk),
                affected_customers=base.affected_customers,
                risk_level=result.confidence_level,
            ),
            recommended_actions=[
                RecommendedAction(
                    priority="High" if sim.estimated_roi >= 2 else "Medium",
                    action="Execute retention campaign as modelled",
                    rationale=result.recommendation,
                ),
                RecommendedAction(priority="Medium",
                    action="Prioritise highest-CLV customers first within budget",
                    rationale="Maximises revenue recovery per offer dollar spent"),
                RecommendedAction(priority="Low",
                    action=f"A/B test {max(5, discount-5):.0f}% vs {discount:.0f}% discount to optimise acceptance",
                    rationale="Lower discount at same ROI frees budget to reach more customers"),
            ],
            confidence_level=result.confidence_level,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Agent 4 — Executive Briefing
# ─────────────────────────────────────────────────────────────────────────────

class ExecutiveBriefingAgent:
    NAME = "ExecutiveBriefingAgent"

    def run(self, message: str, context: dict) -> MultiChatResponse:
        from app.services.dataset_service import DatasetService
        from app.services.recommendation_service import RecommendationService
        from app.decision_engine.insight_engine import InsightEngine
        svc  = DatasetService()
        kpis = svc.kpis()
        enh  = svc.enhanced_kpis()
        biz  = enh.business_metrics
        pl   = RecommendationService().priority_list(top_n=3)
        rl   = _risk_level(kpis.churn_rate_pct)
        top_seg = max(kpis.churn_by_segment.items(), key=lambda x: x[1], default=("N/A", 0))
        top_reg = max(kpis.churn_by_region.items(),  key=lambda x: x[1], default=("N/A", 0))
        churned = int(kpis.total_customers * kpis.churn_rate_pct / 100)
        combined_risk = kpis.revenue_at_risk + biz.revenue_at_risk
        try:
            insight = InsightEngine.from_kpis(kpis, svc.df)
            exec_summary = insight.executive_summary
        except Exception:
            exec_summary = (
                f"EXECUTIVE SUMMARY — Customer retention is at {rl} risk. "
                f"Portfolio of {kpis.total_customers:,} customers: {kpis.churn_rate_pct:.1f}% churn rate, "
                f"{churned:,} customers lost, {_fmt(kpis.revenue_at_risk)} realised revenue loss. "
                f"Forward exposure (high-risk cohort): {_fmt(biz.revenue_at_risk)}. "
                f"Total risk: {_fmt(combined_risk)}. "
                f"Churn concentrated in {top_seg[0]} segment ({top_seg[1]:.1f}%) and "
                f"{top_reg[0]} region ({top_reg[1]:.1f}%). "
                f"Immediate action required: {pl.high_priority_count} High Priority accounts."
            )
        actions = []
        for c in pl.customers[:3]:
            actions.append(RecommendedAction(
                priority="High",
                action=c.recommended_action,
                rationale=f"Customer {c.customer_id} — {c.customer_segment}/{c.plan_type} in {c.region}. CLV {_fmt(c.estimated_clv)}",
            ))
        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=exec_summary,
            key_insights=[
                f"Churn rate: {kpis.churn_rate_pct:.1f}% — {rl} risk | Churned: {churned:,} customers",
                f"Revenue lost (churned CLV): {_fmt(kpis.revenue_at_risk)} | Forward risk: {_fmt(biz.revenue_at_risk)}",
                f"Total exposure: {_fmt(combined_risk)}",
                f"High-value customers at risk: {biz.high_value_customers:,} ({biz.high_value_pct:.1f}% of base)",
                f"Churn concentrated: {top_seg[0]} segment + {top_reg[0]} region",
                f"Action queue: {pl.high_priority_count} High | {pl.medium_priority_count} Medium | {pl.low_priority_count} Low",
                f"Avg CLV: {_fmt(kpis.avg_clv)} | Avg satisfaction: {kpis.avg_satisfaction_score:.1f}/10",
            ],
            business_impact=BusinessImpact(
                revenue_at_risk=_fmt(combined_risk),
                affected_customers=churned,
                risk_level=rl,
            ),
            recommended_actions=actions or [RecommendedAction(
                priority="High",
                action="Deploy immediate retention programme",
                rationale=f"Churn at {kpis.churn_rate_pct:.1f}% — {rl} classification",
            )],
            confidence_level="High",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Agent 5 — Uploaded Data Analyst
# ─────────────────────────────────────────────────────────────────────────────

class UploadedDataAgent:
    NAME = "UploadedDataAgent"

    def run(self, message: str, context: dict) -> MultiChatResponse:
        from app.data_engine.universal_data_service import get_latest_upload_context, get_active_dataframe
        ctx = get_latest_upload_context()
        df  = get_active_dataframe()

        if ctx is None:
            return MultiChatResponse(
                agent_used=self.NAME,
                executive_summary=(
                    "No file uploaded yet. Click 'Upload Data' (top-right) to upload a CSV, Excel, TXT or PDF."
                ),
                key_insights=["No uploaded dataset found — upload a file to enable file-specific analysis"],
                recommended_actions=[RecommendedAction(
                    priority="High",
                    action="Upload a data file to enable file-specific Q&A",
                    rationale="Supports CSV, Excel (.xlsx/.xls), plain text, and PDF",
                )],
                confidence_level="Low",
            )

        intent, params = _detect_intent(message)
        domain  = ctx.get("detected_domain", "Unknown")
        rows    = ctx.get("rows", 0)
        cols    = ctx.get("columns", [])
        issues  = ctx.get("data_quality_issues", [])
        metrics = ctx.get("key_metrics", [])
        recs    = ctx.get("recommended_analysis", [])
        fname   = ctx.get("filename", "uploaded file")

        computed_insights  = self._compute_insights(df, intent, params) if df is not None else []
        computed_exec      = self._compute_summary(df, intent, params, fname) if df is not None else None
        computed_actions   = self._compute_actions(df, intent, domain) if df is not None else []

        base_insights = [
            f"File: '{fname}' | Domain detected: {domain}",
            f"Shape: {rows:,} rows × {len(cols)} columns",
            f"Columns: {', '.join(cols[:8])}{'…' if len(cols)>8 else ''}",
            f"Data quality: {issues[0] if issues else 'No critical issues detected'}",
            f"Key metrics for this domain: {', '.join(metrics[:3])}",
        ]

        return MultiChatResponse(
            agent_used=self.NAME,
            executive_summary=computed_exec or ctx.get("executive_summary", f"Analysed '{fname}'."),
            key_insights=(computed_insights + base_insights)[:8] if computed_insights else base_insights,
            business_impact=BusinessImpact(
                affected_customers=rows,
                risk_level="Moderate" if issues and issues != ["No critical issues detected"] else "Low",
            ),
            recommended_actions=computed_actions or [
                RecommendedAction(priority="High",
                    action=recs[0] if recs else "Perform exploratory data analysis",
                    rationale=f"Primary recommendation for {domain} data"),
                RecommendedAction(priority="Medium",
                    action=recs[1] if len(recs)>1 else "Validate data quality",
                    rationale="Ensures downstream analysis reliability"),
                RecommendedAction(priority="Low",
                    action=recs[2] if len(recs)>2 else "Build baseline KPI dashboard",
                    rationale="Establishes performance benchmark"),
            ],
            confidence_level="High" if rows > 100 else "Medium",
        )

    def _compute_summary(self, df, intent, params, fname) -> Optional[str]:
        try:
            import pandas as pd
            churn_col  = next((c for c in df.columns if 'churn' in c.lower()), None)
            clv_col    = next((c for c in df.columns if any(k in c.lower() for k in ['clv','lifetime_value','ltv'])), None)
            region_col = next((c for c in df.columns if any(k in c.lower() for k in ['region','city','location','state'])), None)
            seg_col    = next((c for c in df.columns if any(k in c.lower() for k in ['segment','tier','plan_type','plantype'])), None)

            if intent == 'churn_rate' and churn_col:
                rate = float(df[churn_col].astype(float).mean() * 100)
                n    = int(df[churn_col].astype(float).sum())
                return (f"Churn rate in '{fname}': {rate:.1f}% ({n:,} of {len(df):,} records). "
                        f"Risk level: {_risk_level(rate)}.")

            if intent == 'revenue_risk' and clv_col and churn_col:
                churned = df[churn_col].astype(float) == 1
                rev     = float(pd.to_numeric(df[clv_col], errors='coerce')[churned].sum())
                return f"Revenue at risk in '{fname}': {_fmt(rev)} (sum of CLV for {int(churned.sum()):,} churned records)."

            if intent == 'region_breakdown' and region_col and churn_col:
                bdown = df.groupby(region_col)[churn_col].apply(lambda s: s.astype(float).mean()*100).sort_values(ascending=False)
                top   = bdown.index[0]
                return (f"Highest-churn region in '{fname}': {top} at {bdown.iloc[0]:.1f}%. "
                        f"Across {bdown.index.nunique()} regions.")

            if intent == 'segment_breakdown' and seg_col and churn_col:
                bdown = df.groupby(seg_col)[churn_col].apply(lambda s: s.astype(float).mean()*100).sort_values(ascending=False)
                top   = bdown.index[0]
                return f"Highest-churn segment in '{fname}': {top} at {bdown.iloc[0]:.1f}%."

            return None
        except Exception:
            return None

    def _compute_insights(self, df, intent, params) -> List[str]:
        insights = []
        try:
            import pandas as pd
            churn_col  = next((c for c in df.columns if 'churn' in c.lower()), None)
            clv_col    = next((c for c in df.columns if any(k in c.lower() for k in ['clv','lifetime_value','ltv'])), None)
            region_col = next((c for c in df.columns if any(k in c.lower() for k in ['region','city','location','state'])), None)
            seg_col    = next((c for c in df.columns if any(k in c.lower() for k in ['segment','tier','plan_type','plantype'])), None)

            if churn_col:
                rate = float(df[churn_col].astype(float).mean() * 100)
                n    = int(df[churn_col].astype(float).sum())
                insights.append(f"Churn rate: {rate:.1f}% ({n:,} records) — {_risk_level(rate)} risk")

            if clv_col and churn_col:
                churned = df[churn_col].astype(float) == 1
                rev = float(pd.to_numeric(df[clv_col], errors='coerce')[churned].sum())
                insights.append(f"Revenue at risk (churned CLV): {_fmt(rev)}")

            if intent == 'region_breakdown' and region_col and churn_col:
                bdown = df.groupby(region_col)[churn_col].apply(lambda s: s.astype(float).mean()*100).sort_values(ascending=False)
                for reg, pct in list(bdown.items())[:5]:
                    insights.append(f"{reg}: {pct:.1f}% churn")

            if intent == 'segment_breakdown' and seg_col and churn_col:
                bdown = df.groupby(seg_col)[churn_col].apply(lambda s: s.astype(float).mean()*100).sort_values(ascending=False)
                for seg, pct in list(bdown.items())[:5]:
                    insights.append(f"{seg}: {pct:.1f}% churn")

            if not insights:
                for c in df.select_dtypes(include='number').columns[:3]:
                    insights.append(f"{c}: mean={df[c].mean():.2f}, std={df[c].std():.2f}, min={df[c].min():.2f}, max={df[c].max():.2f}")
        except Exception:
            pass
        return insights

    def _compute_actions(self, df, intent, domain) -> List[RecommendedAction]:
        actions = []
        try:
            churn_col = next((c for c in df.columns if 'churn' in c.lower()), None)
            if churn_col:
                rate = float(df[churn_col].astype(float).mean() * 100)
                if rate > 20:
                    actions.append(RecommendedAction(priority="High",
                        action="Deploy immediate retention intervention",
                        rationale=f"Churn at {rate:.1f}% — {_risk_level(rate)} risk level"))
                actions.append(RecommendedAction(priority="Medium",
                    action="Build churn prediction model using this dataset",
                    rationale=f"Dataset has {len(df):,} records — sufficient for ML modelling"))
                actions.append(RecommendedAction(priority="Low",
                    action="Segment analysis: compute churn by each categorical column",
                    rationale="Identify which dimensions drive the highest churn rates"))
        except Exception:
            pass
        return actions


# ─────────────────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────────────────

_ROUTES = [
    (["uploaded", "my file", "this file", "this data", "this dataset",
      "the file", "what is this", "analyze this", "analyse this",
      "what did i upload", "what's in the file", "what data"],
     UploadedDataAgent),
    (["simulat", "what if", "what-if", "budget", "roi", "return on",
      "scenario", "forecast", "spend", "retention campaign"],
     ScenarioPlannerAgent),
    (["summary", "leadership", "ceo", "board", "executive", "brief",
      "overview", "status report", "tell me everything"],
     ExecutiveBriefingAgent),
    (["retain", "offer", "priority customer", "priority list",
      "outreach", "who should", "next best", "top customer",
      "who to contact", "action plan", "strateg"],
     RetentionStrategistAgent),
    (["kpi", "churn", "revenue", "segment", "region", "breakdown",
      "metric", "data", "analys", "rate", "score", "satisf", "how many"],
     DataAnalystAgent),
]

_DEFAULT_AGENT = DataAnalystAgent


def _route(message: str) -> type:
    intent, _ = _detect_intent(message)
    # Intent-first hard routing (more accurate than keyword scoring)
    if intent == 'upload_info':                      return UploadedDataAgent
    if intent == 'scenario':                         return ScenarioPlannerAgent
    if intent == 'executive':                        return ExecutiveBriefingAgent
    if intent in ('top_customers', 'strategy'):      return RetentionStrategistAgent
    if intent == 'specific_segment':
        msg_lower = message.lower()
        if any(k in msg_lower for k in ['strateg','retain','offer','recommend']):
            return RetentionStrategistAgent
    # Keyword fallback scoring
    msg_lower = message.lower()
    scores: dict = {}
    for keywords, agent_cls in _ROUTES:
        score = sum(1 for kw in keywords if kw in msg_lower)
        if score:
            scores[agent_cls] = scores.get(agent_cls, 0) + score
    return max(scores, key=lambda c: scores[c]) if scores else _DEFAULT_AGENT


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator entry point
# ─────────────────────────────────────────────────────────────────────────────

class MultiAgentOrchestrator:
    def run(self, req: MultiChatRequest) -> MultiChatResponse:
        from app.data_engine.universal_data_service import get_latest_upload_context
        ctx = dict(req.context or {})
        upload_ctx = get_latest_upload_context()
        if upload_ctx:
            ctx["_upload_context"] = upload_ctx
        agent_cls = _route(req.message)
        return agent_cls().run(req.message, ctx)
