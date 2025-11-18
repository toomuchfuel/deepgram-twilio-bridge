import asyncio
import base64
import json
import sys
import websockets
import os
import signal
import time
from pathlib import Path
from aiohttp import web
from config import VOICE_AGENT_PERSONALITY, VOICE_MODEL, LLM_MODEL, LLM_TEMPERATURE
from database import LogosDatabase
# from database import format_context_for_va  # not used now, but keep if you need it

# ====== GLOBALS ======
shutdown_event = asyncio.Event()
db = None  # Database instance

# Active call/session state, keyed by call_sid
# {
#   call_sid: {
#       'caller_phone': '+614...',
#       'status': 'ringing' | 'active' | 'inactive',
#       'timestamp': float,
#       'session_id': UUID or str | None,
#       'created_at': float,
#       'ended_at': float | None,
#       'guidance': [str, ...]
#   }
# }
active_sessions = {}

# All open dashboard websockets
dashboard_connections = set()


# ====== DATABASE INIT ======
async def initialize_database():
    """Initialize database connection"""
    global db
    try:
        db = LogosDatabase()
        await db.connect()
        print("✅ Database connected successfully")
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"⚠️ Database connection failed: {e}")
        db = None


# ====== DEEPGRAM CONNECTOR ======
def sts_connect():
    """Connect to Deepgram Voice Agent API"""
    api_key = os.getenv('DEEPGRAM_API_KEY')
    if not api_key:
        raise ValueError("DEEPGRAM_API_KEY environment variable is not set")

    return websockets.connect(
        "wss://agent.deepgram.com/v1/agent/converse",
        subprotocols=["token", api_key]
    )


# ====== MEMORY CONTEXT FORMATTER ======
def format_actual_conversation_context(recent_sessions):
    """Format actual conversation content for AI context instead of generic summaries."""
    print(f"🔍 DEBUG: Formatting context for {len(recent_sessions)} sessions")

    context_parts = []

    for i, session_data in enumerate(recent_sessions[-3:]):  # Last 3 sessions
        session_num = session_data.get('session_number', 'Unknown')
        transcript = session_data.get('full_transcript', [])

        # STEP 1: decode JSON string if needed
        if isinstance(transcript, str):
            try:
                decoded = json.loads(transcript)
                if isinstance(decoded, dict) and "messages" in decoded:
                    transcript = decoded["messages"]
                else:
                    transcript = decoded
                print(f"🔍 DEBUG: Decoded JSON transcript for session {session_num}, type={type(transcript)}")
            except json.JSONDecodeError:
                print(f"⚠️ WARNING: Could not JSON-decode transcript for session {session_num}, using raw string")
                transcript = [{"content": transcript, "speaker": "user"}]

        # STEP 2: normalize to list[dict]
        normalized = []
        for item in transcript:
            if isinstance(item, dict):
                normalized.append(item)
            else:
                normalized.append({
                    "content": str(item),
                    "speaker": "user"
                })
        transcript = normalized

        print(f"🔍 DEBUG: Session {session_num} has {len(transcript) if transcript else 0} messages after normalization")

        if not transcript:
            continue

        key_exchanges = []
        for j, msg in enumerate(transcript):
            content = msg.get('content', '').strip()
            speaker = msg.get('speaker', '')

            print(f"🔍 DEBUG: Message {j}: {speaker} - {content[:50]}...")

            # Skip generic greetings and very short responses
            if len(content) > 15 and not content.startswith(
                ('Hello!', 'Hi!', 'Hey!', 'Yes,', 'Nice!', 'Got it!', 'Oh,', 'Okay!', 'Sure!')
            ):
                if speaker == 'user':
                    key_exchanges.append(f'User said: "{content}"')
                    print(f"🔍 DEBUG: Added user statement: {content[:30]}...")
                elif speaker == 'ai' and (
                    'mentioned' in content or 'talked about' in content or 'remember' in content
                ):
                    print(f"🔍 DEBUG: Skipped AI memory claim: {content[:30]}...")
                    continue

        if key_exchanges:
            meaningful_exchanges = key_exchanges[-6:]  # Last 6 meaningful statements
            session_summary = f"Session {session_num}: " + " | ".join(meaningful_exchanges)
            context_parts.append(session_summary)
            print(f"🔍 DEBUG: Session {session_num} summary: {len(meaningful_exchanges)} meaningful exchanges")
        else:
            print(f"🔍 DEBUG: Session {session_num} had no meaningful exchanges")

    if context_parts:
        full_context = f"""
ACTUAL CONVERSATION HISTORY:
{chr(10).join(context_parts)}

IMPORTANT: Only reference what the user actually said above. Do NOT make up details about hobbies, goals, or activities they never mentioned. If you're not sure about something from previous conversations, ask them to remind you rather than guessing."""
        print(f"🔍 DEBUG: Final context length: {len(full_context)} characters")
        print(f"🔍 DEBUG: Context preview: {full_context[:300]}...")
        return full_context

    print("🔍 DEBUG: No meaningful context found")
    return ""


