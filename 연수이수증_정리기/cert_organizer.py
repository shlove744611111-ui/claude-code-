# -*- coding: utf-8 -*-
"""
연수 이수증 정리기 (설치형 / 완전 오프라인)
----------------------------------------------------
- 폴더 안의 PDF 이수증에서 선택한 항목을 추출해 엑셀(.xlsx)로 저장합니다.
- 모든 처리는 이 PC 안에서만 수행되며, 인터넷으로 아무것도 전송하지 않습니다.
- 추출 항목: 이수번호 / 과정명 / 성명 / 직급 / 근무기관 / 이수시간 / 이수일자 / 이수기관
- 꾸러미(법정의무) 연수 키워드를 입력하면 과정명 뒤에 (키워드)로 붙여 줍니다.
- 이수기관은 이수번호 앞부분으로 자동 추정합니다(도장·이미지라 글자가 없어도).
"""

import os
import re
import sys
import glob
import traceback
from datetime import datetime

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
# 추출 규칙 (양식이 다르면 이 라벨 목록만 손보면 됩니다)
# ==================================================================
NUMBER_LABELS = ["연수이수번호", "이수증번호", "이수증서번호", "이수번호", "연수번호",
                 "수료증번호", "수료번호", "증서번호", "발급번호", "등록번호", "관리번호"]
COURSE_LABELS = ["과정명", "연수과정명", "교육과정명", "과정"]
NAME_LABELS = ["성명", "이름", "성함", "수료자", "이수자", "연수자", "교육생"]
RANK_LABELS = ["직급", "직위", "직 급", "현직급"]
ORG_LABELS = ["근무기관", "소속기관", "소속", "근무처", "학교명", "근무학교", "근무지"]
HOURS_LABELS = ["이수시간", "연수시간", "교육시간", "수료시간", "이수 시간"]
DATE_LABELS = ["이수일자", "이수일", "수료일자", "수료일", "이수년월일",
               "연수이수일자", "연수이수일", "교육이수일"]
PERIOD_LABELS = ["연수기간", "교육기간", "이수기간", "수료기간", "연수일자", "교육일자"]
ISSUER_LABELS = ["이수기관", "연수기관", "교육기관", "발급기관", "주관기관", "운영기관"]

# 이수번호 앞부분 → 이수기관 이름
ISSUER_MAP = {
    "중앙교연": "중앙교육연수원",
    "경남교연": "경상남도교육청교육연수원",
    "서울교연": "서울특별시교육청교육연수원",
    "부산교연": "부산광역시교육청교육연수원",
    "대구교연": "대구광역시교육청교육연수원",
    "인천교연": "인천광역시교육청교육연수원",
    "광주교연": "광주광역시교육청교육연수원",
    "대전교연": "대전광역시교육청교육연수원",
    "울산교연": "울산광역시교육청교육연수원",
    "세종교연": "세종특별자치시교육청교육연수원",
    "경기교연": "경기도교육청교육연수원",
    "강원교연": "강원특별자치도교육청교육연수원",
    "충북교연": "충청북도교육청교육연수원",
    "충남교연": "충청남도교육청교육연수원",
    "전북교연": "전북특별자치도교육청교육연수원",
    "전남교연": "전라남도교육청교육연수원",
    "경북교연": "경상북도교육청교육연수원",
    "제주교연": "제주특별자치도교육청교육연수원",
}

# 엑셀 열 정의 (key, 라벨, 엑셀 너비, 기본 선택 여부)
COLUMNS = [
    ("number", "이수번호", 22, False),
    ("course", "과정명", 40, True),
    ("name", "성명", 10, True),
    ("rank", "직급", 16, True),
    ("org", "근무기관", 40, True),
    ("hours", "이수시간", 14, True),
    ("date", "이수일자", 13, True),
    ("issuer", "이수기관", 24, True),
]

DATE_RE = re.compile(r"(\d{4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")
_STOP_RE = re.compile(r"^\s*[가-힣A-Za-z()\s]{1,12}[:：]")


def _spaced(label):
    return r"\s*".join(re.escape(c) for c in label)


def find_value(text, labels):
    lines = text.split("\n")
    for label in labels:
        pat = re.compile(_spaced(label) + r"\s*[:：]?\s*(.+)")
        for ln in lines:
            m = pat.search(ln)
            if m and m.group(1).strip():
                return m.group(1).strip()
    return ""


