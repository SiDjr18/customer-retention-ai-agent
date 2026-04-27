"""DatasetService — loads/enriches 01_Customer_Retention.csv."""
from __future__ import annotations
import math, os
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from app.config import settings
from app.schemas.dataset import (
    ColumnInfo, ColumnsResponse, DatasetProfileResponse,
    FilterRequest, FilterResponse, KPISummaryResponse, SampleResponse,
    CoreKPIs, ChurnConcentration, BusinessMetrics, RiskSegment,
    EnhancedKPISummaryResponse,
)

_CHURN_ALIASES = ["churn_flag","churned","churn","is_churn"]
_CLV_ALIASES   = ["estimated_clv","clv","customer_lifetime_value","ltv"]
_RISK_ALIASES  = ["churn_risk_score","risk_score","churn_score"]
_SAT_ALIASES   = ["satisfaction_score","csat","nps_score","satisfaction"]
_FILTER_ALIAS_MAP: Dict[str,List[str]] = {
    "region":              ["region","city","location"],
    "state":               ["state","province"],
    "city_tier":           ["city_tier","tier"],
    "customer_segment":    ["customer_segment","segment","plantype","plan_type"],
    "acquisition_channel": ["acquisition_channel","channel"],
    "plan_type":           ["plan_type","plantype","plan"],
    "contract_type":       ["contract_type","contracttype","contract"],
}

