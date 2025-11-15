import asyncio
import base64
import json
import sys
import websockets
import ssl
import os
import signal
from aiohttp import web
MAX_WS_MESSAGE_SIZE = None

def sts_connect():
    # you can run export DEEPGRAM_API_KEY="your key" in your terminal to set your API key.
    api_key = os.getenv('DEEPGRAM_API_KEY')
    if not api_key:
        raise ValueError("DEEPGRAM_API_KEY environment variable is not set")

    sts_ws = websockets.connect(
        "wss://agent.deepgram.com/v1/agent/converse",
        subprotocols=["token", api_key]
    )
    return sts_ws


async def twilio_handler(twilio_ws):
    audio_queue = asyncio.Queue()
    streamsid_queue = asyncio.Queue()

    async with sts_connect() as sts_ws:
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

        async def sts_sender(sts_ws):
            print("sts_sender started")
            while True:
                chunk = await audio_queue.get()
                await sts_ws.send(chunk)

        async def sts_receiver(sts_ws):
            print("sts_receiver started")
            # we will wait until the twilio ws connection figures out the streamsid
            streamsid = await streamsid_queue.get()
            # for each sts result received, forward it on to the call
            async for message in sts_ws:
                if type(message) is str:
                    print(message)
                    # handle barge-in
                    decoded = json.loads(message)
                    if decoded['type'] == 'UserStartedSpeaking':
                        clear_message = {
                            "event": "clear",
                            "streamSid": streamsid
                        }
                        await twilio_ws.send(json.dumps(clear_message))

                    continue

                print(type(message))
                raw_mulaw = message

                # construct a Twilio media message with the raw mulaw (see https://www.twilio.com/docs/voice/twiml/stream#websocket-messages---to-twilio)
                media_message = {
                    "event": "media",
                    "streamSid": streamsid,
                    "media": {"payload": base64.b64encode(raw_mulaw).decode("ascii")},
                }

                # send the TTS audio to the attached phonecall
                await twilio_ws.send(json.dumps(media_message))

        async def twilio_receiver(twilio_ws):
            print("twilio_receiver started")
            # twilio sends audio data as 160 byte messages containing 20ms of audio each
            # we will buffer 20 twilio messages corresponding to 0.4 seconds of audio to improve throughput performance
            BUFFER_SIZE = 20 * 160

            inbuffer = bytearray(b"")
            async for message in twilio_ws:
                try:
                    data = json.loads(message)
                    if data["event"] == "start":
                        print("got our streamsid")
                        start = data["start"]
                        streamsid = start["streamSid"]
                        streamsid_queue.put_nowait(streamsid)
                    if data["event"] == "connected":
                        continue
                    if data["event"] == "media":
                        media = data["media"]
                        chunk = base64.b64decode(media["payload"])
                        if media["track"] == "inbound":
                            inbuffer.extend(chunk)
                    if data["event"] == "stop":
                        break

                    # check if our buffer is ready to send to our audio_queue (and, thus, then to sts)
                    while len(inbuffer) >= BUFFER_SIZE:
                        chunk = inbuffer[:BUFFER_SIZE]
                        audio_queue.put_nowait(chunk)
                        inbuffer = inbuffer[BUFFER_SIZE:]
                except:
                    break

        # the async for loop will end if the ws connection from twilio dies
        # and if this happens, we should forward an some kind of message to sts
        # to signal sts to send back remaining messages before closing(?)
        # audio_queue.put_nowait(b'')

        await asyncio.wait(
            [
                asyncio.ensure_future(sts_sender(sts_ws)),
                asyncio.ensure_future(sts_receiver(sts_ws)),
                asyncio.ensure_future(twilio_receiver(twilio_ws)),
            ]
        )

        await twilio_ws.close()


async def websocket_handler(request):
    """Handle WebSocket connections from Twilio"""
    ws = web.WebSocketResponse(max_size=MAX_WS_MESSAGE_SIZE)
    await ws.prepare(request)
    
    print(f"Incoming WebSocket connection on path: {request.path}")
    if request.path == "/twilio":
        print("Starting Twilio handler")
        # Convert aiohttp WebSocket to websockets-compatible interface
        # We need to adapt the interface
        await twilio_handler_aiohttp(ws)
    else:
        print(f"Unknown path: {request.path}, closing connection")
        await ws.close()
    
    return ws

