# 🚗 Car 360 Viewer - Guía Rápida

## Iniciar Servicios

```bash
docker-compose up -d
```

## Subir Video

### Básico (con fondo)
```bash
curl -X POST http://localhost:8000/api/v1/videos \
  -F "file=@tu_video.mp4" \
  -F "frames=36"
```

### Sin fondo (auto flotante)
```bash
curl -X POST http://localhost:8000/api/v1/videos \
  -F "file=@tu_video.mp4" \
  -F "frames=36" \
  -F "remove_bg=true"
```

## Verificar Estado

```bash
curl http://localhost:8000/api/v1/videos/{task_id}
```

## Ver Resultado

Cuando `status: SUCCESS`:

```bash
curl http://localhost:8000/api/v1/videos/{task_id}/result
```

Abre el `viewer_url` en tu navegador.

## Parámetros

| Parámetro | Opciones | Default |
|-----------|----------|---------|
| `frames` | 24, 36, 72 | 36 |
| `remove_bg` | true, false | false |

## URLs Útiles

- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (minioadmin / minioadmin123)
