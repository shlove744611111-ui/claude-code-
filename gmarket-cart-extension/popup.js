/* popup.js — 엑셀 파싱 + 콘텐츠 스크립트와 통신 */

let items = []; // [{name, spec}] — 엑셀에서 읽은 구입 물품
let skippedCount = 0; // 배송비 등 제외한 개수

const $ = (id) => document.getElementById(id);
const fileEl = $("file");
const fileInfo = $("fileInfo");
const itemListEl = $("itemList");
const runBtn = $("runBtn");
const scanBtn = $("scanBtn");
const statusEl = $("status");
const resultEl = $("result");

function setStatus(msg) { statusEl.textContent = msg || ""; }

// 제외할 항목(배송비 등). 상품명에 이 단어가 들어가면 목록에서 뺀다.
const IGNORE_WORDS = ["배송비", "택배비", "선불", "착불"];
function isIgnored(name) {
  const s = String(name).replace(/\s+/g, "");
  return IGNORE_WORDS.some((w) => s.includes(w));
}

const NAME_HEADERS = /^(항목|품목|상품\s*명|물품|품명|상품|품\s*목|name|item|제품|물품명)$/i;
const SPEC_HEADERS = /^(규격|사양|옵션|사이즈|size|spec|스펙|세부|비고)$/i;
const QTY_HEADERS = /^(수량|개수|수\s*량|qty|q'?ty|count)$/i;

/* 엑셀/CSV에서 '항목' 열과 '규격' 열을 찾아 물품 목록을 만든다.
   - 제목 행이 위에 있어도, 헤더 행을 자동으로 찾는다.
   - 헤더를 못 찾으면 첫 열을 상품명으로 가정한다. */
function parseWorkbook(data) {
  const wb = XLSX.read(data, { type: "array" });
  const ws = wb.Sheets[wb.SheetNames[0]];
  if (!ws) return { list: [], skipped: 0 };
  const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: "" });
  if (!rows.length) return { list: [], skipped: 0 };

  // 1) 헤더 행 찾기: 앞쪽 여러 행을 훑어 '항목/품목/상품명…' 셀이 있는 행
  let headerIdx = -1, nameCol = -1, specCol = -1;
  const scan = Math.min(rows.length, 15);
  for (let r = 0; r < scan; r++) {
    const cells = rows[r].map((c) => String(c).trim());
    const nc = cells.findIndex((c) => NAME_HEADERS.test(c));
    if (nc >= 0) {
      headerIdx = r;
      nameCol = nc;
      specCol = cells.findIndex((c) => SPEC_HEADERS.test(c));
      break;
    }
  }

  let startRow;
  if (headerIdx >= 0) {
    startRow = headerIdx + 1;
  } else {
    // 헤더를 못 찾음: 첫 열을 상품명으로 가정하고, 숫자/제목만 있는 맨 윗행은 건너뜀
    nameCol = 0; specCol = -1; startRow = 0;
    // 첫 행이 전부 숫자가 아니고 글자 제목 같으면 1행부터
    const first = rows[0].map((c) => String(c).trim());
    if (first.filter(Boolean).length <= 1) startRow = 1;
  }

  const list = [];
  let skipped = 0;
  for (let r = startRow; r < rows.length; r++) {
    const row = rows[r];
    const name = String(row[nameCol] == null ? "" : row[nameCol]).trim();
    if (!name) continue;
    if (isIgnored(name)) { skipped++; continue; }
    const spec = specCol >= 0 ? String(row[specCol] == null ? "" : row[specCol]).trim() : "";
    list.push({ name, spec });
  }
  return { list, skipped };
}

