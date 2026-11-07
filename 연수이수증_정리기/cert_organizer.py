# -*- coding: utf-8 -*-
"""
연수 이수증 정리기 (로컬 전용 / 완전 오프라인)
----------------------------------------------------
- 폴더 안의 PDF 이수증에서 [이수번호 / 이름 / 이수일자] 만 추출해 엑셀로 정리합니다.
- 모든 처리는 이 PC 안에서만 이루어집니다. 인터넷으로 아무것도 전송하지 않습니다.
- 창(UI) 모드: 그냥 실행하면 폴더 선택 창이 뜹니다.
- 명령줄 모드: python cert_organizer.py "C:\\이수증폴더" 처럼 폴더를 인자로 주면 창 없이 처리합니다.
"""

import os
import re
import sys
import glob
import traceback
from datetime import datetime

# ------------------------------------------------------------------
# PDF / 엑셀 라이브러리 (설치 필요: pip install pdfplumber openpyxl)
# ------------------------------------------------------------------
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    Workbook = None


# ==================================================================
# 추출 규칙 (이수증 양식에 맞춰 이 부분만 손보면 됩니다)
# ==================================================================
# find_value 는 라벨 글자 사이에 공백이 있어도("이 수 번 호") 자동으로 인식합니다.
# 위에 있는 라벨부터 먼저 찾습니다. 양식에 맞게 순서를 바꾸거나 추가하세요.
NUMBER_LABELS = [
    "연수이수번호", "이수증번호", "이수증서번호", "이수번호",
    "연수번호", "수료증번호", "수료번호",
    "증서번호", "발급번호", "자격번호", "등록번호", "관리번호",
]
NAME_LABELS = [
    "성명", "이름", "성함", "수료자", "이수자", "연수자", "교육생",
]
DATE_LABELS = [
    "이수일자", "이수일", "수료일자", "수료일",
    "이수년월일", "연수이수일자", "연수이수일", "교육이수일",
]
# 이수일 라벨이 없을 때, 기간의 '종료일'을 이수일로 사용합니다.
PERIOD_LABELS = [
    "연수기간", "교육기간", "이수기간", "수료기간",
    "연수일자", "교육일자", "연수일", "교육일",
]

# 날짜 형식: 2024년 1월 2일 / 2024-01-02 / 2024.01.02 / 2024/01/02
DATE_RE = re.compile(r"(\d{4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")


def _spaced(label: str) -> str:
    """라벨 글자 사이의 공백을 허용하는 정규식으로 변환."""
    return r"\s*".join(map(re.escape, label))


def find_value(text: str, labels):
    """라벨 뒤에 오는 값을 같은 줄에서 찾아 반환."""
    lines = text.splitlines()
    for label in labels:
        pat = re.compile(_spaced(label) + r"\s*[:：]?\s*(.+)")
        for line in lines:
            m = pat.search(line)
            if m and m.group(1).strip():
                return m.group(1).strip()
    return ""


def _to_iso(m) -> str:
    y, mo, d = m.groups()
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"


def extract_number(val: str) -> str:
    if not val:
        return ""
    v = val.strip()
    # "제 2024-123 호" 형태
    m = re.search(r"제\s*([0-9A-Za-z가-힣\-–()]+)\s*호", v)
    if m:
        return m.group(1).strip()
    # 숫자가 포함된 코드형
    m = re.search(r"([0-9]{2,}[0-9A-Za-z\-–/]*)", v)
    if m:
        return m.group(1).strip()
    tok = v.split()
    return tok[0] if tok else v


def extract_name(val: str) -> str:
    if not val:
        return ""
    v = val.strip()
    # "홍 길 동" 처럼 한 글자씩 띄어쓴 이름
    m = re.match(r"((?:[가-힣]\s+){1,3}[가-힣])", v)
    if m:
        return re.sub(r"\s+", "", m.group(1))
    # 일반 한글 이름
    m = re.search(r"[가-힣]{2,5}", v)
    if m:
        return m.group(0)
    # 영문 이름
    m = re.search(r"[A-Za-z]+(?:\s[A-Za-z]+){0,2}", v)
    return m.group(0).strip() if m else v


