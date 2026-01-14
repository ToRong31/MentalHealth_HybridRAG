#!/bin/bash
# Build and push backend image from local code
# This script builds the backend Docker image locally and pushes it to Docker Hub

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================"
echo "Local Build & Push - Backend"
echo -e "======================================${NC}\n"

# Configuration
DOCKER_USERNAME="torong"
IMAGE_NAME="mentalhealth-backend"
TAG="latest"
FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}:${TAG}"

# Optional: tag by git commit for rollback
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M)"
VERSION_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}:${GIT_SHA}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Check if we're in the right directory
if [ ! -d "backend" ]; then
    echo -e "${RED}Error: backend directory not found${NC}"
    echo "Please run this script from the project root"
    exit 1
fi

if [ ! -f "backend/Dockerfile" ]; then
    echo -e "${RED}Error: backend/Dockerfile not found${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Building backend image from local code (target=runtime)...${NC}"
docker build --pull --no-cache --target runtime \
  -t "${FULL_IMAGE_NAME}" \
  -t "${VERSION_IMAGE_NAME}" \
  -f "backend/Dockerfile" \
  "backend"

echo -e "${GREEN}✓ Build completed successfully${NC}\n"

echo -e "${YELLOW}Step 1.1: Quick sanity check (top layers)...${NC}"
docker history --no-trunc "${FULL_IMAGE_NAME}" | head -n 12 || true
echo ""

# Check if user is logged in to Docker Hub
echo -e "${YELLOW}Step 2: Checking Docker Hub login...${NC}"
if ! docker info | grep -q "Username: ${DOCKER_USERNAME}"; then
    echo -e "${YELLOW}Not logged in to Docker Hub. Logging in...${NC}"
    docker login
fi
echo -e "${GREEN}✓ Docker Hub authenticated${NC}\n"

# Push the image
echo -e "${YELLOW}Step 3: Pushing image to Docker Hub...${NC}"
echo "Images:"
echo "  - ${FULL_IMAGE_NAME}"
echo "  - ${VERSION_IMAGE_NAME}"

docker push "${FULL_IMAGE_NAME}"
docker push "${VERSION_IMAGE_NAME}"

echo -e "${GREEN}✓ Image pushed successfully${NC}\n"

# Summary
echo -e "${GREEN}======================================"
echo "✓ Backend image built and pushed"
echo -e "======================================${NC}"
echo ""
echo "Images:"
echo "  - ${FULL_IMAGE_NAME}"
echo "  - ${VERSION_IMAGE_NAME}"
echo ""
echo -e "${YELLOW}Next steps (on server):${NC}"
echo "1. Pull and restart the backend container:"
echo "   docker compose pull backend"
echo "   docker compose up -d backend"
echo ""
echo "2. Or restart all services:"
echo "   docker compose down"
echo "   docker compose up -d"
echo ""
echo "3. Check backend logs:"
echo "   docker compose logs -f backend"