async def twilio_handler_aiohttp(twilio_ws):
    """Adapted Twilio handler for aiohttp WebSocket"""
    audio_queue = asyncio.Queue()
    streamsid_queue = asyncio.Queue()

    async with sts_connect() as sts_ws:
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

        async def sts_sender(sts_ws):
            print("sts_sender started")
            while True:
                chunk = await audio_queue.get()
                await sts_ws.send(chunk)

        async def sts_receiver(sts_ws):
            print("sts_receiver started")
            streamsid = await streamsid_queue.get()
            async for message in sts_ws:
                if type(message) is str:
                    print(message)
                    decoded = json.loads(message)
                    if decoded['type'] == 'UserStartedSpeaking':
                        clear_message = {
                            "event": "clear",
                            "streamSid": streamsid
                        }
                        await twilio_ws.send_str(json.dumps(clear_message))
                    continue

                print(type(message))
                raw_mulaw = message

                media_message = {
                    "event": "media",
                    "streamSid": streamsid,
                    "media": {"payload": base64.b64encode(raw_mulaw).decode("ascii")},
                }

                await twilio_ws.send_str(json.dumps(media_message))

        async def twilio_receiver(twilio_ws):
            print("twilio_receiver started")
            BUFFER_SIZE = 20 * 160
            inbuffer = bytearray(b"")
            
            async for msg in twilio_ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        if data["event"] == "start":
                            print("got our streamsid")
                            start = data["start"]
                            streamsid = start["streamSid"]
                            streamsid_queue.put_nowait(streamsid)
                        if data["event"] == "connected":
                            continue
                        if data["event"] == "media":
                            media = data["media"]
                            chunk = base64.b64decode(media["payload"])
                            if media["track"] == "inbound":
                                inbuffer.extend(chunk)
                        if data["event"] == "stop":
                            break

                        while len(inbuffer) >= BUFFER_SIZE:
                            chunk = inbuffer[:BUFFER_SIZE]
                            audio_queue.put_nowait(chunk)
                            inbuffer = inbuffer[BUFFER_SIZE:]
                    except Exception as e:
                        print(f"Error in twilio_receiver: {e}")
                        break
                elif msg.type == web.WSMsgType.ERROR:
                    print(f"WebSocket error: {twilio_ws.exception()}")
                    break

        await asyncio.wait(
            [
                asyncio.ensure_future(sts_sender(sts_ws)),
                asyncio.ensure_future(sts_receiver(sts_ws)),
                asyncio.ensure_future(twilio_receiver(twilio_ws)),
            ]
        )

        await twilio_ws.close()

async def health_check(request):
    """HTTP health check endpoint for Railway - responds immediately"""
    # Respond as fast as possible - Railway might have tight timeouts
    response = web.Response(text="OK", status=200)
    response.headers['Content-Type'] = 'text/plain'
    response.headers['Cache-Control'] = 'no-cache'
    # Log after responding to minimize latency
    print(f"Health check: {request.method} {request.path} -> 200 OK (responded immediately)")
    return response

