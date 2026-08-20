-- Migration: Add published_at column to analysis_results table
-- This column stores the timestamp when an article was published

-- Add the column
ALTER TABLE analysis_results ADD COLUMN published_at TIMESTAMP;

-- Verify the column was added
PRAGMA table_info(analysis_results);
