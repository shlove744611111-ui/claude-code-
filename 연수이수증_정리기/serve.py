# -*- coding: utf-8 -*-
"""
이수ON 로컬 실행기 (창 없음)
- 이 PC 안에서만 작은 웹서버를 띄우고, 기본 브라우저에 '이수ON' 화면을 엽니다.
- 인터넷 없이 동작하며(라이브러리 내장), PDF 내용은 브라우저 안에서만 처리됩니다.
- 브라우저 화면을 닫으면(또는 열리지 않으면) 서버가 자동으로 종료됩니다. 별도 창은 없습니다.
"""
import os
import sys
import time
import threading
import webbrowser
import socketserver
import http.server

STATE = {"last": None, "start": time.time()}
IDLE_TIMEOUT = 20      # 브라우저 하트비트가 이만큼 끊기면 종료(초)
OPEN_TIMEOUT = 90      # 브라우저가 한 번도 안 열리면 종료(초)


def base_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


WEB = os.path.join(base_dir(), "web")


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".css": "text/css",
        ".json": "application/json",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        "": "application/octet-stream",
    }

    def __init__(self, *a, **k):
        super().__init__(*a, directory=WEB, **k)

    def log_message(self, *a):  # 조용히
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _nocontent(self):
        STATE["last"] = time.time()
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/ping"):
            self._nocontent()
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/ping"):
            self._nocontent()
            return
        self.send_response(404)
        self.end_headers()


def watchdog(httpd):
    while True:
        time.sleep(2)
        now = time.time()
        if STATE["last"] is None:
            if now - STATE["start"] > OPEN_TIMEOUT:
                break
        elif now - STATE["last"] > IDLE_TIMEOUT:
            break
    try:
        httpd.shutdown()
    except Exception:  # noqa
        pass
    os._exit(0)


def main():
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    port = httpd.server_address[1]
    url = "http://127.0.0.1:%d/index.html" % port
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        webbrowser.open(url)
    except Exception:  # noqa
        pass
    watchdog(httpd)  # 메인 스레드에서 감시(브라우저 닫히면 종료)


if __name__ == "__main__":
    main()
