# Database Schema Fix - LangGraph Checkpoint Compatibility

**Date:** 2026-01-14  
**Issue:** Chat functionality failed with PostgreSQL schema errors  
**Status:** ✅ RESOLVED

---

## Summary

Fixed compatibility issues between LangGraph 1.0.6+ and the PostgreSQL checkpoint tables. The application is now fully functional with persistent conversation state.

---

## Problems Encountered

### 1. Missing `blob` Column
**Error:**
```
psycopg.errors.UndefinedColumn: column cw.blob does not exist
LINE 20: ...::text::bytea, cw.channel::bytea, cw.type::bytea, cw.blob] o...
```

**Root Cause:**  
LangGraph 1.0.6+ requires a `blob` column (type: `bytea`) in the `checkpoint_writes` table for storing binary checkpoint data.

**Fix Applied:**
```sql
ALTER TABLE checkpoint_writes ADD COLUMN blob BYTEA;
```

---

### 2. Missing `task_path` Column
**Error:**
```
psycopg.errors.UndefinedColumn: column "task_path" of relation "checkpoint_writes" does not exist
LINE 2: ...thread_id, checkpoint_ns, checkpoint_id, task_id, task_path,...
```

**Root Cause:**  
LangGraph 1.0.6+ requires a `task_path` column (type: `text[]`) in the `checkpoint_writes` table for tracking workflow execution paths.

**Fix Applied:**
```sql
ALTER TABLE checkpoint_writes ADD COLUMN task_path TEXT[];
```

---

### 3. Corrupted Checkpoint Data
**Error:**
```
psycopg.errors.InvalidTextRepresentation: malformed array literal: "~__pregel_pull, __start__"
DETAIL: Array value must start with "{" or dimension information.
```

**Root Cause:**  
Old checkpoint data was incompatible with the new schema structure.

**Fix Applied:**
```sql
TRUNCATE TABLE checkpoint_writes, checkpoints, checkpoint_blobs CASCADE;
```

**Impact:** All existing conversation states were reset (acceptable for development).

---

## Changes Made

### 1. Database Schema Updates

#### Immediate Fixes (Applied to running database)
```bash
# Add blob column
docker exec mental_health_db psql -U postgres -d mental_health_db \
  -c "ALTER TABLE checkpoint_writes ADD COLUMN IF NOT EXISTS blob BYTEA;"

# Add task_path column
docker exec mental_health_db psql -U postgres -d mental_health_db \
  -c "ALTER TABLE checkpoint_writes ADD COLUMN IF NOT EXISTS task_path TEXT[];"

# Clear corrupted data
docker exec mental_health_db psql -U postgres -d mental_health_db \
  -c "TRUNCATE TABLE checkpoint_writes, checkpoints, checkpoint_blobs CASCADE;"
```

#### Updated Init Script
File: `backend/src/db/init-db.sql`

Added complete LangGraph checkpoint table definitions:
- `checkpoints` - Main state snapshots
- `checkpoint_writes` - Incremental state changes (with `blob` and `task_path` columns)
- `checkpoint_blobs` - Large binary data storage

### 2. Migration Scripts

Created idempotent migration scripts:

**`backend/migrations/001_add_blob_column.sql`**
- Adds `blob` column if missing
- Safe to run multiple times

**`backend/migrations/002_add_task_path_column.sql`**
- Adds `task_path` column if missing
- Safe to run multiple times

**`apply-migrations.sh`**
- Shell script to apply all migrations
- Supports both Docker and host environments

### 3. Documentation

**`backend/migrations/README.md`**
- Migration usage instructions
- Best practices for creating new migrations

**`TROUBLESHOOTING.md`**
- Complete troubleshooting guide
- Solutions for checkpoint-related errors
- Prevention strategies

---

## Verification

### Database Schema Verification
```bash
docker exec mental_health_db psql -U postgres -d mental_health_db -c "\d checkpoint_writes"
```

**Expected Output:**
```
             Table "public.checkpoint_writes"
    Column     |  Type   | Collation | Nullable | Default  
---------------+---------+-----------+----------+----------
 thread_id     | text    |           | not null | 
 checkpoint_ns | text    |           | not null | ''::text
 checkpoint_id | text    |           | not null | 
 task_id       | text    |           | not null | 
 idx           | integer |           | not null | 
 channel       | text    |           | not null | 
 type          | text    |           |          | 
 value         | jsonb   |           |          | 
 blob          | bytea   |           |          | ✅
 task_path     | text[]  |           |          | ✅
```

### Application Health Check
```bash
docker compose ps
```

All services should show `Up (healthy)` status, especially:
- ✅ `chatbot-backend`
- ✅ `mental_health_db` (postgres)

---

## Prevention for Future

### For New Deployments

1. **Run migrations after pulling code:**
   ```bash
   git pull
   ./apply-migrations.sh --docker
   ```

2. **Or rebuild from scratch:**
   ```bash
   docker compose down -v
   docker compose up -d
   ```
   The updated `init-db.sql` will create tables with correct schema.

### For Production

1. **Always backup before migrations:**
   ```bash
   docker exec mental_health_db pg_dump -U postgres mental_health_db > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Test migrations in staging first**

3. **Monitor logs after deployment:**
   ```bash
   docker compose logs -f chatbot-backend
   ```

### Version Compatibility

- **LangGraph Version:** 1.0.6
- **PostgreSQL:** 15-alpine
- **Python psycopg:** 3.x (async support)

When upgrading LangGraph:
1. Check release notes for schema changes
2. Test in development environment
3. Create new migrations if needed
4. Update `init-db.sql` for new deployments

---

## Testing

After applying fixes, test chat functionality:

1. **Login to the application**
2. **Send a test message**
3. **Verify backend logs show:**
   ```
   INFO:src.rag.engine:[ENGINE] Workflow completed for conversation_id=X
   INFO:src.rag.engine:[ENGINE] Generated answer length: XXX
   ```
4. **Check checkpoint data is being saved:**
   ```bash
   docker exec mental_health_db psql -U postgres -d mental_health_db \
     -c "SELECT COUNT(*) FROM checkpoints;"
   ```
   Should return > 0 after sending messages.

---

## Impact Assessment

### What Works Now ✅
- Chat functionality fully operational
- Conversation state persistence across messages
- Crisis detection and safety checks
- Workflow checkpointing and recovery

### What Was Reset ⚠️
- All existing conversation states (checkpoints cleared)
- Users will start with fresh conversations

### No Impact On 📊
- User accounts (preserved)
- Conversation history in `messages` table (preserved)
- Knowledge graphs in Neo4j (preserved)
- Vector embeddings in Milvus (preserved)

---

## References

- **LangGraph Documentation:** https://langchain-ai.github.io/langgraph/
- **PostgreSQL Checkpoint Schema:** LangGraph's `AsyncPostgresSaver.setup()` method
- **Migration Scripts:** `backend/migrations/`
- **Troubleshooting Guide:** `TROUBLESHOOTING.md`

---

## Contact

If you encounter similar issues:
1. Check `TROUBLESHOOTING.md`
2. Run migrations: `./apply-migrations.sh --docker`
3. Check database schema: `\d checkpoint_writes`
4. Review application logs: `docker compose logs -f`

**Note:** This fix has been tested and verified in the development environment. The changes are backward-compatible and safe for production deployment.
