"""J.A.R.V.I.S. agent server — uses anthropic SDK for tool-use + SSE streaming."""
import json, os, socket, subprocess, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    import anthropic
    _SDK_OK = True
except ImportError:
    _SDK_OK = False

PORT = int(os.environ.get('PORT', 8181))
MODEL = 'claude-haiku-5-5'

SYSTEM = """You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), Sir's personal AI assistant, running directly on his computer.

PERSONA:
- Address the user exclusively as "Sir". Never their name, never "you".
- Maintain a dry, witty, polite, refined British cadence at all times. Subtle dry wit encouraged.
- Be precise and efficient. Never break character.

PRIMARY PURPOSE — PROMPT CRAFTING:
Sir uses you primarily to craft precise, well-formed prompts and instructions. When Sir gives a rough idea, help him articulate it into something precise and detailed. Ask clarifying questions with ask_user when you need specifics. Present the enhanced prompt clearly.

ASK_USER TOOL:
- Use ask_user when you need specific information from Sir before proceeding.
- Keep questions focused; 2–4 clear options max.
- After calling ask_user, stop — wait for Sir's response.

COMPUTER AUTOMATION:
- Use run_command, open_app, search_web, and notify to control Sir's computer.
- Narrate what you're doing step by step.
- Use notify when a long task completes.

GOAL COMPILER — only when Sir says "generate a goal [objective]":
/goal [Primary Objective]

Stack: [technologies]

Files:
  - [file]: [purpose]

Acceptance Rules:
  - [rule]

Logging Hooks:
  - [hook]

DISCORD — when Sir asks you to send to Discord:
Output on its own line: DISCORD_SEND: [message]
Then confirm verbally."""

TOOLS_DEF = [
    {
        "name": "ask_user",
        "description": "Ask Sir a clarifying question with multiple-choice options. Use this whenever you need specific information before proceeding. After calling this, stop — Sir will answer and you will continue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The full question to ask"},
                "header": {"type": "string", "description": "Short 2-4 word topic label shown as a chip (e.g. 'App Type', 'Color Theme', 'Target Platform')"},
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-4 concise option labels for Sir to choose from",
                    "minItems": 2,
                    "maxItems": 4
                }
            },
            "required": ["question", "header", "options"]
        }
    },
    {
        "name": "run_command",
        "description": "Execute a PowerShell command on Sir's Windows computer. Use for file operations, system info, app control, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The PowerShell command to execute"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "open_app",
        "description": "Open an application on Sir's computer by name (e.g. 'chrome', 'spotify', 'notepad', 'calculator', 'vscode', 'explorer')",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Application name"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "search_web",
        "description": "Open a Google search in Sir's browser",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "notify",
        "description": "Send a Windows desktop notification to Sir (use when a long background task completes)",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "message": {"type": "string"}
            },
            "required": ["title", "message"]
        }
    }
]

APP_MAP = {
    'chrome': 'chrome', 'google chrome': 'chrome',
    'edge': 'msedge', 'microsoft edge': 'msedge',
    'firefox': 'firefox',
    'notepad': 'notepad',
    'vscode': 'code', 'vs code': 'code', 'visual studio code': 'code',
    'spotify': 'spotify',
    'calculator': 'calc',
    'explorer': 'explorer', 'file explorer': 'explorer',
    'powershell': 'powershell',
    'terminal': 'wt', 'windows terminal': 'wt',
    'discord': 'discord',
    'steam': 'steam',
    'paint': 'mspaint',
}


