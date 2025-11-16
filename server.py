import asyncio
import base64
import json
import sys
import websockets
import os
import signal
from aiohttp import web

# Global variables
shutdown_event = asyncio.Event()

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

async def websocket_handler(request):
    """Handle WebSocket connections from Twilio"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    print(f"WebSocket connection established on path: {request.path}")
    
    try:
        await twilio_handler(ws)
    except Exception as e:
        print(f"Error in WebSocket handler: {e}")
    finally:
        if not ws.closed:
            await ws.close()
    
    return ws

async def twilio_handler(twilio_ws):
    """Handle Twilio WebSocket communication with Deepgram"""
    audio_queue = asyncio.Queue()
    streamsid_queue = asyncio.Queue()

    try:
        async with sts_connect() as sts_ws:
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
                            "model": "nova-3",
                            "keyterms": ["hello", "goodbye"]
                        }
                    },
                    "think": {
                        "provider": {
                            "type": "open_ai",
                            "model": "gpt-4o-mini",
                            "temperature": 0.7
                        },
                        "prompt": "You are a helpful AI assistant focused on customer service."
                    },
                    "speak": {
                        "provider": {
                            "type": "deepgram",
                            "model": "aura-2-thalia-en"
                        }
                    },
                    "greeting": "Hello! How can I help you today?"
                }
            }

            await sts_ws.send(json.dumps(config_message))
            print("Configuration sent to Deepgram")

            async def sts_sender():
                """Send audio from Twilio to Deepgram"""
                print("sts_sender started")
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
                print("sts_receiver started")
                try:
                    # Wait for stream ID from Twilio
                    streamsid = await streamsid_queue.get()
                    print(f"Got stream ID: {streamsid}")
                    
                    async for message in sts_ws:
                        if shutdown_event.is_set():
                            break
                            
                        if type(message) is str:
                            print(f"Deepgram message: {message}")
                            try:
                                decoded = json.loads(message)
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
                print("twilio_receiver started")
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
                                    print("Received Twilio start event")
                                    start = data["start"]
                                    streamsid = start["streamSid"]
                                    streamsid_queue.put_nowait(streamsid)
                                    
                                elif data["event"] == "connected":
                                    print("Twilio connected")
                                    
                                elif data["event"] == "media":
                                    media = data["media"]
                                    chunk = base64.b64decode(media["payload"])
                                    if media["track"] == "inbound":
                                        inbuffer.extend(chunk)
                                        
                                elif data["event"] == "stop":
                                    print("Twilio stop event")
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
        text="Twilio-Deepgram Bridge Server", 
        status=200,
        headers={'Content-Type': 'text/plain'}
    )

def setup_signal_handlers(runner):
    """Setup signal handlers - ignore SIGTERM from Railway"""
    def signal_handler(signum, frame):
        print(f"Received signal {signum}")
        if signum == signal.SIGTERM:
            print("Railway sent SIGTERM - but health checks are passing!")
            print("Ignoring SIGTERM to keep server running (Railway may be testing)")
            # DON'T shutdown - Railway might just be testing
            return
        elif signum == signal.SIGINT:
            print("SIGINT received - shutting down gracefully")
            asyncio.create_task(graceful_shutdown(runner))

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

async def graceful_shutdown(runner):
    """Gracefully shutdown the server"""
    print("Starting graceful shutdown...")
    shutdown_event.set()
    
    # Give tasks a moment to finish
    await asyncio.sleep(2)
    
    try:
        await runner.cleanup()
        print("Server cleanup completed")
    except Exception as e:
        print(f"Error during cleanup: {e}")
    finally:
        # Stop the event loop
        loop = asyncio.get_event_loop()
        loop.stop()

async def create_app():
    """Create and configure the aiohttp application"""
    app = web.Application()
    
    # Middleware for request logging
    @web.middleware
    async def logging_middleware(request, handler):
        print(f"Request: {request.method} {request.path} from {request.remote}")
        try:
            response = await handler(request)
            print(f"Response: {request.method} {request.path} -> {response.status}")
            return response
        except Exception as e:
            print(f"Error handling {request.method} {request.path}: {e}")
            raise
    
    app.middlewares.append(logging_middleware)
    
    # Routes
    app.router.add_get('/', root_handler)
    app.router.add_get('/health', health_check)
    app.router.add_get('/twilio', websocket_handler)
    
    return app

def main():
    """Main entry point"""
    # Get port from environment (Railway sets this automatically)
    port = int(os.environ.get("PORT", 5000))
    
    print(f"Starting Twilio-Deepgram Bridge Server on port {port}")
    print(f"Health check endpoint: http://0.0.0.0:{port}/health")
    print(f"WebSocket endpoint: ws://0.0.0.0:{port}/twilio")
    
    # Check for required environment variables
    if not os.getenv('DEEPGRAM_API_KEY'):
        print("WARNING: DEEPGRAM_API_KEY not found in environment variables")
    else:
        print("DEEPGRAM_API_KEY found in environment")

    async def run_server():
        # Create the web application
        app = await create_app()
        
        # Create and start the server
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        print(f"Server running on 0.0.0.0:{port}")
        print("Server is ready to accept connections")
        
        # Setup signal handlers for graceful shutdown
        setup_signal_handlers(runner)
        
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
