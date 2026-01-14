#!/bin/bash
# Apply database migrations for Mental Health Chatbot
# This script applies all pending migrations in the migrations directory

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================"
echo "Mental Health Chatbot - Database Migrations"
echo -e "======================================${NC}\n"

# Get database connection info from .env or use defaults
DB_USER=${DB_USER:-postgres}
DB_PASSWORD=${DB_PASSWORD:-postgres123}
DB_NAME=${DB_NAME:-mental_health_db}
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}

# Check if running inside Docker or on host
if [ "$1" == "--docker" ]; then
    echo -e "${YELLOW}Running migrations inside Docker container...${NC}"
    PSQL_CMD="docker exec mental_health_db psql -U $DB_USER -d $DB_NAME"
else
    echo -e "${YELLOW}Running migrations on host...${NC}"
    PSQL_CMD="PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"
fi

# Migration directory
MIGRATION_DIR="backend/migrations"

# Check if migration directory exists
if [ ! -d "$MIGRATION_DIR" ]; then
    echo -e "${RED}Error: Migration directory not found: $MIGRATION_DIR${NC}"
    exit 1
fi

# Apply each migration file in order
migration_count=0
for migration_file in $(ls -1 $MIGRATION_DIR/*.sql 2>/dev/null | sort); do
    migration_name=$(basename "$migration_file")
    echo -e "${GREEN}Applying migration: ${migration_name}${NC}"
    
    if [ "$1" == "--docker" ]; then
        docker exec -i mental_health_db psql -U $DB_USER -d $DB_NAME < "$migration_file"
    else
        PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f "$migration_file"
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Migration applied successfully: ${migration_name}${NC}\n"
        migration_count=$((migration_count + 1))
    else
        echo -e "${RED}✗ Migration failed: ${migration_name}${NC}\n"
        exit 1
    fi
done

if [ $migration_count -eq 0 ]; then
    echo -e "${YELLOW}No migrations found in $MIGRATION_DIR${NC}"
else
    echo -e "${GREEN}======================================"
    echo "✓ All $migration_count migration(s) applied successfully"
    echo -e "======================================${NC}"
fi
