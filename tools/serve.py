#!/usr/bin/env python3
"""
Local preview server for the built site (behaves like the live host):
  /            -> site/index.html
  /inter-miami -> site/inter-miami.html   (original Format URLs, no .html)
  unknown      -> site/404.html (status 404)

    python3 tools/serve.py            # then open http://localhost:8000
    python3 tools/serve.py --port 9000
"""
import argparse
import http.server
import os
import re
import socketserver
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), "site")


class Handler(http.server.SimpleHTTPRequestHandler):
    fallback_images = False

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SITE, **kw)

    def send_head(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        local = os.path.join(SITE, path.lstrip("/"))
        if path != "/" and not os.path.splitext(path)[1] and os.path.exists(local.rstrip("/") + ".html"):
            self.path = path.rstrip("/") + ".html"
        elif self.fallback_images and path.endswith(".webp") and not os.path.exists(local):
            alt = re.sub(r"-\d+\.webp$", "-640.webp", path)          # verification only
            if os.path.exists(os.path.join(SITE, alt.lstrip("/"))):
                self.path = alt
        elif path != "/" and not os.path.exists(local):
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            body = open(os.path.join(SITE, "404.html"), "rb").read()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            import io
            return io.BytesIO(body)
        rng = self.headers.get("Range")
        fpath = self.translate_path(self.path)
        if rng and os.path.isfile(fpath):
            return self._send_range(fpath, rng)        # Safari needs byte ranges for <video>
        return super().send_head()

    def _send_range(self, fpath, rng):
        size = os.path.getsize(fpath)
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        if not m:
            return super().send_head()
        start = int(m.group(1)) if m.group(1) else max(0, size - int(m.group(2) or 0))
        end = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
        end = min(end, size - 1)
        if start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        f = open(fpath, "rb")
        f.seek(start)
        import io
        data = f.read(end - start + 1)
        f.close()
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(fpath))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        return io.BytesIO(data)

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--fallback-images", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    Handler.fallback_images = args.fallback_images
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", args.port), Handler) as httpd:
        url = f"http://localhost:{args.port}/"
        print(f"RophysJpeg preview running at {url}  (press Ctrl+C to stop)")
        if not args.no_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
