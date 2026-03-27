# MICROSERVICE PLAN

## Yêu cầu đã chốt

1. Có `infra` riêng (redis, postgres, milvus+etcd+minio, neo4j)
2. Có 3 compose chính theo repo:
   - `frontend/docker-compose.yml`
   - `backend/docker-compose.yml`
   - `ai/docker-compose.yml`
3. Tất cả agent nằm trong `ai/agents/`
4. **Mỗi agent có đủ 3 file riêng**:
   - `Dockerfile`
   - `requirements.txt`
   - `schemas.py`

---

## 1) Cấu trúc thư mục

```text
frontend/
  docker-compose.yml
  Dockerfile
  ...

backend/
  docker-compose.yml
  Dockerfile
  requirements.txt
  src/

ai/
  docker-compose.yml
  shared/
  agents/
    supervisor/
      Dockerfile
      requirements.txt
      schemas.py
      main.py
      ...
    memory/
      Dockerfile
      requirements.txt
      schemas.py
      main.py
      ...
    diagnostic/
      Dockerfile
      requirements.txt
      schemas.py
      main.py
      ...
    theory/
      Dockerfile
      requirements.txt
      schemas.py
      main.py
      ...
    treatment/
      Dockerfile
      requirements.txt
      schemas.py
      main.py
      ...
    support/
      Dockerfile
      requirements.txt
      schemas.py
      main.py
      ...
    crisis/
      Dockerfile
      requirements.txt
      schemas.py
      main.py
      ...

infra/
  docker-compose.yml
```

---

## 2) Ports

- backend: `8000`
- supervisor: `8001`
- memory: `8002`
- diagnostic: `8101`
- theory: `8102`
- treatment: `8103`
- support: `8104`
- crisis: `8105`
- frontend: `8080`

---

## 3) Compose files

### `infra/docker-compose.yml`
- redis
- postgres
- etcd
- minio
- milvus
- neo4j

### `ai/docker-compose.yml`
Services:
- supervisor
- memory
- agent-diagnostic
- agent-theory
- agent-treatment
- agent-support
- agent-crisis

Mỗi service build từ Dockerfile riêng trong `ai/agents/<agent>/Dockerfile`.

### `backend/docker-compose.yml`
- backend service
- env: `SUPERVISOR_URL=http://supervisor:8001`

### `frontend/docker-compose.yml`
- frontend service
- env: `VITE_API_URL=http://backend:8000`

---

## 4) Luồng giao tiếp

- frontend -> backend
- backend -> supervisor (`POST /engine/route`)
- supervisor -> domain agents (`POST /agent/{name}`)
- agents -> memory (`/memory/*`)
- agents -> milvus/neo4j (direct)

---

## 5) Deploy order

```bash
docker network create mental_health_network

docker compose -f infra/docker-compose.yml up -d

docker compose -f ai/docker-compose.yml up --build -d

docker compose -f backend/docker-compose.yml up --build -d

docker compose -f frontend/docker-compose.yml up --build -d
```

---

## 6) Verification

- `GET :8000/health` backend ok
- `GET :8001/health` supervisor ok
- `GET :8002/health` memory ok
- `GET :8101..8105/health` all agents ok
- E2E chat: frontend -> backend -> supervisor -> agent -> response
