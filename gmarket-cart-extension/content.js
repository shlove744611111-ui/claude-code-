/* content.js — 지마켓 장바구니에서 상품을 인식하고 엑셀 목록대로 체크한다.
 *
 * ▼▼▼ 화면 개편으로 인식이 안 될 때 이 SELECTORS를 실제 화면에 맞게 고치세요 ▼▼▼
 *  - F12(개발자도구)로 장바구니 상품명/체크박스의 class나 href를 확인한 뒤 추가하면 됩니다.
 */
const SELECTORS = {
  // 상품명 링크로 인정할 href 패턴(지마켓 상품 상세 URL). 하나라도 포함되면 상품으로 봄.
  productHref: ["goodscode", "item.gmarket", "/vip/", "/Item", "/n/"],
  // (선택) 상품명 요소를 직접 지정하고 싶을 때. 비워두면 href 기반 자동 인식 사용.
  itemNameOverride: [], // 예: ['a.box__item-title', '.text__item-title']
  // (선택) 상품 행 컨테이너를 직접 지정하고 싶을 때.
  itemRowOverride: [],  // 예: ['li.box__item', 'div.list-item']
};
/* ▲▲▲ 여기까지 ▲▲▲ */

(function () {
  if (window.__gmCartExtLoaded) return; // 중복 주입 방지
  window.__gmCartExtLoaded = true;

  const MAX_UP = 8; // 상품명 → 체크박스를 찾을 때 거슬러 올라갈 최대 깊이

  function norm(s) {
    return String(s || "").toLowerCase().replace(/\s+/g, "").replace(/[\[\]（）()·,./_-]/g, "");
  }
  // 상품명을 단어(토큰)들로 쪼갠다 (공백/구분기호 기준). 각 토큰은 정규화.
  function tokenize(raw) {
    return String(raw || "")
      .split(/[\s,./_\-·]+/)
      .map(norm)
      .filter(Boolean);
  }
  function text(el) {
    return (el ? el.textContent : "").replace(/\s+/g, " ").trim();
  }

  // '전체선택' 같은 체크박스는 제외
  function isSelectAll(cb) {
    const hay = norm([cb.id, cb.name, cb.getAttribute("aria-label"),
      cb.closest("label") ? cb.closest("label").textContent : ""].join(" "));
    return /전체|모두|전체선택|selectall|allcheck|checkall/.test(hay);
  }

  function isProductAnchor(a) {
    const href = a.getAttribute("href") || "";
    if (!SELECTORS.productHref.some((p) => href.includes(p))) return false;
    return text(a).length >= 2;
  }

  // 특정 요소에서 위로 올라가며 '아이템 체크박스'를 가진 행을 찾는다
  function findRowAndCheckbox(startEl) {
    let el = startEl;
    for (let i = 0; i < MAX_UP && el; i++) {
      const parent = el.parentElement;
      if (!parent) break;
      const cbs = Array.from(parent.querySelectorAll('input[type="checkbox"]')).filter((c) => !isSelectAll(c));
      if (cbs.length) {
        // 가장 가까운(맨 처음) 체크박스 사용
        return { row: parent, checkbox: cbs[0] };
      }
      el = parent;
    }
    return null;
  }

  // 장바구니 상품 목록 수집: [{name, checkbox, nameEl, row}]
  function collectCartItems() {
    const items = [];
    const seenCb = new Set();

    // 1) 오버라이드가 있으면 우선 사용
    if (SELECTORS.itemNameOverride.length) {
      const nameEls = document.querySelectorAll(SELECTORS.itemNameOverride.join(","));
      nameEls.forEach((nameEl) => {
        const rc = findRowAndCheckbox(nameEl);
        if (rc && !seenCb.has(rc.checkbox)) {
          seenCb.add(rc.checkbox);
          items.push({ name: text(nameEl), checkbox: rc.checkbox, nameEl, row: rc.row });
        }
      });
      if (items.length) return items;
    }

    // 2) 상품 링크(href) 기반 자동 인식
    const anchors = Array.from(document.querySelectorAll("a[href]")).filter(isProductAnchor);
    anchors.forEach((a) => {
      const rc = findRowAndCheckbox(a);
      if (!rc) return;
      if (seenCb.has(rc.checkbox)) {
        // 같은 체크박스에 여러 링크 → 더 긴 이름을 상품명으로
        const exist = items.find((it) => it.checkbox === rc.checkbox);
        if (exist && text(a).length > exist.name.length) { exist.name = text(a); exist.nameEl = a; }
        return;
      }
      seenCb.add(rc.checkbox);
      items.push({ name: text(a), checkbox: rc.checkbox, nameEl: a, row: rc.row });
    });
    if (items.length) return items;

    // 3) 폴백: 아이템 체크박스마다 행에서 가장 긴 링크/텍스트를 상품명으로
    const cbs = Array.from(document.querySelectorAll('input[type="checkbox"]')).filter((c) => !isSelectAll(c));
    cbs.forEach((cb) => {
      if (seenCb.has(cb)) return;
      let row = cb;
      for (let i = 0; i < MAX_UP && row.parentElement; i++) row = row.parentElement;
      const links = Array.from(row.querySelectorAll("a, strong, span"))
        .map((e) => ({ e, t: text(e) }))
        .filter((o) => o.t.length >= 3)
        .sort((a, b) => b.t.length - a.t.length);
      if (links.length) {
        seenCb.add(cb);
        items.push({ name: links[0].t, checkbox: cb, nameEl: links[0].e, row });
      }
    });
    return items;
  }

  function clickTarget(cb) {
    const id = cb.id;
    if (id) {
      const lab = document.querySelector('label[for="' + CSS.escape(id) + '"]');
      if (lab) return lab;
    }
    const wrap = cb.closest("label");
    if (wrap) return wrap;
    return cb;
  }

  // 체크 상태를 want로 맞춘다. 바뀌었으면 true.
  function setChecked(cb, want) {
    if (!!cb.checked === want) return false;
    try { clickTarget(cb).click(); } catch (_) {}
    if (!!cb.checked !== want) {
      // 클릭이 반영 안 되면 강제로 상태를 바꾸고 이벤트를 쏜다
      cb.checked = want;
      cb.dispatchEvent(new Event("input", { bubbles: true }));
      cb.dispatchEvent(new Event("change", { bubbles: true }));
    }
    return true;
  }

  function matchExcel(cartName, excelItems, mode) {
    const nc = norm(cartName);
    if (!nc) return null;
    for (const { raw, n, toks } of excelItems) {
      if (!n) continue;
      if (mode === "exact") {
        if (nc === n) return raw;
        continue;
      }
      // 부분 일치: 엑셀 품목명의 '모든 단어'가 장바구니 상품명에 들어있으면 일치
      const maxTok = toks.reduce((m, t) => Math.max(m, t.length), 0);
      if (toks.length > 0 && maxTok >= 2 && toks.every((t) => nc.includes(t))) return raw;
      // 장바구니 이름이 짧게 잘려 보이는 경우: 반대 방향 포함도 허용
      if (nc.length >= 2 && n.includes(nc)) return raw;
    }
    return null;
  }

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    try {
      if (msg && msg.type === "SCAN") {
        const items = collectCartItems();
        sendResponse({ ok: true, count: items.length, names: items.map((i) => i.name) });
        return;
      }
      if (msg && msg.type === "SELECT") {
        const items = collectCartItems();
        const excelNorms = (msg.items || []).map((raw) => ({ raw, n: norm(raw), toks: tokenize(raw) }));
        const matchedExcel = new Set();
        let checked = 0, uncheckedCount = 0;
        const matchedNames = [];

        items.forEach((it) => {
          const hit = matchExcel(it.name, excelNorms, msg.match);
          if (hit) {
            matchedExcel.add(hit);
            matchedNames.push(it.name);
            if (setChecked(it.checkbox, true)) checked++;
          } else if (msg.uncheckRest) {
            if (setChecked(it.checkbox, false)) uncheckedCount++;
          }
        });

        const unmatchedExcel = excelNorms.map((e) => e.raw).filter((raw) => !matchedExcel.has(raw));
        sendResponse({
          ok: true,
          total: items.length,
          checked,
          uncheckedCount,
          matchedNames,
          unmatchedExcel,
        });
        return;
      }
      sendResponse({ ok: false, error: "알 수 없는 요청" });
    } catch (err) {
      sendResponse({ ok: false, error: String(err && err.message || err) });
    }
    // 동기 응답
  });
})();
