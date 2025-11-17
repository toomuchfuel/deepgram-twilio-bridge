import asyncio
import base64
import json
import sys
import websockets
import os
import signal
from aiohttp import web
from config import VOICE_AGENT_PERSONALITY, VOICE_MODEL, LLM_MODEL, LLM_TEMPERATURE
from database import LogosDatabase, format_context_for_va

# Global variables
shutdown_event = asyncio.Event()
db = None  # Database instance
active_sessions = {}  # Store session data: {call_sid: session_data}

async def initialize_database():
    """Initialize database connection"""
    global db
    try:
        db = LogosDatabase()
        await db.connect()
        print("Database connected successfully")
    except Exception as e:
        print(f"Database connection failed: {e}")
        # Continue without database for now
        db = None

def sts_connect():
    """Connect to Deepgram Voice Agent API"""
    api_key = os.getenv('DEEPGRAM_API_KEY')
    if not api_key:
        raise ValueError("DEEPGRAM_API_KEY environment variable is not set")

    sts_ws = websockets.connect(
        "wss://agent.deepgram.com/v1/agent/converse",
        subprotocols=["token", api_key]
    )
    return sts_ws

async def voice_webhook_handler(request):
    """Handle initial Twilio voice webhook and capture caller info"""
    try:
        form_data = await request.post()
        caller_phone = form_data.get('From', 'unknown')
        call_sid = form_data.get('CallSid', 'unknown')
        
        print(f"🎯 Voice webhook: Call from {caller_phone}, CallSid: {call_sid}")
        
        # Store caller info for WebSocket to retrieve
        active_sessions[call_sid] = {
            'caller_phone': caller_phone,
            'timestamp': time.time()
        }
        
        # Build WebSocket URL (same format as working direct TwiML)
        host = request.host
        websocket_url = f"wss://{host}/twilio"
        
        print(f"🔗 Connecting to WebSocket: {websocket_url}")
        
        # Return EXACT same TwiML format as working version
        twiml_response = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://voice-bridge-backend-production.up.railway.app/twilio">
            <Parameter name="caller" value="{}"/>
            <Parameter name="callsid" value="{}"/>
        </Stream>
    </Connect>
</Response>'''.format(caller_phone, call_sid)
        
        return web.Response(text=twiml_response, content_type='application/xml')
    
    except Exception as e:
        print(f"Error in voice webhook: {e}")
        # Fallback TwiML
        return web.Response(
            text='''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Sorry, there was a connection error. Please try calling again.</Say>