# ====== CLEANUP HANDLER ======
async def bulk_cleanup_handler(request):
    """HTTP endpoint for bulk cleanup operations"""
    if not db:
        return web.Response(text="Database not available", status=500)

    def normalize_phone(phone):
        if not phone:
            return None
        phone = phone.strip().replace(" ", "")
        if phone.startswith("0"):
            phone = "+61" + phone[1:]
        elif phone.startswith("61") and not phone.startswith("+"):
            phone = "+" + phone
        elif not phone.startswith("+") and phone.isdigit():
            phone = "+61" + phone
        return phone

    try:
        params = request.query
        action = params.get('action', '')
        raw_phone = params.get('phone', '')
        days_old = int(params.get('days', 7))

        caller_phone = normalize_phone(raw_phone)

        print(f"🔍 DEBUG: Cleanup action={action}, raw_phone='{raw_phone}', normalized_phone='{caller_phone}', days={days_old}")

        if action == 'delete_old_sessions':
            async with db.pool.acquire() as conn:
                message_count = await conn.fetchval(f'''
                    SELECT COUNT(*) FROM messages 
                    WHERE session_id IN (
                        SELECT session_id FROM sessions 
                        WHERE created_at < NOW() - INTERVAL '{days_old} days'
                    )
                ''')

                session_count = await conn.fetchval(f'''
                    SELECT COUNT(*) FROM sessions 
                    WHERE created_at < NOW() - INTERVAL '{days_old} days'
                ''')

                await conn.execute(f'''
                    DELETE FROM messages 
                    WHERE session_id IN (
                        SELECT session_id FROM sessions 
                        WHERE created_at < NOW() - INTERVAL '{days_old} days'
                    )
                ''')

                await conn.execute(f'''
                    DELETE FROM sessions 
                    WHERE created_at < NOW() - INTERVAL '{days_old} days'
                ''')

            return web.Response(text=f"Deleted old data: {message_count} messages, {session_count} sessions (older than {days_old} days)")

        elif action == 'delete_caller_data' and caller_phone:
            async with db.pool.acquire() as conn:
                print(f"🔍 DEBUG: Looking for sessions with caller_phone = '{caller_phone}'")

                sessions_to_delete = await conn.fetch('''
                    SELECT session_id, caller_phone, created_at 
                    FROM sessions 
                    WHERE caller_phone = $1
                ''', caller_phone)

                print(f"🔍 DEBUG: Found {len(sessions_to_delete)} sessions for {caller_phone}")
                for session in sessions_to_delete:
                    sid = str(session['session_id'])
                    print(f"🔍 DEBUG: Session {sid[:8]}... created {session['created_at']}")

                if sessions_to_delete:
                    message_count = await conn.fetchval('''
                        SELECT COUNT(*) FROM messages 
                        WHERE session_id IN (
                            SELECT session_id FROM sessions 
                            WHERE caller_phone = $1
                        )
                    ''', caller_phone)

                    await conn.execute('''
                        DELETE FROM messages 
                        WHERE session_id IN (
                            SELECT session_id FROM sessions 
                            WHERE caller_phone = $1
                        )
                    ''', caller_phone)

                    await conn.execute('''
                        DELETE FROM sessions 
                        WHERE caller_phone = $1
                    ''', caller_phone)

                    result1 = message_count
                    result2 = len(sessions_to_delete)
                    print(f"🔍 DEBUG: Deleted {result1} messages, {result2} sessions")
                else:
                    result1 = result2 = 0
                    print(f"🔍 DEBUG: No sessions found for {caller_phone}")

                try:
                    caller_count = await conn.fetchval(
                        'SELECT COUNT(*) FROM callers WHERE phone_number = $1',
                        caller_phone
                    )
                    await conn.execute(
                        'DELETE FROM callers WHERE phone_number = $1',
                        caller_phone
                    )
                    result3 = caller_count
                    print(f"🔍 DEBUG: Deleted {result3} caller records")
                except Exception as e:
                    print(f"🔍 DEBUG: Callers table error (probably doesn't exist): {e}")
                    result3 = 0

            return web.Response(
                text=f"Deleted caller {caller_phone}: {result1 or 0} messages, {result2 or 0} sessions, {result3 or 0} caller records"
            )

        elif action == 'count_records':
            async with db.pool.acquire() as conn:
                sessions_count = await conn.fetchval('SELECT COUNT(*) FROM sessions')
                messages_count = await conn.fetchval('SELECT COUNT(*) FROM messages')
                unique_callers = await conn.fetchval('SELECT COUNT(DISTINCT caller_phone) FROM sessions')

                caller_breakdown = await conn.fetch('''
                    SELECT caller_phone, COUNT(*) as session_count, MAX(created_at) as last_call
                    FROM sessions 
                    GROUP BY caller_phone 
                    ORDER BY session_count DESC
                ''')

            breakdown_text = "\n".join(
                f"  {row['caller_phone']}: {row['session_count']} sessions (last: {row['last_call']})"
                for row in caller_breakdown
            )

            cleanup_phone = caller_breakdown[0]['caller_phone'] if caller_breakdown else '+61412247247'
            cleanup_url = f"/cleanup?action=delete_caller_data&phone={cleanup_phone.replace('+', '%2B')}"

            return web.Response(text=f'''Database Records:
- {unique_callers} unique callers
- {sessions_count} total sessions  
- {messages_count} total messages

Breakdown by caller:
{breakdown_text}

To delete your data, use:
{cleanup_url}
'''.strip())

        else:
            return web.Response(text='''
Available cleanup operations:
- /cleanup?action=count_records
- /cleanup?action=delete_old_sessions&days=7  
- /cleanup?action=delete_caller_data&phone=%2B61412247247

Example: /cleanup?action=delete_old_sessions&days=3
''', status=400)

    except Exception as e:
        print(f"❌ Error in cleanup: {e}")
        import traceback
        print(f"🔍 DEBUG: Full cleanup error: {traceback.format_exc()}")
        return web.Response(text=f"Cleanup error: {e}", status=500)


