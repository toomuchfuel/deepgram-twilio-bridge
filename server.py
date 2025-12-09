import asyncio
import base64
import json
import sys
import websockets
import os
import signal
import time
from aiohttp import web, WSMsgType
from config import VOICE_AGENT_PERSONALITY, VOICE_MODEL, LLM_MODEL, LLM_TEMPERATURE
from database import LogosDatabase, format_context_for_va
from aiohttp_cors import setup as cors_setup, ResourceOptions

# Global variables
shutdown_event = asyncio.Event()
db = None  # Database instance
active_sessions = {}  # Store session data: {call_sid: session_data}
inactive_clients = []  # Store ended calls for the dashboard
dashboard_connections = set()  # Track dashboard WebSocket connections
human_guidance_queue = {}  # Store guidance from human operators: {session_id: guidance_text}

async def initialize_database():
    """Initialize database connection"""
    global db
    try:
        db = LogosDatabase()
        await db.connect()
        print("Database connected successfully")
        print("Database tables created successfully")
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

async def broadcast_to_dashboards(message):
    """Send message to all connected dashboard clients"""
    if not dashboard_connections:
        return
    
    disconnected = set()
    for ws in dashboard_connections.copy():
        try:
            await ws.send_str(json.dumps(message))
        except ConnectionResetError:
            disconnected.add(ws)
        except Exception as e:
            print(f"Error broadcasting to dashboard: {e}")
            disconnected.add(ws)
    
    # Remove disconnected clients
    dashboard_connections.difference_update(disconnected)

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
            'timestamp': time.time(),
            'status': 'connecting'
        }

        # Notify dashboard of incoming call - send immediately so dashboard shows call
        await broadcast_to_dashboards({
            'type': 'call_started',
            'call_sid': call_sid,
            'caller_phone': caller_phone,
            'timestamp': time.time()
        })
        
        # Build WebSocket URL (same format as working direct TwiML)
        host = request.host
        websocket_url = f"wss://{host}/twilio"
        
        print(f"🔗 Connecting to WebSocket: {websocket_url}")
        
        # Return EXACT same TwiML format as working version
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
        # Fallback TwiML
        return web.Response(
            text='''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Sorry, there was a connection error. Please try calling again.</Say>
</Response>''',
            content_type='application/xml'
        )

def format_actual_conversation_context(recent_sessions):
    """Format actual conversation content for AI context instead of generic summaries"""
    print(f"🔍 DEBUG: Formatting context for {len(recent_sessions)} sessions")
    
    context_parts = []
    
    for i, session_data in enumerate(recent_sessions[-3:]):  # Last 3 sessions only
        session_num = session_data.get('session_number', 'Unknown')
        transcript = session_data.get('full_transcript', [])

        # 🔧 STEP 1: if transcript is a JSON string, decode it first
        if isinstance(transcript, str):
            try:
                decoded = json.loads(transcript)
                # Some schemas store {"messages": [...]}
                if isinstance(decoded, dict) and "messages" in decoded:
                    transcript = decoded["messages"]
                else:
                    transcript = decoded
                print(f"🔍 DEBUG: Decoded JSON transcript for session {session_num}, type={type(transcript)}")
            except json.JSONDecodeError:
                # Fall back: treat whole thing as one user message
                print(f"⚠️ WARNING: Could not JSON-decode transcript for session {session_num}, using raw string")
                transcript = [{"content": transcript, "speaker": "user"}]

        # 🔧 STEP 2: normalize into list[dict]
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
        
        if transcript:
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
                        key_exchanges.append(f"User said: \"{content}\"")
                        print(f"🔍 DEBUG: Added user statement: {content[:30]}...")
                    elif speaker == 'ai' and (
                        'mentioned' in content or 'talked about' in content or 'remember' in content
                    ):
                        # Skip AI's generic memory claims that might be wrong
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
    
    print(f"🔍 DEBUG: No meaningful context found")
    return ""

async def dashboard_websocket_handler(request):
    """Handle dashboard WebSocket connections for real-time monitoring"""
    print(f"🔍 Dashboard WebSocket handler called from {request.remote}")
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    dashboard_connections.add(ws)
    print(f"🖥️ Dashboard connected. Total dashboards: {len(dashboard_connections)}")

    try:
        # Send current active sessions to new dashboard
        print(f"📤 Sending active sessions: {list(active_sessions.keys())}")
        if active_sessions:
            await ws.send_str(json.dumps({
                'type': 'active_sessions',
                'sessions': list(active_sessions.keys())
            }))

        # Send current inactive clients on connection
        print(f"📤 Sending inactive clients: {len(inactive_clients)} clients")
        await ws.send_str(json.dumps({
            'type': 'inactive_clients',
            'clients': inactive_clients
        }))
        
               
        # Handle incoming dashboard messages
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    message_type = data.get('type')
                    
                    if message_type == 'human_guidance':
                        # Store guidance from human operator
                        session_id = data.get('session_id')
                        guidance = data.get('guidance')
                        human_guidance_queue[session_id] = {
                            'guidance': guidance,
                            'timestamp': time.time()
                        }
                        print(f"👤 Human guidance received for session {session_id}: {guidance}")
                        
                    elif message_type == 'ping':
                        await ws.send_str(json.dumps({'type': 'pong'}))
                        
                except json.JSONDecodeError:
                    print(f"Invalid JSON from dashboard: {msg.data}")
                    
            elif msg.type == WSMsgType.ERROR:
                print(f"❌ Dashboard WebSocket error: {ws.exception()}")
                break
            elif msg.type == WSMsgType.CLOSE:
                print(f"🔌 Dashboard WebSocket closed by client")
                break

    except Exception as e:
        print(f"❌ Dashboard WebSocket exception: {e}")
        import traceback
        traceback.print_exc()
    finally:
        dashboard_connections.discard(ws)
        print(f"🖥️ Dashboard disconnected. Remaining: {len(dashboard_connections)}")

    return ws

