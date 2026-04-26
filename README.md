# Customer Retention AI Agent

> **AI Decision Intelligence platform** that predicts customer churn, surfaces revenue at risk, generates Next Best Actions, and answers retention questions in natural language — all from a single CSV dataset.

---

## Business Problem

Customer churn costs SaaS and subscription businesses 5–25× more than retaining existing customers. Yet most retention teams still rely on lagging indicators and gut feel. This platform turns raw customer data into a live, queryable intelligence system that answers:

- *Which customers will churn in the next 30 days?*
- *How much revenue is at risk — and where?*
- *What is the single best action for each customer right now?*
- *Why is the South region churning faster than North?*

---

## Architecture

```mermaid
graph TD
    CSV[01_Customer_Retention.csv] --> DS[DatasetService]
    DS --> KPI[/dataset/kpis]
    DS --> PROF[/dataset/profile]
    DS --> FILT[/dataset/filter]

    DS --> MT[ModelTraining]
    MT --> PKL[(churn_model.pkl)]
    PKL --> PS[PredictionService]
    PS --> PRED[/predict/churn]
    PS --> BATCH[/predict/batch]
    PS --> MMET[/predict/metrics]

    DS --> RS[RecommendationService]
    RS --> REC[/recommend/customer]
    RS --> RBATCH[/recommend/batch]
    RS --> STRAT[/recommend/strategy-summary]

    DS --> AS[AgentService]
    PS --> AS
    RS --> AS
    AS --> CHAT[/agent/chat]

    DS --> RPT[ReportService]
    RPT --> RPDF[/reports/pdf]
    RPT --> RCSV[/reports/csv]
    RPT --> RPPT[/reports/ppt]

    subgraph Frontend [React Dashboard]
        EO[Executive Overview]
        RE[Risk Explorer]
        CP[Churn Prediction]
        RD[Recommendations]
        AC[Agent Chat]
        RP[Reports]
    end

    CHAT --> AC
    KPI --> EO
    FILT --> RE
    MMET --> CP
    STRAT --> RD
    RPDF & RCSV & RPPT --> RP
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend API** | FastAPI · Python 3.11 · Pydantic v2 |
| **ML Engine** | scikit-learn · XGBoost · pandas · numpy |
| **Report Generation** | reportlab (PDF) · python-pptx (PPT) · pandas (CSV) |
| **AI Agent** | Rule-based intent router (no API key required) |
| **Frontend** | React 18 · Vite · Tailwind CSS · Recharts · Axios |
| **Infrastructure** | Docker · Docker Compose |

---

## Project Structure

```
customer-retention-ai-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI application + router registration
│   │   ├── config.py                # Pydantic Settings (env-driven config)
│   │   ├── api/routes/
│   │   │   ├── health.py            # GET /health
│   │   │   ├── dataset.py           # GET /dataset/* (5 endpoints)
│   │   │   ├── predict.py           # POST /predict/churn|batch + GET /predict/metrics
│   │   │   ├── recommend.py         # POST /recommend/* + GET /recommend/strategy-summary
│   │   │   ├── agent.py             # POST /agent/chat
│   │   │   └── reports.py           # POST /reports/pdf|csv|ppt
│   │   ├── services/
│   │   │   ├── dataset_service.py   # CSV loader, profiler, KPIs, filter
│   │   │   ├── model_training.py    # LR + RF + XGBoost training pipeline
│   │   │   ├── prediction_service.py# Load artefacts, score customers
│   │   │   ├── recommendation_service.py  # 6-rule NBA engine
│   │   │   ├── agent_service.py     # Intent classifier + tool router
│   │   │   └── report_service.py    # PDF / CSV / PPT generation
│   │   ├── schemas/                 # Pydantic request/response models
│   │   ├── models/                  # SQLAlchemy ORM (future)
│   │   └── utils/logger.py
│   ├── artifacts/                   # Trained model .pkl files (git-ignored)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # React Router root
│   │   ├── pages/                   # 6 pages (Overview, Risk, Predict, Reco, Agent, Reports)
│   │   ├── components/              # Sidebar, KpiCard, FilterBar, LoadingState
│   │   ├── services/api.js          # Axios API layer
│   │   └── styles/index.css         # Tailwind + custom utilities
│   ├── vite.config.js
│   └── package.json
├── data/
│   └── 01_Customer_Retention.csv    # Source dataset
├── notebooks/                       # EDA / experimentation
├── reports/                         # Generated reports (git-ignored)
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## API Reference

