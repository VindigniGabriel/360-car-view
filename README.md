# 🚗 Car 360 Spin Viewer

API that converts walk-around videos into interactive 360° spin viewers.

## Features

- Upload walk-around videos (MP4, MOV, AVI)
- Automatic frame extraction (24, 36, or 72 frames)
- Sprite sheet generation for fast loading
- Interactive HTML5 viewer with drag-to-rotate
- Async processing with progress tracking

## Quick Start

### Prerequisites

- Docker & Docker Compose
- ~2GB disk space for images

### Run Locally

```bash
# Clone and start
git clone <repo-url>
cd 360-car-view

# Copy environment file
cp .env.example .env

# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f
```

### API Usage

```bash
# Upload video
curl -X POST http://localhost:8000/api/v1/videos \
  -F "file=@car.mp4" \
  -F "frames=36"

# Check status
curl http://localhost:8000/api/v1/videos/{task_id}

# Get result
curl http://localhost:8000/api/v1/videos/{task_id}/result
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/videos` | Upload video for processing |
| GET | `/api/v1/videos/{task_id}` | Get processing status |
| GET | `/api/v1/videos/{task_id}/result` | Get processing result |
| DELETE | `/api/v1/videos/{task_id}` | Delete video and results |
| GET | `/health` | Health check |

## Architecture

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Client  │────▶│ FastAPI │────▶│ Celery  │────▶│ Worker  │
└─────────┘     └────┬────┘     └────┬────┘     └────┬────┘
                     │               │               │
                     ▼               ▼               ▼
                ┌─────────┐     ┌─────────┐     ┌─────────┐
                │  MinIO  │     │  Redis  │     │ FFmpeg  │
                └─────────┘     └─────────┘     └─────────┘
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ACCESS_KEY` | minioadmin | MinIO access key |
| `MINIO_SECRET_KEY` | minioadmin123 | MinIO secret key |
| `MAX_VIDEO_SIZE_MB` | 100 | Max upload size |
| `DEFAULT_FRAMES` | 36 | Default frame count |

## Development

```bash
# Install dependencies locally
pip install -r requirements.txt

# Run API
uvicorn api.main:app --reload

# Run worker
celery -A worker.celery_app worker -l info
```

## License

MIT