async def dashboard_handler(request):
    """Serve the dashboard HTML page"""
    dashboard_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>LOGOS AI - Human Guidance & Oversight Dashboard</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@700&family=Orbitron:wght@800&display=swap" rel="stylesheet">
  <style>
    :root{--bg:#ffffff;--text:#111827;--muted:#6b7280;--line:#e5e7eb;--chip:#f3f4f6;--accent:#2563eb;--danger:#ef4444;
           --col1:320px; --col2:320px; }
    *{box-sizing:border-box;} html,body{height:100%;} body{margin:0;background:#fff;color:#111;
      font:14px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Inter,Ubuntu,"Helvetica Neue",Arial;}
    .layout{display:grid;grid-template-columns: var(--col1) 6px var(--col2) 6px 1fr;grid-template-rows: 1fr;
             height:calc(100vh - 58px);overflow:hidden;padding:4px;gap:0;}
    .resizer.v{width:6px;cursor:col-resize;background:var(--line);}
    .resizer.v:hover{background:var(--accent);}
    .col{overflow:auto;padding:12px 8px;background:#fff;margin:4px;border:0.6mm solid var(--accent);border-radius:12px;}
    .col h2{font-size:13px;letter-spacing:.3px;text-transform:uppercase;color:#6b7280;margin:4px 6px 8px;}
    .count{color:var(--text);font-weight:700;margin-left:6px;}
    .legend{font-size:10.5px;color:#6b7280;margin:0 6px 8px;}
    .client{display:flex;flex-direction:column;gap:4px;padding:6px;border:1px solid var(--line);border-radius:8px;background:#fff;margin:0;cursor:pointer;}
    .client + .client{border-top:none;}
    .client:hover{ box-shadow:0 2px 8px rgba(0,0,0,.05);}
    .client.selected{outline:2px solid var(--accent);}
    .top{display:flex;align-items:center;gap:6px;justify-content:space-between;}
    .name{font-weight:600;font-size:13px;}
    .id{font-size:11px;color:#6b7280;margin-left:6px;}
    .chip{padding:2px 6px;border-radius:999px;background:#f3f4f6;color:#111;font-size:11px;border:1px solid var(--line);white-space:nowrap;}
    .chip.casual{background:#fef9c3;border-color:#fde68a;}
    .chip.intense{background:#ffedd5;border-color:#fdba74;}
    .chip.distressed{background:#fee2e2;border-color:#fecaca;}
    .chip.live{background:#dcfce7;border-color:#bbf7d0;color:#166534;font-weight:600;}
    .meta{font-size:11px;color:#6b7280;display:flex;gap:8px;flex-wrap:wrap;}
    .bar{height:4px;border-radius:999px;background:#f3f4f6;overflow:hidden;}
    .bar > span{display:block;height:100%;background:linear-gradient(90deg,#ef4444,#f59e0b,#22c55e);width:40%;}
    .right{display:grid;grid-template-rows: var(--rightTop, 60%) 6px 1fr;overflow:hidden;margin:4px;}
    .pane{padding:16px;border-bottom:none;overflow:auto;background:#fff;border:0.6mm solid var(--accent);border-radius:12px;}
    .resizer.h{height:6px;cursor:row-resize;background:var(--line);}
    .resizer.h:hover{background:var(--accent);}
    .pane h3{margin:0 0 8px;font-size:18px;}
    .transcript{display:flex;flex-direction:column;gap:12px;max-width:900px;}
    .msg{border:1px solid var(--line);background:#fff;border-radius:10px;padding:12px 12px;font-size:14px;}
    .msg.ai{border-color:#dbeafe;background:#eff6ff;}
    .msg.user{border-color:#e4e4e7;background:#fafafa;}
    .msg .small,.time{font-size:11px;color:#6b7280;margin-bottom:6px;}
    .stats{display:flex;gap:16px;flex-wrap:wrap;color:#6b7280;font-size:12px;margin:4px 8px 10px;}
    .instruct-box{display:flex;gap:10px;max-width:900px;}
    textarea{flex:1;min-height:120px;padding:12px;border-radius:10px;border:1px solid var(--line);
      font:14px/1.4 system-ui,-apple-system,Segoe UI,Roboto,Inter,Ubuntu,"Helvetica Neue",Arial;}
    button{align-self:flex-start;padding:10px 14px;border-radius:10px;border:1px solid var(--accent);background:#2563eb;color:#fff;font-weight:600;cursor:pointer;}
    .ghost-btn{padding:8px 10px;border-radius:8px;border:1px solid var(--accent);background:#fff;color:#2563eb;font-weight:700;cursor:pointer;}
    .title{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;gap:8px;}
    .title-left{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
    .btns{display:flex; gap:8px; flex-wrap:wrap; align-items:center;}
    .nav-btn{padding:8px 12px;border-radius:8px;border:1px solid var(--line);background:#fff;cursor:pointer;font-weight:600;}
    .nav-btn:hover{box-shadow:0 4px 10px rgba(0,0,0,0.06);}
    .nav-btn.danger{border-color:#ef4444;color:#ef4444;}
    .agent-name{font-weight:800;margin-right:6px;}
    .header{display:flex;gap:12px;align-items:center;justify-content:space-between;position:sticky;top:0;background:#fff;border-bottom:1px solid var(--line);padding:10px 16px;height:58px;}
    .header .brand{font-weight:800;letter-spacing:.2px;font-family:'Poppins', system-ui, -apple-system, Segoe UI, Roboto, Inter, Ubuntu, 'Helvetica Neue', Arial; font-size:150%;}
    .header .brand .logo-word{font-family:'Orbitron', system-ui, -apple-system, Segoe UI, Roboto, Inter, Ubuntu, 'Helvetica Neue', Arial; color:#00C6FF; font-weight:800; font-size:200%;}
    .ready{position:fixed;right:12px;bottom:12px;background:#10b981;color:#fff;padding:6px 10px;border-radius:8px;font-size:12px;z-index:9999;box-shadow:0 6px 16px rgba(0,0,0,.2);}
    .connection-status{padding:4px 8px;border-radius:6px;font-size:11px;font-weight:600;}
    .connection-status.connected{background:#dcfce7;color:#166534;}
    .connection-status.disconnected{background:#fee2e2;color:#dc2626;}
  </style>
</head>
<body>
  <div class="header">
    <div class="brand"><span class="logo-word">LOGOS AI</span> — Human Guidance & Oversight</div>
    <div class="btns">
      <div id="connectionStatus" class="connection-status disconnected">Connecting...</div>
      <span class="agent-name"><strong>Chris Jones — HGI</strong></span>
      <a class="nav-btn">Logout</a>
      <a class="nav-btn">Admin</a>
      <a class="nav-btn">Client Settings</a>
      <a class="nav-btn danger">Urgent Support</a>
      <a class="nav-btn">Assignments</a>
    </div>
  </div>

  <div class="layout" id="layout">
    <!-- Inactive Clients Column (Left) -->
    <div class="col" id="inactive-col" style="grid-column:1;grid-row:1;">
      <h2>Inactive Clients <span id="inactiveCount" class="count">(0)</span></h2>
      <p class="legend">Format: <strong>Name</strong> <span class="id">• RegionID</span> — flags & stats</p>
      <div id="inactiveClients">
        <!-- Inactive clients populated by JavaScript -->
      </div>
    </div>

    <!-- Vertical Resizer -->
    <div class="resizer v" data-col="1"></div>

    <!-- Active Clients Column (Middle) -->
    <div class="col" id="active-col" style="grid-column:3;grid-row:1;">
      <h2>Active Calls <span id="activeCount" class="count">(0)</span></h2>
      <p class="legend">Live conversations requiring guidance</p>
      <div id="activeClients">
        <!-- Active clients populated by JavaScript -->
      </div>
    </div>

    <!-- Vertical Resizer -->
    <div class="resizer v" data-col="2"></div>

    <!-- Right Panel -->
    <div class="right" style="grid-column:5;grid-row:1;">
      <!-- Live Transcript -->
      <div class="pane">
        <div class="title">
          <div class="title-left">
            <h3 id="liveName">Select a client</h3>
            <span id="liveId" style="color:#6b7280;font-size:13px;"></span>
          </div>
          <div class="btns">
            <button class="ghost-btn" id="takeOverBtn">Take Over</button>
            <button class="ghost-btn" id="sessionHistoryBtn">Session History</button>
          </div>
        </div>
        <div class="stats">
          <span id="stat-duration">Duration: --</span>
          <span id="stat-total">Total calls: --</span>
          <span id="stat-avg">Avg: --</span>
          <span id="stat-health">--</span>
          <span id="stat-progress">Progress: --%</span>
        </div>
        <div id="transcript" class="transcript">
          <div class="msg" style="text-align:center;color:#6b7280;padding:40px;">
            Select an active call to view live transcript
          </div>
        </div>
      </div>

      <!-- Horizontal Resizer -->
      <div class="resizer h"></div>

      <!-- Human Guidance Panel -->
      <div class="pane">
        <h3>Human Guidance & Intervention</h3>
        <div class="instruct-box">
          <textarea id="guidanceText" placeholder="Type guidance for the AI here... 

Examples:
- Ask about their sleep patterns
- Suggest a gentle breathing exercise  
- Validate their feelings about work stress
- Guide toward self-reflection on coping strategies"></textarea>
          <button id="sendGuidanceBtn">Send Guidance</button>
        </div>
      </div>
    </div>
  </div>

  <div id="ready" class="ready" style="display:none;">Dashboard Ready</div>

  <script>
    // WebSocket connection for real-time updates
    let ws = null;
    let selectedSession = null;
    let callStartTime = {};
    
    function connectWebSocket() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = protocol + '//' + window.location.host + '/dashboard-ws';
      
      try {
        ws = new WebSocket(wsUrl);
        
        ws.onopen = function() {
          console.log('Dashboard WebSocket connected');
          updateConnectionStatus(true);
          document.getElementById('ready').style.display = 'block';
        };
        
        ws.onmessage = function(event) {
          try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
          } catch (e) {
            console.error('Error parsing WebSocket message:', e);
          }
        };
        
        ws.onclose = function() {
          console.log('Dashboard WebSocket disconnected');
          updateConnectionStatus(false);
          document.getElementById('ready').style.display = 'none';
          setTimeout(connectWebSocket, 3000);
        };
        
        ws.onerror = function(error) {
          console.error('WebSocket error:', error);
          updateConnectionStatus(false);
        };
        
      } catch (e) {
        console.error('Error creating WebSocket:', e);
        updateConnectionStatus(false);
        setTimeout(connectWebSocket, 3000);
      }
    }
    
    function updateConnectionStatus(connected) {
      const statusEl = document.getElementById('connectionStatus');
      if (connected) {
        statusEl.textContent = 'Connected';
        statusEl.className = 'connection-status connected';
      } else {
        statusEl.textContent = 'Disconnected';
        statusEl.className = 'connection-status disconnected';
      }
    }
    
    function handleWebSocketMessage(data) {
      console.log('📨 Dashboard received:', data.type, data);
      switch (data.type) {
        case 'call_started':
          console.log('👤 Adding active client:', data.caller_phone, data.call_sid);
          addActiveClient(data);
          break;
        case 'call_ended':
          console.log('🛑 Removing active client:', data.call_sid);
          removeActiveClient(data.call_sid);
          break;
        case 'transcript_update':
          console.log('💬 Transcript update:', data.role, data.content.substring(0, 50));
          updateTranscript(data);
          break;
        case 'inactive_clients':
          console.log('📋 Inactive clients update, count:', data.clients.length);
          loadInactiveClients(data.clients);
          break;
        case 'active_sessions':
          console.log('🔴 Active sessions:', data.sessions);
          break;
        default:
          console.log('❓ Unknown message type:', data.type);
      }
    }
    
    function loadInactiveClients(clients) {
      const inactiveClients = document.getElementById('inactiveClients');
      inactiveClients.innerHTML = '';
      
      clients.forEach(client => {
        const clientElement = document.createElement('div');
        clientElement.className = 'client';
        clientElement.dataset.clientId = client.id;
        clientElement.innerHTML = `
          <div class="top">
            <div class="name">${client.name}<span class="id"> • ${client.id}</span></div>
            <span class="chip ${client.flag.toLowerCase()}">${client.flag}</span>
          </div>
          <div class="meta">
            <span>${client.calls} calls</span><span>avg ${client.avg}m</span><span>last: ${client.last}</span>
          </div>
          <div class="bar"><span style="width:${client.progress}%"></span></div>
        `;
        
        clientElement.addEventListener('click', () => selectInactiveClient(client));
        inactiveClients.appendChild(clientElement);
      });
      
      document.getElementById('inactiveCount').textContent = `(${clients.length})`;
    }
    
    function selectInactiveClient(client) {
      document.querySelectorAll('#inactive-col .client').forEach(c => c.classList.remove('selected'));
      document.querySelector(`[data-client-id="${client.id}"]`).classList.add('selected');
      
      document.getElementById('liveName').textContent = client.name;
      document.getElementById('liveId').textContent = client.id;
      document.getElementById('stat-duration').textContent = 'Duration: --';
      document.getElementById('stat-total').textContent = `Total calls: ${client.calls}`;
      document.getElementById('stat-avg').textContent = `Avg: ${client.avg}m`;
      document.getElementById('stat-health').textContent = client.health;
      document.getElementById('stat-progress').textContent = `Progress: ${client.progress}%`;
      
      document.getElementById('transcript').innerHTML = `
        <div class="msg" style="text-align:center;color:#6b7280;padding:40px;">
          Historical session data for ${client.name}<br>
          <small>Select an active call to view live transcript</small>
        </div>
      `;
    }
    
    function addActiveClient(callData) {
      console.log('➕ addActiveClient called with:', callData);
      const activeClients = document.getElementById('activeClients');
      callStartTime[callData.call_sid] = Date.now();
      // Check if client already exists to prevent duplicates
      const existingClient = document.querySelector(`[data-call-sid="${callData.call_sid}"]`);
      if (existingClient) {
        console.log('⚠️ Client already exists, skipping duplicate');
        return; // Don't add duplicates
      }
      const clientElement = document.createElement('div');
      clientElement.className = 'client';
      clientElement.dataset.callSid = callData.call_sid;
      clientElement.innerHTML = `
        <div class="top">
          <div class="name">${callData.caller_phone}<span class="id"> • ${callData.call_sid.slice(-6)}</span></div>
          <span class="chip live">LIVE</span>
        </div>
        <div class="meta">
          <span>Active now</span><span class="duration">Duration: 0m 0s</span>
        </div>
      `;

      clientElement.addEventListener('click', () => selectSession(callData.call_sid, callData.caller_phone));
      activeClients.appendChild(clientElement);
      console.log('✅ Active client added to DOM');

      updateActiveCount();

      // Auto-select the first active call
      const activeCount = document.querySelectorAll('#activeClients .client').length;
      console.log('📊 Active clients count:', activeCount);
      if (activeCount === 1) {
        console.log('🎯 Auto-selecting first active call');
        selectSession(callData.call_sid, callData.caller_phone);
      }
    }
    
    function removeActiveClient(callSid) {
      const clientElement = document.querySelector(`[data-call-sid="${callSid}"]`);
      if (clientElement) {
        clientElement.remove();
        updateActiveCount();
        delete callStartTime[callSid];
      }
    }
    
    function updateActiveCount() {
      const activeCount = document.querySelectorAll('#activeClients .client').length;
      document.getElementById('activeCount').textContent = `(${activeCount})`;
    }
    
    function selectSession(callSid, callerPhone) {
      console.log('🎯 Selecting session:', callSid, 'for', callerPhone);
      selectedSession = callSid;
      document.querySelectorAll('.client').forEach(c => c.classList.remove('selected'));
      const clientEl = document.querySelector(`[data-call-sid="${callSid}"]`);
      if (clientEl) {
        clientEl.classList.add('selected');
      }

      document.getElementById('liveName').textContent = callerPhone;
      document.getElementById('liveId').textContent = callSid;

      document.getElementById('transcript').innerHTML = `
        <div class="msg" style="text-align:center;color:#6b7280;padding:20px;">
          Live transcript will appear here once conversation starts...
        </div>
      `;
      console.log('✅ Session selected. selectedSession =', selectedSession);
    }
    
    function updateTranscript(data) {
      console.log('📝 updateTranscript called. selectedSession:', selectedSession, 'data.call_sid:', data.call_sid);
      if (selectedSession !== data.call_sid) {
        console.log('⏭️ Skipping transcript update - session mismatch');
        return;
      }

      const transcript = document.getElementById('transcript');

      if (transcript.children.length === 1 && transcript.children[0].style.textAlign === 'center') {
        transcript.innerHTML = '';
      }

      const msgElement = document.createElement('div');
      msgElement.className = `msg ${data.role}`;
      const time = new Date().toLocaleTimeString();
      msgElement.innerHTML = `
        <div class="time">${time} • ${data.role.toUpperCase()}</div>
        ${data.content}
      `;

      transcript.appendChild(msgElement);
      transcript.scrollTop = transcript.scrollHeight;
      console.log('✅ Transcript updated with', data.role, 'message');
    }
    
    function sendGuidance() {
      if (!selectedSession || !ws) {
        alert('Please select an active session and ensure WebSocket is connected');
        return;
      }
      
      const guidance = document.getElementById('guidanceText').value.trim();
      if (!guidance) {
        alert('Please enter guidance text');
        return;
      }
      
      ws.send(JSON.stringify({
        type: 'human_guidance',
        session_id: selectedSession,
        guidance: guidance
      }));
      
      document.getElementById('guidanceText').value = '';
    }
    function openSessionHistory() {
      const nameEl = document.getElementById('liveName');
      if (!nameEl) {
        alert('No client selected');
        return;
      }
      const phone = nameEl.textContent.trim();
      if (!phone || phone === 'Select a client') {
        alert('No client selected');
        return;
      }

      // Open popup window
      const popup = window.open('', 'SessionHistory', 'width=800,height=600,scrollbars=yes');
      popup.document.write('<html><head><title>Session History - ' + phone + '</title>');
      popup.document.write('<style>body{font-family:system-ui;padding:20px;background:#f9fafb;}h1{margin:0 0 20px;}');
      popup.document.write('.loading{text-align:center;color:#6b7280;padding:40px;}.session{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-bottom:12px;cursor:pointer;}');
      popup.document.write('.session:hover{box-shadow:0 4px 12px rgba(0,0,0,0.1);}.session-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;}');
      popup.document.write('.session-id{font-weight:600;font-size:14px;}.session-date{color:#6b7280;font-size:12px;}.session-meta{color:#6b7280;font-size:13px;}');
      popup.document.write('.error{color:#ef4444;padding:20px;text-align:center;}</style></head><body>');
      popup.document.write('<h1>Session History: ' + phone + '</h1>');
      popup.document.write('<div class="loading">Loading sessions...</div>');
      popup.document.write('</body></html>');

      // Fetch session data
      const url = `/cleanup?action=list_sessions&phone=${encodeURIComponent(phone)}`;
      fetch(url)
        .then(response => response.json())
        .then(data => {
          let html = '<h1>Session History: ' + phone + '</h1>';
          if (data.sessions && data.sessions.length > 0) {
            html += '<p style="color:#6b7280;margin-bottom:20px;">Total sessions: ' + data.count + '</p>';
            data.sessions.forEach(session => {
              const date = new Date(session.created_at).toLocaleString();
              html += "<div class='session' onclick='viewSessionTranscript(\"" + session.session_id + "\")'>";
              html += "<div class='session-header'>";
              html += "<span class='session-id'>Session #" + session.session_number + "</span>";
              html += "<span class='session-date'>" + date + "</span>";
              html += "</div>";
              html += "<div class='session-meta'>Click to view full conversation transcript</div>";
              html += "</div>";
            });
          } else {
            html += '<div class="error">No session history found for this caller.</div>';
          }

          // Add function to view transcript
          html += '<script>';
          html += 'function viewSessionTranscript(sessionId) {';
          html += '  const transcriptUrl = "/cleanup?action=get_session_transcript&session_id=" + sessionId;';
          html += '  fetch(transcriptUrl)';
          html += '    .then(response => response.json())';
          html += '    .then(data => {';
          html += '      let transcriptHtml = "<h1>Session #" + data.session_number + " Transcript</h1>";';
          html += '      transcriptHtml += "<p style=\\"color:#6b7280;margin-bottom:20px;\\">";';
          html += '      transcriptHtml += "Date: " + new Date(data.start_time).toLocaleString() + "<br>";';
          html += '      if (data.duration_seconds) transcriptHtml += "Duration: " + Math.floor(data.duration_seconds / 60) + "m " + (data.duration_seconds % 60) + "s<br>";';
          html += '      transcriptHtml += "</p>";';
          html += '      transcriptHtml += "<button onclick=\\"history.back()\\" style=\\"margin-bottom:20px;padding:8px 16px;border-radius:6px;border:1px solid #2563eb;background:#fff;color:#2563eb;cursor:pointer;\\">← Back to Sessions</button>";';
          html += '      if (data.transcript && data.transcript.length > 0) {';
          html += '        transcriptHtml += "<div style=\\"display:flex;flex-direction:column;gap:12px;\\">";';
          html += '        data.transcript.forEach(msg => {';
          html += '          const bgColor = msg.speaker == \\"ai\\" ? \\"#eff6ff\\" : \\"#fafafa\\";';
          html += '          const borderColor = msg.speaker == \\"ai\\" ? \\"#dbeafe\\" : \\"#e4e4e7\\";';
          html += '          transcriptHtml += "<div style=\\"background:" + bgColor + ";border:1px solid " + borderColor + ";border-radius:8px;padding:12px;\\">";';
          html += '          transcriptHtml += "<div style=\\"font-size:11px;color:#6b7280;margin-bottom:6px;\\">" + msg.speaker.toUpperCase();';
          html += '          if (msg.timestamp) transcriptHtml += " &bull; " + new Date(msg.timestamp).toLocaleTimeString();';
          html += '          transcriptHtml += "</div>";';
          html += '          transcriptHtml += "<div>" + (msg.content || \"\") + "</div>";';
          html += '          transcriptHtml += "</div>";';
          html += '        });';
          html += '        transcriptHtml += "</div>";';
          html += '      } else {';
          html += '        transcriptHtml += "<div class=\\"error\\">No transcript available for this session.</div>";';
          html += '      }';
          html += '      document.body.innerHTML = transcriptHtml;';
          html += '    })';
          html += '    .catch(error => {';
          html += '      document.body.innerHTML = "<h1>Error</h1><div class=\\"error\\">Failed to load transcript: " + error.message + "</div>";';
          html += '    });';
          html += '}';
          html += '</script>';

          popup.document.body.innerHTML = html;
        })
        .catch(error => {
          popup.document.body.innerHTML = '<h1>Session History: ' + phone + '</h1><div class="error">Error loading session history: ' + error.message + '</div>';
        });
    }
     
      // Update call durations every second

    // Update call durations every second
    setInterval(() => {
      Object.keys(callStartTime).forEach(callSid => {
        const element = document.querySelector(`[data-call-sid="${callSid}"] .duration`);
        if (element) {
          const elapsed = Math.floor((Date.now() - callStartTime[callSid]) / 1000);
          const minutes = Math.floor(elapsed / 60);
          const seconds = elapsed % 60;
          element.textContent = `Duration: ${minutes}m ${seconds}s`;
        }
      });
    }, 1000);
    
    // Event listeners
    document.getElementById('sendGuidanceBtn').addEventListener('click', sendGuidance);
    document.getElementById('sessionHistoryBtn').addEventListener('click', openSessionHistory);
    
    // Initialize dashboard
    connectWebSocket();
  </script>
</body>
</html>
    '''
    
    return web.Response(text=dashboard_html, content_type='text/html')

async def bulk_cleanup_handler(request):
    """HTTP endpoint for bulk cleanup operations"""
    if not db:
        return web.Response(text="Database not available", status=500)
    
    def normalize_phone(phone):
        """Normalize phone number format"""
        if not phone:
            return None
        phone = phone.strip()
        phone = phone.replace(" ", "")  # Remove all spaces
        
        # Handle different formats
        if phone.startswith("0"):
            phone = "+61" + phone[1:]
        elif phone.startswith("61") and not phone.startswith("+"):
            phone = "+" + phone
        elif not phone.startswith("+") and phone.isdigit():
            phone = "+61" + phone
            
        return phone
    
    try:
        # Get query parameters
        params = request.query
        action = params.get('action', '')
        raw_phone = params.get('phone', '')
        days_old = int(params.get('days', 7))
        
        # Normalize phone number properly
        normalized_phone = normalize_phone(raw_phone) if raw_phone else None
        
        if action == 'count_sessions':
            if normalized_phone:
                count = await db.count_sessions_by_phone(normalized_phone)
                return web.Response(text=f"Phone {normalized_phone} has {count} sessions")
            else:
                total_count = await db.count_all_sessions()
                return web.Response(text=f"Total sessions in database: {total_count}")
        
        elif action == 'list_sessions':
            if normalized_phone:
                sessions = await db.get_sessions_by_phone(normalized_phone)
                session_list = []
                for session in sessions:
                    session_dict = {
                        'session_id': str(session[0]),
                        'caller_phone': session[1],
                        'created_at': str(session[2]),
                        'session_number': session[3]
                    }
                    session_list.append(session_dict)

                return web.json_response({
                    'phone': normalized_phone,
                    'sessions': session_list,
                    'count': len(session_list)
                })
            else:
                return web.Response(text="Phone parameter required for list_sessions", status=400)

        elif action == 'get_session_transcript':
            session_id = params.get('session_id', '')
            if not session_id:
                return web.Response(text="session_id parameter required", status=400)

            try:
                # Query database for session transcript
                async with db.pool.acquire() as conn:
                    session = await conn.fetchrow('''
                        SELECT
                            session_id,
                            caller_phone,
                            start_time,
                            end_time,
                            duration_seconds,
                            full_transcript,
                            session_number
                        FROM sessions
                        WHERE session_id = $1
                    ''', session_id)

                    if not session:
                        return web.Response(text="Session not found", status=404)

                    # Parse transcript
                    transcript = session['full_transcript']
                    if isinstance(transcript, str):
                        import json
                        transcript = json.loads(transcript)

                    return web.json_response({
                        'session_id': str(session['session_id']),
                        'caller_phone': session['caller_phone'],
                        'start_time': str(session['start_time']),
                        'end_time': str(session['end_time']) if session['end_time'] else None,
                        'duration_seconds': session['duration_seconds'],
                        'session_number': session['session_number'],
                        'transcript': transcript or []
                    })
            except Exception as e:
                print(f"Error fetching session transcript: {e}")
                return web.Response(text=f"Error: {str(e)}", status=500)
        
        elif action == 'delete_old_sessions':
            deleted_count = await db.delete_old_sessions(days_old)
            return web.Response(text=f"Deleted {deleted_count} sessions older than {days_old} days")
        
        elif action == 'delete_phone_sessions':
            if normalized_phone:
                deleted_count = await db.delete_sessions_by_phone(normalized_phone)
                return web.Response(text=f"Deleted {deleted_count} sessions for phone {normalized_phone}")
            else:
                return web.Response(text="Phone parameter required for delete_phone_sessions", status=400)
        
        elif action == 'cleanup_empty_sessions':
            deleted_count = await db.cleanup_empty_sessions()
            return web.Response(text=f"Deleted {deleted_count} empty sessions (no messages)")
        
        else:
            help_text = """
Available cleanup actions:
- count_sessions?phone=PHONE - Count sessions for specific phone
- count_sessions - Count all sessions  
- list_sessions?phone=PHONE - List sessions for specific phone (JSON)
- delete_old_sessions?days=N - Delete sessions older than N days (default 7)
- delete_phone_sessions?phone=PHONE - Delete all sessions for specific phone
- cleanup_empty_sessions - Delete sessions with no messages

Phone formats supported: +61412345678, 0412345678, 61412345678, 412345678
            """
            return web.Response(text=help_text, content_type='text/plain')
        
    except Exception as e:
        print(f"Error in bulk cleanup: {e}")
        return web.Response(text=f"Error: {e}", status=500)

async def websocket_handler(request):
    """Handle Twilio WebSocket connections for voice processing"""
    ws = web.WebSocketResponse(protocols=['voice-bridge'])
    await ws.prepare(request)
    print("🔌 WebSocket connection established")
    
    # Initialize variables for this specific call
    audio_queue = asyncio.Queue()
    streamsid_queue = asyncio.Queue()
    session_id = None
    caller_context = None
    caller_phone = None
    call_sid = None
    
    # We'll wait for caller info from Twilio start event before configuring Deepgram
    caller_info_ready = asyncio.Event()

    try:
        async def twilio_receiver():
            """Receive audio from Twilio and buffer for Deepgram"""
            nonlocal session_id, caller_phone, call_sid
            print("📱 twilio_receiver started")
            BUFFER_SIZE = 20 * 160  # Buffer 20 messages (0.4 seconds)
            inbuffer = bytearray(b"")
            
            try:
                async for msg in ws:
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
                                
                                # Extract caller info from parameters (sent via TwiML)
                                custom_params = start.get("customParameters", {})
                                if custom_params:
                                    caller_phone = custom_params.get("caller", "unknown")
                                    call_sid = custom_params.get("callsid", actual_call_sid)
                                    print(f"📱 Updated caller info from parameters: {caller_phone}")
                                    
                                    # Signal that caller info is ready
                                    caller_info_ready.set()
                                    
                                    # Update active sessions
                                    if call_sid in active_sessions:
                                        active_sessions[call_sid]['status'] = 'active'
                                    
                                                                    
                                await streamsid_queue.put(streamsid)
                                print(f"📨 StreamSid queued: {streamsid}")
                                
                            elif data["event"] == "media" and "media" in data:
                                # Buffer audio data
                                chunk = base64.b64decode(data["media"]["payload"])
                                inbuffer.extend(chunk)
                                
                                # Send to Deepgram when buffer is full
                                if len(inbuffer) >= BUFFER_SIZE:
                                    await audio_queue.put(bytes(inbuffer))
                                    inbuffer.clear()
                                    
                            elif data["event"] == "stop":
                                print("🛑 Call ended by Twilio")
                                # Send any remaining buffered audio
                                if inbuffer:
                                    await audio_queue.put(bytes(inbuffer))
                                                              
                                # Move call from active to inactive list and notify dashboards
                                if call_sid:
                                    # Get session info if we have it
                                    session_info = active_sessions.get(call_sid, {})
                                    start_ts = session_info.get('timestamp')
                                    duration_sec = time.time() - start_ts if start_ts else 0
                                     
                                    # Derive phone / display name
                                    phone = caller_phone or session_info.get('caller_phone') or "Unknown"
                                     
                                    # Build a simple inactive client summary with last 6 chars of call_sid as ID
                                    inactive_clients.append({
                                        'id': call_sid[-8:],  # Use last 8 chars for readability
                                        'name': phone,
                                        'flag': 'Casual',
                                        'calls': 1,
                                        'avg': int(duration_sec // 60) if duration_sec else 0,
                                        'last': 'Just now',
                                        'progress': 50,
                                        'health': 'Stable',
                                    })
                                     
                                    # Remove from active sessions if present
                                    if call_sid in active_sessions:
                                        del active_sessions[call_sid]
                                     
                                    # Notify dashboards that call ended
                                    await broadcast_to_dashboards({
                                        'type': 'call_ended',
                                        'call_sid': call_sid
                                    })
                                     
                                    # Send updated inactive clients list
                                    await broadcast_to_dashboards({
                                        'type': 'inactive_clients',
                                        'clients': inactive_clients
                                    })

                                
                        except json.JSONDecodeError as e:
                            print(f"Failed to decode JSON: {e}")
                        except Exception as e:
                            print(f"Error processing Twilio message: {e}")
                    
                    elif msg.type == web.WSMsgType.ERROR:
                        print(f"WebSocket error: {msg.data}")
                        break
                        
            except Exception as e:
                print(f"Error in twilio_receiver: {e}")

        # Start Twilio receiver first to get caller info
        twilio_task = asyncio.create_task(twilio_receiver())
        
        # Wait for caller info before setting up Deepgram
        await caller_info_ready.wait()
        
        # Now load database context with caller info
        ai_prompt = VOICE_AGENT_PERSONALITY  # Start with base prompt
        
        if db and caller_phone != 'unknown':
            try:
                print(f"🔍 DEBUG: Loading context for {caller_phone}")
                caller_data = await db.get_or_create_caller(caller_phone, call_sid or "websocket-call")
                session_id = caller_data['session_id']
                caller_context = caller_data['context']
                
                print(f"💾 Loaded caller context - Session {caller_data['session_number']}")
                
                if caller_data['context']['recent_sessions']:
                    print(f"📚 Found {len(caller_data['context']['recent_sessions'])} previous sessions")
                    
                    # Format ACTUAL conversation content instead of generic summaries
                    actual_context = format_actual_conversation_context(caller_data['context']['recent_sessions'])
                    
                    if actual_context:
                        # Update AI prompt with REAL conversation history
                        ai_prompt = f"""{VOICE_AGENT_PERSONALITY}

{actual_context}

Remember: Only refer to what this caller actually said in previous conversations. If you're unsure about details, ask them to remind you instead of guessing."""
                        
                        print(f"🧠 AI prompt enhanced with ACTUAL conversation content")
                    
            except Exception as e:
                print(f"❌ Database error: {e}")

        # Check for human guidance
        if session_id and session_id in human_guidance_queue:
            guidance = human_guidance_queue[session_id]
            ai_prompt += f"\n\nHUMAN GUIDANCE: {guidance['guidance']}"
            print(f"👤 Including human guidance: {guidance['guidance']}")
            del human_guidance_queue[session_id]

        # NOW set up Deepgram with the complete AI prompt
        async with sts_connect() as sts_ws:
            # Send configuration to Deepgram with complete prompt including context
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
                                            # Map Deepgram roles to database-compatible roles
                                            db_role = 'ai' if role == 'assistant' else role
                                            await db.add_message(session_id, db_role, content, decoded)
                                            print(f"💬 Stored message: {db_role} - {content[:50]}...")
                                            
                                        except Exception as e:
                                            print(f"Error storing message: {e}")
                                        
                                        # Broadcast to dashboard (outside database transaction)
                                        try:
                                            await broadcast_to_dashboards({
                                                'type': 'transcript_update',
                                                'session_id': str(session_id),      # <-- Convert UUID to string
                                                'call_sid': call_sid,
                                                'role': db_role,
                                                'content': content,
                                                'timestamp': time.time()
                                            })
                                        except Exception as e:
                                            print(f"Error broadcasting to dashboard: {e}")
                                            
                                                                       
                                if decoded['type'] == 'UserStartedSpeaking':
                                    # Handle barge-in
                                    clear_message = {
                                        "event": "clear",
                                        "streamSid": streamsid
                                    }
                                    await ws.send_str(json.dumps(clear_message))
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
                            await ws.send_str(json.dumps(media_message))

                except Exception as e:
                    print(f"Error in sts_receiver: {e}")

            # Run Deepgram tasks with the already-running Twilio task
            await asyncio.gather(
                sts_sender(),
                sts_receiver(),
                twilio_task,
                return_exceptions=True
            )

            # Fallback: if the call ended without a clean 'stop' event,
            # make sure it is moved to inactive clients.
            if call_sid:
                already_inactive = any(c.get('id') == call_sid for c in inactive_clients)
                if not already_inactive:
                    session_info = active_sessions.get(call_sid, {})
                    start_ts = session_info.get('timestamp')
                    duration_sec = time.time() - start_ts if start_ts else 0

                    phone = caller_phone or session_info.get('caller_phone') or "Unknown"

                    inactive_clients.append({
                        'id': call_sid[-8:],  # Use last 8 chars for readability
                        'name': phone,
                        'flag': 'Casual',
                        'calls': 1,
                        'avg': int(duration_sec // 60) if duration_sec else 0,
                        'last': 'Just now',
                        'progress': 50,
                        'health': 'Stable',
                    })

                    if call_sid in active_sessions:
                        del active_sessions[call_sid]

                    await broadcast_to_dashboards({
                        'type': 'call_ended',
                        'call_sid': call_sid
                    })

                    await broadcast_to_dashboards({
                        'type': 'inactive_clients',
                        'clients': inactive_clients
                    })


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
        text="Twilio-Deepgram Bridge Server with Human Guidance Dashboard", 
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
    
    # Setup CORS
    cors = cors_setup(app, defaults={
        "*": ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*"
        )
    })
    
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
    app.router.add_post('/webhook/voice', voice_webhook_handler)  # Twilio voice webhook
    app.router.add_get('/twilio', websocket_handler)  # WebSocket endpoint for calls
    app.router.add_get('/cleanup', bulk_cleanup_handler)  # Bulk cleanup operations
    
    # Dashboard routes
    app.router.add_get('/dashboard', dashboard_handler)  # Dashboard HTML page
    app.router.add_get('/dashboard-ws', dashboard_websocket_handler)  # Dashboard WebSocket
    
    # Add CORS to all routes
    for route in list(app.router.routes()):
        cors.add(route)
    
    return app

def main():
    """Main entry point"""
    # Get port from environment (Railway sets this automatically)
    port = int(os.environ.get("PORT", 5000))
    
    print(f"🚀 Starting LOGOS AI Server with Dashboard on port {port}")
    print(f"🔍 Health check endpoint: http://0.0.0.0:{port}/health")
    print(f"📞 Voice webhook: http://0.0.0.0:{port}/webhook/voice")
    print(f"🔌 WebSocket endpoint: ws://0.0.0.0:{port}/twilio")
    print(f"🗑️ Cleanup endpoint: http://0.0.0.0:{port}/cleanup")
    print(f"🖥️ Dashboard: http://0.0.0.0:{port}/dashboard")
    print(f"📡 Dashboard WebSocket: ws://0.0.0.0:{port}/dashboard-ws")
    
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
        print("💬 AI memory with comprehensive debug logging enabled!")
        print("🗑️ Use /cleanup endpoint for bulk database operations")
        print("🖥️ Human Guidance Dashboard available at /dashboard")
        
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
