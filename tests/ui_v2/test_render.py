"""WRT 渲染層測試組｜test-first 契約 E：Streamlit 渲染層（`src/ui_v2/render.py`）

⚠️ **本檔是規格書，不是現況描述。** 撰寫當下 `src/ui_v2/render.py` **尚不存在**，
   本檔因此**應該是紅燈**（`ImportError: cannot import name 'render'`）——
   紅燈即本輪的正確產出。實作由 WRI 組補上，⛔ 本組不寫實作。

────────────────────────────────────────────────────────────────────
實作組（WRI）必須提供：`src/ui_v2/render.py`
────────────────────────────────────────────────────────────────────
`render_page_today(view_model) -> None`
    **唯一 import streamlit 的檔。** 做三件事：
      ① 把 `markup.page_css(mode)` 注入**一次**；
      ② 逐 block 呼叫 `st.markdown(markup.grid_html(...), unsafe_allow_html=True)`
         —— **一個 grid ＝ 一次呼叫**，⛔ 不得拆成多次；
         有登記層級網格的層（`page_today.LAYER_GRID_COLS`，實測只有第二層）
         再由 `markup.layer_html()` 把該層的 block 包成一列並排；
      ③ 主 CTA 用**真 widget**（`st.button` / `st.form_submit_button`），
         ⛔ 不得畫成一段長得像按鈕的 HTML。

`view_model` 的形狀（本檔即契約，見 `_fake_view_model()`）::

    {
      "mode":     "dark",                       # 傳給 markup.page_css()
      "blocks":   [ {"block": <block key>,
                     "cards": [ {state, title, value, level, badge_n, facts}, … ]}, … ],
      "main_cta": dict(page_today.main_cta_state(...)),   # {"enabled": bool, "note": str|None}
    }

  ⚠️ 這個形狀**是本組定的，不是客戶或規格給的** —— 規格只到 `markup` 那一層。
     WRI 若有更好的切法，請走總管、⛔ 不要自己改測試遷就實作
     （`CLAUDE.md §-2` 規則 3/4：實作者不得自己驗收自己）。

────────────────────────────────────────────────────────────────────
本檔守的三件事（刻意只有三條 —— 冒煙，不是把 `markup` 再測一遍）
────────────────────────────────────────────────────────────────────
  ① 整頁 mount 沒有 uncaught exception，而且**在 `markup` 層驗過的字串真的走到
     `st.markdown` 上**（不然 `markup` 全綠、頁面卻是空的，沒人會發現）。
  ② CSS 只注入一次；**每個 grid 恰好一次 `st.markdown`**，且那一段自己閉合。
  ③ 主 CTA 是 `at.button` 裡的真 widget，標籤**逐字**等於 `page_today.MAIN_CTA["label"]`。

⚠️ **`at.form_submit_button` 不存在** —— `st.form_submit_button` 產生的鈕落在
   `at.button`（本組實測前總管已複驗）。本檔一律查 `at.button`。

⛔ **本檔刻意不掛 `@pytest.mark.slow`。** 該 marker 的定義（`pytest.ini:8`）是
   「Streamlit AppTest 等 runtime e2e（**單測 >5s**）；CI slow lane 跑」，
   而本檔是 0.0x 秒級的冒煙；掛上去會落進 `continue-on-error` 的 informational
   lane ⇒ **紅了不擋 merge ＝ 守衛降級**。要跑得慢再改，別先把煞車拆了。

⛔ **本檔不在模組層 stub streamlit** —— repo 有三層污染防線
   （`tests/conftest.py` 的 identity 還原 ＋ `pytest_collection_finish` backstop
   ＋ `tests/test_zz_streamlit_pollution_lock.py`）。這裡用真的 `AppTest`。
"""
from __future__ import annotations

import re

import pytest

from src.ui_v2 import components, page_today  # noqa: F401  （components 供未來擴充／文件對照）
from src.ui_v2 import markup, render   # ← 本輪不存在 → ImportError。**紅燈即正確產出。**


_CLASS_ATTR_RE = re.compile(r'class\s*=\s*"([^"]*)"')
_FIRST_TAG_RE = re.compile(r"<\s*[A-Za-z][^>]*>")

#: `:root` 裡一定會有的宣告形式，用來數「CSS 被注入了幾次」。
#: ⛔ 不寫死顏色值 —— 只認 token 名，值改了本條不該跟著紅。
_CSS_FINGERPRINT = "--paper:"


def _first_tag_classes(html: str) -> set[str]:
    m = _FIRST_TAG_RE.search(html)
    assert m, f"沒有產出任何 HTML 標籤：{html[:120]!r}"
    cm = _CLASS_ATTR_RE.search(m.group(0))
    return set(cm.group(1).split()) if cm else set()


