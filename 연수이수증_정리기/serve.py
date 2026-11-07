# -*- coding: utf-8 -*-
"""
이수ON 로컬 실행기
- 이 PC 안에서만 작은 웹서버를 띄우고, 기본 브라우저에 '이수ON' 화면을 엽니다.
- 인터넷 없이 동작하며(엔진·OCR데이터 내장), PDF 내용은 브라우저 안에서만 처리됩니다.
- 상태 창을 닫으면 종료됩니다.
"""
import os
import sys
import threading
import webbrowser
import socketserver
import http.server


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
        ".wasm": "application/wasm",
        ".gz": "application/octet-stream",
        ".traineddata": "application/octet-stream",
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

    try:
        import tkinter as tk
        root = tk.Tk()
        root.title("이수ON")
        root.geometry("440x210")
        tk.Label(root, text="이수ON 실행 중", font=("Malgun Gothic", 16, "bold")).pack(pady=(24, 6))
        tk.Label(root, text="브라우저 창에서 사용하세요.\n사용이 끝나면 이 창을 닫으면 종료됩니다.",
                 fg="#1a7f46", justify="center").pack()
        tk.Label(root, text=url, fg="#2457d6").pack(pady=6)

        def reopen():
            try:
                webbrowser.open(url)
            except Exception:  # noqa
                pass

        tk.Button(root, text="브라우저 다시 열기", width=18, height=2, command=reopen).pack(pady=8)

        def on_close():
            try:
                httpd.shutdown()
            except Exception:  # noqa
                pass
            root.destroy()
            os._exit(0)

        root.protocol("WM_DELETE_WINDOW", on_close)
        root.mainloop()
    except Exception:  # tkinter 불가 → 콘솔 대기
        print("이수ON 실행 중:", url)
        print("종료하려면 이 창을 닫으세요.")
        import time
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
