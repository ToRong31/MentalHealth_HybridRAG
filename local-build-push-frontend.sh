#!/bin/bash
# Script to build and push FRONTEND ONLY to DockerHub
# Run this on LOCAL machine after making frontend changes

set -e

DOCKERHUB_USERNAME="torong"
VERSION_TAG="${1:-latest}"

echo "========================================="
echo "Building & Pushing Frontend"
echo "========================================="
echo "DockerHub: $DOCKERHUB_USERNAME"
echo "Version: $VERSION_TAG"
echo "========================================="

# Check DockerHub login
echo "Checking DockerHub login..."
docker info > /dev/null 2>&1 || { echo "Docker not running!"; exit 1; }

echo ""
echo "Step 1: Building frontend image..."
docker build -t ${DOCKERHUB_USERNAME}/mentalhealth-frontend:${VERSION_TAG} \
             -t ${DOCKERHUB_USERNAME}/mentalhealth-frontend:latest \
             --build-arg VITE_API_URL="" \
             ./frontend

echo ""
echo "Step 2: Pushing to DockerHub..."
docker push ${DOCKERHUB_USERNAME}/mentalhealth-frontend:${VERSION_TAG}
docker push ${DOCKERHUB_USERNAME}/mentalhealth-frontend:latest

echo ""
echo "========================================="
echo "Frontend pushed successfully!"
echo "========================================="
echo ""
echo "Pushed:"
echo "  - ${DOCKERHUB_USERNAME}/mentalhealth-frontend:${VERSION_TAG}"
echo "  - ${DOCKERHUB_USERNAME}/mentalhealth-frontend:latest"
echo ""
echo "Next: Run ec2-update-frontend.sh on EC2 server"
echo "========================================="
