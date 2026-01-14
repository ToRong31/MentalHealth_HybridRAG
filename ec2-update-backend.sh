#!/bin/bash
# EC2 Update Script - Backend Only
# Run this script on EC2 server after pushing new backend image from local
# This will pull the latest backend image and restart the container

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================"
echo "EC2 Backend Update"
echo -e "======================================${NC}\n"

# Configuration
IMAGE_NAME="torong/mentalhealth-backend:latest"

echo -e "${YELLOW}Step 1: Pulling latest backend image from Docker Hub...${NC}"
docker compose pull backend

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to pull image${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Image pulled successfully${NC}\n"

echo -e "${YELLOW}Step 2: Stopping current backend container...${NC}"
docker compose stop backend

echo -e "${GREEN}✓ Backend stopped${NC}\n"

echo -e "${YELLOW}Step 3: Starting backend with new image...${NC}"
docker compose up -d backend

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to start backend${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Backend started${NC}\n"

echo -e "${YELLOW}Step 4: Waiting for backend to be healthy (30 seconds)...${NC}"
sleep 30

# Check if backend is healthy
BACKEND_STATUS=$(docker compose ps backend --format json 2>/dev/null | grep -o '"Health":"[^"]*"' | cut -d'"' -f4 || echo "unknown")

if [ "$BACKEND_STATUS" == "healthy" ]; then
    echo -e "${GREEN}✓ Backend is healthy${NC}\n"
elif [ "$BACKEND_STATUS" == "starting" ]; then
    echo -e "${YELLOW}⚠ Backend is still starting (this is normal)${NC}\n"
else
    echo -e "${YELLOW}⚠ Backend status: $BACKEND_STATUS${NC}\n"
fi

# Show recent logs
echo -e "${YELLOW}Step 5: Checking recent logs...${NC}"
docker compose logs backend --tail 30

echo ""
echo -e "${GREEN}======================================"
echo "✓ Backend Update Complete"
echo -e "======================================${NC}"
echo ""
echo "Image: ${IMAGE_NAME}"
echo ""
echo -e "${YELLOW}Verification:${NC}"
echo "1. Check backend status:"
echo "   docker compose ps backend"
echo ""
echo "2. Check backend logs:"
echo "   docker compose logs -f backend"
echo ""
echo "3. Check database schema:"
echo "   ./verify-checkpoint-schema.sh"
echo ""
echo "4. Test chat functionality through the UI"