def find_label_value(text, labels, multi=False):
    lines = text.split("\n")
    for label in labels:
        pat = re.compile(r"^\s*" + _spaced(label) + r"\s*[:：]\s*(.*)$")
        for j, ln in enumerate(lines):
            m = pat.search(ln)
            if m:
                val = (m.group(1) or "").strip()
                if multi:
                    for k in range(j + 1, len(lines)):
                        l2 = lines[k]
                        if not l2.strip():
                            break
                        if _STOP_RE.search(l2):
                            break
                        val += l2.strip()
                if val:
                    return val
    return ""


def _to_iso(m):
    return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def extract_date_str(v):
    ms = list(DATE_RE.finditer(v or ""))
    return _to_iso(ms[-1]) if ms else ""


def extract_number(v):
    if not v:
        return ""
    m = re.search(r"제\s*([0-9A-Za-z가-힣\-–()]+)\s*호", v)
    if m:
        return m.group(1).strip()
    m = re.search(r"([0-9]{2,}[0-9A-Za-z\-–/]*)", v)
    if m:
        return m.group(1).strip()
    t = v.strip().split()
    return t[0] if t else v.strip()


def extract_name(v):
    if not v:
        return ""
    m = re.match(r"((?:[가-힣]\s+){1,3}[가-힣])", v.strip())
    if m:
        return re.sub(r"\s+", "", m.group(1))
    m = re.search(r"[가-힣]{2,5}", v)
    if m:
        return m.group(0)
    m = re.search(r"[A-Za-z]+(?:\s[A-Za-z]+){0,2}", v)
    return m.group(0).strip() if m else v.strip()


def extract_number_full(text):
    v = find_value(text, NUMBER_LABELS)
    n = extract_number(v) if v else ""
    if n:
        return n
    m = re.search(r"제\s*([0-9A-Za-z가-힣][0-9A-Za-z가-힣\-–()/]*)\s*호", text)
    return m.group(1).strip() if m else ""


def extract_date_full(text):
    d = extract_date_str(find_value(text, DATE_LABELS))
    if d:
        return d
    d = extract_date_str(find_value(text, PERIOD_LABELS))
    if d:
        return d
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if ("증명" in ln) or ("발급" in ln) or ("수여" in ln):
            for j in range(i, min(i + 3, len(lines))):
                ms = list(DATE_RE.finditer(lines[j]))
                if ms:
                    return _to_iso(ms[-1])
    ms = list(DATE_RE.finditer(text))
    return _to_iso(ms[-1]) if ms else ""


def issuer_from_number(num):
    if not num:
        return ""
    m = re.match(r"\s*제?\s*([가-힣A-Za-z]+)", num)
    if not m:
        return ""
    key = m.group(1)
    if key in ISSUER_MAP:
        return ISSUER_MAP[key]
    if re.search(r"(연수원|교육원|진흥원|평생교육|교육연수)", key) and len(key) >= 4:
        return key
    for k, v in ISSUER_MAP.items():
        if key.startswith(k) or k.startswith(key):
            return v
    return ""


def extract_issuer_from_text(text):
    v = find_label_value(text, ISSUER_LABELS, False)
    if v:
        return v.strip()
    markers = ["연수원", "교육원", "교육청", "학교", "평생교육", "센터", "교육연수", "진흥원"]
    lines = [s.strip() for s in text.split("\n") if s.strip()]
    for ln in reversed(lines):
        core = re.sub(r"\s*[\(（][^\)）]*[\)）]\s*$", "", ln).strip()
        if core.endswith("장") and len(core) >= 4 and any(mk in core for mk in markers):
            name = re.sub(r"\s+", "", re.sub(r"장$", "", core)).strip()
            if len(name) >= 2:
                return name
    return ""


def _norm(s):
    return re.sub(r"\s+", "", s or "")


def compose_course(base, full_text, keywords, bundle_on):
    if bundle_on and keywords:
        hay = _norm(full_text)
        matched = [k for k in keywords if k and _norm(k) in hay]
        if matched:
            return (base or "") + "(" + ", ".join(matched) + ")"
    return base or ""


def extract_text(path):
    if pdfplumber is None:
        raise RuntimeError("pdfplumber 가 설치되어 있지 않습니다. (pip install pdfplumber)")
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def process_pdf(path, keywords=None, bundle_on=False, issuer_default=""):
    keywords = keywords or []
    row = {"file": os.path.basename(path), "_failed": False,
           "number": "", "course": "", "name": "", "rank": "",
           "org": "", "hours": "", "date": "", "issuer": ""}
    try:
        text = extract_text(path)
    except Exception as e:  # noqa
        row["_failed"] = True
        row["_err"] = str(e)
        return row
    if not text.strip():
        row["_failed"] = True
        return row

    row["number"] = extract_number_full(text)
    row["course"] = compose_course(find_label_value(text, COURSE_LABELS, True),
                                    text, keywords, bundle_on)
    row["name"] = extract_name(find_label_value(text, NAME_LABELS, False)
                               or find_value(text, NAME_LABELS))
    row["rank"] = find_label_value(text, RANK_LABELS, False)
    row["org"] = find_label_value(text, ORG_LABELS, True)
    row["hours"] = find_label_value(text, HOURS_LABELS, False)
    row["date"] = extract_date_full(text)
    row["issuer"] = (extract_issuer_from_text(text)
                     or issuer_default
                     or issuer_from_number(row["number"]))
    return row


