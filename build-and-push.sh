#!/bin/bash

# Script to build and push Docker images to DockerHub
# Usage: ./build-and-push.sh [version_tag]

set -e

# Configuration
DOCKERHUB_USERNAME="torong"
VERSION_TAG="${1:-latest}"

echo "========================================="
echo "Building and Pushing Docker Images"
echo "========================================="
echo "DockerHub Username: $DOCKERHUB_USERNAME"
echo "Version Tag: $VERSION_TAG"
echo "========================================="

# Check if logged in to DockerHub
echo "Checking DockerHub login..."
if ! docker info | grep -q "Username: $DOCKERHUB_USERNAME"; then
    echo "Not logged in to DockerHub. Please login:"
    docker login
fi

# Load environment variables if .env.production exists
if [ -f .env.production ]; then
    echo "Loading environment variables from .env.production..."
    export $(grep -v '^#' .env.production | xargs)
fi

echo ""
echo "Step 1: Building Backend Image..."
echo "-----------------------------------"
docker build -t ${DOCKERHUB_USERNAME}/mentalhealth-backend:${VERSION_TAG} \
             -t ${DOCKERHUB_USERNAME}/mentalhealth-backend:latest \
             ./backend

echo ""
echo "Step 2: Building Frontend Image..."
echo "-----------------------------------"
docker build -t ${DOCKERHUB_USERNAME}/mentalhealth-frontend:${VERSION_TAG} \
             -t ${DOCKERHUB_USERNAME}/mentalhealth-frontend:latest \
             --build-arg VITE_API_URL="${VITE_API_URL:-}" \
             ./frontend

echo ""
echo "Step 3: Pushing Backend Image..."
echo "-----------------------------------"
docker push ${DOCKERHUB_USERNAME}/mentalhealth-backend:${VERSION_TAG}
docker push ${DOCKERHUB_USERNAME}/mentalhealth-backend:latest

echo ""
echo "Step 4: Pushing Frontend Image..."
echo "-----------------------------------"
docker push ${DOCKERHUB_USERNAME}/mentalhealth-frontend:${VERSION_TAG}
docker push ${DOCKERHUB_USERNAME}/mentalhealth-frontend:latest

echo ""
echo "========================================="
echo "✅ Build and Push Completed Successfully!"
echo "========================================="
echo ""
echo "Images pushed:"
echo "  - ${DOCKERHUB_USERNAME}/mentalhealth-backend:${VERSION_TAG}"
echo "  - ${DOCKERHUB_USERNAME}/mentalhealth-backend:latest"
echo "  - ${DOCKERHUB_USERNAME}/mentalhealth-frontend:${VERSION_TAG}"
echo "  - ${DOCKERHUB_USERNAME}/mentalhealth-frontend:latest"
echo ""
echo "Next steps:"
echo "  1. SSH to your EC2 server"
echo "  2. Pull latest code or copy docker-compose-production.yml"
echo "  3. Run: docker compose -f docker-compose-production.yml pull"
echo "  4. Run: docker compose -f docker-compose-production.yml up -d"
echo "========================================="