# ====== DASHBOARD BROADCAST ======
async def broadcast_to_dashboards(message: dict):
    """Send a message to all connected dashboard websockets."""
    if not dashboard_connections:
        return
    dead = []
    data = json.dumps(message)
    for ws in list(dashboard_connections):
        try:
            await ws.send_str(data)
        except Exception as e:
            print(f"⚠️ Error sending to dashboard WS: {e}")
            dead.append(ws)
    for ws in dead:
        dashboard_connections.discard(ws)


def snapshot_active_sessions():
    """Return a serializable snapshot of current sessions for dashboard."""
    sessions = []
    now = time.time()
    for call_sid, info in active_sessions.items():
        sessions.append({
            "call_sid": call_sid,
            "caller_phone": info.get("caller_phone", "unknown"),
            "status": info.get("status", "unknown"),
            "session_id": str(info.get("session_id") or ""),
            "created_at": info.get("created_at"),
            "ended_at": info.get("ended_at"),
            "age_seconds": now - info.get("created_at", now)
        })
    return sessions


# ====== HTTP HANDLERS ======
async def voice_webhook_handler(request):
    """Initial Twilio voice webhook; returns TwiML that streams to /twilio."""
    try:
        form_data = await request.post()
        caller_phone = form_data.get('From', 'unknown')
        call_sid = form_data.get('CallSid', 'unknown')

        print(f"🎯 Voice webhook: Call from {caller_phone}, CallSid: {call_sid}")

        active_sessions[call_sid] = {
            "caller_phone": caller_phone,
            "status": "ringing",
            "timestamp": time.time(),
            "created_at": time.time(),
            "ended_at": None,
            "session_id": None,
            "guidance": []
        }

        await broadcast_to_dashboards({
            "type": "call_started",
            "call_sid": call_sid,
            "caller_phone": caller_phone,
            "status": "ringing",
            "timestamp": time.time()
        })

        host = request.host
        websocket_url = f"wss://{host}/twilio"
        print(f"🔗 Twilio will connect to WebSocket: {websocket_url}")

        twiml_response = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{websocket_url}">
            <Parameter name="caller" value="{caller_phone}"/>
            <Parameter name="callsid" value="{call_sid}"/>
        </Stream>
    </Connect>