fileEl.addEventListener("change", async (e) => {
  resultEl.hidden = true;
  const f = e.target.files[0];
  if (!f) return;
  try {
    setStatus("엑셀 읽는 중…");
    const buf = await f.arrayBuffer();
    const parsed = parseWorkbook(new Uint8Array(buf));
    items = parsed.list;
    skippedCount = parsed.skipped;
    if (!items.length) {
      fileInfo.textContent = "상품명을 찾지 못했습니다. '항목'(또는 상품명) 열이 있는지 확인해 주세요.";
      itemListEl.hidden = true;
      runBtn.disabled = true;
    } else {
      fileInfo.textContent = `${f.name} — 물품 ${items.length}개` +
        (skippedCount ? ` (배송비 등 ${skippedCount}개 제외)` : "");
      itemListEl.hidden = false;
      itemListEl.innerHTML = items.map((it, i) =>
        `<div>${i + 1}. ${escapeHtml(it.name)}` +
        (it.spec ? ` <span class="muted">[${escapeHtml(it.spec)}]</span>` : "") + `</div>`).join("");
      runBtn.disabled = false;
    }
    setStatus("");
  } catch (err) {
    console.error(err);
    fileInfo.textContent = "엑셀을 읽는 중 오류가 났습니다: " + err.message;
    runBtn.disabled = true;
  }
});

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function sendToTab(message) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) throw new Error("활성 탭을 찾을 수 없습니다.");
  if (!/gmarket\.co\.kr/.test(tab.url || "")) {
    throw new Error("지마켓 장바구니 페이지를 연 상태에서 실행해 주세요.");
  }
  try {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
  } catch (_) { /* 이미 주입돼 있으면 무시 */ }
  return await chrome.tabs.sendMessage(tab.id, message);
}

scanBtn.addEventListener("click", async () => {
  resultEl.hidden = true;
  setStatus("장바구니 상품을 읽는 중…");
  try {
    const res = await sendToTab({ type: "SCAN" });
    if (!res || !res.ok) throw new Error((res && res.error) || "응답 없음");
    setStatus("");
    resultEl.hidden = false;
    if (res.count === 0) {
      resultEl.innerHTML = `<span class="warn">장바구니에서 상품을 0개 인식했습니다.</span><br>장바구니 페이지가 맞는지, 또는 아래 '안 될 때' 설명을 확인해 주세요.`;
    } else {
      resultEl.innerHTML = `장바구니에서 <b>${res.count}개</b> 상품 인식:<ul>` +
        res.names.map((n) => `<li>${escapeHtml(n)}</li>`).join("") + `</ul>`;
    }
  } catch (err) {
    setStatus("");
    resultEl.hidden = false;
    resultEl.innerHTML = `<span class="warn">오류: ${escapeHtml(err.message)}</span>`;
  }
});

runBtn.addEventListener("click", async () => {
  if (!items.length) return;
  resultEl.hidden = true;
  setStatus("장바구니에서 선택하는 중…");
  const match = document.querySelector('input[name="match"]:checked').value;
  const uncheckRest = $("uncheckRest").checked;
  try {
    const res = await sendToTab({ type: "SELECT", items, match, uncheckRest });
    if (!res || !res.ok) throw new Error((res && res.error) || "응답 없음");
    setStatus("");
    resultEl.hidden = false;
    let html = `장바구니 상품 <b>${res.total}개</b> 중 <b>${res.checked}개</b> 체크` +
      (uncheckRest ? `, ${res.uncheckedCount}개 해제` : "") + `.`;
    if (skippedCount) html += ` <span class="muted">(배송비 등 ${skippedCount}개는 처음부터 제외)</span>`;
    if (res.unmatchedExcel && res.unmatchedExcel.length) {
      html += `<br><span class="warn">장바구니에서 못 찾은 물품 ${res.unmatchedExcel.length}개:</span><ul>` +
        res.unmatchedExcel.map((n) => `<li>${escapeHtml(n)}</li>`).join("") + `</ul>`;
    }
    resultEl.innerHTML = html;
  } catch (err) {
    setStatus("");
    resultEl.hidden = false;
    resultEl.innerHTML = `<span class="warn">오류: ${escapeHtml(err.message)}</span>`;
  }
});

/* 옵션 기억 */
chrome.storage?.local.get(["match", "uncheckRest"], (v) => {
  if (v.match) { const el = document.querySelector(`input[name="match"][value="${v.match}"]`); if (el) el.checked = true; }
  if (typeof v.uncheckRest === "boolean") $("uncheckRest").checked = v.uncheckRest;
});
document.addEventListener("change", () => {
  const match = document.querySelector('input[name="match"]:checked')?.value;
  chrome.storage?.local.set({ match, uncheckRest: $("uncheckRest").checked });
});
