# CA Automation — AI Engine

FastAPI + Celery microservice that powers the TDS filing workflow:
extracts data from challan PDFs and Excel sheets, compares totals,
and generates OLTAS `.csi` and NSDL FVU `.txt` return files.

---

## Architecture

```
ca-automation-ai-engine/
├── api/
│   ├── app.py               # FastAPI application factory
│   └── routes/
│       └── tds.py           # All /api/v1/tds/* endpoints
├── features/
│   └── tds/
│       ├── extractors/      # PDF & Excel extraction logic
│       ├── generators/      # CSI & FVU file generators
│       ├── processors/      # Form builders (24Q, 26Q, 27Q, 27EQ …)
│       ├── schemas/         # Pydantic models (ChallanData, DeducteeRecord …)
│       └── validators/      # TDS amount & PAN validation
├── workers/
│   ├── celery_app.py        # Celery app + task routing config
│   └── tasks/tds/
│       ├── extraction_tasks.py   # Async challan / Excel extraction
│       └── generation_tasks.py   # Async CSI / FVU file generation
├── config/
│   └── settings.py          # Pydantic-Settings config (reads .env)
├── scripts/                 # Manual test scripts
├── tds-doc/                 # Sample challan PDF & Excel for testing
├── output/                  # Generated files land here (gitignored)
├── Makefile                 # One-liner dev commands
├── docker-compose.yml       # Full stack (Redis + API + Worker + Flower)
└── requirements.txt
```

**TDS request flow:**

```
NestJS backend
  │
  ├─ POST /api/v1/tds/upload/challan   → ChallanExtractor (PyMuPDF) → challanData JSON
  ├─ POST /api/v1/tds/upload/excel     → ExcelExtractor (openpyxl)  → deducteesData JSON
  ├─ POST /api/v1/tds/compare          → TDSValidator + auto-fill    → comparisonData JSON
  ├─ POST /api/v1/tds/generate/csi     → Celery task → .csi file
  ├─ POST /api/v1/tds/generate/fvu     → Celery task → .txt file
  ├─ GET  /api/v1/tds/status/{task_id} → Celery AsyncResult
  └─ GET  /api/v1/tds/download/{task_id} → FileResponse
```

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12+ | Use `python3 --version` to verify |
| Redis | 7+ | Required for Celery broker + result backend |
| pip | latest | `pip install --upgrade pip` |

Install Redis locally (macOS):

```bash
brew install redis
brew services start redis
```

Or run Redis with Docker (no local install needed):

```bash
docker run -d -p 6379:6379 --name caa-redis redis:7-alpine
```

---

## Local Setup (recommended for development)

### 1. Clone and enter the directory

```bash
cd ca-automation-ai-engine
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
      # macOS / Linux
# .venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
# or
make install
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` as needed — defaults work for local Redis on `localhost:6379`:

```env
APP_NAME="CAA AI Service"
APP_VERSION="1.0.0"
DEBUG=false

REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

UPLOAD_DIR=/tmp/caa-ai/uploads
OUTPUT_DIR=/tmp/caa-ai/outputs
MAX_FILE_SIZE=10485760        # 10 MB
```

### 5. Create output directories

```bash
mkdir -p /tmp/caa-ai/uploads /tmp/caa-ai/outputs
```

### 6. Start the API server

```bash
make dev
# or
uvicorn api.app:app --host 0.0.0.0 --port 4000 --reload
```

API will be available at: `http://localhost:4000`

Interactive docs: `http://localhost:4000/docs`

### 7. Start the Celery worker (separate terminal)

```bash
source .venv/bin/activate
make worker
# or
celery -A workers.celery_app worker --loglevel=info --queues=tds --concurrency=4
```

### 8. (Optional) Start Flower — Celery monitoring UI

```bash
source .venv/bin/activate
make flower
# or
celery -A workers.celery_app flower --port=5555
```

Flower dashboard: `http://localhost:5555`

---

## Docker Setup (production-like)

Runs Redis + API + Worker + Flower in one command.

```bash
# Build and start all services
make docker-up
# or
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
make docker-down
# or
docker-compose down
```

