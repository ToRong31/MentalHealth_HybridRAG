-- Migration: Add task_path column to checkpoint_writes table
-- Date: 2026-01-14
-- Reason: LangGraph 1.0.6+ requires task_path column in checkpoint_writes table
-- This migration is idempotent and safe to run multiple times

-- Add task_path column to checkpoint_writes if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'checkpoint_writes'
        AND column_name = 'task_path'
    ) THEN
        ALTER TABLE checkpoint_writes ADD COLUMN task_path TEXT[];
        RAISE NOTICE 'Added task_path column to checkpoint_writes table';
    ELSE
        RAISE NOTICE 'task_path column already exists in checkpoint_writes table';
    END IF;
END $$;

-- Verify the column was added
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'checkpoint_writes'
        AND column_name = 'task_path'
    ) THEN
        RAISE NOTICE 'Migration completed successfully: checkpoint_writes.task_path column verified';
    ELSE
        RAISE EXCEPTION 'Migration failed: checkpoint_writes.task_path column not found';
    END IF;
END $$;
