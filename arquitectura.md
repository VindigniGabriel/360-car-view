# 🏗️ Arquitectura Local y Estrategia de Migración para *Car 360 Spin Viewer*

API que convierte un video walk-around grabado por el usuario en un visor interactivo 360° estabilizado.

---

# 📋 Definición del Producto

| Aspecto | Especificación |
|---------|----------------|
| **Tipo de visor** | Secuencia de frames rotables (360° interactivo) |
| **Frames por rotación** | Configurable: 24, 36 o 72 frames |
| **Input esperado** | Video walk-around completo (360°) |
| **Centrado del objeto** | Automático - auto perfectamente centrado en cada frame |
| **Remoción de fondo** | Opcional - auto "flotante" con fondo transparente |
| **Stack** | 100% open-source |

---

# 🔍 Análisis de Viabilidad

## ✅ Factibilidad

| Aspecto | Evaluación |
|---------|------------|
| **Factibilidad técnica** | ✅ Factible |
| **Herramientas open source** | ✅ Disponibles |
| **Complejidad** | ⭐⭐⭐ Media |
| **GPU requerida** | ❌ Opcional (acelera pero no es crítica) |

## ⚠️ Decisión Arquitectónica: COLMAP vs Pipeline Simplificado

### Problema con COLMAP
COLMAP está diseñado para **reconstrucción 3D (Structure from Motion)**, no para estabilización de video walk-around. Es **overkill** para este caso de uso.

### Solución Adoptada
Pipeline simplificado usando:
- **FFmpeg + vidstab** para estabilización
- **YOLOv8** para detección y centrado del auto
- **OpenCV** para tracking y extracción de frames

## 📦 Stack Open Source Final

| Componente | Herramienta | Propósito |
|------------|-------------|-----------|
| **API** | FastAPI | Endpoints REST |
| **Queue** | Celery + Redis | Procesamiento asíncrono |
| **Storage** | MinIO | Almacenamiento S3-compatible |
| **Estabilización** | FFmpeg + vidstab | Estabilizar video |
| **Detección objeto** | YOLOv8 (ultralytics) | Detectar y localizar auto |
| **Tracking** | OpenCV | Seguimiento de features |
| **Procesamiento** | Pillow/OpenCV | Crop, resize, centrado |
| **Remoción fondo** | rembg (U2Net) | Eliminar fondo para transparencia |
| **Visor 360** | HTML5/JS custom | Frontend interactivo |

---

# 🔄 Pipeline de Procesamiento

```
┌─────────────────────────────────────────────────────────────┐
│                     PIPELINE COMPLETO                        │
├─────────────────────────────────────────────────────────────┤
│  1. Upload Video (validación: duración, resolución)         │
│       ↓                                                      │
│  2. FFmpeg: Estabilización con vidstab                      │
│       ↓                                                      │
│  3. Extracción de N frames equidistantes (24/36/72)         │
│       ↓                                                      │
│  4. YOLOv8: Detección del auto en cada frame                │
│       ↓                                                      │
│  5. Normalización: crop centrado, resize uniforme           │
│       ↓                                                      │
│  6. [Opcional] rembg: Remoción de fondo (si remove_bg=true) │
│       ↓                                                      │
│  7. Optimización: WebP (con fondo) o PNG (transparente)     │
│       ↓                                                      │
│  8. Generación de sprite sheet + visor HTML5                │
│       ↓                                                      │
│  9. Output: JSON metadata + imágenes + visor embebible      │
└─────────────────────────────────────────────────────────────┘
```

## Detalle Técnico del Pipeline

### Paso 2: Estabilización
```bash
# Análisis de movimiento
ffmpeg -i input.mp4 -vf vidstabdetect=shakiness=5:accuracy=15 -f null -

# Aplicar estabilización
ffmpeg -i input.mp4 -vf vidstabtransform=smoothing=30:input=transforms.trf output_stabilized.mp4
```

### Paso 3-4: Detección y Tracking
```python
from ultralytics import YOLO

model = YOLO('yolov8n.pt')
results = model(frame)
# Extraer bounding box del auto (class 2 = car)
```

