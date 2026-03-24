# Database Migrations

This directory contains SQL migration files for the Mental Health Chatbot database schema updates.

## Migration Files

Migration files are numbered sequentially and should be applied in order:

- `001_add_blob_column.sql` - Adds `blob` column to `checkpoint_writes` table for LangGraph 1.0.6+ compatibility
- `002_add_task_path_column.sql` - Adds `task_path` column to `checkpoint_writes` table for LangGraph 1.0.6+ compatibility

## How to Apply Migrations

### Method 1: Using the migration script (Recommended)

For Docker environment:
```bash
./apply-migrations.sh --docker
```

For host environment:
```bash
./apply-migrations.sh
```

### Method 2: Manual application

```bash
# Using docker exec
docker exec mental_health_db psql -U postgres -d mental_health_db < backend/migrations/001_add_blob_column.sql

# Or using psql directly (if PostgreSQL is on host)
psql -U postgres -d mental_health_db -f backend/migrations/001_add_blob_column.sql
```

## Creating New Migrations

1. Create a new SQL file with the next sequential number:
   - Format: `XXX_description.sql`
   - Example: `002_add_user_preferences.sql`

2. Make the migration idempotent (safe to run multiple times):
   ```sql
   -- Check if change is needed before applying
   DO $$
   BEGIN
       IF NOT EXISTS (...) THEN
           -- Apply change
           RAISE NOTICE 'Applied migration';
       ELSE
           RAISE NOTICE 'Already applied';
       END IF;
   END $$;
   ```

3. Test the migration:
   ```bash
   ./apply-migrations.sh --docker
   ```

## Notes

- All migrations are idempotent (safe to run multiple times)
- Migrations are applied in alphabetical order (hence the numbering)
- Each migration should be atomic (all-or-nothing)
- Always test migrations on development environment first

## Troubleshooting

### Migration Failed

If a migration fails:

1. Check the error message
2. Fix the SQL in the migration file
3. Re-run the migration script
4. If needed, manually rollback changes before re-applying

### Check Applied Migrations

```bash
docker exec mental_health_db psql -U postgres -d mental_health_db -c "\d checkpoint_writes"
```

## LangGraph Checkpoint Schema

The checkpoint tables are automatically created by LangGraph's `setup()` method, but we maintain explicit migrations to:

1. Ensure schema consistency across environments
2. Add missing columns for newer LangGraph versions
3. Document schema changes

Current checkpoint tables:
- `checkpoints` - Main workflow state snapshots
- `checkpoint_writes` - Incremental state changes
- `checkpoint_blobs` - Large binary data storage
