#!/bin/bash
# Script to pull and update FRONTEND ONLY on EC2
# Run this on EC2 server after frontend has been pushed

set -e

echo "========================================="
echo "Updating Frontend on EC2"
echo "========================================="

cd /home/ubuntu/MentalHealth_HybridRAG

echo "Step 1: Pulling latest frontend image..."
docker compose -f docker-compose-production.yml pull frontend

echo ""
echo "Step 2: Restarting frontend container..."
docker compose -f docker-compose-production.yml up -d frontend

echo ""
echo "Step 3: Waiting for frontend to be ready..."
sleep 5

echo ""
echo "Step 4: Checking status..."
docker compose -f docker-compose-production.yml ps frontend

echo ""
echo "========================================="
echo "Frontend updated successfully!"
echo "========================================="
echo ""
echo "Test your application:"
echo "  - http://$(curl -s ifconfig.me)"
echo ""
echo "View logs:"
echo "  docker compose -f docker-compose-production.yml logs -f frontend"
echo "========================================="
