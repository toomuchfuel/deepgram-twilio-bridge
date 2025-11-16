# Voice Agent Configuration for LOGOS AI

# Simple, natural personality - NO over-prompting
VOICE_AGENT_PERSONALITY = """You are having a casual chat with someone who called you. 
Be naturally curious about what they share. 
Ask simple follow-up questions like a friend would. 
Keep it conversational and relaxed."""

# Voice settings
VOICE_MODEL = "aura-2-theia-en"  # Australian accent
VOICE_TEMPERATURE = 0.7

# LLM settings  
LLM_MODEL = "gpt-4o-mini"
LLM_TEMPERATURE = 0.7

# Conversation timing settings (in milliseconds)
ENDPOINTING_MS = 1500  # Wait 1.5 seconds of silence before responding
UTTERANCE_END_MS = 2000  # Backup timeout of 2 seconds
INTERIM_RESULTS = True  # Show partial transcripts