def extract_date(val: str) -> str:
    if not val:
        return ""
    ms = list(DATE_RE.finditer(val))
    if ms:
        # 기간(두 날짜)이면 마지막 날짜(종료=이수일)를 사용
        return _to_iso(ms[-1])
    return ""


def extract_number_full(text: str) -> str:
    """이수번호 추출: 라벨 → '제 ○○○ 호' 상단 번호 순으로 시도."""
    v = find_value(text, NUMBER_LABELS)
    n = extract_number(v) if v else ""
    if n:
        return n
    # '제 경남교연-2026-446420 호' 형태
    m = re.search(r"제\s*([0-9A-Za-z가-힣][0-9A-Za-z가-힣\-–()/]*)\s*호", text)
    if m:
        return m.group(1).strip()
    return ""


def extract_date_full(text: str) -> str:
    """이수일자 추출: 이수일 라벨 → 기간 종료일 → 증명/발급일 → 문서 마지막 날짜."""
    # 1) 이수일/수료일 라벨
    d = extract_date(find_value(text, DATE_LABELS))
    if d:
        return d
    # 2) 연수기간/교육기간 등의 '종료일'
    d = extract_date(find_value(text, PERIOD_LABELS))
    if d:
        return d
    # 3) '증명/발급/수여' 문구가 있는 줄 및 그 아래의 날짜
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if ("증명" in line) or ("발급" in line) or ("수여" in line):
            for j in range(i, min(i + 3, len(lines))):
                ms = list(DATE_RE.finditer(lines[j]))
                if ms:
                    return _to_iso(ms[-1])
    # 4) 문서 전체에서 마지막으로 나오는 날짜(보통 하단 발급일)
    ms = list(DATE_RE.finditer(text))
    if ms:
        return _to_iso(ms[-1])
    return ""


def extract_text(pdf_path: str) -> str:
    """PDF에서 텍스트 추출 (레이아웃 유지)."""
    if pdfplumber is None:
        raise RuntimeError("pdfplumber 가 설치되어 있지 않습니다. (pip install pdfplumber)")
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def process_pdf(path: str) -> dict:
    """PDF 한 개를 처리해 결과 dict 반환."""
    result = {
        "파일명": os.path.basename(path),
        "이수번호": "",
        "이름": "",
        "이수일자": "",
        "비고": "",
    }
    try:
        text = extract_text(path)
    except Exception as e:  # noqa
        result["비고"] = f"오류: {e}"
        return result

    if not text.strip():
        result["비고"] = "텍스트 추출 실패(스캔 이미지로 보임. OCR 필요)"
        return result

    result["이수번호"] = extract_number_full(text)
    result["이름"] = extract_name(find_value(text, NAME_LABELS))
    result["이수일자"] = extract_date_full(text)

    missing = [k for k in ("이수번호", "이름", "이수일자") if not result[k]]
    if missing:
        result["비고"] = "검토필요: " + ", ".join(missing) + " 미검출"
    return result


def write_excel(rows, out_path: str):
    """결과를 보기 좋은 엑셀로 저장."""
    if Workbook is None:
        raise RuntimeError("openpyxl 가 설치되어 있지 않습니다. (pip install openpyxl)")

    wb = Workbook()
    ws = wb.active
    ws.title = "연수이수증"

    headers = ["번호", "파일명", "이수번호", "이름", "이수일자", "비고"]
    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="305496")
    header_font = Font(bold=True, color="FFFFFF")
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    warn_fill = PatternFill("solid", fgColor="FFF2CC")

    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=c)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = border

    for i, r in enumerate(rows, start=1):
        row_vals = [i, r["파일명"], r["이수번호"], r["이름"], r["이수일자"], r["비고"]]
        ws.append(row_vals)
        excel_row = i + 1
        has_warn = bool(r["비고"])
        for c in range(1, len(headers) + 1):
            cell = ws.cell(row=excel_row, column=c)
            cell.border = border
            cell.alignment = center if c in (1, 3, 5) else left
            if has_warn:
                cell.fill = warn_fill

    widths = [6, 34, 20, 12, 14, 34]
    for idx, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = w

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"

    wb.save(out_path)


def collect_pdfs(folder: str):
    pdfs = []
    for pat in ("*.pdf", "*.PDF"):
        pdfs.extend(glob.glob(os.path.join(folder, pat)))
    return sorted(set(pdfs))


