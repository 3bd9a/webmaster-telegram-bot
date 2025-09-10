from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import logging

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_error(404)

def run_server(port=8000):
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, HealthHandler)
    logging.info(f'Starting health check server on port {port}')
    httpd.serve_forever()

def start_health_server():
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    return server_thread
