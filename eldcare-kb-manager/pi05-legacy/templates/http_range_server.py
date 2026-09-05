#!/usr/bin/env python3
"""HTTP server with Range request support (206 Partial Content)"""
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

class RangeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().do_GET()
        
        if not os.path.exists(path):
            self.send_error(404)
            return
        
        file_size = os.path.getsize(path)
        
        # Handle Range header
        range_header = self.headers.get('Range')
        if range_header:
            try:
                range_spec = range_header.replace('bytes=', '').split('-')
                start = int(range_spec[0]) if range_spec[0] else 0
                end = int(range_spec[1]) if range_spec[1] else file_size - 1
                if start >= file_size:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{file_size}')
                    self.end_headers()
                    return
                end = min(end, file_size - 1)
                length = end - start + 1
                
                self.send_response(206)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Length', str(length))
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Accept-Ranges', 'bytes')
                self.end_headers()
                
                with open(path, 'rb') as f:
                    f.seek(start)
                    self.wfile.write(f.read(length))
                return
            except Exception as e:
                print(f"Range error: {e}")
        
        # Normal response
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(file_size))
        self.send_header('Accept-Ranges', 'bytes')
        self.end_headers()
        
        with open(path, 'rb') as f:
            self.wfile.write(f.read())
    
    def translate_path(self, path):
        # Remove leading slash and serve from current directory
        return path.lstrip('/')

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = ThreadingHTTPServer(('', port), RangeHandler)
    print(f'Range HTTP server running on port {port}')
    server.serve_forever()