def run(folder: str, log=print):
    """폴더 처리 → 엑셀 저장. 저장 경로를 반환."""
    pdfs = collect_pdfs(folder)
    if not pdfs:
        raise RuntimeError("선택한 폴더에 PDF 파일이 없습니다.")

    rows = []
    for idx, p in enumerate(pdfs, start=1):
        log(f"[{idx}/{len(pdfs)}] 처리 중: {os.path.basename(p)}")
        rows.append(process_pdf(p))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(folder, f"연수이수증_정리_{stamp}.xlsx")
    write_excel(rows, out_path)

    ok = sum(1 for r in rows if not r["비고"])
    log(f"\n완료! 총 {len(rows)}건 중 {ok}건 정상, {len(rows) - ok}건 검토 필요")
    log(f"저장 위치: {out_path}")
    return out_path, rows


# ==================================================================
# 창(UI) 모드
# ==================================================================
def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext

    root = tk.Tk()
    root.title("연수 이수증 정리기")
    root.geometry("640x460")

    folder_var = tk.StringVar()

    top = tk.Frame(root, padx=12, pady=10)
    top.pack(fill="x")

    tk.Label(top, text="이수증 PDF 폴더:").grid(row=0, column=0, sticky="w")
    entry = tk.Entry(top, textvariable=folder_var, width=52)
    entry.grid(row=0, column=1, padx=6)

    def pick():
        d = filedialog.askdirectory(title="이수증 PDF가 들어있는 폴더 선택")
        if d:
            folder_var.set(d)

    tk.Button(top, text="폴더 선택", command=pick).grid(row=0, column=2)

    note = tk.Label(
        root,
        text="※ 모든 처리는 이 PC 안에서만 이루어지며, 외부(인터넷)로 전송되지 않습니다.",
        fg="#1a7f37", padx=12,
    )
    note.pack(anchor="w")

    log_box = scrolledtext.ScrolledText(root, height=18, font=("Consolas", 10))
    log_box.pack(fill="both", expand=True, padx=12, pady=8)

    def log(msg=""):
        log_box.insert("end", str(msg) + "\n")
        log_box.see("end")
        root.update_idletasks()

    def start():
        folder = folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("안내", "먼저 이수증 PDF 폴더를 선택하세요.")
            return
        log_box.delete("1.0", "end")
        try:
            out_path, rows = run(folder, log=log)
            warn = sum(1 for r in rows if r["비고"])
            msg = f"정리 완료!\n\n저장: {out_path}"
            if warn:
                msg += f"\n\n⚠ {warn}건은 자동 인식이 불완전합니다.\n엑셀의 노란색 행(비고)을 확인하세요."
            if messagebox.askyesno("완료", msg + "\n\n저장한 폴더를 열까요?"):
                try:
                    os.startfile(folder)  # Windows
                except Exception:
                    pass
        except Exception as e:  # noqa
            log("\n[오류] " + str(e))
            log(traceback.format_exc())
            messagebox.showerror("오류", str(e))

    btns = tk.Frame(root, pady=6)
    btns.pack()
    tk.Button(btns, text="정리 시작", width=16, height=2, command=start,
              bg="#305496", fg="white").pack(side="left", padx=6)
    tk.Button(btns, text="닫기", width=10, height=2, command=root.destroy).pack(side="left", padx=6)

    if pdfplumber is None or Workbook is None:
        log("[경고] 필요한 라이브러리가 없습니다. 'EXE만들기.bat' 또는 '실행하기.bat'를 이용해 설치하세요.")

    root.mainloop()


# ==================================================================
# 진입점
# ==================================================================
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:  # 폴더 인자가 있으면 창 없이 처리
        folder = args[0]
        if not os.path.isdir(folder):
            print("폴더를 찾을 수 없습니다:", folder)
            sys.exit(1)
        run(folder)
    else:
        try:
            run_gui()
        except Exception as e:  # tkinter 불가 등
            print("창 모드를 열 수 없습니다:", e)
            print('사용법: python cert_organizer.py "이수증폴더경로"')
            sys.exit(1)


if __name__ == "__main__":
    main()