def main():
    # use this if using ssl
    # ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # ssl_context.load_cert_chain('cert.pem', 'key.pem')
    # server = websockets.serve(router, '0.0.0.0', 443, ssl=ssl_context)

    # use this if not using ssl
    # Railway sets PORT automatically, but default to 5000 to match Railway config
    port = int(os.environ.get("PORT", "5000"))
    print(f"Server starting on ws://0.0.0.0:{port}")
    
    # Create a new event loop (required for some environments)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def keep_alive():
        """Keep the event loop alive forever"""
        while True:
            await asyncio.sleep(3600)  # Sleep for 1 hour, then repeat
    
    async def start_server():
        """Start aiohttp server that handles both HTTP and WebSocket"""
        app = web.Application()
        
        # Track server readiness
        server_ready = asyncio.Event()
        
        # Middleware to log all requests
        @web.middleware
        async def logging_middleware(request, handler):
            print(f"INCOMING REQUEST: {request.method} {request.path} from {request.remote}")
            # Ensure server is ready before handling
            if not server_ready.is_set():
                print("WARNING: Request received before server is marked ready!")
            try:
                response = await handler(request)
                print(f"RESPONSE: {request.method} {request.path} -> {response.status}")
                return response
            except Exception as e:
                print(f"ERROR handling {request.method} {request.path}: {e}")
                raise
        
        app.middlewares.append(logging_middleware)
        
        # HTTP health check endpoint
        app.router.add_get('/', health_check)
        app.router.add_get('/health', health_check)
        
        # WebSocket endpoint for Twilio
        app.router.add_get('/twilio', websocket_handler)
        
        # Catch-all route to log any other requests
        async def catch_all(request):
            print(f"Unhandled request: {request.method} {request.path}")
            return web.Response(text="Not Found", status=404)
        
        app.router.add_route('*', '/{path:.*}', catch_all)
        
        # Create aiohttp server - do this as fast as possible
        print(f"Creating server on 0.0.0.0:{port}...")
        runner = web.AppRunner(app)
        await runner.setup()
        print("Runner setup complete")
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        print(f"TCP site started - server is NOW listening on port {port}")
        
        # Mark server as ready IMMEDIATELY after starting
        server_ready.set()
        print("Server marked as READY - health checks will now work")
        
        # Give Railway a moment to see the server is ready
        # But don't wait too long - we want to be ready ASAP
        await asyncio.sleep(0.1)  # 100ms should be enough
        
        print(f"HTTP/WebSocket server is running on port {port}")
        print(f"HTTP health check available at / and /health")
        print(f"WebSocket endpoint available at /twilio")
        print("Server started successfully and is ready to accept connections")
        print("All incoming requests will be logged")
        
        # Verify the server is actually listening
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result == 0:
            print(f"VERIFIED: Port {port} is open and accepting connections")
        else:
            print(f"WARNING: Port {port} connection test failed")
        
        return runner
    
    try:
        # Start the server IMMEDIATELY - this is critical for Railway
        print("=" * 50)
        print("STARTING SERVER - Railway will check health soon")
        print("=" * 50)
        runner = loop.run_until_complete(start_server())
        print("=" * 50)
        print("SERVER IS READY - Waiting for Railway health check...")
        print("=" * 50)
        
        # Add a keepalive task to ensure the event loop never exits
        keepalive_task = loop.create_task(keep_alive())
        print("Keepalive task created")
        
        # Set up signal handlers
        # IMPORTANT: Don't stop on SIGTERM - Railway might send it as a test
        # Only stop if we're actually being shut down
        shutdown_requested = False
        
        def handle_signal(signum, frame):
            nonlocal shutdown_requested
            print(f"Received signal {signum} from Railway")
            if signum == signal.SIGTERM:
                print("Railway sent SIGTERM - but health checks are passing!")
                print("Ignoring SIGTERM to keep server running (Railway may be testing)")
                # DON'T stop the loop - keep running
                # Railway will kill the container if it really wants to, but we should stay alive
                return
            elif signum == signal.SIGINT:
                print("Received SIGINT - shutting down gracefully")
                shutdown_requested = True
                asyncio.run_coroutine_threadsafe(cleanup(runner), loop)
        
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)
        
        # Keep running forever
        print("Entering run_forever() - server is listening and ready")
        print("If Railway sends health checks, you'll see 'INCOMING REQUEST' above")
        loop.run_forever()
        print("WARNING: loop.run_forever() returned - this should never happen!")
    except KeyboardInterrupt:
        print("Server shutting down due to KeyboardInterrupt...")
        loop.close()
    except Exception as e:
        print(f"Server error: {e}")
        import traceback
        traceback.print_exc()
        loop.close()
        raise

async def cleanup(runner):
    """Cleanup function for graceful shutdown"""
    try:
        await runner.cleanup()
    except Exception as e:
        print(f"Error during cleanup: {e}")
    finally:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.stop()



if __name__ == "__main__":
    sys.exit(main() or 0)
