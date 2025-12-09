# LOGOS AI Database Schema
# Railway PostgreSQL Setup

import asyncpg
import json
import os
from datetime import datetime, timedelta
import uuid

class LogosDatabase:
    def __init__(self):
        # Railway provides DATABASE_URL automatically
        self.db_url = os.getenv('DATABASE_URL')
        self.pool = None
    
    async def connect(self):
        """Initialize database connection pool"""
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=1,
            max_size=10,
            command_timeout=30
        )
        await self.create_tables()
    
    async def create_tables(self):
        """Create all required tables"""
        async with self.pool.acquire() as conn:
            # Callers table - main client profiles
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS callers (
                    phone_number VARCHAR(20) PRIMARY KEY,
                    display_name VARCHAR(100),
                    preferred_name VARCHAR(100),
                    master_prompt TEXT DEFAULT '',
                    ongoing_context TEXT DEFAULT '',
                    age INTEGER,
                    background_info TEXT DEFAULT '',
                    primary_concerns TEXT DEFAULT '',
                    communication_tone VARCHAR(50) DEFAULT 'supportive',
                    communication_style VARCHAR(50) DEFAULT 'conversational',
                    safety_flags TEXT DEFAULT '',
                    risk_level VARCHAR(20) DEFAULT 'low',
                    treatment_goals TEXT DEFAULT '',
                    hgo_notes TEXT DEFAULT '',
                    first_call_date TIMESTAMP DEFAULT NOW(),
                    last_call_date TIMESTAMP,
                    total_calls INTEGER DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Add new columns if they don't exist (for existing databases)
            try:
                await conn.execute('ALTER TABLE callers ADD COLUMN IF NOT EXISTS preferred_name VARCHAR(100)')
                await conn.execute('ALTER TABLE callers ADD COLUMN IF NOT EXISTS age INTEGER')
                await conn.execute('ALTER TABLE callers ADD COLUMN IF NOT EXISTS background_info TEXT DEFAULT \'\'')
                await conn.execute('ALTER TABLE callers ADD COLUMN IF NOT EXISTS primary_concerns TEXT DEFAULT \'\'')
                await conn.execute('ALTER TABLE callers ADD COLUMN IF NOT EXISTS communication_tone VARCHAR(50) DEFAULT \'supportive\'')
                await conn.execute('ALTER TABLE callers ADD COLUMN IF NOT EXISTS communication_style VARCHAR(50) DEFAULT \'conversational\'')
                await conn.execute('ALTER TABLE callers ADD COLUMN IF NOT EXISTS safety_flags TEXT DEFAULT \'\'')
                await conn.execute('ALTER TABLE callers ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20) DEFAULT \'low\'')
                await conn.execute('ALTER TABLE callers ADD COLUMN IF NOT EXISTS treatment_goals TEXT DEFAULT \'\'')
                await conn.execute('ALTER TABLE callers ADD COLUMN IF NOT EXISTS hgo_notes TEXT DEFAULT \'\'')
            except Exception as e:
                print(f"Note: Could not add new columns (may already exist): {e}")
            
            # Sessions table - individual call records
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    caller_phone VARCHAR(20) REFERENCES callers(phone_number),
                    twilio_call_sid VARCHAR(50) UNIQUE,
                    start_time TIMESTAMP DEFAULT NOW(),
                    end_time TIMESTAMP,
                    duration_seconds INTEGER,
                    full_transcript JSONB,
                    summary TEXT,
                    mood_detected VARCHAR(50),
                    key_topics TEXT[],
                    session_number INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Messages table - real-time conversation storage
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id UUID REFERENCES sessions(session_id),
                    timestamp TIMESTAMP DEFAULT NOW(),
                    speaker VARCHAR(10) CHECK (speaker IN ('user', 'ai')),
                    content TEXT NOT NULL,
                    deepgram_data JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Indexes for performance
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_caller ON sessions(caller_phone)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)')
            
            print("Database tables created successfully")

    async def get_or_create_caller(self, phone_number, call_sid):
        """Get caller profile or create new one. Returns caller data + loaded context."""
        async with self.pool.acquire() as conn:
            # Get or create caller
            caller = await conn.fetchrow('''
                INSERT INTO callers (phone_number, last_call_date, total_calls)
                VALUES ($1, NOW(), 1)
                ON CONFLICT (phone_number) 
                DO UPDATE SET 
                    last_call_date = NOW(),
                    total_calls = callers.total_calls + 1,
                    updated_at = NOW()
                RETURNING *
            ''', phone_number)
            
            # Create new session
            session = await conn.fetchrow('''
                INSERT INTO sessions (caller_phone, twilio_call_sid, session_number)
                VALUES ($1, $2, $3)
                RETURNING session_id, session_number
            ''', phone_number, call_sid, caller['total_calls'])
            
            # Load conversation context (last 20 sessions with full transcripts)
            recent_context = await self.load_conversation_context(phone_number)
            
            return {
                'caller': dict(caller),
                'session_id': session['session_id'],
                'session_number': session['session_number'],
                'context': recent_context
            }
    
    async def load_conversation_context(self, phone_number):
        """Load conversation context for VA memory"""
        async with self.pool.acquire() as conn:
            # Get last 20 sessions with full transcripts
            recent_sessions = await conn.fetch('''
                SELECT session_id, start_time, full_transcript, summary, key_topics, session_number
                FROM sessions 
                WHERE caller_phone = $1 AND end_time IS NOT NULL
                ORDER BY start_time DESC 
                LIMIT 20
            ''', phone_number)
            
            # Get older session summaries (21+)
            older_summaries = await conn.fetch('''
                SELECT start_time, summary, key_topics, session_number
                FROM sessions 
                WHERE caller_phone = $1 AND end_time IS NOT NULL
                ORDER BY start_time DESC 
                OFFSET 20 LIMIT 50
            ''', phone_number)
            
            return {
                'recent_sessions': [dict(row) for row in recent_sessions],
                'older_summaries': [dict(row) for row in older_summaries]
            }
    
    async def add_message(self, session_id, speaker, content, deepgram_data=None):
        """Add message during conversation (non-blocking)"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO messages (session_id, speaker, content, deepgram_data)
                VALUES ($1, $2, $3, $4)
            ''', session_id, speaker, content, json.dumps(deepgram_data) if deepgram_data else None)
    
    async def end_session(self, session_id, summary=None, key_topics=None, mood=None):
        """End session and update with summary"""
        async with self.pool.acquire() as conn:
            # Get all messages for full transcript
            messages = await conn.fetch('''
                SELECT speaker, content, timestamp 
                FROM messages 
                WHERE session_id = $1 
                ORDER BY timestamp
            ''', session_id)
            
            full_transcript = [
                {
                    'speaker': msg['speaker'],
                    'content': msg['content'],
                    'timestamp': msg['timestamp'].isoformat()
                }
                for msg in messages
            ]
            
            # Calculate duration
            start_time = await conn.fetchval('SELECT start_time FROM sessions WHERE session_id = $1', session_id)
            duration = int((datetime.now() - start_time).total_seconds())
            
            # Update session
            await conn.execute('''
                UPDATE sessions SET 
                    end_time = NOW(),
                    duration_seconds = $2,
                    full_transcript = $3,
                    summary = $4,
                    key_topics = $5,
                    mood_detected = $6
                WHERE session_id = $1
            ''', session_id, duration, json.dumps(full_transcript), summary, key_topics, mood)
            
            # Archive disabled - keep ALL transcripts for HGO access
            # await self.archive_old_transcripts(session_id)
    
    async def archive_old_transcripts(self, current_session_id):
        """Convert old full transcripts to summaries only"""
        async with self.pool.acquire() as conn:
            # Get caller phone from current session
            caller_phone = await conn.fetchval('''
                SELECT caller_phone FROM sessions WHERE session_id = $1
            ''', current_session_id)
            
            # Clear full_transcript for sessions beyond the 20 most recent
            await conn.execute('''
                UPDATE sessions 
                SET full_transcript = NULL 
                WHERE caller_phone = $1 
                AND session_id NOT IN (
                    SELECT session_id FROM sessions 
                    WHERE caller_phone = $1 AND end_time IS NOT NULL
                    ORDER BY start_time DESC 
                    LIMIT 20
                )
            ''', caller_phone)
    
    async def update_caller_context(self, phone_number, new_context_item):
        """Add to ongoing context based on conversation"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE callers 
                SET ongoing_context = COALESCE(ongoing_context, '') || $2 || E'\n',
                    updated_at = NOW()
                WHERE phone_number = $1
            ''', phone_number, new_context_item)
    async def update_master_prompt(self, phone_number, master_prompt):
        """Update master prompt (HGO dashboard will use this)"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE callers 
                SET master_prompt = $2,
                    updated_at = NOW()
                WHERE phone_number = $1
            ''', phone_number, master_prompt)

    async def get_caller_history(self, phone_number):
        """Get all caller data for HGO dashboard"""
        async with self.pool.acquire() as conn:
            caller = await conn.fetchrow(
                'SELECT * FROM callers WHERE phone_number = $1',
                phone_number
            )
            
            if not caller:
                return None
            
            # Get all sessions with available data
            sessions = await conn.fetch('''
                SELECT s.*, 
                       CASE 
                           WHEN s.full_transcript IS NOT NULL THEN 'full'
                           ELSE 'summary'
                       END as transcript_type
                FROM sessions s
                WHERE s.caller_phone = $1 
                ORDER BY s.start_time DESC
            ''', phone_number)
            
            return {
                'caller': dict(caller),
                'sessions': [dict(session) for session in sessions]
            }

    async def get_sessions_by_phone(self, phone_number):
        """
        Used by /cleanup?action=list_sessions&phone=...
        Returns basic info for all sessions for a given phone.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                '''
                SELECT 
                    session_id,
                    caller_phone,
                    created_at,
                    session_number
                FROM sessions
                WHERE caller_phone = $1
                ORDER BY created_at DESC
                ''',
                phone_number
            )
        
        return rows


# Integration helper functions
def format_context_for_va(context_data, caller_data):
    """Format loaded context for VA system prompt"""
    master_prompt = caller_data['master_prompt'] or ""
    ongoing_context = caller_data['ongoing_context'] or ""
    
    context_prompt = f"""
{master_prompt}

Background: {ongoing_context}

Recent conversations:"""
    
    # Add recent session summaries
    for session in context_data['recent_sessions'][:5]:  # Last 5 sessions
        if session['summary']:
            context_prompt += f"\n- Session {session['session_number']}: {session['summary']}"
    
    # Add older context if available
    if context_data['older_summaries']:
        context_prompt += f"\n\nEarlier topics discussed: "
        topics = []
        for summary in context_data['older_summaries'][:3]:
            if summary['key_topics']:
                topics.extend(summary['key_topics'])
        context_prompt += ", ".join(list(set(topics))[:10])  # Unique topics, max 10
    
    return context_prompt.strip()
