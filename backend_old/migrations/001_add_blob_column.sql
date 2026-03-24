-- Migration: Add blob column to checkpoint_writes table
-- Date: 2026-01-14
-- Reason: LangGraph 1.0.6+ requires blob column in checkpoint_writes table
-- This migration is idempotent and safe to run multiple times

-- Add blob column to checkpoint_writes if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'checkpoint_writes'
        AND column_name = 'blob'
    ) THEN
        ALTER TABLE checkpoint_writes ADD COLUMN blob BYTEA;
        RAISE NOTICE 'Added blob column to checkpoint_writes table';
    ELSE
        RAISE NOTICE 'blob column already exists in checkpoint_writes table';
    END IF;
END $$;

-- Verify the column was added
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'checkpoint_writes'
        AND column_name = 'blob'
    ) THEN
        RAISE NOTICE 'Migration completed successfully: checkpoint_writes.blob column verified';
    ELSE
        RAISE EXCEPTION 'Migration failed: checkpoint_writes.blob column not found';
    END IF;
END $$;