### Health
| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Liveness probe |

### Dataset
| Method | Endpoint | Description |
|---|---|---|
| GET | `/dataset/columns` | Column names + dtypes |
| GET | `/dataset/sample?n=10` | Preview N rows |
| GET | `/dataset/profile` | Full profiling report |
| GET | `/dataset/kpis` | Business KPI summary |
| POST | `/dataset/filter` | Filter by region / segment / plan / etc. |

### Prediction
| Method | Endpoint | Description |
|---|---|---|
| POST | `/predict/churn` | Single customer churn probability |
| POST | `/predict/batch` | Batch churn scoring |
| GET | `/predict/metrics` | Model metrics + feature importance |

### Recommendations (NBA)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/recommend/customer` | Next Best Action for one customer |
| POST | `/recommend/batch` | Batch NBA scoring |
| GET | `/recommend/strategy-summary` | Aggregate strategy breakdown |

### Agent
| Method | Endpoint | Description |
|---|---|---|
| POST | `/agent/chat` | Natural-language query → structured JSON |

### Reports
| Method | Endpoint | Description |
|---|---|---|
| POST | `/reports/pdf` | Generate PDF executive report |
| POST | `/reports/csv` | Export customer action list as CSV |
| POST | `/reports/ppt` | Generate PPT (or Markdown fallback) |
| GET | `/reports/export/{filename}` | Download generated report |

Interactive docs: **http://localhost:8000/docs**

---

## Setup & Quickstart

### Prerequisites
- Python 3.11+
- Node.js 20+
- (Optional) Docker + Docker Compose

### 1. Clone & prepare data

```bash
git clone https://github.com/your-username/customer-retention-ai-agent.git
cd customer-retention-ai-agent

# Place your dataset here:
cp /path/to/01_Customer_Retention.csv data/
```

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env

# Train the churn model (creates artifacts/churn_model.pkl)
python -m app.services.model_training

# Start the API
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 4. Docker (all-in-one)

```bash
cp .env.example .env
docker compose up --build
# Backend → http://localhost:8000
# Frontend → http://localhost:5173
```

---

## Dashboard Features

| Page | Features |
|---|---|
| **Executive Overview** | KPI cards, churn-by-region bar chart, churn-by-segment pie chart |
| **Risk Explorer** | Searchable + sortable customer table, multi-dimension filter bar, risk badges |
| **Churn Prediction** | Model comparison table, feature importance bar chart, training instructions |
| **Recommendations** | Strategy distribution chart, per-strategy cards, revenue-protected estimates |
| **AI Agent** | Conversational chat, intent classification, structured executive responses |
| **Reports** | One-click PDF / CSV / PPT generation with download links |

---

## ML Model Explanation

The churn prediction engine:

1. **Preprocessing** — median imputation for numerics, mode imputation + one-hot encoding for categoricals, StandardScaler for numeric features.
2. **Candidate models** — Logistic Regression (baseline), Random Forest, XGBoost (optional).
3. **Evaluation** — accuracy, precision, recall, F1, ROC-AUC on a stratified 20% hold-out.
4. **Model selection** — highest ROC-AUC wins and is saved to `artifacts/churn_model.pkl`.
5. **Feature importance** — extracted from `feature_importances_` (tree models) or `|coef_|` (LR).

---

## Next Best Action Rules

| Priority | Rule | Action |
|---|---|---|
| 1 | Churn ≥ 0.65 AND CLV ≥ 75th pct | Premium Retention Offer |
| 2 | Churn ≥ 0.65 AND complaints ≥ 3 | Service Recovery Call |
| 3 | Churn ≥ 0.65 AND payment failures ≥ 2 | Payment Support Plan |
| 4 | Churn < 0.35 AND upsell prob ≥ 0.65 | Upsell Premium Plan |
| 5 | Satisfaction ≤ 4.0 / 10 | CX Intervention |
| 6 | Default | Monitor |

