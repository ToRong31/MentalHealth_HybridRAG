#!/bin/bash
# Script to rebuild frontend locally on EC2

set -e

echo "========================================="
echo "Rebuilding Frontend on EC2"
echo "========================================="

# Check if frontend source exists
if [ ! -d "./frontend/src" ]; then
    echo "❌ Frontend source not found!"
    echo "Please clone your repository or copy frontend source code first."
    exit 1
fi

cd frontend

echo "Step 1: Installing dependencies..."
npm install

echo "Step 2: Building frontend..."
export VITE_API_URL=""
npm run build

echo "Step 3: Copying built files to nginx..."
docker cp dist/. chatbot-frontend:/usr/share/nginx/html/

echo "Step 4: Reloading nginx..."
docker exec chatbot-frontend nginx -s reload

echo ""
echo "========================================="
echo "✅ Frontend rebuilt successfully!"
echo "========================================="
echo ""
echo "Test: curl http://localhost"
