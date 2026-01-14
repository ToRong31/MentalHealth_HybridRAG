#!/bin/bash
# EC2 Update Script - Backend Only

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}======================================"
echo "EC2 Backend Update"
echo -e "======================================${NC}\n"

SERVICE="backend"

# Ensure we're in the compose directory
if [ ! -f "docker-compose.yml" ] && [ ! -f "docker-compose-production.yml" ]; then
  echo -e "${YELLOW}⚠ Cannot find docker-compose.yml here. Make sure you run this in the project root on EC2.${NC}"
fi

echo -e "${YELLOW}Step 1: Pulling latest backend image from Docker Hub...${NC}"
docker compose pull "${SERVICE}"
echo -e "${GREEN}✓ Image pulled successfully${NC}\n"

echo -e "${YELLOW}Step 2: Recreating backend container with new image...${NC}"
docker compose up -d --force-recreate "${SERVICE}"
echo -e "${GREEN}✓ Backend started${NC}\n"

echo -e "${YELLOW}Step 3: Waiting for backend health (up to 90s)...${NC}"

CONTAINER_ID="$(docker compose ps -q "${SERVICE}" | head -n 1)"
if [ -z "${CONTAINER_ID}" ]; then
  echo -e "${RED}✗ Cannot find container for service '${SERVICE}'${NC}"
  docker compose ps
  exit 1
fi

# Poll health status (works if your compose defines healthcheck)
deadline=$((SECONDS + 90))
status="unknown"

while [ $SECONDS -lt $deadline ]; do
  status="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "${CONTAINER_ID}" 2>/dev/null || echo "unknown")"
  if [ "${status}" = "healthy" ]; then
    echo -e "${GREEN}✓ Backend is healthy${NC}\n"
    break
  fi
  if [ "${status}" = "unhealthy" ]; then
    echo -e "${RED}✗ Backend is unhealthy${NC}\n"
    break
  fi
  echo -e "${YELLOW}... status: ${status}${NC}"
  sleep 5
done

echo -e "${YELLOW}Step 4: Showing recent logs...${NC}"
docker compose logs "${SERVICE}" --tail 50

echo ""
echo -e "${GREEN}======================================"
echo "✓ Backend Update Complete"
echo -e "======================================${NC}"
echo ""
echo "Verification:"
echo "  docker compose ps ${SERVICE}"
echo "  docker compose logs -f ${SERVICE}"