| Service | URL |
|---------|-----|
| API | `http://localhost:8000` |
| API docs (Swagger) | `http://localhost:8000/docs` |
| Flower (Celery UI) | `http://localhost:5555` |
| Redis | `localhost:6379` |

> **Note:** The `docker-compose.yml` runs the API on port **8000**.
> The `make dev` / Makefile local command runs on port **4000** (matches `AI_ENGINE_URL` in the NestJS backend `.env`).

---

## API Reference

Base path: `/api/v1/tds`

### Health check

```
GET /health
```

### Form registry

```
GET /api/v1/tds/forms
GET /api/v1/tds/forms/{form_key}     # e.g. 24Q, 26Q, 27Q, 27EQ
```

### Upload & extract

```
POST /api/v1/tds/upload/challan
  Content-Type: multipart/form-data
  Body: file=<PDF>

POST /api/v1/tds/upload/excel
  Content-Type: multipart/form-data
  Body: file=<XLSX>, tds_type=salary|professional|rent
```

### Compare challan vs deductees

```
POST /api/v1/tds/compare
  Body: { "challan": {...}, "deductees": [...] }
```

### Generate files (async via Celery)

```
POST /api/v1/tds/generate/csi
  Body: { "challan": {...}, "status": "F" }
  Returns: { "task_id": "...", "filename": "..." }

POST /api/v1/tds/generate/fvu
  Body: { "tds_type": "salary", "quarter": "Q4", "challan": {...}, "deductees": [...], "deductor": {...} }
  Returns: { "task_id": "...", "filename": "..." }
```

### Poll task status

```
GET /api/v1/tds/status/{task_id}
  Returns: { "task_id": "...", "status": "PENDING|STARTED|SUCCESS|FAILURE", "result": {...} }
```

### Download generated file

```
GET /api/v1/tds/download/{task_id}
  Returns: File (.csi or .txt)
```

---

## Testing

Sample files are in `tds-doc/`:

- `26052900117523ICIC_ChallanReceipt.pdf` — ICICI Bank ITNS 281 challan
- `Salary Breakup details- DEUS IT SOLUTIONS.xlsx` — deductee salary sheet

### Quick API smoke test

```bash
# Health check
curl http://localhost:4000/health

# Upload challan PDF
curl -X POST http://localhost:4000/api/v1/tds/upload/challan \
  -F "file=@tds-doc/26052900117523ICIC_ChallanReceipt.pdf"

# Upload Excel
curl -X POST http://localhost:4000/api/v1/tds/upload/excel \
  -F "file=@tds-doc/Salary Breakup details- DEUS IT SOLUTIONS.xlsx" \
  -F "tds_type=salary"
```

### Script-based tests

```bash
python scripts/test_challan_extraction.py
python scripts/test_excel_extraction.py
```

### pytest

```bash
make test
# or
pytest tests/ -v
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `CAA AI Service` | Service name shown in docs |
| `APP_VERSION` | `1.0.0` | Service version |
| `DEBUG` | `false` | Enable debug logging |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection (general) |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery task broker |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/1` | Celery result store |
| `UPLOAD_DIR` | `/tmp/caa-ai/uploads` | Where uploaded files are saved |
| `OUTPUT_DIR` | `/tmp/caa-ai/outputs` | Where generated `.csi`/`.txt` files land |
| `MAX_FILE_SIZE` | `10485760` | Max upload size in bytes (10 MB) |

---

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make install` | Install Python dependencies |
| `make dev` | Start API server on port 4000 with hot reload |
| `make worker` | Start Celery worker (TDS queue, 4 concurrent) |
| `make flower` | Start Flower monitoring UI on port 5555 |
| `make docker-up` | Start full stack with Docker Compose |
| `make docker-down` | Stop Docker Compose services |
| `make test` | Run pytest suite |
| `make lint` | Run ruff linter and format check |

---

## Connecting to the NestJS Backend

In `ca-backend-nest/.env`, set:

```env
AI_ENGINE_URL=http://localhost:4000
```

The NestJS `TdsFilingService` calls this URL directly for all extraction, comparison, and generation requests.
