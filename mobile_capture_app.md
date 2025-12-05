# 📱 Native Mobile Capture App – Technical Brief

## 1. Objetivo
Garantizar que los walk-arounds capturados desde un smartphone sean estables, completos (360°) y listos para enviarse al pipeline 360-car-view sin reprocesos manuales.

---
## 2. Criterios de captura
1. **Cobertura 360° real**
   - Guía visual con puntos cardinales (0°, 90°, 180°, 270°).
   - Feedback si falta algún segmento.
2. **Distancia y altura consistentes**
   - HUD con círculo ideal y mensajes si la distancia varía.
3. **Estabilidad**
   - Estabilización por software usando datos IMU (Sensor Fusion) + OIS si disponible.
4. **Iluminación / Exposición**
   - Bloqueo de exposición al iniciar.
   - Avisos si hay exceso de luz / contraluz extremo.
5. **Audio opcional**
   - Grabación de notas de voz o mute.
6. **Reprocesos rápidos**
   - Repetir solo un tramo (por ejemplo “Segmento 2 – lateral derecho”).

---
## 3. Arquitectura propuesta

```
┌──────────────────────────┐
│      Native App (iOS/Android)      │
├──────────────────────────┤
│ 1. Camera Module                 │
│    - Sensor fusion stabilization │
│    - Exposure lock               │
│    - Quality monitor (fps/lux)   │
│                                  │
│ 2. Capture Orchestrator          │
│    - Flow manager (segments)     │
│    - Guidance UI (AR overlay)    │
│    - Validation (coverage, blur) │
│                                  │
│ 3. Local Storage                 │
│    - Temporary segmented video   │
│    - Metadata (IMU traces)       │
│                                  │
│ 4. Uploader                      │
│    - Compression (H.265/AV1)     │
│    - Background upload           │
│    - Resume on failure           │
└──────────────────────────┘
             │
             │ HTTPS (chunked upload + metadata)
             ▼
┌──────────────────────────┐
│ car360 API backend       │
│ - /api/v1/videos/mobile  │
│ - Receives video+metadata│
│ - Stores in MinIO        │
│ - Kicks Celery task      │
└──────────────────────────┘
```

### Módulos clave
1. **Camera Module**
   - Usa APIs nativas (AVFoundation / CameraX).
   - Accede a giroscopio, acelerómetro, magnetómetro para estabilización.
2. **Guidance Layer**
   - Overlay AR (ARKit/ARCore opcional) o HUD 2D.
   - Indicador de progreso y “checkpoint” cada N grados.
3. **Quality Monitor**
   - Detecta blur en tiempo real (FFT o Laplacian variance).
   - Detecta exceso de velocidad de giro.
4. **Metadata Manager**
   - Adjunta datos IMU por frame (para debugging).
   - Guarda info de entorno (luz, temperatura, etc.).
5. **Uploader**
   - Soporta redes inestables (Wi-Fi/5G) con reintentos.
   - Puede enviar video crudo o comprimido + snapshots.

---
## 4. Interacción con backend
| Paso | Acción |
|------|--------|
| 1 | App solicita token temporal (Auth) |
| 2 | App inicia sesión/captura video |
| 3 | Segmentos se guardan localmente (cache) |
| 4 | Tras finalizar, se crea un JSON de metadatos (duración, fps, sensores) |
| 5 | Se llama `POST /api/v1/videos/mobile` enviando video + metadata |
| 6 | Backend guarda en MinIO y dispara `process_video` |
| 7 | App escucha `GET /api/v1/videos/{task_id}` para mostrar estado |

---
## 5. Tecnologías recomendadas
| Plataforma | Lenguaje | Framework | Notas |
|------------|----------|-----------|-------|
| iOS | Swift/SwiftUI | AVFoundation + CoreMotion | Soporte ARKit opcional |
| Android | Kotlin | CameraX + SensorManager | Soporte ARCore opcional |
| Compartido | Rust/Cpp Core (opcional) | Para pipeline IMU/stabilization si se desea compartir lógica |

---
## 6. Roadmap sugerido
1. **MVP (2-3 semanas)**
   - UI guía + captura básica
   - Subida chunked + tracking de tarea
2. **Versión Pro (4-6 semanas)**
   - Estabilización avanzada con IMU
   - Guardado offline y reanudación
   - Telemetría / analytics de captura
3. **Enterprise**
   - Multi-usuario, roles
   - Integración con catálogos / VIN lookup
   - Envío automático a producción (S3)

---
## 7. Criterios de calidad
- FPS constante (ideal 30fps).
- Desviación estándar de distancia < 10%.
- Cobertura mínima: 330° (alerta si no se completa).
- Tamaño de video optimizado (<200MB ideal).
- Proceso de subida debe reintentarse hasta éxito.

---
## 8. Futuras extensiones
- Captura de fotos HDR para interiores.
- LiDAR/Depth scanning para reconstrucción 3D.
- Integración con accesorios (gimbal Bluetooth).
- Post-procesamiento on-device (pre-normalizar frames).

---
**Resultado esperado:** una app nativa que garantice datos perfectos para el pipeline 360-car-view, reduciendo reprocesos y entregando experiencias consistentes.