def _carries_class(html: str, cls: str) -> bool:
    """`html` 裡有沒有一個 `class="…"` **屬性**含這個 class。

    ⚠️ 刻意只認屬性、不認裸字串 —— CSS 那一段也會出現 `.cls{…}`，
       用裸字串會把樣式表誤算成一次 grid 渲染。
    """
    pat = re.compile(r"(?<![\w-])" + re.escape(cls) + r"(?![\w-])")
    return any(pat.search(m.group(1)) for m in _CLASS_ATTR_RE.finditer(html))


def _count_class_attrs(html: str, cls: str) -> int:
    """`html` 裡有幾個 `class="…"` **屬性**含這個 class（⛔ 不認 CSS 選擇器的裸字串）。"""
    pat = re.compile(r"(?<![\w-])" + re.escape(cls) + r"(?![\w-])")
    return sum(1 for m in _CLASS_ATTR_RE.finditer(html) if pat.search(m.group(1)))


def _fake_view_model() -> dict:
    """最小可渲染的假 view model —— **全部欄位從契約層動態取**，⛔ 不手抄 block 清單。"""
    return {
        "mode": "dark",
        "blocks": [
            {
                "block": block,
                "cards": [
                    {
                        "state": "live",
                        "title": f"{block} 標題",
                        "value": "12.3",
                        "level": "中性",
                        "badge_n": page_today.resolve_badge(state="live"),
                        "facts": (),
                    }
                ],
            }
            for block in page_today.BLOCK_COLS
        ],
        "main_cta": dict(page_today.main_cta_state()),
    }


@pytest.fixture(scope="module")
def at(tmp_path_factory):
    """整頁跑一次，三條測試共用（`scope="module"` —— ⛔ 不要一條跑一次）。"""
    try:
        from streamlit.testing.v1 import AppTest
    except Exception as exc:   # pragma: no cover - collection stub 生態
        pytest.skip(f"streamlit.testing.v1.AppTest 不可用：{exc}")

    script = tmp_path_factory.mktemp("ui_v2_render") / "_ui_v2_today.py"
    script.write_text(
        "from src.ui_v2.render import render_page_today\n"
        f"render_page_today({_fake_view_model()!r})\n",
        encoding="utf-8",
    )
    _at = AppTest.from_file(str(script), default_timeout=120)
    _at.run()
    return _at


def _markdown_values(at) -> list[str]:
    return [m.value for m in at.markdown]


# ══════════════════════════════════════════════════════════════════
# ① mount 乾淨 ＋ markup 驗過的東西真的走到畫面上
# ══════════════════════════════════════════════════════════════════
def test_the_page_mounts_and_paints_the_markup_i_verified(at):
    """冷啟動整頁 mount：**沒有 uncaught exception，而且不是一張空頁**。

    ⚠️ 這一條看得到的只有「畫得出來、而且畫的是 `markup` 產的那些字串」；
       它**看不到**版面在真瀏覽器裡排成幾欄（沒有 layout engine，
       `AppTest` 也沒有 viewport 參數）。版面對不對不在本檔射程內。
    """
    assert not at.exception, f"render_page_today mount 有 uncaught exception：{at.exception}"

    values = _markdown_values(at)
    assert values, "整頁一個 st.markdown 都沒有 —— 空頁"
    blob = "\n".join(values)

    # (a) 樣式表真的被注入
    assert _CSS_FINGERPRINT in blob, "CSS 沒有被注入（找不到 token 宣告）"

    # (b) 每個 block 的 grid 容器 class 都出現在畫面上
    for block in page_today.BLOCK_COLS:
        for cls in _first_tag_classes(markup.grid_html(block=block, cards=("<i>x</i>",))):
            assert _carries_class(blob, cls), (
                f"{block} 的 grid 容器 class {cls!r} 沒有走到 st.markdown 上"
            )

    # (c) 徽章的圖示＋文字真的畫出來（`UI_COMPONENTS.md §2`：⛔ 不得只靠顏色）
    live_badge = page_today.resolve_badge(state="live")
    spec = components.badge(live_badge)
    assert spec["icon"] in blob, f"#{live_badge} 的圖示沒有畫出來"
    assert spec["text"] in blob, f"#{live_badge} 的文字沒有畫出來"