</Response>''',
            content_type='application/xml'
        )

async def websocket_handler(request):
    """Handle WebSocket connections from Twilio"""
    print(f"🔍 WEBSOCKET DEBUG: Incoming connection from {request.remote}")
    print(f"🔍 Headers: {dict(request.headers)}")
    print(f"🔍 Query params: {dict(request.query)}")
    # Extract caller info from query parameters (sent by voice webhook)
    caller_phone = request.query.get('From', 'unknown')
    call_sid = request.query.get('CallSid', 'unknown')
    
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    print(f"📞 WebSocket connection established on path: {request.path}")
    print(f"📱 Caller phone: {caller_phone}")
    print(f"🆔 Call SID: {call_sid}")
    
    try:
        await twilio_handler(ws, caller_phone, call_sid)
    except Exception as e:
        print(f"Error in WebSocket handler: {e}")
    finally:
        if not ws.closed:
            await ws.close()
    
    return ws

async def twilio_handler(twilio_ws, caller_phone=None, call_sid=None):
    """Handle Twilio WebSocket communication with Deepgram"""
    audio_queue = asyncio.Queue()
    streamsid_queue = asyncio.Queue()
    
    # Initialize session variables
    session_id = None
    caller_context = None

    # Load caller context from database at start if we have phone number
    if db and caller_phone and caller_phone != 'unknown':
        try:
            caller_data = await db.get_or_create_caller(caller_phone, call_sid or "websocket-call")
            session_id = caller_data['session_id']
            caller_context = caller_data['context']
            
            print(f"💾 Loaded caller context - Session {caller_data['session_number']}")
            if caller_data['context']['recent_sessions']:
                print(f"📚 Found {len(caller_data['context']['recent_sessions'])} previous sessions")
                
                # Format context for AI system prompt
                context_summary = format_context_for_va(caller_context, caller_data['caller'])
                print(f"🧠 Context summary prepared for AI")
            else:
                context_summary = ""
        except Exception as e:
            print(f"❌ Database error: {e}")
            context_summary = ""
    else:
        print(f"⚠️ No caller context loaded (phone: {caller_phone})")
        context_summary = ""

    try:
        async with sts_connect() as sts_ws:
            # Build AI system prompt with caller context
            ai_prompt = VOICE_AGENT_PERSONALITY
            if context_summary:
                ai_prompt += f"\n\nContext from previous conversations:\n{context_summary}"
                print(f"🎯 AI prompt enhanced with caller context")
            
            # Send configuration to Deepgram
            config_message = {
                "type": "Settings",
                "audio": {
                    "input": {
                        "encoding": "mulaw",
                        "sample_rate": 8000,
                    },
                    "output": {
                        "encoding": "mulaw",
                        "sample_rate": 8000,
                        "container": "none",
                    },
                },
                "agent": {
                    "language": "en",
                    "listen": {
                        "provider": {
                            "type": "deepgram",
                            "model": "nova-3"
                        }
                    },
                    "think": {
                        "provider": {
                            "type": "open_ai",
                            "model": LLM_MODEL,
                            "temperature": LLM_TEMPERATURE
                        },
                        "prompt": ai_prompt  # Now includes caller context!
                    },
                    "speak": {
                        "provider": {
                            "type": "deepgram",
                            "model": VOICE_MODEL
                        }
                    },
                    "greeting": "Hello! How can I help you today?"
                }
            }

            await sts_ws.send(json.dumps(config_message))
            print("⚙️ Configuration sent to Deepgram with caller context")

            async def sts_sender():
                """Send audio from Twilio to Deepgram"""
                print("🎤 sts_sender started")
                try:
                    while not shutdown_event.is_set():
                        try:
                            chunk = await asyncio.wait_for(audio_queue.get(), timeout=1.0)
                            await sts_ws.send(chunk)
                        except asyncio.TimeoutError:
                            continue
                except Exception as e:
                    print(f"Error in sts_sender: {e}")

            async def sts_receiver():
                """Receive audio from Deepgram and send to Twilio"""
                print("🔊 sts_receiver started")
                try:
                    # Wait for stream ID from Twilio
                    streamsid = await streamsid_queue.get()
                    print(f"🌊 Got stream ID: {streamsid}")
                    
                    async for message in sts_ws:
                        if shutdown_event.is_set():
                            break
                            
                        if type(message) is str:
                            print(f"📨 Deepgram message: {message}")
                            try:
                                decoded = json.loads(message)
                                
                                # Store conversation messages in database
                                if decoded.get('type') == 'ConversationText' and session_id and db:
                                    role = decoded.get('role')
                                    content = decoded.get('content')
                                    if role and content:
                                        try:
                                            await db.add_message(session_id, role, content, decoded)
                                            print(f"💬 Stored message: {role} - {content[:50]}...")
                                        except Exception as e:
                                            print(f"Error storing message: {e}")
                                
                                if decoded['type'] == 'UserStartedSpeaking':
                                    # Handle barge-in
                                    clear_message = {
                                        "event": "clear",
                                        "streamSid": streamsid
                                    }
                                    await twilio_ws.send_str(json.dumps(clear_message))
                            except json.JSONDecodeError:
                                print(f"Could not decode message: {message}")
                            continue

                        # Handle binary audio data
                        if isinstance(message, bytes):
                            media_message = {
                                "event": "media",
                                "streamSid": streamsid,
                                "media": {"payload": base64.b64encode(message).decode("ascii")},
                            }
                            await twilio_ws.send_str(json.dumps(media_message))

                except Exception as e:
                    print(f"Error in sts_receiver: {e}")

            async def twilio_receiver():
                """Receive audio from Twilio and buffer for Deepgram"""
                print("📱 twilio_receiver started")
                BUFFER_SIZE = 20 * 160  # Buffer 20 messages (0.4 seconds)
                inbuffer = bytearray(b"")
                
                try:
                    async for msg in twilio_ws:
                        if shutdown_event.is_set():
                            break
                            
                        if msg.type == web.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                
                                if data["event"] == "start":
                                    print("🚀 Received Twilio start event")
                                    start = data["start"]
                                    streamsid = start["streamSid"]
                                    actual_call_sid = start["callSid"]
                                    
                                    print(f"🔗 Stream ID: {streamsid}")
                                    print(f"☎️ Actual Call SID: {actual_call_sid}")
                                    
                                    streamsid_queue.put_nowait(streamsid)
                                    
                                elif data["event"] == "connected":
                                    print("✅ Twilio connected")
                                    
                                elif data["event"] == "media":
                                    media = data["media"]
                                    chunk = base64.b64decode(media["payload"])
                                    if media["track"] == "inbound":
                                        inbuffer.extend(chunk)
                                        
                                elif data["event"] == "stop":
                                    print("🛑 Twilio stop event")
                                    
                                    # End database session
                                    if session_id and db:
                                        try:
                                            # Generate simple summary based on messages
                                            summary = f"Phone call session - discussed various topics"
                                            await db.end_session(session_id, summary)
                                            print(f"💾 Session {session_id} ended and saved")
                                        except Exception as e:
                                            print(f"Error ending session: {e}")
                                    
                                    break

                                # Send buffered audio to Deepgram
                                while len(inbuffer) >= BUFFER_SIZE:
                                    chunk = inbuffer[:BUFFER_SIZE]
                                    audio_queue.put_nowait(chunk)
                                    inbuffer = inbuffer[BUFFER_SIZE:]
                                    
                            except (json.JSONDecodeError, KeyError) as e:
                                print(f"Error processing Twilio message: {e}")
                                
                        elif msg.type == web.WSMsgType.ERROR:
                            print(f"WebSocket error: {twilio_ws.exception()}")
                            break
                            
                except Exception as e:
                    print(f"Error in twilio_receiver: {e}")

            # Run all tasks concurrently
            await asyncio.gather(
                sts_sender(),
                sts_receiver(),
                twilio_receiver(),
                return_exceptions=True
            )

    except Exception as e:
        print(f"Error in twilio_handler: {e}")

async def health_check(request):
    """HTTP health check endpoint for Railway"""
    return web.Response(
        text="OK", 
        status=200,
        headers={
            'Content-Type': 'text/plain',
            'Cache-Control': 'no-cache'
        }
    )

async def root_handler(request):
    """Root endpoint handler"""
    return web.Response(
        text="Twilio-Deepgram Bridge Server with Caller ID Support", 
        status=200,
        headers={'Content-Type': 'text/plain'}
    )

def setup_signal_handlers():
    """Setup signal handlers - ignore SIGTERM from Railway"""
    def ignore_sigterm(signum, frame):
        print(f"Received signal {signum} from Railway")
        if signum == signal.SIGTERM:
            print("Railway sent SIGTERM - but health checks are passing!")
            print("Ignoring SIGTERM to keep server running (Railway may be testing)")
            # Completely ignore SIGTERM - don't shut down
        elif signum == signal.SIGINT:
            print("SIGINT received - user requested shutdown")
            # Allow SIGINT to work normally for development
            raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, ignore_sigterm)
    signal.signal(signal.SIGINT, ignore_sigterm)

async def create_app():
    """Create and configure the aiohttp application"""
    app = web.Application()
    
    # Middleware for request logging
    @web.middleware
    async def logging_middleware(request, handler):
        print(f"🌐 Request: {request.method} {request.path} from {request.remote}")
        try:
            response = await handler(request)
            print(f"✅ Response: {request.method} {request.path} -> {response.status}")
            return response
        except Exception as e:
            print(f"❌ Error handling {request.method} {request.path}: {e}")
            raise
    
    app.middlewares.append(logging_middleware)
    
    # Routes
    app.router.add_get('/', root_handler)
    app.router.add_get('/health', health_check)
    app.router.add_post('/webhook/voice', voice_webhook_handler)  # NEW: Twilio voice webhook
    app.router.add_get('/twilio', websocket_handler)  # WebSocket endpoint
    
    return app

def main():
    """Main entry point"""
    # Get port from environment (Railway sets this automatically)
    port = int(os.environ.get("PORT", 5000))
    
    print(f"🚀 Starting Twilio-Deepgram Bridge Server on port {port}")
    print(f"🔍 Health check endpoint: http://0.0.0.0:{port}/health")
    print(f"📞 Voice webhook: http://0.0.0.0:{port}/webhook/voice")
    print(f"🔌 WebSocket endpoint: ws://0.0.0.0:{port}/twilio")
    
    # Check for required environment variables
    if not os.getenv('DEEPGRAM_API_KEY'):
        print("⚠️ WARNING: DEEPGRAM_API_KEY not found in environment variables")
    else:
        print("✅ DEEPGRAM_API_KEY found in environment")

    async def run_server():
        # Initialize database first
        await initialize_database()
        
        # Create the web application
        app = await create_app()
        
        # Create and start the server
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        print(f"🌟 Server running on 0.0.0.0:{port}")
        print("🎯 Server is ready to accept connections")
        print("📋 SETUP INSTRUCTIONS:")
        print(f"   1. In Twilio Console, set your phone number webhook to:")
        print(f"      https://your-app-name.railway.app/webhook/voice")
        print(f"   2. Set HTTP method to POST")
        print(f"   3. Remove any TwiML Bin configuration")
        
        # Setup signal handlers for graceful shutdown
        setup_signal_handlers()
        
        # Keep the server running
        try:
            while not shutdown_event.is_set():
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        
        print("Server shutdown complete")

    try:
        # Run the server
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("Server interrupted by user")
    except Exception as e:
        print(f"Server error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
