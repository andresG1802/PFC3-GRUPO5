
# Model Wampís (Microservicio)

Servicio FastAPI independiente para traducción ES↔Wampís vía glosario.

## Ejecutar local
```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8081
```

## Docker
```bash
docker build -t model-wampis:latest .
docker run -p 8081:8081 model-wampis:latest
```

## Endpoints
- GET /health
- POST /translate
- POST /upload_glossary
- POST /reload
```

## docker-compose (añadir a tu compose raíz)
```yaml
  model_wampis:
    build:
      context: ./model_wampis
    container_name: model_wampis
    ports:
      - "8081:8081"
    restart: unless-stopped
```

