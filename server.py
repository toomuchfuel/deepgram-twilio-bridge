import asyncio
import base64
import json
import sys
import websockets
import ssl
import os
import signal
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


async def router(websocket, path):
    print(f"Incoming WebSocket connection on path: {path}")
    if path == "/twilio":
        print("Starting Twilio handler")
        await twilio_handler(websocket)
    else:
        print(f"Unknown path: {path}, closing connection")
        await websocket.close()

async def handle_connection(reader, writer):
    """Handle both HTTP health checks and WebSocket connections"""
    try:
        # Peek at the first bytes to determine if it's HTTP or WebSocket upgrade
        peek_data = await asyncio.wait_for(reader.read(1024), timeout=1.0)
        
        request_str = peek_data.decode('utf-8', errors='ignore')
        
        # Check if it's a WebSocket upgrade request
        if 'Upgrade: websocket' in request_str or 'upgrade: websocket' in request_str.lower():
            # This is a WebSocket upgrade - we need to handle it differently
            # The websockets library expects to handle this, so we can't intercept it easily
            # For now, close this and let the WebSocket server handle it
            writer.close()
            await writer.wait_closed()
            return
        
        # Check if it's a plain HTTP GET request (health check)
        if request_str.startswith('GET'):
            response = "HTTP/1.1 200 OK\r\n"
            response += "Content-Type: text/plain\r\n"
            response += "Content-Length: 2\r\n"
            response += "Connection: close\r\n"
            response += "\r\n"
            response += "OK"
            writer.write(response.encode('utf-8'))
            await writer.drain()
            print("Health check request responded with 200 OK")
            writer.close()
            await writer.wait_closed()
        else:
            # Unknown request type
            writer.close()
            await writer.wait_closed()
    except asyncio.TimeoutError:
        # Timeout reading - might be a different protocol
        writer.close()
        await writer.wait_closed()
    except Exception as e:
        print(f"Connection handler error: {e}")
        try:
            writer.close()
        except:
            pass

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
        """Start WebSocket server - websockets library handles upgrades"""
        # Start WebSocket server (websockets library handles HTTP upgrade requests automatically)
        # The websockets library will respond with HTTP 101 Switching Protocols for WebSocket upgrades
        ws_server = await websockets.serve(
            router, 
            "0.0.0.0", 
            port, 
            max_size=MAX_WS_MESSAGE_SIZE,
            # Ensure WebSocket upgrade is handled properly
            ping_interval=20,
            ping_timeout=10
        )
        print(f"WebSocket server is running and listening on port {port}")
        print(f"Server will respond with HTTP 101 for WebSocket upgrade requests")
        print("Server started successfully")
        print("NOTE: Railway HTTP health checks will fail - WebSocket server only handles WebSocket upgrades")
        return ws_server
    
    try:
        # Start the server
        server = loop.run_until_complete(start_server())
        
        # Add a keepalive task to ensure the event loop never exits
        keepalive_task = loop.create_task(keep_alive())
        print("Keepalive task created, entering run_forever()")
        
        # Set up signal handlers for graceful shutdown (but log when they're received)
        def handle_signal(signum, frame):
            print(f"Received signal {signum} - Railway may be shutting down container")
            # Let the signal propagate normally for graceful shutdown
        
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)
        
        # Keep running forever - this should never return
        print("Calling loop.run_forever() - this should block indefinitely")
        print("If you see 'Stopping Container' after this, Railway is killing the process externally")
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
    finally:
        print("Main function exiting - this should not happen if run_forever() works")



if __name__ == "__main__":
    sys.exit(main() or 0)