---

## AI Agent Capabilities

The agent classifies user intent from plain English using keyword matching and routes to internal services:

| Intent | Example query |
|---|---|
| `churn_rate` | "What is the overall churn rate?" |
| `high_risk` | "Show the most at-risk customers in South" |
| `revenue_risk` | "How much revenue are we losing?" |
| `region_analysis` | "Which region has the worst churn?" |
| `segment_analysis` | "How is Enterprise performing vs SMB?" |
| `kpi_summary` | "Give me a full KPI dashboard" |
| `recommend` | "What retention strategy should we use?" |
| `predict` | "How do I score a new customer?" |
| `data_profile` | "Are there data quality issues?" |

All responses follow a structured schema: `executive_summary`, `key_findings`, `recommended_actions`, `supporting_data`, `confidence_level`.

---

## CV Bullet Points

```
• Designed and built a production-grade Customer Retention AI Agent: end-to-end platform
  spanning data ingestion, ML churn prediction (LR / RF / XGBoost, best ROC-AUC selection),
  rule-based Next Best Action engine, and natural-language agent interface — all served via
  a FastAPI REST API with interactive Swagger docs.

• Engineered a modular ML pipeline (scikit-learn ColumnTransformer, GridSearchCV-ready)
  achieving churn prediction with automatic model selection; artefacts persisted to disk and
  served via a live inference endpoint supporting both single and batch scoring.

• Built a McKinsey-style React + Tailwind executive dashboard with 6 pages (Executive
  Overview, Risk Explorer, Churn Prediction, Recommendations, AI Agent Chat, Reports),
  Recharts visualisations, a sticky filter bar, and live API integration via Axios.

• Implemented a deterministic AI Agent (no LLM API key required) with a keyword intent
  classifier routing 9 intent types to internal analytics services, returning structured
  executive JSON responses consumed by a conversational React chat UI.

• Developed a report generation module producing PDF (reportlab), CSV (pandas), and
  PowerPoint (python-pptx) outputs with graceful fallback to Markdown; reports
  downloadable via a streaming FastAPI FileResponse endpoint.
```

---

## LinkedIn Post Draft

```
🚀 Just shipped my Customer Retention AI Agent — a full-stack AI Decision Intelligence
platform built from scratch.

The problem: subscription businesses lose 20–30% of revenue to churn every year, yet most
retention teams still work from spreadsheets.

What I built:
✅ Churn prediction engine — LR / Random Forest / XGBoost with automatic best-model selection
✅ Next Best Action rules engine — 6 prioritised interventions per customer
✅ AI Agent chat — answer any retention question in plain English, no API key required
✅ Executive dashboard — 6-page React + Tailwind UI with live filters and Recharts
✅ Report generation — one-click PDF, CSV, and PowerPoint exports
✅ Fully containerised — Docker Compose gets you from zero to live in < 5 minutes

Tech stack: FastAPI · scikit-learn · XGBoost · pandas · React · Vite · Tailwind · Recharts · Docker

The thing I'm most proud of? The AI Agent works entirely with rule-based intent routing —
no OpenAI bill, no latency, just fast deterministic analytics delivered in a conversational UI.

Repo: github.com/your-username/customer-retention-ai-agent

#MachineLearning #Python #React #FastAPI #CustomerRetention #DataScience #AIAgent
```

---

## Screenshots

> Add screenshots to `docs/screenshots/` and reference them here.

| Page | Preview |
|---|---|
| Executive Overview | `docs/screenshots/overview.png` |
| Risk Explorer | `docs/screenshots/risk-explorer.png` |
| AI Agent Chat | `docs/screenshots/agent-chat.png` |

---

## Contributing

1. Fork → feature branch → PR
2. Run `uvicorn app.main:app --reload` and `npm run dev` for local dev
3. Add tests under `backend/tests/`

---

## License

MIT — see [LICENSE](LICENSE)