### Paso 5: Extracción de Frames
```python
# Para 36 frames = 10° por frame
total_frames = video.frame_count
step = total_frames // num_frames  # 24, 36, o 72
```

### Paso 6: Centrado Automático
```python
# Usar bounding box de YOLO para centrar
center_x = (bbox.x1 + bbox.x2) / 2
center_y = (bbox.y1 + bbox.y2) / 2
# Crop cuadrado centrado en el auto
```

---

# ⚠️ Consideraciones y Casos Edge

## Validación de Input
- **Duración mínima**: ~10 segundos para cobertura 360°
- **Resolución mínima**: 720p recomendado
- **Cobertura angular**: Detectar si el video cubre 360° completos

## Casos Edge a Manejar
| Caso | Solución |
|------|----------|
| Video incompleto (<360°) | Advertir al usuario, generar visor parcial |
| Múltiples autos en escena | Seleccionar el más prominente/centrado |
| Iluminación variable | Normalización de histograma por frame |
| Obstrucciones temporales | Interpolación o skip de frames afectados |
| Velocidad de caminata variable | Selección por ángulo, no por tiempo |

---

# 1️⃣ Arquitectura Local (Desarrollo)

## 🧩 Componentes

### **1. FastAPI (API principal)**

* Recibe el video (multipart/form-data)
* Valida formato, duración y tamaño
* Lo sube a MinIO
* Genera `task_id` y envía la tarea a Celery
* Expone ruta para consultar progreso
* Publica URLs finales del resultado

### **2. Celery (workers)**

* Orquestación de tareas asíncronas
* Worker CPU: estabilización, extracción de frames
* Worker GPU (opcional): YOLOv8 para detección rápida

### **3. Redis**

* Broker de mensajes Celery

### **4. MinIO (S3 local)**

* Almacén de videos originales
* Almacén de frames procesados
* Almacén de sprites y visor final

### **5. FFmpeg + YOLOv8 + OpenCV**

* FFmpeg: estabilización con vidstab
* YOLOv8: detección de vehículos
* OpenCV: procesamiento de imágenes

---

# 2️⃣ Estructura del Proyecto

```
project/
├── api/
│   ├── main.py              # FastAPI endpoints
│   ├── schemas.py           # Pydantic models
│   └── dependencies.py      # MinIO client, etc.
├── worker/
│   ├── celery_app.py        # Configuración Celery
│   ├── tasks.py             # Definición de tareas
│   └── pipeline/
│       ├── stabilizer.py    # FFmpeg vidstab
│       ├── detector.py      # YOLOv8 detección
│       ├── extractor.py     # Extracción de frames
│       ├── normalizer.py    # Crop, resize, centrado
│       ├── sprite_builder.py # Generación sprite sheet
│       └── viewer_generator.py # HTML5 viewer
├── viewer/
│   ├── template.html        # Template del visor 360
│   └── assets/              # JS/CSS del visor
├── models/                  # YOLOv8 weights (volumen)
├── temp/                    # Archivos temporales
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.worker
├── requirements.txt
└── .env
```

---

# 3️⃣ docker-compose.yml (Versión Actualizada)

```yaml
version: "3.9"
services:

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    restart: always
    environment:
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
      - MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
      - MINIO_BUCKET=car360
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - minio
    volumes:
      - ./temp:/app/temp

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    command: celery -A worker.celery_app worker -l info
    restart: always
    environment:
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
      - MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - minio
    volumes:
      - ./models:/app/models
      - ./temp:/app/temp

  # Worker GPU opcional - descomentar si hay GPU disponible
  # worker_gpu:
  #   build:
  #     context: .
  #     dockerfile: Dockerfile.worker
  #   runtime: nvidia
  #   command: celery -A worker.celery_app worker -Q gpu_tasks -l info
  #   deploy:
  #     resources:
  #       reservations:
  #         devices:
  #           - capabilities: [gpu]
  #   environment:
  #     - MINIO_ENDPOINT=minio:9000
  #     - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
  #     - MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
  #     - REDIS_URL=redis://redis:6379/0
  #   volumes:
  #     - ./models:/app/models
  #     - ./temp:/app/temp

  redis:
    image: redis:7-alpine
    restart: always

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"  # MinIO Console
    restart: always
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    volumes:
      - minio_data:/data

volumes:
  minio_data:
```

