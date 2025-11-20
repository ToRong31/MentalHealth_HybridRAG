#!/bin/bash

# Mental Health Chatbot - Startup Script

echo "🚀 Starting Mental Health Chatbot..."
echo ""

# Check if backend/src/.env exists
if [ ! -f backend/src/.env ]; then
    echo "⚠️  backend/src/.env file not found!"
    echo "❌ Please make sure backend/src/.env exists with your GEMINI_API_KEY"
    echo "   You can get an API key from: https://makersuite.google.com/app/apikey"
    echo ""
    read -p "Press Enter after creating the backend/src/.env file..."
    exit 1
fi

# Check if GEMINI_API_KEY is set
if grep -q "GEMINI_API_KEY=your_gemini_api_key_here" backend/src/.env; then
    echo "⚠️  WARNING: GEMINI_API_KEY is not configured!"
    echo "   Please edit backend/src/.env and add your actual API key"
    echo ""
    read -p "Press Enter after updating the GEMINI_API_KEY..."
fi

echo ""
echo "🐳 Starting Docker containers..."
echo "   Note: Using Milvus Cloud (Zilliz) - no local Milvus container"
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
echo "   This may take 20-30 seconds for first startup..."
sleep 20

echo ""
echo "✅ Services started!"
echo ""
echo "📍 Access points:"
echo "   - Chatbot UI:        http://localhost"
echo "   - API Documentation: http://localhost:8000/docs"
echo "   - Neo4j Browser:     http://localhost:7474"
echo "     (username: neo4j, password: kguser2005)"
echo ""
echo "📊 Check status:"
echo "   docker-compose ps"
echo ""
echo "📝 View logs:"
echo "   docker-compose logs -f backend"
echo "   docker-compose logs -f frontend"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose down"
echo ""

