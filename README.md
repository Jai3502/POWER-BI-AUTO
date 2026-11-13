# AutoBI (POWER-BI-AUTO)

> **Enterprise-Ready Automated Analytics & Business Intelligence Dashboard**

AutoBI is an automated business intelligence and data visualization web platform. Users can upload raw datasets in **Excel (`.xlsx`, `.xls`)** or **CSV (`.csv`)** format, and AutoBI automatically profiles schemas, identifies column data types, computes high-impact KPIs, generates interactive Plotly visualizations, and provides interactive slicers, real-time table search, pagination, and data export.

---

## 🌟 Key Features

- **Automated Data Profiling**: Intelligent heuristic detection of dates, numerical metrics, categorical dimensions, and unique identifiers.
- **Dynamic KPI Generation**: Calculates record counts, null counts, duplicate rows, completeness rates, and key numeric summaries formatted with standard abbreviations (`K`, `M`, `B`).
- **Interactive Visualizations (Plotly Express)**:
  - Category breakdown (Bar charts)
  - Dimension distribution (Donut charts with automatic long-tail aggregation)
  - Time-series trends (Monthly resampled line & area charts)
  - Numerical distributions (Histograms with marginal boxplots)
  - Bivariate correlation (Scatter plots)
  - Categorical averages (Average bar charts)
  - Multi-variable statistical correlation (Heatmap matrix)
- **Sub-Second Dynamic Filtering**: Multi-select categorical slicers recalculate metrics and re-render charts asynchronously with automated caching.
- **Interactive Data Preview**: Instant client-side row search, configurable page sizes (10, 25, 50, 100), and pagination.
- **Data Exporting**: Download filtered or full worksheet datasets in CSV or Excel formats on demand.
- **Multi-Worksheet Navigation**: Seamlessly switch between sheets in a multi-tab workbook.
- **Persistent Metadata Store**: Built-in SQLite database tracks upload history and file sessions across server restarts.
- **Production Architecture**: Configured for WSGI servers (Waitress on Windows, Gunicorn on Linux), Docker containerization, structured rotating file logging, health-check probes, and security headers.

---

## 🏗️ Architecture

```
POWER-BI-AUTO/
├── app.py                      # Flask Application Factory & Route Controllers
├── config.py                   # Environment-driven configuration classes
├── wsgi.py                     # Production WSGI entrypoint (Waitress / Gunicorn)
├── requirements.txt            # Pinned production dependencies
├── Dockerfile                  # Multi-stage production container build
├── docker-compose.yml          # Container orchestration with named volumes
├── .env.example                # Template for environment configuration
│
├── services/                   # Business Logic & Analytics Services
│   ├── analyzer.py             # Schema profiling, type detection, KPIs & summaries
│   ├── chart_service.py        # Automated Plotly chart generation & styling
│   ├── db_service.py           # SQLite persistence for upload sessions & history
│   └── excel_service.py        # Excel/CSV parser, caching layer & file exporter
│
├── static/                     # Frontend Assets
│   ├── css/style.css           # Clean modern dashboard styles & responsive layout
│   └── js/dashboard.js         # Client-side Plotly rendering, search & pagination
│
├── templates/                  # Jinja2 Templates
│   ├── index.html              # Drag-and-drop file upload & recent dashboards
│   ├── dashboard.html          # Main interactive BI dashboard
│   └── error.html              # Branded error pages (404, 413, 500)
│
└── tests/                      # Automated Test Suite
    ├── test_services.py        # Unit tests for services and analyzers
    └── test_app.py             # Integration tests for routes and API endpoints
```

---

## 🚀 Quickstart & Local Setup

### 1. Prerequisites
- Python 3.10+ installed

### 2. Clone and Setup Environment
```bash
# Clone the repository
git clone https://github.com/your-username/POWER-BI-AUTO.git
cd POWER-BI-AUTO

# Create and activate virtual environment
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 4. Run Development Server
```bash
python app.py
```
Open your browser and visit: `http://127.0.0.1:5000`

---

## 🏭 Production Deployment

### Option A: Using Waitress (Windows & Cross-Platform)
AutoBI includes native `waitress` support in `wsgi.py`:
```bash
python wsgi.py
```
This spawns a multi-threaded production WSGI server listening on `http://0.0.0.0:5000`.

### Option B: Using Gunicorn (Linux / Cloud VM)
```bash
gunicorn --bind 0.0.0.0:5000 --workers 4 --threads 2 --timeout 120 wsgi:app
```

### Option C: Docker Container Deployment
Build and run with Docker:
```bash
# Build Docker image
docker build -t autobi:latest .

# Run container
docker run -d -p 5000:5000 --name autobi-prod autobi:latest
```

### Option D: Docker Compose
```bash
docker-compose up -d
```
Docker Compose automatically provisions persistent volumes for:
- Uploaded files (`uploads/`)
- High-speed cached tables (`cache/`)
- SQLite metadata database (`data/`)
- Rotating application logs (`logs/`)

---

## 🧪 Running Automated Tests

Run the full automated test suite:
```bash
python -m unittest discover tests
```
Or with `pytest`:
```bash
pytest tests/ -v
```

---

## 🔌 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/health` | `GET` | Health check probe returning service status (`200 OK`). |
| `/` | `GET` | Main landing page with file upload and recent dashboards. |
| `/upload` | `POST` | Multipart file upload endpoint (`.xlsx`, `.xls`, `.csv`). |
| `/dashboard/<file_id>` | `GET` | Dashboard interface for given file ID. Accepts `?sheet=<name>`. |
| `/api/filter/<file_id>` | `POST` | Asynchronous slicer endpoint. Receives `{ sheet: "...", filters: {...} }` and returns updated KPIs and Plotly charts. |
| `/api/export/<file_id>` | `GET` | Exports filtered or complete dataset as `format=csv` or `format=xlsx`. |

---

## 🛡️ Security & Reliability

- **File Limits**: Enforces a configurable 50 MB payload upload limit (`MAX_CONTENT_LENGTH`).
- **Filename Sanitization**: Sanitizes file paths via Werkzeug's `secure_filename`.
- **Security Headers**: Injects `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, and `X-XSS-Protection`.
- **Structured Logging**: Automatic log rotation (`logs/autobi.log`) with timestamped error and audit traces.
- **Error Handling**: Graceful fallback pages for 400, 404, 413, and 500 error conditions.

---

## 📄 License
This project is licensed under the MIT License.
