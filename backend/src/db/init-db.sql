-- Initialize mental_health_db database
-- This script runs automatically when postgres container first starts.

-- Create conversation_memories table
CREATE TABLE IF NOT EXISTS conversation_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL UNIQUE,
    user_id UUID NOT NULL,
    buffer JSONB NOT NULL DEFAULT '[]',
    summary TEXT,
    slots JSONB NOT NULL DEFAULT '{}',
    crisis_state JSONB NOT NULL DEFAULT '{"is_high_risk": false, "crisis_level": "none"}',
    language VARCHAR(5) NOT NULL DEFAULT 'vi',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_conv_memories_conv_id ON conversation_memories(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conv_memories_user_id ON conversation_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_memories_active ON conversation_memories(is_active) WHERE is_active = TRUE;

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_conv_memories_updated_at ON conversation_memories;
CREATE TRIGGER update_conv_memories_updated_at
    BEFORE UPDATE ON conversation_memories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Crisis logs table (for audit)
CREATE TABLE IF NOT EXISTS crisis_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL,
    user_id UUID NOT NULL,
    crisis_level VARCHAR(20) NOT NULL,
    indicators JSONB NOT NULL DEFAULT '[]',
    response_provided TEXT,
    escalation_done BOOLEAN NOT NULL DEFAULT FALSE,
    hotline_provided BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crisis_logs_conv_id ON crisis_logs(conversation_id);
CREATE INDEX IF NOT EXISTS idx_crisis_logs_user_id ON crisis_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_crisis_logs_level ON crisis_logs(crisis_level);
CREATE INDEX IF NOT EXISTS idx_crisis_logs_created ON crisis_logs(created_at DESC);

-- Users table (simple auth)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title VARCHAR(255),
    language VARCHAR(5) NOT NULL DEFAULT 'vi',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_active ON conversations(is_active) WHERE is_active = TRUE;
