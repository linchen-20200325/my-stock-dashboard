"""「🚦 今天」頁版面與狀態契約 —— 純結構層（契約 C）。

唯一資料來源：`docs/v2/spec/UI_PAGE_TODAY.md`（＋ 它引用的第 1、2 份）。
每個值旁以 `# UI_PAGE_TODAY.md <章節名>` 標出處（⛔ 不寫行號 —— CLAUDE.md §8.2.A.0 規則 1）。
⛔ 本檔不 import streamlit：**本輪只做結構定義**（四層有哪些 block、各自掛哪一階、
   狀態怎麼映射），`st.*` 渲染留到下一輪。

**四層由層序自動掛**（UI_COMPONENTS.md §1「四層由 `layers[].n` 自動掛，⛔ 非逐塊手選」）：本檔的 `tier`／
`badge_size`／`title_px` **一律自 `components.tier_for_layer(layer)` 推導**，
⛔ 不逐塊寫死 —— 手選在結構上就沒有落點。

**§1 Fail Loud 在本頁的落點**（UI_PAGE_TODAY.md ④ 反例自檢）：
灰態／紅態的大字區**一律留白**，⛔ 不顯示 `0`、⛔ 不顯示上一輪殘值；
`degraded` **觀測照出、判決留白**；`partial` 分子分母拿不到 → **fail-safe 降級 #7**，
⛔ 不得退回 #1「正常」（往「看起來沒事」退就是假綠燈）。
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Final, Iterable, Mapping

from src.ui_v2 import components


def _frozen(mapping: dict) -> Mapping:
    return MappingProxyType(mapping)


# ══════════════════════════════════════════════════════════════════
# ① 四層結構 —— UI_PAGE_TODAY.md ① 四層結構表
# ⚠️ 線框 `n0` 為**葉外 chrome**（五頁共用，不屬任何葉）→ 據實列出，⛔ 不計入四層。
# ⚠️ 第三層與第四層**線框同為 `n3`**（UI_PAGE_TODAY.md ① 四層結構表
#    「第三層 操作列」／「第四層 展開佐證」兩列逐字），非筆誤。
# ══════════════════════════════════════════════════════════════════
_LAYER_PLAN: Final[tuple[tuple[int, str, tuple[str, ...], bool, bool], ...]] = (
    # (layer, wireframe_n, blocks, has_main_cta, allows_interaction)
    # 葉外 chrome：3 張狀態卡（交易日／總經／Sheet），
    # UI_PAGE_TODAY.md ① 四層結構表「葉外」列 ＋ ①「葉外 chrome」段。
    # allows_interaction=True 的依據：UI_PAGE_TODAY.md ③「實作有、線框無」表
    # 「頁首『上一次更新的結果』整段」列：「…含**全頁唯一** `st.expander`…
    # 建議掛 `n0` 葉外 chrome」—— expander 即互動元件。
    (0, "n0", ("today.statusbar",), False, True),
    # 第一層＝**單一結論燈** ＋ 一句話結論
    #（user 2026-09-16 裁示，UI_PAGE_TODAY.md ①「第一層 `today.verdict`」段）；
    # ⛔ 不再是 3 張並排卡。互動：UI_PAGE_TODAY.md ③「線框有、實作無」表
    # 「『展開佐證 ▸』觸發器」列，逐字落在 today.verdict.live。
    (1, "n1", ("today.verdict",), False, True),
    # 第二層＝3 張並排卡（UI_PAGE_TODAY.md ①「第二層」段「3 張並排卡」已決句）；
    # ⛔ 本層不得放任何按鈕、連結、`st.popover`（UI_PAGE_TODAY.md ①「第二層」段起手句
    #   ／同節 `today.holdings` 條「組成**只用既有元件**」行）。
    (2, "n2", ("today.summary", "today.key_banner", "today.holdings"), False, False),
    # ⚠️ ~~第三層＝操作列，**全站唯一一顆主 CTA** 掛在這裡~~（UI_PAGE_TODAY.md ① 四層結構表
    #「第三層 操作列」列 ＋ ①「第三層 `today.actions`」段）。
    #   **2026-09-22 有意識的政策變更，⛔ 不是漏刪；決策者：客戶。**
    #   **現行：第三層＝操作列，「每頁首屏唯一一顆」主 CTA 掛在這裡**（出處同上列，未變）。
    #   客戶裁示逐字：「**不是「全站唯一」，是「每頁首屏唯一」。** 理由：客戶原話是
    #   『首屏僅允許一顆主 CTA』——是『每屏一顆』。」
    #   **舊說法的理由仍然成立，⛔ 不是寫錯**：在只有「🚦 今天」一頁時，「全站唯一」與
    #   「每頁首屏唯一」**外延相同** —— 兩句話挑不出差別，寫哪個都對。
    #   **被權衡掉的原因**：五頁 IA 落地後，🔎 選股頁有自己的主 CTA `🎯 開始選股`
    #   ⇒「全站唯一」變成**假的**。`docs/v2/spec/UI_PAGE_FIND.md` ① 已逐字否證：
    #   「⚠️ **2026-09-16 修正（WJ）**：原寫「**全站唯一一顆**主 CTA」**不成立** ——
    #    葉2 那顆同為 `type="primary"`…可宣稱的是…「**選股**主 CTA 只有一顆、
    #    且在預設葉 l1 可見」；⛔ 不得寫成全站唯一。」
    #   ⚠️ **FIND 規格單方面否證、其餘落點未同步** ⇒ 本輪就是在補這個同步。
    (3, "n3", ("today.actions",), True, True),
    # 第四層＝展開佐證（UI_PAGE_TODAY.md ① 四層結構表「第四層 展開佐證」列
    # ＋ ①「第四層」段）；t4 ＝ 1px **dashed**。
    (4, "n3", ("today.warroom", "today.detail"), False, True),
)


def _build_layers() -> tuple[Mapping[str, object], ...]:
    """把層序展開成版面層 —— `tier`／`badge_size`／`title_px` 全部**自動掛**。

    UI_COMPONENTS.md §1「四層由 `layers[].n` 自動掛，⛔ 非逐塊手選」：
    這個函式就是那句話的可執行形式 —— 三個密度相關欄位都只有一個來源
    （`components.tier_for_layer` → `components.CARD_TIERS`），沒有第二條路可以塞值。
    """
    built = []
    for layer, wireframe_n, blocks, has_main_cta, allows_interaction in _LAYER_PLAN:
        tier = components.tier_for_layer(layer)
        tier_spec = components.CARD_TIERS[tier]
        built.append(_frozen({
            "layer": layer,
            "wireframe_n": wireframe_n,
            "blocks": tuple(blocks),
            "tier": tier,
            "badge_size": tier_spec["badge_size"],
            "title_px": tier_spec["title_px"],
            "has_main_cta": has_main_cta,
            "allows_interaction": allows_interaction,
        }))
    return tuple(built)


LAYERS: Final[tuple[Mapping[str, object], ...]] = _build_layers()

#: block → **block 內部**一列放幾格，記法 `(桌機, 平板, 手機)`。
#: ⚠️ 語意：`cols` ＝ **一列幾格**，多的**換行排下一列、不是加欄**
#:   （`src/ui/views/_ui_kit.py::grid()` 逐字：先 `_n = min(cols, MAX_COLS)` 夾上限，
#:   內層 `_rows()` 再 `for _i in range(0, len(items), _n):` 切塊、
#:   每塊各 `yield _chunk, st.columns(len(_chunk))` ⇒ 開的是**新的一列**、不是更多欄）。
#: 🔴 ⛔ **不是**「這個 block 佔頁面幾欄」—— 同一層的幾個 block 彼此怎麼並排，
#:   看 `LAYER_GRID_COLS`（**兩個不同的網格，⛔ 不要混用**）。
#:
#: ⚠️ ~~`today.holdings` 刻意不在表內：線框 `n2` 未定義其 cols ⇒ ⛔ 不得自行發明一組塞進來。~~
#:   **2026-09-21 有意識的政策變更，⛔ 不是漏刪；決策者 AI 總管。**
#:   規格洞**已由總管推導補上**（見 `COLS_DERIVATION`）。**舊規則的理由仍然成立**：
#:   在**來歷沒被寫出來**之前填一組值就是捏造。**新規則為何勝出**：反捏造真正要擋的是
#:   「**把推導值偽裝成線框值**」，而那件事現在**擋在 `COLS_PROVENANCE` 上、機器驗得到**，
#:   比「一律不准填」更精準 —— 後者的代價是規格洞**永遠補不起來**。
BLOCK_COLS: Final[Mapping[str, tuple[int, int, int]]] = _frozen({
    "today.statusbar":  (1, 1, 1),   # UI_PAGE_TODAY.md ①「葉外 chrome」段
    "today.verdict":    (1, 1, 1),   # UI_PAGE_TODAY.md ①「第一層 today.verdict」段
    # ⚠️ ~~`"today.summary": (3, 2, 1)`   # UI_PAGE_TODAY.md ①「第二層」today.summary 條~~
    #   **2026-09-22 有意識的政策變更，⛔ 不是漏刪；決策者：客戶。**
    #   客戶裁示 B 逐字：「把 today.summary 從「卡內三欄」改成「三張獨立卡」。」
    #   ⇒ 3/2/1 → 1/1/1。
    #   **舊值的理由仍然成立**：線框 `wf_page_today.js` 的 `today.summary` block 逐字寫
    #   `cols: { desktop: 3, tablet: 2, phone: 1 }`，照線框抄是當時**唯一有來歷**的作法。
    #   **新值為何勝出**：那個 3/2/1 究竟是「卡內欄數」還是「層網格」，本來就是 U-1 的
    #   **真矛盾**（線框與原型兩端互斥，規格與本檔都只登記、不解）——
    #   ⛔ 不是實作可以自己挑一邊的事：**版面只有客戶能拍板**
    #   （CLAUDE.md §-1.5.D §03-2 ①），而客戶 2026-09-22 拍了。
    # 🔵 **客戶裁示值（⛔ 非線框值）** —— UI_PAGE_TODAY.md ③「U-1 已決」段；
    #   線框 `wf_page_today.js` 寫 3/2/1，客戶 2026-09-22 裁示 B **覆寫**
    #   （⛔ 線框檔本身不改 —— 它是客戶審過的版面來源，裁示是覆寫它、⛔ 不是改寫它）。
    # ⛔ 本筆**刻意不掛**其餘六筆那種 `# UI_PAGE_TODAY.md <章節名>` 的線框出處註解：
    #    那種註解代表「**線框寫了這個值**」，而線框**沒有**寫 1/1/1。
    "today.summary":    (1, 1, 1),
    "today.key_banner": (1, 1, 1),   # UI_PAGE_TODAY.md ①「第二層」today.key_banner 條
    "today.actions":    (1, 1, 1),   # UI_PAGE_TODAY.md ①「第三層 today.actions」段
    "today.warroom":    (1, 1, 1),   # UI_PAGE_TODAY.md ①「第四層」段
    "today.detail":     (3, 2, 1),   # UI_PAGE_TODAY.md ①「第四層」段
    # ⚠️⚠️ 總管推導值（**非線框**）—— 見 UI_PAGE_TODAY.md §① holdings cols 段
    # ⛔ 本筆**刻意不掛**其餘七筆那種 `# UI_PAGE_TODAY.md <章節名>` 的線框出處註解：
    #    那種註解代表「線框寫了這個值」，而線框 `n2` **沒有**定義這個 block 的 cols。
    "today.holdings":   (1, 1, 1),
})

#: 線框 `cols 3/2/1`（＝ 桌機 3／平板 2／手機 1）。
G3_COLS: Final[tuple[int, int, int]] = (3, 2, 1)


# ══════════════════════════════════════════════════════════════════
# `cols` 的**來歷**（provenance）—— ⛔ 註解不算數，來歷要機器讀得到
#
# 為什麼要有這組結構：`BLOCK_COLS` 裡混了 ~~兩~~ **三**種東西 ——
#   · ~~七筆~~ **六筆線框值**（客戶審過的 `wf_page_today.js` 寫死的）；
#   · 一筆**總管推導值**（線框沒寫、由 §① 排列段的 `cols` 語意 ＋ 原型形狀推出來的）；
#   · 🔵 一筆**客戶裁示值**（線框**有**寫、但被客戶 2026-09-22 裁示 B **覆寫**：
#     `today.summary` 3/2/1 → 1/1/1）。
#   **2026-09-22 有意識的政策變更，⛔ 不是漏刪；決策者：客戶。**
#   **舊句的理由仍然成立**：在客戶裁示之前，`BLOCK_COLS` 真的只有「線框值」與
#   「總管推導值」兩種，「兩種／七筆」是當時可驗的最誠實寫法。
#   **被權衡掉的只有那兩個字面數字** —— 客戶裁示 B 生出了第三種來歷；
#   ⛔ 不把它登記成獨立的一種，就等於讓 1/1/1 看起來像線框值（正是本段要擋的事）。
# 三者**可信度不同**，⛔ 不得長得一樣。把推導值／裁示值偽裝成線框值
# ＝ CLAUDE.md §1 的造假（「錯誤的數字比沒有數字更危險」的同一族問題：
#   **來歷錯的數字**會讓下一個人以為它經過客戶審查，從而不敢動、也不去補真正的線框）。
# 🔵 ⚠️ 客戶裁示值另有一個**反向**的風險：它確實經過客戶，但**線框仍寫著舊值** ——
#   若把它登記成線框值，下一個人去讀線框會讀到 3/2/1，以為 code 寫錯而「改回去」。
#   ⇒ 裁示值必須同時留下 `wireframe_value`（被覆寫掉的那個值），兩邊才對得起來。
# ══════════════════════════════════════════════════════════════════
#: ~~來歷的兩個字面值。⛔ 不得新增第三種而不同步 `COLS_DERIVATION` 與測試。~~
#: **2026-09-22 有意識的政策變更，⛔ 不是漏刪；決策者：客戶。**
#: **現行：來歷的三個字面值。⛔ 不得新增第四種而不同步 `COLS_DERIVATION` 與測試。**
#: **舊句的理由仍然成立，而且本次正是照它走的**：它要求的從來不是「永遠只能兩種」，
#: 而是「**新增一種就必須同步 `COLS_DERIVATION` 與測試**」—— 本次新增
#: `COLS_RULED_BY_CLIENT` 時，`COLS_DERIVATION` 新增一筆、
#: `tests/ui_v2/test_today_page.py` 的 C-1 段守衛同批一起改，⛔ 沒有繞過這個條件。
#: **被權衡掉的只有那個字面數字「兩」**（客戶裁示 B 生出了第三種來歷）。
COLS_FROM_WIREFRAME: Final[str] = "wireframe"
COLS_DERIVED_BY_LEAD: Final[str] = "derived_by_lead"
#: 🔵 **第三種來歷（2026-09-22 新增）**：線框**有**定義這個 block 的 `cols`，
#: 但客戶**明示裁示覆寫**它。
#: ⚠️ 與 `COLS_DERIVED_BY_LEAD` 的**關鍵差異**（⛔ 不要混用）——
#:   · 推導值＝**填線框沒寫的洞**（`wireframe_defines_cols=False`、`wireframe_value=None`）；
#:   · 裁示值＝**推翻線框寫過的值**（`wireframe_defines_cols=True`、`wireframe_value` 是舊值）。
#: 🔴 **只有客戶能做後者**（CLAUDE.md §-1.5.D §03-2 ①：版面異動必須客戶拍板）——
#: 總管**只能填洞、⛔ 不能覆寫線框**。守衛見 `tests/ui_v2/test_today_page.py` C-1 段
#: `test_the_lead_may_only_fill_a_hole_never_override_the_wireframe`。
COLS_RULED_BY_CLIENT: Final[str] = "client_ruling"

COLS_PROVENANCE: Final[Mapping[str, str]] = _frozen({
    "today.statusbar":  COLS_FROM_WIREFRAME,
    "today.verdict":    COLS_FROM_WIREFRAME,
    "today.summary":    COLS_RULED_BY_CLIENT,   # 🔵 客戶 2026-09-22 裁示 B 覆寫線框 3/2/1
    "today.key_banner": COLS_FROM_WIREFRAME,
    "today.actions":    COLS_FROM_WIREFRAME,
    "today.warroom":    COLS_FROM_WIREFRAME,
    "today.detail":     COLS_FROM_WIREFRAME,
    "today.holdings":   COLS_DERIVED_BY_LEAD,   # 🔴 ⛔ 不是線框值
})

#: 來歷**不是**線框的 block（**兩種**：總管推導填洞／🔵 客戶裁示覆寫）。
#: ⛔ 不得漏登 —— 漏登＝那個值看起來就像線框寫的、像客戶審過的。
#: ⚠️ **⛔ 刻意不改名**（2026-09-22）：客戶裁示值嚴格說不是「推導」出來的，
#:   但本常數是 computed（`src != COLS_FROM_WIREFRAME`），改名要動全部 caller 與測試，
#:   屬 §8.1 step 6 的反例（純 cosmetic、動到一堆 caller）。**語意以本註解為準。**
DERIVED_COLS: Final[frozenset[str]] = frozenset(
    block for block, src in COLS_PROVENANCE.items() if src != COLS_FROM_WIREFRAME
)

#: 每一筆**非線框值**的**推導鏈／裁示逐字 ＋ 決策者 ＋ 日期**
#: （UI_PAGE_TODAY.md §① holdings cols 段 ／ ③「U-1 已決」段）。
#: ⛔ 「總管說的」不算來歷 —— 要寫得出**怎麼推出來的**，下一個人才驗得到；
#: 客戶裁示則要**引得出原話**，⛔ 不得改寫語意（改寫＝把客戶的裁示換成自己的版本）。
#: ⚠️ 兩筆的**鍵集合必須一致**（含 `wireframe_value`）：鍵不齊會讓守衛只對其中一筆生效，
#:   而「只對一筆生效的守衛」看起來是綠的（CLAUDE.md §-2 規則 6 那個死碼實證的同一族）。
COLS_DERIVATION: Final[Mapping[str, Mapping[str, object]]] = _frozen({
    "today.holdings": _frozen({
        "value": (1, 1, 1),
        "decided_by": "AI 總管",
        "decided_on": "2026-09-21",
        "is_wireframe_value": False,
        "wireframe_defines_cols": False,   # 線框 `n2` 未定義此 block 的 cols
        # 🆕 2026-09-22 補（與 `today.summary` 那筆的鍵集合對齊）：
        # 線框沒寫 ⇒ **沒有「被覆寫掉的線框值」這種東西**。
        # ⛔ 不得填一個 tuple 進來：填了就等於宣稱「線框本來寫了 X、我把它改成 Y」，
        #    而「覆寫線框」是**客戶才能做的事**（CLAUDE.md §-1.5.D §03-2 ①）。
        "wireframe_value": None,
        "spec_section": "UI_PAGE_TODAY.md §① holdings cols 段",
        "basis": (
            "① `cols` 語意＝block 內部一列幾格：`src/ui/views/_ui_kit.py::grid()` 逐字 —— "
            "先 `_n = min(cols, MAX_COLS)` 夾上限，內層 `_rows()` 再 "
            "`for _i in range(0, len(items), _n):` 切塊、"
            "每塊各開一次 `yield _chunk, st.columns(len(_chunk))`，多的換行排下一列；"
            "`src/ui_v2/components.py` 的 `MAX_COLS` 註解與 `resolve_cols()` 同義。",
            "② 原型已畫出這張卡的形狀 —— `docs/v2/prototype/ui_prototype_today.html` 的"
            "「C. 持倉健檢」段（`section.blk.t2`，標題 `id` 為 `h-t`）："
            "一張 `.blk.t2` ＋ 一顆 `b2` 徽章（`s7`）＋ 卡內一個 `.stack` 裝 4 條 `.rowline` "
            "key-value ＋ 一行 `.note` 揭露句 —— 內部沒有網格。",
            "③ 規格同段同句法的刻意差異：UI_PAGE_TODAY.md ④ 反例自檢 A「第二層」條"
            "對 `today.summary` 寫"
            "「三格各自 #6（逐格獨立判態）」、對 `today.holdings` 寫整塊一顆 #7；"
            "`holdings_badge(*, n_classified)` 簽名裡也沒有「第幾格」這個參數"
            " ⇒ 這張卡是一個判態單位，不是三格。",
        ),
        # ⛔ 被打掉的第四條，⛔ 不得補回 `basis`：
        #    「①「第二層」today.holdings 條『組成只用既有元件：卡 .blk.t2 …』的『卡』
        #      是單數所以只有一張卡」—— 中文不標複數，這條推不出來
        #    （UI_PAGE_TODAY.md ① 四層結構表「第二層 核心卡」列就是拿 t2 當**型別**用）。
        #    守衛：tests/ui_v2/test_today_page.py
        #         ::test_rejected_singular_noun_argument_is_not_in_the_derivation_chain
        "rejected_basis": (
            "「卡 `.blk.t2`」是單數 ⇒ 只有一張卡（中文不標複數，⛔ 推不出來，已推翻）",
        ),
    }),
    # ═══════════════════════════════════════════════════════════
    # 🔵 客戶 2026-09-22 裁示 B —— U-1（`today.summary` 的 3/2/1 是卡內欄數還是
    #    層網格）結案。原登記見 UI_PAGE_TODAY.md ③ 尚未判定段，現已搬到 ③「U-1 已決」段。
    #
    # 🔴 **本筆最重要的一句：客戶裁示的是「第三個形狀」。**
    #    ⛔ 不得被寫成「客戶選了線框那端」，也⛔ 不得被寫成「客戶選了原型那端」——
    #      · 線框那端＝「**卡內三欄網格 3/2/1**」：客戶**同意有三個東西**（三張卡），
    #        但**不同意它們是一張卡內的三欄**（裁示逐字「不卡內三欄」）；
    #      · 原型那端＝「**一張 `.blk.t2` 卡內三條 `.rowline` 垂直堆疊**」：
    #        客戶**同意卡內不再有網格**，但**不同意它們共用一張卡**（逐字「三張獨立卡」）。
    #    ⇒ 兩端**各被採用一半、各被否掉一半**，合起來是一個**兩端都沒有畫過**的形狀。
    #    ⛔ 日後任何人把這筆改寫成「客戶採用了線框／原型」都是竄改裁示。
    # ═══════════════════════════════════════════════════════════
    "today.summary": _frozen({
        "value": (1, 1, 1),
        "decided_by": "客戶",
        "decided_on": "2026-09-22",
        "is_wireframe_value": False,
        # 🔵 與 holdings 那筆的**關鍵差異**：線框**有**定義這個 block 的 cols（3/2/1），
        #    本筆是**覆寫**它、⛔ 不是填洞。⇒ 只有客戶做得到（§-1.5.D §03-2 ①）。
        "wireframe_defines_cols": True,
        # 被覆寫掉的那個線框值，逐字留著 —— ⛔ 不得因為「已經不用了」就刪：
        # **線框檔本身沒有改**，下一個人去讀 `wf_page_today.js` 仍會讀到 3/2/1，
        # 要靠這一欄才對得起來（否則會以為 code 寫錯而「改回去」）。
        "wireframe_value": (3, 2, 1),
        "spec_section": "UI_PAGE_TODAY.md ③「U-1 已決」段",
        "basis": (
            "① 客戶 2026-09-22 裁示 B（逐字，⛔ 不得改寫語意）："
            "「把 today.summary 從「卡內三欄」改成「三張獨立卡」。」",
            "②「三張卡各自獨立，不互相壓縮」（客戶逐字）⇒ "
            "`BLOCK_COLS[\"today.summary\"]` 3/2/1 → 1/1/1 —— "
            "`cols` ＝ block 內部一列幾格，1 ⇒ 每列一格、三張卡在 block 內各佔一列"
            "垂直堆疊，⛔ 不會被擠成三分之一寬互相壓縮。",
            "③「layer_html 的 3 欄不變，block 內部不再巢狀網格」（客戶逐字）⇒ "
            "`LAYER_GRID_COLS[2]` 維持 `(3, 2, 1)`、⛔ 不動 —— "
            "客戶動的是 **block 內部**那一層網格，⛔ 不是**層級**網格。",
        ),
        # ⛔ 兩個**被裁掉**的讀法（＝ U-1 矛盾的兩端），⛔ 不得補回 `basis`：
        "rejected_basis": (
            "線框讀法「卡內三欄網格 3/2/1」：客戶裁示不採（逐字「不卡內三欄」）",
            "舊原型讀法「一張 `.blk.t2` 卡內三條 `.rowline`」：客戶裁示不採"
            "（逐字「三張獨立卡」—— ⛔ 不是一張卡）",
        ),
    }),
})


def cols_scope(block_key: str) -> str:
    """`BLOCK_COLS[block_key]` 管的是哪一層網格 —— 一律 `"inside_block"`。

    存在的理由是**把誤讀擋在型別上**：`BLOCK_COLS` 講的永遠是 **block 內部**一列幾格，
    ⛔ 從來不是「這個 block 在層裡佔幾欄」。後者是 `LAYER_GRID_COLS`／`blocks_per_row()`。
    """
    if block_key not in BLOCK_COLS:
        raise KeyError(f"未知的 block：{block_key!r}")
    return "inside_block"


# ══════════════════════════════════════════════════════════════════
# **層級網格** —— 同一層的幾個 block 彼此怎麼並排（⛔ 與 `BLOCK_COLS` 是兩件事）
#
# 🔴 這一段防的是一個不會被任何徽章／狀態測試抓到的誤讀：
#    `BLOCK_COLS["today.holdings"] == (1, 1, 1)` 是**卡內**一列一格，
#    ⛔ **不是**「它獨佔一列、堆在第二層最下面」。
#    把 holdings 畫成第三張全寬卡疊在底部 ＝ 正面違反客戶 2026-09-16
#    「第二層＝**3 張並排卡**」的裁示（UI_PAGE_TODAY.md ①「第二層」段已決句
#    ／③「`today.verdict` 形狀」段裁決逐字）。
# ══════════════════════════════════════════════════════════════════
#: 層序 → 該層 block 的並排欄數 `(桌機, 平板, 手機)`。
#: **只登記第二層**：客戶 2026-09-16 裁示「3 張並排卡」＋ 原型 `.g3` CSS 實測 ——
#: `ui_prototype_today.html` 全檔 `grid-template-columns` **只有三處，全在 `.g3` 上**
#: （⇒ `grep -n grid-template-columns` 即可一次列齊，⛔ 不必靠行號）：
#:   ① 基準規則（不在任何 media query 內）`.g3{…grid-template-columns:1fr…}` ＝ 手機 **1** 欄；
#:   ② `@media (min-width:641px) and (max-width:880px)` 內
#:      `.g3{grid-template-columns:repeat(2,minmax(0,1fr))}` ＝ 平板 **2** 欄；
#:   ③ `@media (min-width:881px)` 內
#:      `.g3{grid-template-columns:repeat(3,minmax(0,1fr))}` ＝ 桌機 **3** 欄。
#: 原型在 ① 上方自己標了同一句：「網格：第二層 3 卡＝ ≥881 三欄 / 641–880 兩欄 / ≤640 單欄」。
#: ⛔ 其餘各層**無來源**，⛔ 不得發明一組（CLAUDE.md §1 反捏造）—— 問到就 raise。
LAYER_GRID_COLS: Final[Mapping[int, tuple[int, int, int]]] = _frozen({
    2: (3, 2, 1),   # UI_PAGE_TODAY.md §① 第二層「層級網格」段
})


def blocks_per_row(layer: int, viewport_px: int) -> int:
    """該層在這個視窗寬下，**一列排得下幾個 block**。

    未登記層級網格的層 → `KeyError`。⛔ 不回一個猜的值：
    「猜一個看起來合理的排法」正是 §1 禁止的「自己估一個合理值」。
    """
    try:
        cols = LAYER_GRID_COLS[layer]
    except KeyError:
        raise KeyError(
            f"第 {layer!r} 層沒有登記層級網格：只有第二層有來源"
            "（客戶 2026-09-16「3 張並排卡」＋ 原型 `.g3` 實測）。"
            "⛔ 不得為其他層發明一組 —— 要填請先補規格與來歷。"
        ) from None
    return components.resolve_cols(cols, viewport_px)


def rows_of_layer(layer: int, viewport_px: int) -> int:
    """該層在這個視窗寬下**佔幾列**（block 數 ÷ 每列格數，無條件進位）。

    桌機第二層應為 **1 列** —— 三張卡並排，⛔ 沒有任何一張被擠到下一列。
    """
    per_row = blocks_per_row(layer, viewport_px)
    n_blocks = len(blocks_of_layer(layer))
    return -(-n_blocks // per_row)   # ceil division，⛔ 不用浮點（避免邊界誤差）


#: 各 block 依線框 `states` 會用到的徽章號。
#: ⚠️ 只登記規格**明文列出**的四個 block；`today.statusbar`／`key_banner`／`actions`／
#:   `holdings` 規格未給徽章清單 ⇒ ⛔ 不自行補一組（規格的洞，見交付報告）。
BLOCK_BADGES: Final[Mapping[str, tuple[int, ...]]] = _frozen({
    "today.verdict": (1, 3, 4, 5, 6, 7),           # ①「第一層 today.verdict」段
    "today.summary": (1, 3, 4, 5, 6, 7, 8, 9),     # ①「第二層」today.summary 條
    "today.warroom": (1, 3, 5, 6, 7),              # ①「第四層」段
    "today.detail":  (1, 3, 4, 5, 6, 7, 8, 9),     # ①「第四層」段
})

#: **已撤回、不是待補**的 block（UI_PAGE_TODAY.md ③「線框有、實作無」表 `chrome.asof` 列）：
#: `get_macro_state()` 只有 9 key、無 `as_of` ⇒ 原「逐格顯示 as_of」規格已撤回。
#: ⛔ 不得從 `LAYERS` 悄悄消失而不留紀錄（§-2 規則 6 的同一紀律）。
WITHDRAWN_BLOCKS: Final[frozenset[str]] = frozenset({"chrome.asof"})

#: **客戶未裁、去向開放**的卡
#: （UI_PAGE_TODAY.md ③「`today.verdict` 形狀」段「兩卡最終去向＝開放項」）。
#: 客戶只裁示「不搬」進 `today.summary`，**沒有裁示要刪** ⇒
#: ⛔ 不得自行判定刪除、⛔ 不得自行安排到第二層其他 block，但也⛔ 不得默默消失。
OPEN_ITEMS: Final[frozenset[str]] = frozenset({"verdict.exposure", "verdict.regime"})

_BLOCK_LAYER: Final[Mapping[str, int]] = _frozen(
    {block: layer["layer"] for layer in LAYERS for block in layer["blocks"]}
)


def blocks_of_layer(layer: int) -> tuple[str, ...]:
    """該層由上而下的 block key。未知層序 → `ValueError`。"""
    for entry in LAYERS:
        if entry["layer"] == layer:
            return entry["blocks"]
    raise ValueError(f"未知的層序 {layer!r}：只有 0（葉外 chrome）與 1~4 四層")


def tier_for_block(block_key: str) -> str:
    """block → 卡密度。**⛔ 刻意不提供 tier 覆寫參數**：密度只能由它所在的層決定。"""
    try:
        layer = _BLOCK_LAYER[block_key]
    except KeyError:
        raise KeyError(f"未知的 block：{block_key!r}") from None
    return components.tier_for_layer(layer)


# ══════════════════════════════════════════════════════════════════
# ③ 三卡歸位（user 2026-09-16 裁示，
#   UI_PAGE_TODAY.md ③「`today.verdict` 形狀」段「3 卡歸位」已決段）
# 裁示逐字：位階 ← summary.regime（既有）／動能 ← 未接線（exposure 不是動能，不搬）
#          ／風險 ← danger（對得上，直接對映）
# ══════════════════════════════════════════════════════════════════
SUMMARY_COLUMNS: Final[tuple[Mapping[str, object], ...]] = (
    # (a) 既有、維持現接線；⛔ 不得把 `verdict.regime` 搬過去（同源重複＝撞欄不是填空）
    _frozen({"name": "位階", "source": "summary.regime", "wired": True, "badge": None}),
    # (b) 維持未接線；⛔ 不得拿 `verdict.exposure` 頂替（exposure ＝ 配置油門帶，不是動能）。
    #     未接線態依 ② 走 #5，⛔ 不得畫成 #1。
    _frozen({"name": "動能", "source": None, "wired": False, "badge": 5}),
    # (c) 直接對映
    _frozen({"name": "風險", "source": "verdict.danger", "wired": True, "badge": None}),
)

# UI_PAGE_TODAY.md ② 落差 4（#10 `emits_level=False`）
#「本頁**不畫 #10**；⛔ 但不得因此把 #10 併進 #8」
BADGES_NOT_ON_PAGE: Final[frozenset[int]] = frozenset({10})
BADGES_ON_PAGE: Final[frozenset[int]] = frozenset(
    b["n"] for b in components.BADGES if b["n"] not in BADGES_NOT_ON_PAGE
)


# ══════════════════════════════════════════════════════════════════
# 第三層 主 CTA —— UI_PAGE_TODAY.md ①「第三層 `today.actions`」段
#                ／④ 反例自檢 A「第三層 `today.actions`」條
# ══════════════════════════════════════════════════════════════════
#: 字串 SSOT ＝ `shared/ia_nav.py ACTION_LABELS[ACTION_UPDATE_TODAY]`，
#: 與線框 `mainCTA.label` **逐字相同**（UI_PAGE_TODAY.md ①「第三層 `today.actions`」段）。
MAIN_CTA: Final[Mapping[str, object]] = _frozen({
    "label": "🚀 更新今日戰情",
    # UI_PAGE_TODAY.md ①「第三層 `today.actions`」段：按鈕規格取 UI_COMPONENTS §3 主 CTA
    "button": "primary_cta",
    # ⚠️ ~~UI_COMPONENTS.md §3 按鈕表「主 CTA（**全站唯一一顆**）」列~~
    # ⚠️ ~~`"unique_per_site": True,`~~
    #   **2026-09-22 有意識的政策變更，⛔ 不是漏刪；決策者：客戶。**
    #   **現行：UI_COMPONENTS.md §3 按鈕表「主 CTA（**每頁首屏唯一一顆**）」列。**
    #   客戶裁示逐字：「**不是「全站唯一」，是「每頁首屏唯一」。** 理由：客戶原話是
    #   『首屏僅允許一顆主 CTA』——是『每屏一顆』。」
    #   🔴 ⚠️ **這不只是文案 —— 鍵名本身在說謊**（客戶裁示逐字：「舊名：`unique_per_site`
    #   → 新名：`unique_per_first_screen`。理由：留著會誤導下一個人。」）：
    #   `unique_per_site` 讀起來像「**契約保證全站只有一顆**」，而那件事**實測為假**；
    #   留著它，下一個讀 code 的人會建立在這個假契約上繼續蓋 ⇒ **鍵名一併改**。
    #   舊鍵名逐字保留在本刪除線註解內供追溯，**code 端不留** ——
    #   留在 code 端就還是會被 grep 到、當成活契約使用。
    #   **舊名的理由仍然成立，⛔ 不是寫錯**：在只有「🚦 今天」一頁時，「全站唯一」與
    #   「每頁首屏唯一」**外延相同**，寫哪個都對。
    #   **被權衡掉的原因**：五頁 IA 落地後，🔎 選股頁有自己的主 CTA `🎯 開始選股`
    #   ⇒「全站唯一」變成**假的**（`docs/v2/spec/UI_PAGE_FIND.md` ① 2026-09-16 已逐字否證，
    #   見上方 `_LAYER_PLAN` 第三層註解的逐字引用）。
    #   ⛔ **值不動、⛔ 邏輯不動** —— 依 CLAUDE.md §8.2.A.4「只動字串、⛔ 不動邏輯」，
    #   ＋ **客戶就本次鍵名改動的明示授權**（⛔ 不得據此擴大解釋為一般性改 code 授權）。
    "unique_per_first_screen": True,
})

#: 上游這輪失敗（可重試）時的說明字，
#: UI_PAGE_TODAY.md ④ 反例自檢 A「第三層 `today.actions`」條逐字。
MAIN_CTA_RETRY_NOTE: Final[str] = "可以重試 —— 上游這輪失敗，不是程式錯誤。"

#: 契約漂移時的說明字，UI_PAGE_TODAY.md ④ 反例自檢 A「第三層 `today.actions`」條
#: 的 `MISS_CONTRACT_DRIFT` 例外逐字。
#: ⛔ 不得對契約漂移給「可重跑」指引 —— 重按不會好，給錯指引比不給更糟。
MAIN_CTA_CONTRACT_DRIFT_NOTE: Final[str] = "🔴 重按不會好，程式要修，請回報。"

#: 契約漂移的 miss reason（`FAILED_REASONS` 內），
#: UI_PAGE_TODAY.md ④ 反例自檢 A「第三層 `today.actions`」條例外／B「⛔ 全域」條。
MISS_CONTRACT_DRIFT: Final[str] = "MISS_CONTRACT_DRIFT"


def main_cta_state(*, failure_reason: str | None = None) -> Mapping[str, object]:
    """主 CTA 的可按性與說明字（UI_PAGE_TODAY.md ④ 反例自檢 A「第三層 `today.actions`」條）。

    - 一般的上游失敗（`MISS_NO_INPUT` 等）→ **可按** ＋「可以重試」；
    - `MISS_CONTRACT_DRIFT` → **停用** ＋「重按不會好，程式要修，請回報。」
    """
    if failure_reason == MISS_CONTRACT_DRIFT:
        return _frozen({"enabled": False, "note": MAIN_CTA_CONTRACT_DRIFT_NOTE})
    if failure_reason is None:
        return _frozen({"enabled": True, "note": None})
    return _frozen({"enabled": True, "note": MAIN_CTA_RETRY_NOTE})


# ══════════════════════════════════════════════════════════════════
# ② 狀態 → 徽章（UI_PAGE_TODAY.md ② 狀態覆蓋）
# ══════════════════════════════════════════════════════════════════
#: 線框鍵 `error` ↔ 常數值 `"failed"`：以**常數**為準，線框鍵名視為同義
#: （UI_PAGE_TODAY.md ② 落差 5「#6 字面不一致」，⛔ 不得為對齊線框去改 `UI_FAILED` 的值）。
_STATE_BADGE: Final[Mapping[str, int]] = _frozen({
    "live":     1,   # ② 狀態覆蓋表 `live` 列
    "loading":  2,   # ② 狀態覆蓋表 `loading` 列；⛔ 不得拿 #3 冒充載入中
    "idle":     3,   # ② 狀態覆蓋表 `idle` 列
    "degraded": 4,   # ② 狀態覆蓋表 `degraded` 列
    "unwired":  5,   # ② 狀態覆蓋表 `unwired` 列
    "failed":   6,   # ② 狀態覆蓋表 `error` 列的常數值 `UI_FAILED="failed"`
    "error":    6,   # ② 落差 5「#6 字面不一致」（線框鍵，同義）
    # `missing` 無獨立常數、併入 UI_EMPTY：兩鍵**都畫 #7**
    # （UI_PAGE_TODAY.md ② 落差 2「#7 被 `empty`＋`missing` 兩鍵共用」；
    #  ⛔ 不得畫成 #8 —— #8 專屬 MISS_NOT_APPLICABLE，
    #  重跑無效，畫錯等於給錯指引）。
    "missing":  7,
})

#: #8 專屬的缺值原因（UI_PAGE_TODAY.md ② 狀態覆蓋表 `na` 列「靠 `miss_reason` 分辨」）。
MISS_NOT_APPLICABLE: Final[str] = "MISS_NOT_APPLICABLE"

_KNOWN_STATES: Final[frozenset[str]] = frozenset(_STATE_BADGE) | {"empty", "na", "partial"}


#: #11「▨ 無資料」—— 有效的空結果（客戶 2026-09-26 新增，UI_COMPONENTS.md §2 #11 列）。
VALID_EMPTY_BADGE: Final[int] = 11


def resolve_badge(
    *,
    state: str,
    miss_reason: str | None = None,
    numerator: int | None = None,
    denominator: int | None = None,
    valid_empty: bool = False,
) -> int:
    """狀態（＋缺值原因／分子分母／有效空結果旗標）→ 徽章號 ~~#1~#10~~ #1~#11。

    📌 **2026-09-26 客戶新增 #11（有意識的規格變更，⛔ 不是漏刪）**：
    `valid_empty=True` ⇒ #11「▨ 無資料」。**只接受 `state="empty"`**；
    其餘任何狀態帶這個旗標 → `ValueError`（⛔ 不讓 #11 擴散到別的態 —— 客戶裁示逐字：
    真缺漏／還沒載入／未評估／可重試…一律維持原徽章）。
    ⚠️ **誰可以傳 `True` 不由本函式決定**：那是登記制，登記處在
    `src/ui/views/page_today.py::V2_VALID_EMPTY_PAIRS`（只列經逐張審過的 `(key, now)`）。

    `empty`／`na` 靠 `miss_reason` 分辨 #7 vs #8
    （UI_PAGE_TODAY.md ② 狀態覆蓋表 `empty`／`missing`／`na` 三列）。
    `partial` 走 **fail-safe**：分子分母任一拿不到 → 降級 #7「缺漏 · 可重跑」，
    ⛔ 不得退回 #1「正常」（UI_COMPONENTS.md §2 硬規則（fail-safe）
    ／UI_PAGE_TODAY.md ② 落差 3「#9 `partial`」）；
    L3 補齊分子分母後自動接回 #9，**不是永久降級**
    （UI_PAGE_TODAY.md ② 落差 3「#9 `partial`」末句）。
    """
    if state not in _KNOWN_STATES:
        raise ValueError(
            f"未知的狀態 {state!r}：七態 SSOT 在 shared/ui_state.py，"
            "⛔ 不得為了畫得出來就給它一個近似的徽章"
        )

    if valid_empty:
        if state != "empty" or miss_reason is not None:
            raise ValueError(
                f"#11「有效的空結果」只給 `state='empty'` 且無缺值原因的卡，"
                f"收到 state={state!r}、miss_reason={miss_reason!r} —— "
                "⛔ 不得讓 #11 擴散到缺漏／不適用／未載入等其他態（客戶 2026-09-26 裁示）")
        return VALID_EMPTY_BADGE

    if state == "partial":
        if numerator is None or denominator is None:
            return 7   # fail-safe：缺資訊時往保守側退
        return 9

    if state in ("empty", "na"):
        return 8 if miss_reason == MISS_NOT_APPLICABLE else 7

    return _STATE_BADGE[state]


# ══════════════════════════════════════════════════════════════════
# ④ 缺值時的畫面行為 —— UI_PAGE_TODAY.md ④ 反例自檢（§1 Fail Loud 的 UI 面）
# ══════════════════════════════════════════════════════════════════
#: 灰態與紅態：大字區**一律留白**，⛔ 不得顯示 `0` 或上一輪殘值。
_BLANK_VALUE_STATES: Final[frozenset[str]] = frozenset({
    "failed", "error",                                  # 紅態
    "idle", "loading", "unwired", "empty", "missing", "na",  # 灰態
})

#: 判決留白的狀態：`degraded` ＝ 門檻已失準 ⇒ ⛔ 不照失效門檻判燈
#: （但**觀測照出**，⛔ 不因為門檻失效就把值藏起來，
#:   UI_PAGE_TODAY.md ④ 反例自檢 B「`degraded` 的格子」條）。
_BLANK_LEVEL_STATES: Final[frozenset[str]] = _BLANK_VALUE_STATES | {"degraded"}


def card_value_text(*, state: str, value: object) -> str | None:
    """卡片大字區的**觀測值**字串；灰態／紅態一律 `None`（留白）。

    ⛔ 全域：缺值一律不顯示為 `0`（UI_PAGE_TODAY.md ④ 反例自檢 B「⛔ 全域」條）。
    """
    if state not in _KNOWN_STATES:
        raise ValueError(f"未知的狀態 {state!r}")
    if state in _BLANK_VALUE_STATES:
        return None
    if value is None:
        # 有色態卻沒有值 —— 留白比印出 "None" 誠實（§1：寧可留白，不可造假）。
        return None
    return str(value)


def card_level_text(*, state: str, level: object) -> str | None:
    """卡片的**判決**（燈號等級）字串；`degraded` 一律 `None`（判決留白）。"""
    if state not in _KNOWN_STATES:
        raise ValueError(f"未知的狀態 {state!r}")
    if state in _BLANK_LEVEL_STATES:
        return None
    if level is None:
        return None
    return str(level)


def observation_miss_reason(value: object, miss_reason: str | None) -> str | None:
    """檢查 `(值, 缺值原因)` 二元組的合法性（UI_PAGE_TODAY.md ④ 反例自檢 B「⛔ 全域」條）。

    `(None, None)`（沒有值也沒有原因）與 `(值, MISS_*)`（有值卻同時宣告缺漏）
    皆為**非法二元組** → 一律回 `"MISS_CONTRACT_DRIFT"`。
    合法時回傳原本的 `miss_reason`（有值時為 `None`）。
    """
    has_value = value is not None
    has_reason = miss_reason is not None
    if has_value == has_reason:
        # 兩者皆有 或 兩者皆無 —— 兩種都是契約漂移。
        return MISS_CONTRACT_DRIFT
    return miss_reason


# ══════════════════════════════════════════════════════════════════
# 🆕 第二層 `today.holdings` 持倉健檢 —— UI_PAGE_TODAY.md ①「第二層」today.holdings 條
# 🔴 資料限制（硬規則）：持股來源 `stock_watchlist` 的 schema **只有**
#    `name`／`ticker`／`updated_at` 三欄 ⇒ **這張卡拿不到部位大小**。
# ══════════════════════════════════════════════════════════════════
#: **可顯示**的九項，皆由**檔數**推得
#: （UI_PAGE_TODAY.md ①「第二層」today.holdings 條「**可顯示**（皆由檔數推得）」行）。
#: 🔴 **這是白名單／准許清單，⛔ 不是必填清單**（2026-09-21 消歧義）：
#:   規格「**可顯示**（皆由檔數推得）」該行**只有後半**「＋ 等權假設揭露句一行」標了**必填**；
#:   九項是「**至多**這些」、⛔ 不是「**至少**這些」。**渲染端可以只畫子集** ——
#:   原型 `ui_prototype_today.html`「C. 持倉健檢」段（`section.blk.t2`，標題 `id` 為 `h-t`）
#:   這張卡實際只畫 **4 條** key-value：持股檔數／已分類檔數／產業數／最大單一產業（檔數等權）。
#: ⛔ **不得顯示**：損益、部位佔比、金額、張數、均價，
#:   或任何需要張數／均價才算得出來的量
#:   （UI_PAGE_TODAY.md ①「第二層」today.holdings 條「⛔ **不得顯示**」行）。
#: ⚠️ `UI_COMPONENTS.md` §4「每卡至多顯示 **4 對**」**射程外**：那句的主語鏈是
#:   `## 4. 表格` → §4 表格斷點表「手機 ≤640」列「一列＝一張卡」→ §4「手機卡片流（新訂）」
#:   → §4「**降為佐證**…每卡至多顯示 **4 對**」⇒ 它管**表格在 ≤640px 降級成的 `.blk.t3` 卡片流**。
#:   `today.holdings` 是第二層 `.blk.t2` **核心卡**、不是表格的一列
#:   ⇒ **9 項 vs 4 對⛔ 不構成衝突**，⛔ 不得把「4 對」當卡內列數的通則。
HOLDINGS_DISPLAY_FIELDS: Final[tuple[str, ...]] = (
    "n_total", "n_classified", "n_unclassified", "n_industries",
    "coverage_pct", "top1_pct", "top3_pct", "hhi", "n_eff",
)


def unknown_holdings_fields(fields: Iterable[str]) -> tuple[str, ...]:
    """回傳 `fields` 裡**不在白名單內**的欄位（空 tuple ＝ 全部合法）。

    - **任何子集都合法** —— 白名單是「至多這些」，⛔ 不是「至少這些」（見上方註解）。
    - **白名單外的欄位要被指名回報**，⛔ 不得靜默放行（§1 Fail Loud）：
      本卡拿不到部位大小（`stock_watchlist` 只有 `name`／`ticker`／`updated_at` 三欄），
      混進 `pnl`／`position_pct`／`avg_cost` 這類欄位＝**畫一個算不出來的數字**。
    - ⚠️ 本函式**只回報、不 raise**：它的呼叫端是渲染前的檢查點，
      由呼叫端決定要炸還是要把違規欄位擋掉；⛔ 但不得把回傳值丟掉當沒看到。
    """
    allowed = frozenset(HOLDINGS_DISPLAY_FIELDS)
    return tuple(f for f in fields if f not in allowed)

#: `concentration.py` 一律 `basis='equal_weight'` 並要求 UI 揭露該假設
#: （UI_PAGE_TODAY.md ①「第二層」today.holdings 條「🔴 **資料限制（硬規則）**」與
#:   「**可顯示**（皆由檔數推得）」兩行，`BASIS_EQUAL_WEIGHT`）。
HOLDINGS_BASIS: Final[str] = "equal_weight"

#: 標籤**逐字**，⛔ 不得標成「部位佔比」
#: （UI_PAGE_TODAY.md ①「第二層」today.holdings 條「`top1_pct` 標籤逐字」行）。
HOLDINGS_TOP1_LABEL: Final[str] = "最大單一產業（檔數等權）"

#: 等權假設揭露句一行（**必填**），說明字級 `--ink-3` `11.5px`
#: （UI_PAGE_TODAY.md ①「第二層」today.holdings 條「**可顯示**（皆由檔數推得）」行末）。
#: ⚠️ 規格要求「必填」但**未給逐字文案** ⇒ 本句為實作組草擬（見交付報告）。
HOLDINGS_EQUAL_WEIGHT_DISCLOSURE: Final[Mapping[str, object]] = _frozen({
    "text": "集中度以「檔數等權」計算 —— 持股來源只有代號與名稱，沒有張數與均價，"
            "因此這裡的百分比是檔數佔比，不是部位佔比。",
    "color": "--ink-3",   # UI_TOKENS.md §B 字型 token 表「說明」列的色
    "font_px": 11.5,      # UI_TOKENS.md §B 字型 token 表「說明」列 `11.5px`
})


def holdings_badge(*, n_classified: int) -> int:
    """持倉健檢卡的徽章號。

    `is_computable=False`（`n_classified == 0`）→ **#7 缺漏 · 可重跑**
    （Sheet 失敗可重試），⛔ 不得顯示 `0` 或「完美分散」、⛔ 不得退回 #1
    （UI_PAGE_TODAY.md ①「第二層」today.holdings 條「`is_computable=False`」行
    ／④ 反例自檢 A「第二層」條）。
    """
    if not isinstance(n_classified, int) or isinstance(n_classified, bool):
        raise TypeError(f"n_classified 必須是 int，收到 {type(n_classified).__name__}")
    if n_classified < 0:
        raise ValueError(f"n_classified 不得為負：{n_classified}")
    return 7 if n_classified == 0 else 1


__all__ = [
    "LAYERS", "BLOCK_COLS", "BLOCK_BADGES", "WITHDRAWN_BLOCKS", "OPEN_ITEMS",
    # `cols` 的來歷（⛔ 註解不算數，來歷要機器讀得到）
    "COLS_FROM_WIREFRAME", "COLS_DERIVED_BY_LEAD", "COLS_RULED_BY_CLIENT",
    "COLS_PROVENANCE", "DERIVED_COLS", "COLS_DERIVATION", "cols_scope",
    # 層級網格（⛔ 與 BLOCK_COLS 是兩個不同的網格）
    "LAYER_GRID_COLS", "blocks_per_row", "rows_of_layer",
    "SUMMARY_COLUMNS", "BADGES_ON_PAGE", "BADGES_NOT_ON_PAGE",
    "MAIN_CTA", "MAIN_CTA_RETRY_NOTE", "MAIN_CTA_CONTRACT_DRIFT_NOTE", "G3_COLS",
    "HOLDINGS_DISPLAY_FIELDS", "unknown_holdings_fields",
    "HOLDINGS_BASIS", "HOLDINGS_TOP1_LABEL",
    "HOLDINGS_EQUAL_WEIGHT_DISCLOSURE",
    "MISS_CONTRACT_DRIFT", "MISS_NOT_APPLICABLE",
    "tier_for_block", "blocks_of_layer", "resolve_badge", "VALID_EMPTY_BADGE",
    "card_value_text", "card_level_text", "observation_miss_reason",
    "main_cta_state", "holdings_badge",
]
