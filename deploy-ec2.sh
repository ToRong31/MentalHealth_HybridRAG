#!/bin/bash

# Script to deploy on EC2 server
# This script should be run on the EC2 server

set -e

echo "========================================="
echo "Deploying Mental Health App on EC2"
echo "========================================="

# Check if docker-compose-production.yml exists
if [ ! -f docker-compose-production.yml ]; then
    echo "❌ Error: docker-compose-production.yml not found!"
    echo "Please make sure you have the docker-compose-production.yml file in the current directory."
    exit 1
fi

# Check if .env.production exists
if [ ! -f .env.production ]; then
    echo "⚠️  Warning: .env.production not found!"
    echo "Creating a template .env.production file..."
    cat > .env.production << 'EOF'
# Database Configuration
DB_USER=postgres
DB_PASSWORD=postgres123
DB_NAME=mental_health_db
DB_PORT=5432

# PgAdmin Configuration (optional - for debugging)
PGADMIN_EMAIL=admin@admin.com
PGADMIN_PASSWORD=admin123
PGADMIN_PORT=5050

# Backend Configuration
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_DAYS=7

# Frontend Configuration
VITE_API_URL=
EOF
    echo "✅ Template .env.production created. Please update it with your values."
    echo "Press Enter to continue or Ctrl+C to exit and edit .env.production first..."
    read
fi

echo ""
echo "Step 1: Pulling latest Docker images..."
echo "-----------------------------------"
docker compose -f docker-compose-production.yml pull

echo ""
echo "Step 2: Stopping existing containers..."
echo "-----------------------------------"
docker compose -f docker-compose-production.yml down

echo ""
echo "Step 3: Starting services..."
echo "-----------------------------------"
docker compose -f docker-compose-production.yml up -d

echo ""
echo "Step 4: Waiting for services to be healthy..."
echo "-----------------------------------"
sleep 10

echo ""
echo "Step 5: Checking service status..."
echo "-----------------------------------"
docker compose -f docker-compose-production.yml ps

echo ""
echo "========================================="
echo "✅ Deployment Completed!"
echo "========================================="
echo ""
echo "Service URLs:"
echo "  - Application: http://$(curl -s ifconfig.me)"
echo "  - Backend Health: http://$(curl -s ifconfig.me)/api/health"
echo "  - Neo4j Browser: http://$(curl -s ifconfig.me):7474"
echo "  - MinIO Console: http://$(curl -s ifconfig.me):9001"
echo ""
echo "Useful commands:"
echo "  - View logs: docker compose -f docker-compose-production.yml logs -f [service_name]"
echo "  - Stop all: docker compose -f docker-compose-production.yml down"
echo "  - Restart: docker compose -f docker-compose-production.yml restart [service_name]"
echo "========================================="