</Response>'''

        return web.Response(text=twiml_response, content_type='application/xml')

    except Exception as e:
        print(f"Error in voice webhook: {e}")
        return web.Response(
            text='''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Sorry, there was a connection error. Please try calling again.</Say>
</Response>''',
            content_type='application/xml'
        )


async def health_check(request):
    return web.Response(
        text="OK",
        status=200,
        headers={'Content-Type': 'text/plain', 'Cache-Control': 'no-cache'}
    )


async def root_handler(request):
    return web.Response(
        text="Twilio-Deepgram Bridge Server with HGO Dashboard",
        status=200,
        headers={'Content-Type': 'text/plain'}
    )


# ====== DASHBOARD HTML (simple v24-style) ======
async def dashboard_handler(request):
    """Serve the HGO dashboard page."""
    # If you have a separate HTML file, you could read it here instead.
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>LOGOS AI – HGO Oversight Dashboard</title>
<style>
  body { margin:0; font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#050816; color:#e5e7eb; }
  .app { display:flex; flex-direction:column; height:100vh; }
  header { padding:12px 20px; border-bottom:1px solid #1f2933; display:flex; align-items:center; justify-content:space-between; }
  header h1 { font-size:18px; margin:0; }
  header .status { font-size:12px; opacity:.7; }
  main { flex:1; display:flex; padding:12px; gap:12px; box-sizing:border-box; }
  .col { flex:1; background:#020617; border-radius:12px; padding:10px; border:1px solid #111827; display:flex; flex-direction:column; min-width:0; }
  h2 { font-size:14px; margin:0 0 8px; display:flex; justify-content:space-between; align-items:center; }
  h3 { font-size:13px; margin:0 0 4px; }
  .count { font-size:11px; opacity:.7; }
  .list { flex:1; overflow-y:auto; padding-right:4px; }
  .client-card { border-radius:10px; padding:8px; margin-bottom:6px; background:#020617; border:1px solid #1f2937; cursor:pointer; }
  .client-card.active { border-color:#38bdf8; box-shadow:0 0 0 1px #0ea5e955; }
  .client-name { font-size:13px; font-weight:600; }
  .client-meta { font-size:11px; opacity:.8; margin-top:2px; }
  .badge { display:inline-flex; align-items:center; padding:2px 6px; border-radius:999px; font-size:10px; margin-right:4px; }
  .badge.danger { background:#7f1d1d; color:#fecaca; }
  .badge.ok { background:#064e3b; color:#bbf7d0; }
  .badge.info { background:#0f172a; color:#e5e7eb; }
  .session-header { margin-bottom:8px; }
  .session-id { font-size:11px; opacity:.7; margin-left:6px; }
  .transcript { flex:1; background:#020617; border-radius:10px; padding:8px; border:1px solid #1f2937; overflow-y:auto; font-size:12px; }
  .msg { margin-bottom:6px; max-width:90%; padding:6px 8px; border-radius:8px; }
  .msg.user { background:#0f172a; align-self:flex-start; }
  .msg.ai { background:#111827; align-self:flex-end; }
  .msg .sender { font-size:10px; opacity:.7; margin-bottom:2px; }
  .msg .text { white-space:pre-wrap; }
  .guidance { margin-top:8px; }
  textarea { width:100%; min-height:70px; resize:vertical; border-radius:8px; border:1px solid #1f2937; background:#020617; color:#e5e7eb; padding:6px; font-size:12px; box-sizing:border-box; }
  button { margin-top:6px; padding:6px 10px; border-radius:999px; border:none; font-size:12px; background:#0ea5e9; color:#0b1120; cursor:pointer; }
  button:disabled { opacity:0.5; cursor:default; }
</style>
</head>
<body>
<div class="app">
  <header>
    <div>
      <h1>LOGOS AI – Human Guidance Dashboard</h1>
      <div class="status" id="status">Connecting to live sessions…</div>
    </div>
  </header>
  <main>
    <div class="col" id="inactive-col">
      <h2>Inactive Clients <span class="count" id="inactive-count">(0)</span></h2>
      <div class="list" id="inactive-list"></div>
    </div>
    <div class="col" id="active-col">
      <h2>Active Clients <span class="count" id="active-count">(0)</span></h2>
      <div class="list" id="active-list"></div>
    </div>
    <div class="col" id="live-col">
      <div class="session-header">
        <h3 id="live-title">Live Session — <span id="liveName">None</span></h3>
        <div class="session-id" id="liveId"></div>
      </div>
      <div class="transcript" id="transcript"></div>
      <div class="guidance">
        <h3>Human Guidance to AI / Caller</h3>
        <textarea id="guidance-input" placeholder="Type an instruction for the AI or a note about what you’re seeing…"></textarea>
        <button id="guidance-send" disabled>Send Guidance</button>
      </div>
    </div>
  </main>
</div>
<script>
let ws = null;
let activeSessions = {}; // call_sid -> {caller_phone, status, session_id}
let selectedCallSid = null;

function connectWS() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = proto + '//' + window.location.host + '/dashboard-ws';
  ws = new WebSocket(url);

  ws.onopen = () => {
    document.getElementById('status').textContent = 'Connected to live sessions';
    ws.send(JSON.stringify({type: 'subscribe_dashboard'}));
  };

  ws.onclose = () => {
    document.getElementById('status').textContent = 'Disconnected – retrying…';
    setTimeout(connectWS, 2000);
  };

  ws.onerror = () => {
    document.getElementById('status').textContent = 'WebSocket error';
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleMessage(data);
    } catch (e) {
      console.error('Bad WS message', e, event.data);
    }
  };
}

function handleMessage(data) {
  switch (data.type) {
    case 'active_sessions':
      updateSessionsSnapshot(data.sessions);
      break;
    case 'call_started':
      addOrUpdateSession(data.call_sid, data);
      break;
    case 'call_ended':
      markSessionEnded(data.call_sid);
      break;
    case 'transcript_update':
      handleTranscriptUpdate(data);
      break;
    default:
      console.log('Unknown message', data);
  }
}

function updateSessionsSnapshot(list) {
  activeSessions = {};
  list.forEach(s => { activeSessions[s.call_sid] = s; });
  renderLists();
}

function addOrUpdateSession(call_sid, payload) {
  if (!activeSessions[call_sid]) {
    activeSessions[call_sid] = {};
  }
  Object.assign(activeSessions[call_sid], payload);
  if (!activeSessions[call_sid].status) activeSessions[call_sid].status = 'active';
  renderLists();
}

function markSessionEnded(call_sid) {
  if (activeSessions[call_sid]) {
    activeSessions[call_sid].status = 'inactive';
    activeSessions[call_sid].ended_at = Date.now()/1000;
  }
  renderLists();
}

function renderLists() {
  const inactiveList = document.getElementById('inactive-list');
  const activeList = document.getElementById('active-list');
  inactiveList.innerHTML = '';
  activeList.innerHTML = '';

  let inactiveCount = 0;
  let activeCount = 0;

  Object.keys(activeSessions).forEach(call_sid => {
    const s = activeSessions[call_sid];
    const card = document.createElement('div');
    card.className = 'client-card';
    if (call_sid === selectedCallSid) card.classList.add('active');
    card.onclick = () => { selectSession(call_sid); };

    const name = s.caller_phone || 'Unknown';
    const status = s.status || 'unknown';

    card.innerHTML = `
      <div class="client-name">${name}</div>
      <div class="client-meta">
        <span class="badge ${status === 'active' ? 'ok' : 'info'}">${status}</span>
        ${s.session_id ? `<span class="badge info">Session ${s.session_id.slice(0,8)}</span>` : ''}
      </div>
    `;

    if (status === 'active') {
      activeList.appendChild(card);
      activeCount++;
    } else {
      inactiveList.appendChild(card);
      inactiveCount++;
    }
  });

  document.getElementById('inactive-count').textContent = `(${inactiveCount})`;
  document.getElementById('active-count').textContent = `(${activeCount})`;
}

function selectSession(call_sid) {
  selectedCallSid = call_sid;
  const s = activeSessions[call_sid];
  document.getElementById('liveName').textContent = s ? (s.caller_phone || 'Unknown') : 'None';
  document.getElementById('liveId').textContent = s && s.session_id ? `Call: ${call_sid} | Session: ${s.session_id}` : `Call: ${call_sid}`;
  document.getElementById('guidance-send').disabled = false;
  document.querySelectorAll('.client-card').forEach(c => c.classList.remove('active'));
  renderLists(); // re-apply active selection
}

function handleTranscriptUpdate(data) {
  const call_sid = data.call_sid;
  if (!call_sid) return;
  addOrUpdateSession(call_sid, data);
  if (!selectedCallSid) {
    selectSession(call_sid);
  }
  if (selectedCallSid === call_sid) {
    const box = document.getElementById('transcript');
    const div = document.createElement('div');
    div.className = 'msg ' + (data.role === 'ai' ? 'ai' : 'user');
    const who = data.role === 'ai' ? 'AI' : 'Caller';
    div.innerHTML = `
      <div class="sender">${who}</div>
      <div class="text">${data.content}</div>
    `;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }
}

document.getElementById('guidance-send').addEventListener('click', () => {
  const txt = document.getElementById('guidance-input').value.trim();
  if (!txt || !ws || ws.readyState !== WebSocket.OPEN || !selectedCallSid) return;
  ws.send(JSON.stringify({
    type: 'human_guidance',
    call_sid: selectedCallSid,
    guidance: txt
  }));
  document.getElementById('guidance-input').value = '';
});

connectWS();
</script>
</body>
</html>
    """.strip()
    return web.Response(text=html, content_type='text/html')


# ====== DASHBOARD WEBSOCKET ======
async def dashboard_websocket_handler(request):
    """Handle dashboard WebSocket connections for real-time monitoring."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    dashboard_connections.add(ws)
    print("📊 Dashboard connected")
    # On connect, send snapshot
    await ws.send_str(json.dumps({
        "type": "active_sessions",
        "sessions": snapshot_active_sessions()
    }))

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    print(f"⚠️ Bad JSON from dashboard: {msg.data}")
                    continue

                if data.get("type") == "subscribe_dashboard":
                    # Already sent snapshot
                    pass
                elif data.get("type") == "human_guidance":
                    call_sid = data.get("call_sid")
                    guidance = data.get("guidance", "").strip()
                    if call_sid and guidance:
                        info = active_sessions.get(call_sid)
                        if info is None:
                            active_sessions[call_sid] = {
                                "caller_phone": "unknown",
                                "status": "active",
                                "timestamp": time.time(),
                                "created_at": time.time(),
                                "ended_at": None,
                                "session_id": None,
                                "guidance": []
                            }
                            info = active_sessions[call_sid]
                        info.setdefault("guidance", []).append(guidance)
                        print(f"🧭 Human guidance for {call_sid}: {guidance[:80]}")

                        # Optionally, record in DB if session exists
                        if db and info.get("session_id"):
                            try:
                                await db.add_message(info["session_id"], "hgo", guidance, {"source": "dashboard"})
                            except Exception as e:
                                print(f"⚠️ Error saving HGO guidance: {e}")
                else:
                    print(f"ℹ️ Unknown dashboard message: {data}")

            elif msg.type == web.WSMsgType.ERROR:
                print(f"⚠️ Dashboard WS error: {ws.exception()}")
                break

    finally:
        dashboard_connections.discard(ws)
        print("📊 Dashboard disconnected")

    return ws


# ====== TWILIO WEBSOCKET HANDLERS ======
async def websocket_handler(request):
    """Handle WebSocket connections from Twilio."""
    print(f"🔍 WEBSOCKET DEBUG: Incoming connection from {request.remote}")
    print(f"🔍 Headers: {dict(request.headers)}")
    print(f"🔍 Query params: {dict(request.query)}")

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    print(f"📞 Twilio WebSocket connection established on path: {request.path}")

    try:
        await twilio_handler(ws)
    except Exception as e:
        print(f"Error in WebSocket handler: {e}")
    finally:
        if not ws.closed:
            await ws.close()

    return ws


async def twilio_handler(twilio_ws):
    """Handle Twilio WebSocket communication with Deepgram."""
    audio_queue = asyncio.Queue()
    streamsid_queue = asyncio.Queue()

    session_id = None
    caller_phone = None
    call_sid = None

    caller_info_ready = asyncio.Event()

    try:
        async def twilio_receiver():
            nonlocal session_id, caller_phone, call_sid
            print("📱 twilio_receiver started")
            BUFFER_SIZE = 20 * 160  # 0.4 seconds at 8k mulaw
            inbuffer = bytearray(b"")

            try:
                async for msg in twilio_ws:
                    if shutdown_event.is_set():
                        break

                    if msg.type == web.WSMsgType.TEXT:
                        try:
                            data = json.loads(msg.data)
                        except json.JSONDecodeError:
                            print(f"⚠️ Error decoding Twilio message: {msg.data}")
                            continue

                        event_type = data.get("event")
                        if event_type == "start":
                            print("🚀 Received Twilio start event")
                            start = data.get("start", {})
                            streamsid = start.get("streamSid")
                            actual_call_sid = start.get("callSid")
                            custom_params = start.get("customParameters", {})

                            caller_phone = custom_params.get("caller", "unknown")
                            call_sid = custom_params.get("callsid", actual_call_sid)

                            print(f"📱 Caller phone from Twilio: {caller_phone}")
                            print(f"☎️ Call SID: {call_sid}")
                            print(f"🔗 Stream ID: {streamsid}")

                            # Update active_sessions
                            info = active_sessions.get(call_sid) or {}
                            info.update({
                                "caller_phone": caller_phone,
                                "status": "active",
                                "timestamp": time.time(),
                                "created_at": info.get("created_at", time.time()),
                                "ended_at": None,
                                "session_id": None,
                                "guidance": info.get("guidance", [])
                            })
                            active_sessions[call_sid] = info

                            await broadcast_to_dashboards({
                                "type": "call_started",
                                "call_sid": call_sid,
                                "caller_phone": caller_phone,
                                "status": "active",
                                "timestamp": time.time()
                            })

                            streamsid_queue.put_nowait(streamsid)
                            caller_info_ready.set()

                        elif event_type == "connected":
                            print("✅ Twilio connected event")

                        elif event_type == "media":
                            media = data.get("media", {})
                            chunk = base64.b64decode(media.get("payload", ""))
                            if media.get("track") == "inbound":
                                inbuffer.extend(chunk)

                        elif event_type == "stop":
                            print("🛑 Twilio stop event")
                            # Mark session inactive
                            if call_sid and call_sid in active_sessions:
                                active_sessions[call_sid]["status"] = "inactive"
                                active_sessions[call_sid]["ended_at"] = time.time()
                                await broadcast_to_dashboards({
                                    "type": "call_ended",
                                    "call_sid": call_sid
                                })
                            # End DB session
                            if session_id and db:
                                try:
                                    summary = "Phone call session (summary TBD)"
                                    await db.end_session(session_id, summary)
                                    print(f"💾 Session {session_id} ended and saved")
                                except Exception as e:
                                    print(f"⚠️ Error ending session: {e}")
                            break

                        # Flush buffered audio to Deepgram
                        while len(inbuffer) >= BUFFER_SIZE:
                            chunk = inbuffer[:BUFFER_SIZE]
                            audio_queue.put_nowait(chunk)
                            inbuffer = inbuffer[BUFFER_SIZE:]

                    elif msg.type == web.WSMsgType.ERROR:
                        print(f"⚠️ WebSocket error from Twilio: {twilio_ws.exception()}")
                        break

            except Exception as e:
                print(f"Error in twilio_receiver: {e}")

        twilio_task = asyncio.create_task(twilio_receiver())

        # Wait until we know caller_phone/call_sid
        await caller_info_ready.wait()

        # Build base prompt and memory context
        ai_prompt = VOICE_AGENT_PERSONALITY

        if db and caller_phone != 'unknown':
            try:
                print(f"🔍 DEBUG: Loading context for {caller_phone}")
                caller_data = await db.get_or_create_caller(caller_phone, call_sid or "websocket-call")
                session_id = caller_data['session_id']
                ctx = caller_data.get('context') or {}

                print(f"💾 Loaded caller context - Session {caller_data.get('session_number')}")
                recent = (ctx.get('recent_sessions') or []) if isinstance(ctx, dict) else []

                if recent:
                    print(f"📚 Found {len(recent)} previous sessions")
                    actual_context = format_actual_conversation_context(recent)
                    if actual_context:
                        ai_prompt = f"""{VOICE_AGENT_PERSONALITY}

{actual_context}

Remember: Only refer to what this caller actually said in previous conversations."""
                        print("🧠 AI prompt enhanced with ACTUAL conversation content")
                        print(f"📝 Full prompt preview: {ai_prompt[:500]}...")
                    else:
                        print("🔍 DEBUG: No actual context generated")
                else:
                    print("🔍 DEBUG: No previous sessions found")

                # Update active_sessions with DB session_id
                if call_sid and call_sid in active_sessions:
                    active_sessions[call_sid]["session_id"] = session_id

            except Exception as e:
                print(f"❌ Database error while loading context: {e}")
                import traceback
                print(traceback.format_exc())

        # Connect to Deepgram
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
                            "model": "nova-3"
                        }
                    },
                    "think": {
                        "provider": {
                            "type": "open_ai",
                            "model": LLM_MODEL,
                            "temperature": LLM_TEMPERATURE
                        },
                        "prompt": ai_prompt
                    },
                    "speak": {
                        "provider": {
                            "type": "deepgram",
                            "model": VOICE_MODEL
                        }
                    },
                    "greeting": "Hello, I’m LOGOS AI. How can I support you today?"
                }
            }

            await sts_ws.send(json.dumps(config_message))
            print("⚙️ Configuration sent to Deepgram with prompt & context")

            async def sts_sender():
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
                print("🔊 sts_receiver started")
                try:
                    streamsid = await streamsid_queue.get()
                    print(f"🌊 Got Twilio stream ID: {streamsid}")

                    async for message in sts_ws:
                        if shutdown_event.is_set():
                            break

                        if isinstance(message, str):
                            print(f"📨 Deepgram text message: {message}")
                            try:
                                decoded = json.loads(message)
                            except json.JSONDecodeError:
                                continue

                            # Store conversation messages in DB
                            if decoded.get("type") == "ConversationText" and session_id and db:
                                role = decoded.get("role")
                                content = decoded.get("content")
                                if role and content:
                                    db_role = "ai" if role == "assistant" else role
                                    try:
                                        await db.add_message(session_id, db_role, content, decoded)
                                        print(f"💬 Stored message: {db_role} - {content[:60]}...")
                                    except Exception as e:
                                        print(f"⚠️ Error storing message: {e}")

                                    # Also broadcast to dashboard
                                    await broadcast_to_dashboards({
                                        "type": "transcript_update",
                                        "session_id": str(session_id),
                                        "call_sid": call_sid,
                                        "role": db_role,
                                        "content": content,
                                        "timestamp": time.time()
                                    })

                            # Handle barge-in
                            if decoded.get("type") == "UserStartedSpeaking":
                                clear_message = {
                                    "event": "clear",
                                    "streamSid": streamsid
                                }
                                await twilio_ws.send_str(json.dumps(clear_message))
                        else:
                            # Binary audio from Deepgram
                            print(f"🎧 Received binary audio from Deepgram, {len(message)} bytes")
                            media_message = {
                                "event": "media",
                                "streamSid": streamsid,
                                "media": {"payload": base64.b64encode(message).decode("ascii")},
                            }
                            await twilio_ws.send_str(json.dumps(media_message))

                except Exception as e:
                    print(f"Error in sts_receiver: {e}")

            await asyncio.gather(
                sts_sender(),
                sts_receiver(),
                twilio_task,
                return_exceptions=True
            )

    except Exception as e:
        print(f"Error in twilio_handler: {e}")


# ====== SIGNAL HANDLING ======
def setup_signal_handlers():
    def ignore_sigterm(signum, frame):
        print(f"Received signal {signum}")
        if signum == signal.SIGTERM:
            print("Ignoring SIGTERM to keep server running (Railway behavior)")
        elif signum == signal.SIGINT:
            print("SIGINT received - stopping")
            raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, ignore_sigterm)
    signal.signal(signal.SIGINT, ignore_sigterm)


# ====== APP FACTORY ======
async def create_app():
    app = web.Application()

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

    app.router.add_get('/', root_handler)
    app.router.add_get('/health', health_check)
    app.router.add_post('/webhook/voice', voice_webhook_handler)
    app.router.add_get('/twilio', websocket_handler)
    app.router.add_get('/cleanup', bulk_cleanup_handler)
    app.router.add_get('/dashboard', dashboard_handler)
    app.router.add_get('/dashboard-ws', dashboard_websocket_handler)

    return app


# ====== MAIN ======
def main():
    port = int(os.environ.get("PORT", 5000))

    print(f"🚀 Starting Twilio-Deepgram Bridge Server on port {port}")
    print(f"🔍 Health: http://0.0.0.0:{port}/health")
    print(f"📞 Voice webhook: http://0.0.0.0:{port}/webhook/voice")
    print(f"🔌 Twilio WS: ws://0.0.0.0:{port}/twilio")
    print(f"🗑️ Cleanup: http://0.0.0.0:{port}/cleanup")
    print(f"📊 Dashboard: http://0.0.0.0:{port}/dashboard")

    if not os.getenv('DEEPGRAM_API_KEY'):
        print("⚠️ WARNING: DEEPGRAM_API_KEY not set")
    else:
        print("✅ DEEPGRAM_API_KEY found")

    async def run_server():
        await initialize_database()
        app = await create_app()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()

        print(f"🌟 Server running on 0.0.0.0:{port}")
        setup_signal_handlers()

        try:
            while not shutdown_event.is_set():
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    try:
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