def row_note(row, selected_keys):
    if row.get("_failed"):
        return "텍스트 추출 실패 (스캔본일 수 있음)"
    labels = {k: l for k, l, _w, _d in COLUMNS}
    miss = [labels[k] for k in selected_keys if not row.get(k)]
    return ("검토필요: " + ", ".join(miss) + " 미검출") if miss else ""


def write_excel(rows, selected_keys, out_path):
    if Workbook is None:
        raise RuntimeError("openpyxl 가 설치되어 있지 않습니다. (pip install openpyxl)")
    labels = {k: l for k, l, _w, _d in COLUMNS}
    widths = {k: w for k, _l, w, _d in COLUMNS}

    wb = Workbook()
    ws = wb.active
    ws.title = "연수이수증"

    headers = ["번호"] + [labels[k] for k in selected_keys] + ["비고"]
    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="305496")
    header_font = Font(bold=True, color="FFFFFF")
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
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
        note = row_note(r, selected_keys)
        values = [i] + [r.get(k, "") for k in selected_keys] + [note]
        ws.append(values)
        er = i + 1
        for c in range(1, len(headers) + 1):
            cell = ws.cell(row=er, column=c)
            cell.border = border
            cell.alignment = center if c == 1 else left
            if note:
                cell.fill = warn_fill

    ws.column_dimensions["A"].width = 6
    for idx, k in enumerate(selected_keys, start=2):
        ws.column_dimensions[get_column_letter(idx)].width = widths[k]
    ws.column_dimensions[get_column_letter(len(headers))].width = 32

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"
    wb.save(out_path)


def collect_pdfs(folder):
    out = []
    for pat in ("*.pdf", "*.PDF"):
        out.extend(glob.glob(os.path.join(folder, pat)))
    return sorted(set(out))


def run(folder, selected_keys=None, keywords=None, bundle_on=False,
        issuer_default="", log=print):
    if selected_keys is None:
        selected_keys = [k for k, _l, _w, d in COLUMNS if d]
    pdfs = collect_pdfs(folder)
    if not pdfs:
        raise RuntimeError("선택한 폴더에 PDF 파일이 없습니다.")
    rows = []
    for idx, p in enumerate(pdfs, start=1):
        log(f"[{idx}/{len(pdfs)}] {os.path.basename(p)}")
        rows.append(process_pdf(p, keywords, bundle_on, issuer_default))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(folder, f"연수이수증_정리_{stamp}.xlsx")
    write_excel(rows, selected_keys, out_path)
    ok = sum(1 for r in rows if not row_note(r, selected_keys))
    log(f"\n완료! 총 {len(rows)}건 중 {ok}건 정상, {len(rows) - ok}건 검토 필요")
    log(f"저장: {out_path}")
    return out_path, rows


