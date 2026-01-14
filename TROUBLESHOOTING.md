# Troubleshooting Guide

Common issues and their solutions for the Mental Health Chatbot.

## Table of Contents

- [Database Errors](#database-errors)
- [Docker Issues](#docker-issues)
- [Chat Functionality Issues](#chat-functionality-issues)
- [LangGraph Checkpoint Errors](#langgraph-checkpoint-errors)

---

## Database Errors

### Error: `column cw.blob does not exist` or `column "task_path" does not exist`

**Symptom:**
```
psycopg.errors.UndefinedColumn: column cw.blob does not exist
LINE 20: ...::text::bytea, cw.channel::bytea, cw.type::bytea, cw.blob] o...
```
or
```
psycopg.errors.UndefinedColumn: column "task_path" of relation "checkpoint_writes" does not exist
LINE 2: ...thread_id, checkpoint_ns, checkpoint_id, task_id, task_path,...
```

**Cause:**
LangGraph 1.0.6+ requires additional columns (`blob` and `task_path`) in the `checkpoint_writes` table. These columns were missing in older database schemas.

**Solution:**

1. **Quick Fix (Immediate) - Add both missing columns:**
   ```bash
   docker exec mental_health_db psql -U postgres -d mental_health_db -c "ALTER TABLE checkpoint_writes ADD COLUMN IF NOT EXISTS blob BYTEA;"
   docker exec mental_health_db psql -U postgres -d mental_health_db -c "ALTER TABLE checkpoint_writes ADD COLUMN IF NOT EXISTS task_path TEXT[];"
   ```

2. **Permanent Fix (For new deployments):**
   Apply all migrations:
   ```bash
   ./apply-migrations.sh --docker
   ```

3. **Verify the fix:**
   ```bash
   docker exec mental_health_db psql -U postgres -d mental_health_db -c "\d checkpoint_writes"
   ```
   
   You should see both `blob` (bytea) and `task_path` (text[]) columns in the output.

**Prevention:**
- The migration scripts have been updated in `backend/src/db/init-db.sql` to include both columns
- Always run migrations after pulling new code: `./apply-migrations.sh --docker`
- When upgrading LangGraph version, check release notes for schema changes

---

## Docker Issues

### Container fails to start

**Symptom:**
Container exits immediately after starting.

**Diagnosis:**
```bash
docker logs chatbot-backend --tail 100
docker logs mental_health_db --tail 100
```

**Common Causes:**

1. **Port already in use:**
   ```bash
   # Check which process is using the port
   sudo lsof -i :8000
   sudo lsof -i :5432
   
   # Kill the process or change the port in docker-compose.yml
   ```

2. **Database connection failed:**
   - Check if PostgreSQL container is running: `docker ps | grep mental_health_db`
   - Check database logs: `docker logs mental_health_db`
   - Verify environment variables in `.env` file

3. **Missing dependencies:**
   ```bash
   # Rebuild the image
   docker-compose build --no-cache chatbot-backend
   docker-compose up -d
   ```

---

## Chat Functionality Issues

### Chat endpoint returns 500 error

**Diagnosis:**
```bash
# Check backend logs
docker logs chatbot-backend --tail 50 -f

# Check database connection
docker exec mental_health_db psql -U postgres -d mental_health_db -c "SELECT 1;"
```

**Common Causes:**

1. **Graph not initialized:**
   - Wait for backend to fully start (check logs for "✓ APPLICATION READY")
   - Restart backend: `docker-compose restart chatbot-backend`

2. **Database connection lost:**
   ```bash
   # Restart database
   docker-compose restart postgres
   
   # Check database health
   docker exec mental_health_db pg_isready -U postgres
   ```

3. **LLM API key issues:**
   - Check `.env` file for valid API keys (OPENAI_API_KEY, GEMINI_API_KEY)
   - Verify API key permissions and quota

### Chat response is empty or generic

**Possible Causes:**

1. **RAG retrieval failed:**
   - Check Milvus connection: `docker ps | grep milvus`
   - Check Neo4j connection: `docker ps | grep neo4j`
   - Check backend logs for retrieval errors

2. **LLM API rate limit:**
   - Check API usage in provider dashboard
   - Wait and retry after rate limit resets

---

## LangGraph Checkpoint Errors

### Error: `checkpointer not initialized`

**Symptom:**
```
RuntimeError: Checkpointer initialization failed
```

**Solution:**

1. **Check database connectivity:**
   ```bash
   docker exec mental_health_db pg_isready -U postgres
   ```

2. **Verify checkpoint tables exist:**
   ```bash
   docker exec mental_health_db psql -U postgres -d mental_health_db -c "\dt"
   ```
   
   Should show: `checkpoints`, `checkpoint_writes`, `checkpoint_blobs`

3. **If tables are missing, run migrations:**
   ```bash
   ./apply-migrations.sh --docker
   ```

4. **Restart backend:**
   ```bash
   docker-compose restart chatbot-backend
   ```

### Error: `thread_id not found` or state lost

**Symptom:**
Conversation context is lost between messages.

**Diagnosis:**
```bash
# Check if checkpoints are being saved
docker exec mental_health_db psql -U postgres -d mental_health_db -c "SELECT COUNT(*) FROM checkpoints;"
```

**Solution:**

1. **Verify conversation_id is being passed correctly:**
   - Check frontend is sending the same `conversation_id` for all messages in a conversation
   - Check backend logs for `thread_id=conversation_X` entries

2. **Check checkpoint permissions:**
   ```bash
   docker exec mental_health_db psql -U postgres -d mental_health_db -c "SELECT * FROM checkpoints LIMIT 5;"
   ```

3. **Clear corrupted checkpoints (if needed):**
   ```bash
   # WARNING: This will reset all conversation states
   docker exec mental_health_db psql -U postgres -d mental_health_db -c "TRUNCATE TABLE checkpoints CASCADE;"
   ```

---

## General Debugging Tips

### Enable detailed logging

1. **Backend logging:**
   Edit `backend/main.py`:
   ```python
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Database query logging:**
   Edit `backend/src/db/session.py`:
   ```python
   engine = create_async_engine(
       settings.DATABASE_URL,
       echo=True,  # Set to True for SQL query logging
   )
   ```

3. **Restart to apply changes:**
   ```bash
   docker-compose restart chatbot-backend
   ```

### View all container logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f chatbot-backend
docker-compose logs -f postgres
docker-compose logs -f neo4j
```

### Check service health

```bash
# All containers
docker-compose ps

# Health checks
docker exec chatbot-backend curl -f http://localhost:8000/health
docker exec mental_health_db pg_isready -U postgres
docker exec neo4j cypher-shell -u neo4j -p kguser2005 "RETURN 1"
```

### Reset everything (nuclear option)

```bash
# WARNING: This will delete all data
docker-compose down -v
docker-compose up -d
```

---

## Getting Help

If you encounter an issue not covered here:

1. **Check logs:**
   ```bash
   docker-compose logs -f > debug.log
   ```

2. **Gather system info:**
   ```bash
   docker-compose version
   docker version
   docker-compose ps
   docker-compose config
   ```

3. **Create an issue with:**
   - Error message and full stack trace
   - Steps to reproduce
   - System info and logs
   - What you've already tried

---

## Prevention Best Practices

1. **Always run migrations after pulling new code:**
   ```bash
   git pull
   ./apply-migrations.sh --docker
   docker-compose restart
   ```

2. **Keep database backups:**
   ```bash
   docker exec mental_health_db pg_dump -U postgres mental_health_db > backup.sql
   ```

3. **Monitor container health:**
   ```bash
   docker-compose ps
   # All services should show "Up" and "healthy"
   ```

4. **Review logs regularly:**
   ```bash
   docker-compose logs --tail=100
   ```

5. **Keep dependencies updated:**
   ```bash
   # Update Python packages
   pip install --upgrade -r backend/requirements.txt
   
   # Rebuild containers
   docker-compose build --no-cache
   ```
