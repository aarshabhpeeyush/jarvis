"""Tiny local proxy server for J.A.R.V.I.S. — no dependencies beyond Python."""
import http.client, json, os, ssl, socket
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get('PORT', 8181))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        p = self.path.split('?')[0]
        if p in ('/', '/jarvis.html'):
            self._file('jarvis.html', 'text/html; charset=utf-8')
        elif p == '/manifest.json':
            self._file('manifest.json', 'application/manifest+json')
        elif p in ('/icon-192.png', '/icon-512.png'):
            size = 192 if '192' in p else 512
            self._icon(size)
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
        # Generate a minimal SVG-based PNG-like icon as an SVG served as image/svg+xml
        # Safari supports SVG for apple-touch-icon via the manifest
        cx = size // 2
        r1 = int(size * 0.42)
        r2 = int(size * 0.30)
        r3 = int(size * 0.14)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">'
            f'<rect width="{size}" height="{size}" fill="#050507"/>'
            f'<circle cx="{cx}" cy="{cx}" r="{r1}" fill="none" stroke="#FFB700" stroke-width="{max(2,size//64)}"/>'
            f'<circle cx="{cx}" cy="{cx}" r="{r2}" fill="none" stroke="#FFCC00" stroke-width="{max(2,size//80)}"/>'
            f'<circle cx="{cx}" cy="{cx}" r="{r3}" fill="#FFB700"/>'
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
        body   = self.rfile.read(length)
        key    = self.headers.get('x-api-key', '')
        ctx    = ssl.create_default_context()
        conn   = http.client.HTTPSConnection('api.anthropic.com', context=ctx)
        conn.request('POST', '/v1/messages', body=body, headers={
            'x-api-key': key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        })
        resp = conn.getresponse()
        self.send_response(resp.status)
        self.send_header('Content-Type', resp.headers.get('Content-Type','application/json'))
        self._cors(); self.end_headers()
        while True:
            chunk = resp.read(4096)
            if not chunk: break
            try: self.wfile.write(chunk); self.wfile.flush()
            except: break
        conn.close()

    def log_message(self, *a): pass  # silence access logs

os.chdir(os.path.dirname(os.path.abspath(__file__)))
try:
    local_ip = socket.gethostbyname(socket.gethostname())
    ipad_url = f'\n  http://{local_ip}:{PORT}/jarvis.html  (iPad / phone on same WiFi)'
except Exception:
    ipad_url = ''
print('─────────────────────────────────────────')
print('  J.A.R.V.I.S. running at:')
print(f'  http://localhost:{PORT}/jarvis.html  (this PC){ipad_url}')
print('  Keep this window open.')
print('─────────────────────────────────────────')
HTTPServer(('', PORT), Handler).serve_forever()
