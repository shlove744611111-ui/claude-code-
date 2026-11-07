# -*- coding: utf-8 -*-
"""
이수ON 로컬 실행기 (RapidOCR 한국어, 완전 로컬)
- 브라우저에 웹 화면을 열고, 스캔 PDF는 로컬 서버가 RapidOCR(PP-OCR 한국어)로 인식합니다.
- 모든 처리는 이 PC 안에서만. 외부 전송 없음. (모델은 설치 시 ./models 에 받아둠)
- 브라우저를 닫으면 자동 종료됩니다.
"""
import os
import sys
import time
import threading
import webbrowser
import socketserver
import http.server


def base_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


WEB = os.path.join(base_dir(), "web")
MODELS = os.path.join(base_dir(), "models")

STATE = {"last": None, "start": time.time()}
IDLE_TIMEOUT = 30
OPEN_TIMEOUT = 120

_engine = None
_lock = threading.Lock()


def get_engine():
    global _engine
    with _lock:
        if _engine is None:
            from rapidocr import RapidOCR
            os.makedirs(MODELS, exist_ok=True)
            _engine = RapidOCR(params={
                "Global.use_cls": False,
                "Global.model_root_dir": MODELS,
                "Det.lang_type": "ch",
                "Rec.lang_type": "korean",
                "Rec.ocr_version": "PP-OCRv4",
            })
        return _engine


def run_ocr(pdf_bytes):
    import numpy as np
    import pypdfium2 as pdfium
    eng = get_engine()
    pdf = pdfium.PdfDocument(pdf_bytes)
    out = []
    try:
        for i in range(len(pdf)):
            pil = pdf[i].render(scale=3.0).to_pil().convert("RGB")
            res = eng(np.array(pil))
            if not res or res.boxes is None:
                continue
            items = []
            for box, txt in zip(res.boxes, res.txts):
                ys = [p[1] for p in box]
                xs = [p[0] for p in box]
                items.append((sum(ys) / 4.0, min(xs), txt))
            items.sort(key=lambda t: t[0])
            lines, cur, last = [], [], None
            for y, x, t in items:
                if last is not None and abs(y - last) > 24:
                    lines.append(cur)
                    cur = []
                cur.append((x, t))
                last = y
            if cur:
                lines.append(cur)
            for ln in lines:
                ln.sort(key=lambda t: t[0])
                out.append(" ".join(t for _, t in ln))
    finally:
        pdf.close()
    return "\n".join(out)


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        ".html": "text/html; charset=utf-8", ".js": "text/javascript",
        ".css": "text/css", ".json": "application/json", ".wasm": "application/wasm",
        ".png": "image/png", ".svg": "image/svg+xml", "": "application/octet-stream",
    }

    def __init__(self, *a, **k):
        super().__init__(*a, directory=WEB, **k)

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _text(self, code, body):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/ping"):
            STATE["last"] = time.time()
            self.send_response(204); self.send_header("Content-Length", "0"); self.end_headers()
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/ping"):
            STATE["last"] = time.time()
            self.send_response(204); self.send_header("Content-Length", "0"); self.end_headers()
            return
        if self.path.startswith("/ocr"):
            STATE["last"] = time.time()
            try:
                n = int(self.headers.get("Content-Length", "0"))
                data = self.rfile.read(n)
                self._text(200, run_ocr(data))
            except Exception as e:  # noqa
                self._text(500, "OCR오류: " + str(e))
            return
        self.send_response(404); self.end_headers()


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
    threading.Thread(target=lambda: (get_engine(),), daemon=True).start()
    try:
        webbrowser.open(url)
    except Exception:  # noqa
        pass
    watchdog(httpd)


if __name__ == "__main__":
    main()