# ══════════════════════════════════════════════════════════════════
# ② CSS 注入一次 ＋ 一個 grid ＝ 一次 st.markdown
# ══════════════════════════════════════════════════════════════════
def test_css_is_injected_once_and_each_grid_is_a_single_markdown_call(at):
    """🔴 總管拍板的實作約束 2：**一個網格要在一次 `st.markdown` 裡整段吐完**。

    未閉合的 `<div>` **不會**跨呼叫包住下一次的產出 —— Streamlit 每次
    `st.markdown` 各自是一個獨立的 DOM 節點，開在 A 呼叫、想收在 B 呼叫，
    結果是版面靜默走樣（不會報錯、不會變紅）。
    repo 先例：`src/ui/render/station_cards.py` docstring 逐字
    「整面牆是一次 `st.markdown` 的純 HTML」。

    ⚠️ **刻意不釘「一個 block 一次 markdown」**：第二層的三個 block 會被
    `layer_html()` 包成一列並排，很自然地落在同一次 `st.markdown` 裡。
    本條釘的是**不變的那兩件事**：每個 block 的網格容器**全頁恰好出現一次**、
    以及**凡是帶網格的那一次呼叫，自己閉合**。怎麼分段由實作決定。

    順便守 CSS 只注入一次 —— 注入兩次不會壞掉，但後面那份會蓋前面那份，
    改了樣式卻沒反應時沒有人查得到原因。
    """
    assert not at.exception, f"mount 有 uncaught exception：{at.exception}"
    values = _markdown_values(at)

    injected = [v for v in values if _CSS_FINGERPRINT in v]
    assert len(injected) == 1, f"CSS 被注入了 {len(injected)} 次，應為 1 次"

    blob = "\n".join(values)
    for block in page_today.BLOCK_COLS:
        # 每個 block 的卡標在假 view model 裡是**唯一的**（`_fake_view_model`），
        # 所以數它比數 class 靠譜 —— 不依賴實作怎麼命名、也不會把
        # 共用同一個網格 class 的兩個 block 算成一個。
        title = f"{block} 標題"
        assert blob.count(title) == 1, (
            f"{block} 的卡在畫面上出現 {blob.count(title)} 次，應為 1 次 —— "
            "0 次代表這個 block 根本沒畫，>1 次代表畫重複了"
        )

    for v in values:
        if "<div" not in v:
            continue
        assert v.count("<div") == v.count("</div>"), (
            f"這一次 st.markdown 的 `<div>` 開 {v.count('<div')} 閉 {v.count('</div>')} —— "
            f"未閉合的標籤不會跨呼叫生效：{v[:160]!r}"
        )


def test_the_second_layer_is_wrapped_in_its_layer_grid(at):
    """🔴 有登記層級網格的層，畫面上要真的有那個**層級網格容器**。

    沒有它，第二層的三個 block 只會直向堆疊 —— `today.holdings` 變成
    疊在最下面的全寬卡，正面違反客戶 2026-09-16「第二層＝**3 張並排卡**」。
    ⚠️ 這一條看得到的是「**層級網格容器有被畫出來、而且那一段自己閉合**」；
       它**看不到**瀏覽器真的把三張卡排成一列（沒有 layout engine）——
       欄數正確與否由 `test_markup.py` 在 CSS 文字上守。
    """
    assert not at.exception, f"mount 有 uncaught exception：{at.exception}"
    assert page_today.LAYER_GRID_COLS, "沒有任何層登記層級網格 —— 本條要重寫"
    values = _markdown_values(at)

    for layer in sorted(page_today.LAYER_GRID_COLS):
        n = len(page_today.blocks_of_layer(layer))
        probe = markup.layer_html(
            layer=layer,
            block_htmls=tuple(f"<i>x{i}</i>" for i in range(n)),
        )
        for cls in _first_tag_classes(probe):
            hits = sum(_count_class_attrs(v, cls) for v in values)
            assert hits == 1, (
                f"第 {layer} 層的層級網格 class {cls!r} 在畫面上出現 {hits} 次，應為 1 次"
            )


# ══════════════════════════════════════════════════════════════════
# ③ 主 CTA 是真 widget
# ══════════════════════════════════════════════════════════════════
def test_the_main_cta_is_a_real_button_with_the_exact_label(at):
    """主 CTA 必須是 `at.button` 裡的**真 widget**，標籤**逐字**等於 SSOT。

    畫成 HTML 假鈕的話：按下去不會 rerun、鍵盤 tab 不到、螢幕閱讀器讀不出
    「這是按鈕」—— 而畫面上看起來一模一樣。
    ⚠️ `at.form_submit_button` **不存在**；`st.form_submit_button` 產生的鈕
       也落在 `at.button`，所以兩種寫法本條都吃。
    """
    assert not at.exception, f"mount 有 uncaught exception：{at.exception}"

    label = page_today.MAIN_CTA["label"]
    labels = [b.label for b in at.button]
    assert label in labels, f"主 CTA 不是真 widget（`at.button` 只有 {labels}）"
    assert labels.count(label) == 1, (
        f"主 CTA 出現 {labels.count(label)} 顆 —— "
        "`UI_COMPONENTS.md §3 按鈕表主 CTA 列`「主 CTA（**全站唯一一顆**）」"
    )

    blob = "\n".join(_markdown_values(at))
    assert label not in blob, "主 CTA 的標籤同時被畫成 HTML —— ⛔ 不得有一顆假鈕"
