#!/bin/bash
# Verify LangGraph Checkpoint Schema
# This script checks if all required columns exist in checkpoint tables

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================"
echo "LangGraph Checkpoint Schema Verification"
echo -e "======================================${NC}\n"

# Check if running inside Docker or on host
if [ "$1" == "--host" ]; then
    DB_USER=${DB_USER:-postgres}
    DB_PASSWORD=${DB_PASSWORD:-postgres123}
    DB_NAME=${DB_NAME:-mental_health_db}
    DB_HOST=${DB_HOST:-localhost}
    DB_PORT=${DB_PORT:-5432}
    PSQL_CMD="PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -A"
else
    PSQL_CMD="docker exec mental_health_db psql -U postgres -d mental_health_db -t -A"
fi

echo -e "${YELLOW}Checking checkpoint_writes table schema...${NC}\n"

# Check if table exists
TABLE_EXISTS=$($PSQL_CMD -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'checkpoint_writes');" 2>/dev/null || echo "f")

if [ "$TABLE_EXISTS" != "t" ]; then
    echo -e "${RED}✗ checkpoint_writes table does not exist!${NC}"
    echo -e "${YELLOW}Run migrations: ./apply-migrations.sh --docker${NC}"
    exit 1
fi

echo -e "${GREEN}✓ checkpoint_writes table exists${NC}\n"

# Check required columns
REQUIRED_COLUMNS=("thread_id" "checkpoint_ns" "checkpoint_id" "task_id" "idx" "channel" "type" "value" "blob" "task_path")
MISSING_COLUMNS=()

echo "Checking required columns:"
for col in "${REQUIRED_COLUMNS[@]}"; do
    COL_EXISTS=$($PSQL_CMD -c "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'checkpoint_writes' AND column_name = '$col');" 2>/dev/null || echo "f")
    
    if [ "$COL_EXISTS" == "t" ]; then
        # Get column type
        COL_TYPE=$($PSQL_CMD -c "SELECT data_type FROM information_schema.columns WHERE table_name = 'checkpoint_writes' AND column_name = '$col';" 2>/dev/null)
        echo -e "  ${GREEN}✓${NC} $col (type: $COL_TYPE)"
    else
        echo -e "  ${RED}✗${NC} $col ${RED}MISSING${NC}"
        MISSING_COLUMNS+=("$col")
    fi
done

echo ""

# Check other checkpoint tables
echo "Checking other checkpoint tables:"
CHECKPOINT_TABLES=("checkpoints" "checkpoint_blobs")
for table in "${CHECKPOINT_TABLES[@]}"; do
    TABLE_EXISTS=$($PSQL_CMD -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '$table');" 2>/dev/null || echo "f")
    if [ "$TABLE_EXISTS" == "t" ]; then
        echo -e "  ${GREEN}✓${NC} $table"
    else
        echo -e "  ${YELLOW}⚠${NC}  $table ${YELLOW}MISSING (will be created by LangGraph)${NC}"
    fi
done

echo ""

# Summary
if [ ${#MISSING_COLUMNS[@]} -eq 0 ]; then
    echo -e "${GREEN}======================================"
    echo "✓ All required columns present!"
    echo "Schema is ready for LangGraph 1.0.6+"
    echo -e "======================================${NC}"
    
    # Show table stats
    echo -e "\n${YELLOW}Table Statistics:${NC}"
    CHECKPOINT_COUNT=$($PSQL_CMD -c "SELECT COUNT(*) FROM checkpoints;" 2>/dev/null || echo "0")
    WRITES_COUNT=$($PSQL_CMD -c "SELECT COUNT(*) FROM checkpoint_writes;" 2>/dev/null || echo "0")
    echo "  - Checkpoints: $CHECKPOINT_COUNT"
    echo "  - Writes: $WRITES_COUNT"
    
    exit 0
else
    echo -e "${RED}======================================"
    echo "✗ Missing columns detected!"
    echo -e "======================================${NC}"
    echo -e "\nMissing columns: ${MISSING_COLUMNS[*]}"
    echo -e "\n${YELLOW}Fix:${NC}"
    echo "  ./apply-migrations.sh --docker"
    echo -e "\n${YELLOW}Or manually:${NC}"
    
    for col in "${MISSING_COLUMNS[@]}"; do
        case $col in
            "blob")
                echo "  docker exec mental_health_db psql -U postgres -d mental_health_db -c \"ALTER TABLE checkpoint_writes ADD COLUMN blob BYTEA;\""
                ;;
            "task_path")
                echo "  docker exec mental_health_db psql -U postgres -d mental_health_db -c \"ALTER TABLE checkpoint_writes ADD COLUMN task_path TEXT[];\""
                ;;
        esac
    done
    
    exit 1
fi