---

# 4️⃣ Dockerfiles

## Dockerfile.api
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Dockerfile.worker
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instalar FFmpeg con soporte vidstab
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker/ ./worker/
COPY viewer/ ./viewer/

CMD ["celery", "-A", "worker.celery_app", "worker", "-l", "info"]
```

## requirements.txt
```
# API
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
pydantic==2.5.2

# Worker
celery[redis]==5.3.4
redis==5.0.1

# Storage
minio==7.2.0

# Computer Vision
opencv-python-headless==4.8.1.78
ultralytics==8.0.200
Pillow==10.1.0
numpy==1.26.2

# Video processing
ffmpeg-python==0.2.0
```

---

# 5️⃣ Flujo Completo del Sistema

```
Cliente → FastAPI → MinIO → Celery/Redis → Worker → Pipeline → MinIO → API → Cliente
```

### Detalle del Flujo

| Paso | Componente | Acción |
|------|------------|--------|
| 1 | Cliente | Sube video + selecciona frames (24/36/72) |
| 2 | FastAPI | Valida video, genera `task_id` |
| 3 | MinIO | Almacena video original |
| 4 | Celery | Encola tarea de procesamiento |
| 5 | Worker | Ejecuta pipeline completo |
| 5.1 | FFmpeg | Estabiliza video (vidstab) |
| 5.2 | YOLOv8 | Detecta auto en cada frame |
| 5.3 | OpenCV | Extrae N frames equidistantes |
| 5.4 | Pillow | Normaliza: crop, resize, centrado |
| 5.5 | Builder | Genera sprite sheet + visor HTML |
| 6 | MinIO | Almacena resultados |
| 7 | FastAPI | Retorna URLs de descarga |

---

# 6️⃣ API Endpoints

## Endpoints Principales

```
POST   /api/v1/videos              # Subir video
GET    /api/v1/videos/{task_id}    # Estado del procesamiento
GET    /api/v1/videos/{task_id}/result  # Obtener resultado
DELETE /api/v1/videos/{task_id}    # Eliminar video y resultados
```

## Request: Subir Video
```http
POST /api/v1/videos
Content-Type: multipart/form-data

file: <video.mp4>
frames: 36        # Opciones: 24, 36, 72
remove_bg: false  # true para auto flotante sin fondo
```

## Response: Estado
```json
{
  "task_id": "abc123",
  "status": "PROCESSING",  // PENDING, PROCESSING, SUCCESS, FAILURE
  "progress": 45,          // Porcentaje 0-100
  "step": "detecting",     // stabilizing, detecting, extracting, normalizing, building
  "created_at": "2024-01-15T10:30:00Z"
}
```

## Response: Resultado (SUCCESS)
```json
{
  "task_id": "abc123",
  "status": "SUCCESS",
  "result": {
    "viewer_url": "https://minio/car360/abc123/viewer.html",
    "sprite_url": "https://minio/car360/abc123/sprite.webp",
    "frames_url": "https://minio/car360/abc123/frames/",
    "metadata": {
      "total_frames": 36,
      "frame_width": 800,
      "frame_height": 600,
      "processing_time_seconds": 45,
      "format": "webp",
      "transparent": false
    }
  }
}
```

### Con remoción de fondo (remove_bg=true)
```json
{
  "metadata": {
    "total_frames": 36,
    "format": "png",
    "transparent": true
  }
}
```

---

# 7️⃣ Visor 360° Interactivo

## Opciones de Output

| Formato | Descripción | Uso |
|---------|-------------|-----|
| **Sprite Sheet** | Una imagen con todos los frames en grid | Carga rápida, un solo request |
| **Frames individuales** | N imágenes separadas | Lazy loading, alta resolución |
| **Visor embebible** | HTML + JS autocontenido | Integración directa en sitios |

## Tecnologías para el Visor

| Librería | Licencia | Características |
|----------|----------|-----------------|
| **Spritespin** | MIT | Sprite sheets, touch support |
| **360-image-viewer** | MIT | Lightweight, vanilla JS |
| **Three.js** | MIT | Si se requiere 3D real en futuro |

## Ejemplo de Visor HTML5
```html
<!DOCTYPE html>
<html>
<head>
  <title>360° Car Viewer</title>
  <style>
    .viewer-container {
      width: 100%;
      max-width: 800px;
      aspect-ratio: 4/3;
      cursor: grab;
    }
  </style>
