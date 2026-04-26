"""DatasetService — loads/enriches 01_Customer_Retention.csv."""
from __future__ import annotations
import math, os
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from app.config import settings
from app.schemas.dataset import (ColumnInfo, ColumnsResponse, DatasetProfileResponse,
    FilterRequest, FilterResponse, KPISummaryResponse, SampleResponse)

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
        sub = df.head(req.limit).replace({np.nan:None})
        return FilterResponse(total_matches=len(df), returned_rows=len(sub),
            filters_applied=applied, records=sub.to_dict(orient="records"))
