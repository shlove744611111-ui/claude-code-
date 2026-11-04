/* popup.js — 엑셀 파싱 + 콘텐츠 스크립트와 통신 */

let items = []; // 엑셀에서 읽은 구입 물품명 배열

const $ = (id) => document.getElementById(id);
const fileEl = $("file");
const fileInfo = $("fileInfo");
const itemListEl = $("itemList");
const runBtn = $("runBtn");
const scanBtn = $("scanBtn");
const statusEl = $("status");
const resultEl = $("result");

function setStatus(msg) { statusEl.textContent = msg || ""; }

/* 엑셀/CSV에서 상품명 열을 찾아 목록으로 만든다 */
function parseWorkbook(data) {
  const wb = XLSX.read(data, { type: "array" });
  const ws = wb.Sheets[wb.SheetNames[0]];
  if (!ws) return [];
  const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: "" });
  if (!rows.length) return [];

  // 헤더 행에서 '상품명/품목/물품/name' 열을 찾는다
  const headerRow = rows[0].map((c) => String(c).trim());
  const nameKeywords = /(상품\s*명|품\s*목|물\s*품|품명|name|item)/i;
  let nameCol = headerRow.findIndex((h) => nameKeywords.test(h));
  let startRow = 0;
  if (nameCol >= 0) {
    startRow = 1; // 헤더가 있으니 다음 행부터
  } else {
    // 헤더가 없으면: 첫 행의 각 셀이 숫자가 아닌 글자를 담은 '가장 왼쪽' 열을 상품명 열로 가정
    nameCol = 0;
    const looksLikeHeaderOnlyNumbers = headerRow.every((c) => c === "" || /^\d+$/.test(c));
    startRow = looksLikeHeaderOnlyNumbers ? 1 : 0;
  }

  const out = [];
  for (let r = startRow; r < rows.length; r++) {
    const cell = rows[r][nameCol];
    const name = (cell === undefined || cell === null) ? "" : String(cell).trim();
    if (name) out.push(name);
  }
  return out;
}

fileEl.addEventListener("change", async (e) => {
  resultEl.hidden = true;
  const f = e.target.files[0];
  if (!f) return;
  try {
    setStatus("엑셀 읽는 중…");
    const buf = await f.arrayBuffer();
    items = parseWorkbook(new Uint8Array(buf));
    if (!items.length) {
      fileInfo.textContent = "상품명을 찾지 못했습니다. 첫 번째 열에 품목명을 넣거나, 헤더에 '상품명' 열을 만들어 주세요.";
      itemListEl.hidden = true;
      runBtn.disabled = true;
    } else {
      fileInfo.textContent = `${f.name} — 품목 ${items.length}개`;
      itemListEl.hidden = false;
      itemListEl.innerHTML = items.map((n, i) => `<div>${i + 1}. ${escapeHtml(n)}</div>`).join("");
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

/* 현재 탭이 지마켓인지 확인하고 콘텐츠 스크립트에 메시지를 보낸다.
   content_scripts로 자동 주입되지만, 설치 전 열려 있던 탭 대비로 한 번 더 주입한다. */
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
    if (res.unmatchedExcel && res.unmatchedExcel.length) {
      html += `<br><span class="warn">장바구니에서 못 찾은 엑셀 품목 ${res.unmatchedExcel.length}개:</span><ul>` +
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