def tool_run_command(command):
    try:
        r = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
            capture_output=True, text=True, timeout=30
        )
        return {'success': r.returncode == 0,
                'output': r.stdout[:2000] if r.stdout else '',
                'error':  r.stderr[:300]  if r.stderr  else ''}
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'Timed out after 30s'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def tool_open_app(name):
    try:
        cmd = APP_MAP.get(name.lower().strip(), name)
        subprocess.Popen(cmd, shell=True)
        return {'success': True, 'message': f'Opened {name}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def tool_search_web(query):
    try:
        webbrowser.open(f'https://www.google.com/search?q={query}')
        return {'success': True, 'message': f'Searching: {query}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def tool_notify(title, message):
    try:
        t = title.replace('"', '').replace("'", '')
        m = message.replace('"', '').replace("'", '')
        ps = (
            'Add-Type -AssemblyName System.Windows.Forms; '
            '$n = New-Object System.Windows.Forms.NotifyIcon; '
            '$n.Icon = [System.Drawing.SystemIcons]::Information; '
            '$n.Visible = $true; '
            f'$n.ShowBalloonTip(5000, "{t}", "{m}", '
            '[System.Windows.Forms.ToolTipIcon]::Info); '
            'Start-Sleep -Seconds 6; $n.Dispose()'
        )
        subprocess.Popen(
            ['powershell', '-WindowStyle', 'Hidden', '-Command', ps],
            creationflags=0x08000000
        )
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


EXECUTORS = {
    'run_command': lambda i: tool_run_command(i['command']),
    'open_app':    lambda i: tool_open_app(i['name']),
    'search_web':  lambda i: tool_search_web(i['query']),
    'notify':      lambda i: tool_notify(i['title'], i['message']),
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        p = self.path.split('?')[0]
        if p in ('/', '/jarvis.html'):
            self._file('jarvis.html', 'text/html; charset=utf-8')
        elif p == '/manifest.json':
            self._file('manifest.json', 'application/manifest+json')
        elif p in ('/icon-192.png', '/icon-512.png'):
            self._icon(192 if '192' in p else 512)
        else:
            self.send_response(404); self.end_headers()

    def _file(self, name, ct):
        try:
            with open(name, 'rb') as f: data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', len(data))
            self.end_headers(); self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404); self.end_headers()

    def _icon(self, size):
        cx = size // 2
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">'
            f'<rect width="{size}" height="{size}" fill="#050507"/>'
            f'<circle cx="{cx}" cy="{cx}" r="{int(size*.42)}" fill="none" stroke="#FFB700" stroke-width="{max(2,size//64)}"/>'
            f'<circle cx="{cx}" cy="{cx}" r="{int(size*.30)}" fill="none" stroke="#FFCC00" stroke-width="{max(2,size//80)}"/>'
            f'<circle cx="{cx}" cy="{cx}" r="{int(size*.14)}" fill="#FFB700"/>'
            f'</svg>'
        ).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'image/svg+xml')
        self.send_header('Content-Length', len(svg))
        self.end_headers(); self.wfile.write(svg)

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST,GET,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,x-api-key')

    def do_POST(self):
        if self.path != '/chat':
            self.send_response(404); self.end_headers(); return

        length = int(self.headers.get('Content-Length', 0))
        body   = json.loads(self.rfile.read(length))
        key    = self.headers.get('x-api-key', '').strip()

        if not _SDK_OK:
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self._cors(); self.end_headers()
            self._emit({'type': 'error', 'message': 'anthropic package not installed. Run: pip install anthropic'})
            self._emit({'type': 'done'})
            return

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self._cors()
        self.end_headers()

        def emit(event):
            try:
                self.wfile.write(f'data: {json.dumps(event)}\n\n'.encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        try:
            client   = anthropic.Anthropic(api_key=key)
            messages = list(body.get('messages', []))

            while True:
                with client.messages.stream(
                    model=MODEL,
                    max_tokens=4096,
                    system=SYSTEM,
                    tools=TOOLS_DEF,
                    messages=messages
                ) as stream:
                    for text in stream.text_stream:
                        emit({'type': 'text_token', 'text': text})
                    response = stream.get_final_message()

                if response.stop_reason == 'end_turn':
                    break

                if response.stop_reason == 'tool_use':
                    # Build assistant message for history
                    asst = []
                    for b in response.content:
                        if b.type == 'text':
                            asst.append({'type': 'text', 'text': b.text})
                        elif b.type == 'tool_use':
                            asst.append({'type': 'tool_use', 'id': b.id, 'name': b.name, 'input': b.input})
                    messages.append({'role': 'assistant', 'content': asst})

                    tool_results = []
                    for b in response.content:
                        if b.type != 'tool_use':
                            continue
                        emit({'type': 'tool_start', 'name': b.name, 'input': b.input})

                        if b.name == 'ask_user':
                            emit({
                                'type': 'question',
                                'question': b.input.get('question', ''),
                                'header':   b.input.get('header', 'SELECT'),
                                'options':  b.input.get('options', [])
                            })
                            emit({'type': 'done'})
                            return  # Pause — client sends answer as next message

                        executor = EXECUTORS.get(b.name)
                        result   = executor(b.input) if executor else {'success': False, 'error': f'Unknown tool: {b.name}'}
                        emit({'type': 'tool_result', 'name': b.name, 'result': result})
                        tool_results.append({
                            'type': 'tool_result',
                            'tool_use_id': b.id,
                            'content': json.dumps(result)
                        })

                    messages.append({'role': 'user', 'content': tool_results})
                else:
                    break

        except anthropic.APIStatusError as e:
            emit({'type': 'error', 'message': f'API Error ({e.status_code}): {e.message}'})
        except Exception as e:
            emit({'type': 'error', 'message': str(e)})

        emit({'type': 'done'})

    def _emit(self, event):
        try:
            self.wfile.write(f'data: {json.dumps(event)}\n\n'.encode())
            self.wfile.flush()
        except Exception:
            pass

    def log_message(self, *a): pass


os.chdir(os.path.dirname(os.path.abspath(__file__)))
try:
    local_ip = socket.gethostbyname(socket.gethostname())
    ipad_url = f'\n  http://{local_ip}:{PORT}/jarvis.html  (iPad / phone on same WiFi)'
except Exception:
    ipad_url = ''

if not _SDK_OK:
    print('WARNING: anthropic package missing - run: pip install anthropic')
print('-----------------------------------------')
print('  J.A.R.V.I.S. running at:')
print(f'  http://localhost:{PORT}/jarvis.html  (this PC){ipad_url}')
print(f'  Model: {MODEL}')
print('  Keep this window open.')
print('-----------------------------------------')
HTTPServer(('', PORT), Handler).serve_forever()
