#!/bin/bash
# Build and push backend image from local code
# This script builds the backend Docker image locally and pushes it to Docker Hub

set -e

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

echo -e "${YELLOW}Step 1: Building backend image from local code...${NC}"
docker build -t ${FULL_IMAGE_NAME} ./backend

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Build failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Build completed successfully${NC}\n"

# Check if user is logged in to Docker Hub
echo -e "${YELLOW}Step 2: Checking Docker Hub login...${NC}"
if ! docker info | grep -q "Username: ${DOCKER_USERNAME}"; then
    echo -e "${YELLOW}Not logged in to Docker Hub. Logging in...${NC}"
    docker login
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Docker login failed${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Docker Hub authenticated${NC}\n"

# Push the image
echo -e "${YELLOW}Step 3: Pushing image to Docker Hub...${NC}"
echo "Image: ${FULL_IMAGE_NAME}"
docker push ${FULL_IMAGE_NAME}

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Push failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Image pushed successfully${NC}\n"

# Summary
echo -e "${GREEN}======================================"
echo "✓ Backend image built and pushed"
echo -e "======================================${NC}"
echo ""
echo "Image: ${FULL_IMAGE_NAME}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
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