</head>
<body>
  <div id="viewer" class="viewer-container"></div>
  <script src="spritespin.js"></script>
  <script>
    SpriteSpin.createOrUpdate({
      target: '#viewer',
      source: SpriteSpin.sourceArray('frames/frame_{frame}.jpg', {
        frame: [0, 35],
        digits: 2
      }),
      frames: 36,
      sense: -1,
      animate: false
    });
  </script>
</body>
</html>
```

---

# 8️⃣ Migración a Producción

## Cambios para Cloud

| Local | Producción |
|-------|------------|
| MinIO | AWS S3 / Cloudflare R2 |
| Redis local | Redis Cloud / ElastiCache |
| Docker Compose | Kubernetes / ECS |
| Volúmenes locales | EFS / Persistent Volumes |

## Variables de Entorno (Producción)
```env
# Storage
S3_ENDPOINT=s3.amazonaws.com
S3_ACCESS_KEY=<secret>
S3_SECRET_KEY=<secret>
S3_BUCKET=car360-prod
S3_REGION=us-east-1

# Queue
REDIS_URL=redis://redis-cluster:6379/0

# App
MAX_VIDEO_SIZE_MB=100
ALLOWED_EXTENSIONS=mp4,mov,avi
DEFAULT_FRAMES=36
```

---

# 9️⃣ Roadmap

## Fase 1 – MVP Local (1-2 semanas)
- [ ] Endpoints FastAPI (upload, status, result)
- [ ] Celery + Redis configurado
- [ ] MinIO + carga de videos
- [ ] Extracción básica de frames (sin estabilización)
- [ ] Visor 360° simple

## Fase 2 – Pipeline Completo (1-2 semanas)
- [ ] Estabilización con vidstab
- [ ] Integración YOLOv8 para detección
- [ ] Centrado automático del auto
- [ ] Selección inteligente de frames por ángulo
- [ ] Sprite sheet generator

## Fase 3 – Optimización (1 semana)
- [ ] Compresión de imágenes (WebP)
- [ ] Lazy loading de frames
- [ ] Cache de modelos YOLOv8
- [ ] Métricas y logging

## Fase 4 – Producción (1-2 semanas)
- [ ] Migración a S3
- [ ] CI/CD pipeline
- [ ] Monitoreo (Prometheus/Grafana)
- [ ] Rate limiting y autenticación

---

# 🔧 Comandos de Desarrollo

```bash
# Iniciar servicios
docker-compose up -d

# Ver logs
docker-compose logs -f worker

# Probar API
curl -X POST http://localhost:8000/api/v1/videos \
  -F "file=@car.mp4" \
  -F "frames=36"

# Verificar estado
curl http://localhost:8000/api/v1/videos/{task_id}
```

---

# ✅ Resumen

| Aspecto | Estado |
|---------|--------|
| **Viabilidad** | ✅ Confirmada |
| **Stack** | 100% Open Source |
| **GPU** | Opcional (acelera YOLOv8) |
| **Complejidad** | Media |
| **Tiempo estimado MVP** | 2-3 semanas |

## Próximos Pasos

1. **Implementar API FastAPI** con endpoints básicos
2. **Configurar Celery** con tareas del pipeline
3. **Desarrollar pipeline** de procesamiento
4. **Crear visor 360°** embebible
5. **Testing** con video de prueba (`car.mp4`)