def _find_col(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
    lmap = {c.lower(): c for c in df.columns}
    for a in aliases:
        if a.lower() in lmap: return lmap[a.lower()]
    return None

def _safe(val, d=4):
    try: return round(float(val), d)
    except: return 0.0

def _sig(x):
    return 1.0/(1.0+math.exp(-max(-20.0,min(20.0,float(x)))))


class DatasetService:
    def __init__(self):
        self._df = self._load_and_enrich()
        self._churn_col = _find_col(self._df, _CHURN_ALIASES)
        self._clv_col   = _find_col(self._df, _CLV_ALIASES)
        self._risk_col  = _find_col(self._df, _RISK_ALIASES)
        self._sat_col   = _find_col(self._df, _SAT_ALIASES)

    def _load_and_enrich(self) -> pd.DataFrame:
        path = os.path.join(settings.DATA_DIR, settings.DATASET_FILENAME)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Dataset not found at '{path}'.")
        df = pd.read_csv(path, low_memory=False)
        df.columns = [c.strip().lower().replace(" ","_") for c in df.columns]

        def gc(name, fill):
            return pd.to_numeric(df[name],errors="coerce").fillna(fill) if name in df.columns \
                   else pd.Series(fill, index=df.index, dtype=float)

        mc, tm = gc("monthlycharges",0), gc("tenuremonths",12)
        pd_, st = gc("paymentdelaydays",0), gc("supporttickets",0)

        if "estimated_clv"        not in df.columns: df["estimated_clv"]        = (mc*tm).round(2)
        if "churn_risk_score"     not in df.columns: df["churn_risk_score"]     = (0.05*pd_+0.10*st-2.0).apply(_sig).round(4)
        if "satisfaction_score"   not in df.columns: df["satisfaction_score"]   = (10.0-(pd_/10.0).clip(0,9)).round(1)
        if "upsell_probability"   not in df.columns:
            df["upsell_probability"] = df["plantype"].apply(lambda p: 0.75 if str(p).lower()=="standard" else 0.30) \
                if "plantype" in df.columns else pd.Series(0.4, index=df.index)
        if "retention_offer_cost" not in df.columns: df["retention_offer_cost"] = (df["estimated_clv"]*0.10).round(2)
        if "complaints_90d"       not in df.columns: df["complaints_90d"]       = st.astype(int)
        if "payment_failures_12m" not in df.columns: df["payment_failures_12m"] = (pd_>30).astype(int)
        if "region"               not in df.columns and "city" in df.columns: df["region"] = df["city"]
        if "customer_segment"     not in df.columns and "plantype" in df.columns: df["customer_segment"] = df["plantype"]
        return df

    @property
    def df(self): return self._df

    def _col_info(self, col):
        s = self._df[col]; n = int(s.isna().sum())
        return ColumnInfo(name=col, dtype=str(s.dtype), null_count=n,
            null_pct=_safe(n/max(len(s),1)*100,2), unique_count=int(s.nunique()))

    def columns(self):
        return ColumnsResponse(total_columns=len(self._df.columns),
            columns=[self._col_info(c) for c in self._df.columns])

    def sample(self, n=10):
        sub = self._df.head(n).replace({np.nan:None})
        return SampleResponse(total_rows=len(self._df), returned_rows=len(sub),
            records=sub.to_dict(orient="records"))

    def profile(self):
        df = self._df
        missing = [self._col_info(c) for c in df.columns if df[c].isna().any()]
        num_stats = {c: {k: _safe(v) for k,v in df[c].describe().items()}
                     for c in df.select_dtypes(include="number").columns}
        cat_stats = {}
        for c in df.select_dtypes(include=["object","category"]).columns:
            vc = df[c].value_counts()
            cat_stats[c] = {"unique":int(df[c].nunique()),
                "top": str(vc.index[0]) if len(vc) else None,
                "top_freq": int(vc.iloc[0]) if len(vc) else 0}
        return DatasetProfileResponse(total_rows=len(df), total_columns=len(df.columns),
            duplicate_rows=int(df.duplicated().sum()), missing_values_report=missing,
            numeric_stats=num_stats, categorical_stats=cat_stats)

    def kpis(self):
        """Original KPI method — unchanged, used by agent_service."""
        df = self._df; total = len(df)
        churned = pd.Series([False]*total, index=df.index)
        churn_rate = 0.0
        if self._churn_col:
            churned = df[self._churn_col].astype(float)==1
            churn_rate = _safe(churned.sum()/max(total,1)*100, 2)
        avg_clv = rev_risk = 0.0
        cc = _find_col(df, ["estimated_clv","clv","customer_lifetime_value"])
        if cc:
            cs = pd.to_numeric(df[cc], errors="coerce")
            avg_clv, rev_risk = _safe(cs.mean()), _safe(cs[churned].sum())
        avg_risk = _safe(pd.to_numeric(df[self._risk_col],errors="coerce").mean()) if self._risk_col else 0.0
        avg_sat  = _safe(pd.to_numeric(df[self._sat_col], errors="coerce").mean()) if self._sat_col  else 0.0

        def breakdown(canonical):
            col = _find_col(df, _FILTER_ALIAS_MAP.get(canonical,[canonical]))
            if not col or not self._churn_col: return {}
            return {str(k): float(_safe(v*100,2))
                    for k,v in df.groupby(col)[self._churn_col]
                    .apply(lambda s: s.astype(float).mean()).items()}

        return KPISummaryResponse(total_customers=total, churn_rate_pct=churn_rate,
            avg_clv=avg_clv, revenue_at_risk=rev_risk,
            avg_churn_risk_score=avg_risk, avg_satisfaction_score=avg_sat,
            churn_by_segment=breakdown("customer_segment"),
            churn_by_region=breakdown("region"))

    def enhanced_kpis(self) -> EnhancedKPISummaryResponse:
        """Enhanced KPI method — adds business_metrics, risk_segments, executive_note."""
        df = self._df
        total = len(df)

        # --- Core KPIs (delegate to existing kpis()) ---
        base = self.kpis()
        core_kpis = CoreKPIs(
            total_customers=base.total_customers,
            churn_rate_pct=base.churn_rate_pct,
            avg_clv=base.avg_clv,
            revenue_at_risk=base.revenue_at_risk,
            avg_churn_risk_score=base.avg_churn_risk_score,
            avg_satisfaction_score=base.avg_satisfaction_score,
            churn_by_segment=base.churn_by_segment,
            churn_by_region=base.churn_by_region,
        )

        # --- Numeric series ---
        clv_s = (pd.to_numeric(df[self._clv_col], errors="coerce").fillna(0)
                 if self._clv_col else pd.Series(0.0, index=df.index))
        risk_s = (pd.to_numeric(df[self._risk_col], errors="coerce").fillna(0)
                  if self._risk_col else pd.Series(0.0, index=df.index))

        # revenue_at_risk: sum CLV for top-quartile risk customers (75th percentile threshold)
        # Using percentile instead of hard 0.6 cutoff so metric is meaningful regardless of score scale
        risk_75th = risk_s.quantile(0.75)
        high_risk_mask = risk_s >= risk_75th
        biz_revenue_at_risk = _safe(clv_s[high_risk_mask].sum())

        # high_value_customers: count where CLV > 75th percentile
        clv_75th = clv_s.quantile(0.75)
        hv_mask = clv_s > clv_75th
        high_value_count = int(hv_mask.sum())
        high_value_pct = _safe(high_value_count / max(total, 1) * 100, 2)

        # churn_concentration: region with most churned customers
        region_col = _find_col(df, _FILTER_ALIAS_MAP.get("region", ["region"]))
        top_region = "Unknown"
        top_region_count = 0
        pct_of_total_churned = 0.0

        if region_col and self._churn_col:
            churned_mask = df[self._churn_col].astype(float) == 1
            region_churned = df[churned_mask].groupby(region_col).size()
            if len(region_churned) > 0:
                top_region = str(region_churned.idxmax())
                top_region_count = int(region_churned.max())
                total_churned = int(churned_mask.sum())
                pct_of_total_churned = _safe(top_region_count / max(total_churned, 1) * 100, 2)
        elif region_col:
            # fallback: use high-risk customers
            region_risk = df[high_risk_mask].groupby(region_col).size()
            if len(region_risk) > 0:
                top_region = str(region_risk.idxmax())
                top_region_count = int(region_risk.max())
                total_high_risk = int(high_risk_mask.sum())
                pct_of_total_churned = _safe(top_region_count / max(total_high_risk, 1) * 100, 2)

        churn_concentration = ChurnConcentration(
            top_region=top_region,
            customer_count=top_region_count,
            pct_of_total_churned=pct_of_total_churned,
        )

        business_metrics = BusinessMetrics(
            revenue_at_risk=biz_revenue_at_risk,
            high_value_customers=high_value_count,
            high_value_pct=high_value_pct,
            churn_concentration=churn_concentration,
        )

        # --- Risk Segments: groupby(region, customer_segment, plan_type) ---
        segment_col = _find_col(df, _FILTER_ALIAS_MAP.get("customer_segment", ["customer_segment"]))
        plan_col    = _find_col(df, _FILTER_ALIAS_MAP.get("plan_type", ["plan_type"]))

        group_cols = [c for c in [region_col, segment_col, plan_col] if c is not None]
        risk_segments: List[RiskSegment] = []

        if group_cols:
            for keys, sub in df.groupby(group_cols):
                if not isinstance(keys, tuple):
                    keys = (keys,)

                def _kval(col):
                    return str(keys[group_cols.index(col)]) if col and col in group_cols else "N/A"

                sub_clv  = (pd.to_numeric(sub[self._clv_col],  errors="coerce").fillna(0)
                            if self._clv_col  else pd.Series(0.0, index=sub.index))
                sub_risk = (pd.to_numeric(sub[self._risk_col], errors="coerce").fillna(0)
                            if self._risk_col else pd.Series(0.0, index=sub.index))

                churn_rate_val = 0.0
                if self._churn_col:
                    churn_rate_val = _safe(sub[self._churn_col].astype(float).mean() * 100, 2)

                risk_segments.append(RiskSegment(
                    region=_kval(region_col),
                    customer_segment=_kval(segment_col),
                    plan_type=_kval(plan_col),
                    customer_count=len(sub),
                    avg_churn_risk_score=_safe(sub_risk.mean()),
                    churn_rate=churn_rate_val,
                    total_clv=_safe(sub_clv.sum()),
                    revenue_at_risk=_safe(sub_clv[sub_risk >= risk_75th].sum()),
                ))

        # sort by revenue_at_risk desc, cap at top 20
        risk_segments.sort(key=lambda x: x.revenue_at_risk, reverse=True)
        risk_segments = risk_segments[:20]

        # --- Executive Note ---
        top_seg = risk_segments[0] if risk_segments else None
        if top_seg:
            executive_note = (
                f"Revenue at risk from top-quartile churn-risk customers (risk score ≥ {risk_75th:.2f}): "
                f"${biz_revenue_at_risk:,.0f}. "
                f"Highest churn concentration in {top_region} region "
                f"({pct_of_total_churned:.1f}% of total churned). "
                f"Top risk segment: {top_seg.customer_segment} / {top_seg.plan_type} in {top_seg.region} "
                f"({top_seg.churn_rate:.1f}% churn rate, ${top_seg.revenue_at_risk:,.0f} at risk). "
                f"{high_value_count} high-value customers ({high_value_pct:.1f}% of base) "
                f"require priority retention outreach."
            )
        else:
            executive_note = (
                f"Revenue at risk: ${biz_revenue_at_risk:,.0f}. "
                f"{high_value_count} high-value customers identified for priority retention."
            )

        return EnhancedKPISummaryResponse(
            core_kpis=core_kpis,
            business_metrics=business_metrics,
            risk_segments=risk_segments,
            executive_note=executive_note,
        )

    def filter_data(self, req: FilterRequest):
        df = self._df.copy(); applied: Dict[str,str] = {}
        for canonical, val in {
            "region": req.region, "state": req.state, "city_tier": req.city_tier,
            "customer_segment": req.customer_segment,
            "acquisition_channel": req.acquisition_channel,
            "plan_type": req.plan_type, "contract_type": req.contract_type,
        }.items():
            if val is None: continue
            col = _find_col(df, _FILTER_ALIAS_MAP.get(canonical,[canonical]))
            if col is None: continue
            df = df[df[col].astype(str).str.strip().str.lower()==val.strip().lower()]
            applied[canonical] = val
   