# ==================================================================
# 설치형 GUI
# ==================================================================
def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("연수 이수증 정리기")
    root.geometry("860x620")

    folder_var = tk.StringVar()
    bundle_var = tk.BooleanVar(value=False)
    kw_var = tk.StringVar()
    issuer_var = tk.StringVar()
    col_vars = {k: tk.BooleanVar(value=d) for k, _l, _w, d in COLUMNS}

    pad = {"padx": 10, "pady": 4}

    # 1) 폴더 선택
    f1 = tk.LabelFrame(root, text="이수증 PDF 폴더", padx=10, pady=8)
    f1.pack(fill="x", **pad)
    tk.Entry(f1, textvariable=folder_var).pack(side="left", fill="x", expand=True)

    def pick():
        d = filedialog.askdirectory(title="이수증 PDF가 들어있는 폴더 선택")
        if d:
            folder_var.set(d)
    tk.Button(f1, text="폴더 선택", command=pick).pack(side="left", padx=(8, 0))

    # 2) 추출 항목
    f2 = tk.LabelFrame(root, text="엑셀로 추출할 항목", padx=10, pady=8)
    f2.pack(fill="x", **pad)
    for i, (k, label, _w, _d) in enumerate(COLUMNS):
        tk.Checkbutton(f2, text=label, variable=col_vars[k]).grid(
            row=i // 4, column=i % 4, sticky="w", padx=6, pady=2)

    # 3) 꾸러미 키워드 / 이수기관
    f3 = tk.LabelFrame(root, text="옵션", padx=10, pady=8)
    f3.pack(fill="x", **pad)
    tk.Checkbutton(f3, text="꾸러미(법정의무) 키워드 사용", variable=bundle_var).grid(
        row=0, column=0, sticky="w")
    tk.Entry(f3, textvariable=kw_var, width=48).grid(row=0, column=1, sticky="we", padx=8)
    tk.Label(f3, text="예: 성희롱, 아동학대, 부패방지", fg="#888").grid(row=0, column=2, sticky="w")
    tk.Label(f3, text="이수기관 기본값").grid(row=1, column=0, sticky="w", pady=(6, 0))
    tk.Entry(f3, textvariable=issuer_var, width=48).grid(row=1, column=1, sticky="we", padx=8, pady=(6, 0))
    tk.Label(f3, text="(번호로 자동 추정, 직접 입력 시 우선)", fg="#888").grid(row=1, column=2, sticky="w", pady=(6, 0))
    f3.columnconfigure(1, weight=1)

    # 4) 실행 + 결과표
    f4 = tk.Frame(root)
    f4.pack(fill="both", expand=True, **pad)

    cols = ["번호"] + [l for _k, l, _w, _d in COLUMNS] + ["비고"]
    tree = ttk.Treeview(f4, columns=cols, show="headings", height=12)
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, width=90 if c not in ("과정명", "근무기관", "비고") else 150, anchor="w")
    tree.column("번호", width=40, anchor="center")
    tree.tag_configure("warn", background="#FFF6DF")
    vsb = ttk.Scrollbar(f4, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="left", fill="y")

    status = tk.StringVar(value="PDF 폴더를 선택하고 [정리 시작]을 누르세요.")
    note = tk.Label(root, textvariable=status, anchor="w", fg="#1a7f46")
    note.pack(fill="x", padx=12)

    privacy = tk.Label(root, text="※ 모든 처리는 이 PC 안에서만 이루어지며 외부로 전송되지 않습니다.",
                       anchor="w", fg="#1a7f46")
    privacy.pack(fill="x", padx=12, pady=(0, 4))

    def selected_keys():
        return [k for k, _l, _w, _d in COLUMNS if col_vars[k].get()]

    def start():
        folder = folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("안내", "먼저 이수증 PDF 폴더를 선택하세요.")
            return
        keys = selected_keys()
        if not keys:
            messagebox.showwarning("안내", "추출할 항목을 하나 이상 선택하세요.")
            return
        kws = [s.strip() for s in re.split(r"[,\n]+", kw_var.get()) if s.strip()]
        for i in tree.get_children():
            tree.delete(i)
        try:
            out_path, rows = run(folder, keys, kws, bundle_var.get(),
                                 issuer_var.get().strip(),
                                 log=lambda m: status.set(m.replace("\n", " ")))
            for i, r in enumerate(rows, start=1):
                n = row_note(r, keys)
                vals = [i] + [r.get(k, "") for k, _l, _w, _d in COLUMNS] + [n]
                tree.insert("", "end", values=vals, tags=("warn",) if n else ())
            warn = sum(1 for r in rows if row_note(r, keys))
            msg = f"정리 완료!  (총 {len(rows)}건, 검토 필요 {warn}건)\n\n저장: {out_path}"
            if messagebox.askyesno("완료", msg + "\n\n저장한 폴더를 열까요?"):
                try:
                    os.startfile(folder)  # Windows
                except Exception:
                    pass
        except Exception as e:  # noqa
            messagebox.showerror("오류", str(e))
            status.set("오류: " + str(e))

    btns = tk.Frame(root)
    btns.pack(pady=6)
    tk.Button(btns, text="정리 시작 → 엑셀 저장", width=24, height=2,
              command=start, bg="#305496", fg="white").pack(side="left", padx=6)
    tk.Button(btns, text="닫기", width=10, height=2, command=root.destroy).pack(side="left", padx=6)

    if pdfplumber is None or Workbook is None:
        status.set("[경고] 구성요소 미설치 — 'EXE만들기.bat' 또는 '실행하기.bat'로 설치하세요.")

    root.mainloop()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        folder = args[0]
        if not os.path.isdir(folder):
            print("폴더를 찾을 수 없습니다:", folder)
            sys.exit(1)
        run(folder)
    else:
        try:
            run_gui()
        except Exception as e:  # noqa
            print("창 모드를 열 수 없습니다:", e)
            print('사용법: python cert_organizer.py "이수증폴더경로"')
            sys.exit(1)


if __name__ == "__main__":
    main()
