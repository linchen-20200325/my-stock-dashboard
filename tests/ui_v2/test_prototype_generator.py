"""讓 CI **真的執行** `docs/v2/prototype/gen_today_v2.py` 的守衛。

**本檔存在的唯一理由（病根）**
    產生器內有 **183 道 `assert` ＋ 6 道 `raise`**（量測日 2026-09-22），它們是五頁
    原型的全部品質守衛（卡面禁詞、版面契約、徽章、逐字 SSOT、代理污染…）。
    但 `pytest.ini` 的 `testpaths = tests` 讓 `docs/` **從不被收集**，而在本檔之前
    `tests/` 底下**沒有任何一支測試 import 它** ⇒ 那些守衛**在 CI 一道都不會跑**，
    只在「有人記得手動跑一次產生器」時才生效。
    ⇒ 這正是 `CLAUDE.md §-2` 點名的失效模式：**沒有守衛的地方，CI 會一直保持全綠。**
    本檔把它從「靠人記得跑」變成「漏了就紅燈」。

**分工（三支測試，⛔ 不重疊）**
    ① `test_generator_module_imports`   —— import 產生器本身 ＝ 跑它的**模組層**守衛。
    ② `test_generator_main_runs_clean`  —— 呼叫 `main()` ＝ 跑 `main()` 與它呼叫到的守衛。
    ③ `test_generated_html_matches_committed_artifact` —— 產物漂移守衛（見下）。
    ＋ `test_repo_artifact_is_never_overwritten` —— 本檔自己的自我保護（見下）。

🔴 **⛔ 絕不覆寫 repo 的 `docs/v2/prototype/today_v2.html`**
    產生器的 `OUT` 是**模組層常數**，且**只在 `main()` 內被用到**（寫檔、回讀、最後 print）
    ⇒ 本檔 import 模組後**先把 `mod.OUT` 指到 `tmp_path`**，再呼叫 `main()`。
    覆寫的後果有兩個，兩個都很貴：(a) CI 的工作區變髒；
    (b) **會掩蓋「產生器與產物已經不同步」這種真正該被抓到的漂移** —— 每跑一次測試就
    順手把產物改成最新，③ 就永遠是綠的。故本檔另外釘一道「位元未變」的自我保護。

**③ 漂移守衛比對什麼、⛔ 不比對什麼（讀者請先看這段）**
    ✅ **逐行比對**整份 HTML（1063 行），其中特別包含兩個**承重欄位**：
       · `src/ui_v2 底下 N 個 .py 的內容 sha256 ＝ <64 hex>`
         —— 改了 `src/ui_v2/` 卻沒重產原型，這一行會不一樣 ⇒ **這是最有價值的漂移訊號**。
       · `src/ui_v2/ 工作區乾淨（無未提交變更）`
         —— 工作區髒掉會變成「有未提交變更：…」⇒ 那是**合理的 fail loud**，⛔ 不 skip。
    ⛔ **正規化（＝不比對）四處**，理由一律是「**它記的是這一次執行的環境，⛔ 不帶漂移訊號**」：
       1. `產生當下 HEAD ＝ <sha>` —— 產生時本次改動還沒 commit，故它**恆為父 commit**
          （結構使然，已登記為原型缺口 **K15**，該缺口就畫在產物自己的附錄裡）。
       2. `(b) 產生日期：<YYYY-MM-DD>` ＋ 頁尾的 `於 <YYYY-MM-DD> 產生的靜態快照`
          —— 來源是 `datetime.date.today()`。⚠️ **不正規化的話，這支測試會在產物產生的
          隔天開始每天紅一次**，而那⛔ 不是漂移，是「過了一天」。
       3. `(a) 產生來源：… 分支 <branch>，src/ui_v2/ 於 commit <sha>（<date>）` ＋ 頁尾的
          `commit <短碼>` —— 來源是 `git rev-parse --abbrev-ref HEAD` 與
          `git log -1 -- src/ui_v2`，**兩者在 CI 的 checkout 下都會與本機不同**（實測見下）。
    ⚠️ **每一道正規化都釘了「它必須命中恰好 1 次」**（兩份文字各驗一次）——
       產生器日後改掉欄位措辭時，這裡會**當場紅**，⛔ 不會讓正規化器自己變成一個無聲的洞。

⚠️ **為什麼 (a) 那一行非正規化不可（實測，⛔ 不是推測）**
    · `actions/checkout@v4` 預設 `fetch-depth: 1` ⇒ **淺 clone 只有一個 commit**。
      實測（`git clone --depth 1` 本機重現）：`git log -1 --format=%H -- src/ui_v2`
      在淺 clone 下回傳的是 **HEAD 自己**，⛔ 不是真正最後動到 `src/ui_v2/` 的那個 commit
      —— 因為那唯一的 commit 看不到父節點，git 視它為「引入了全部檔案」。
    · `pull_request` 事件的 checkout 是 **detached HEAD** ⇒
      實測 `git rev-parse --abbrev-ref HEAD` 回傳字串 `HEAD`，⛔ 不是分支名。
    ⇒ 只正規化 HEAD 那一行的話，這支測試會**本機全綠、CI 全紅** ——
      而一支「在 CI 紅得沒有道理」的守衛，會是下一個人第一個拿去 skip 的東西。
    ✅ **端到端實測（2026-09-22，本機重現整條管線）**：在
       `git clone --depth 1` ＋ `git checkout --detach` 的 clone 裡，把產生日期假造成
       23 天後（2026-10-15）跑一次產生器 —— 產物的 `(a)`／HEAD／`(b)` 三處**全都與
       repo 的不同**（分支印成 `HEAD`、commit 印成 HEAD 的 sha、日期印成未來日），
       而 `工作區` 與 `內容 sha256` 兩行**逐字相同**；套上本檔的正規化之後，
       與 repo 已 commit 的產物 **逐字相同**。
       ⇒ 「正規化這四處、⛔ 不正規化那兩行」的切法是實測過的，⛔ 不是推測。
    ⚠️ **但那是本機等價重現，⛔ 沒有在真的 GitHub Actions 上跑過**
       （沙箱驗不到，依 `CLAUDE.md §-1.5.A-7 (2)` 據實標明）——
       若 CI 的 checkout 行為與上述假設不同，第一次跑就會紅，屆時請看差異再調 `_VOLATILE_FIELDS`。
"""
from __future__ import annotations

import difflib
import importlib.util
import pathlib
import re
import sys
import types

import pytest

#: `tests/ui_v2/test_prototype_generator.py` ⇒ 往上第 2 層是 repo 根。
#: ⛔ 不寫死絕對路徑（換一個 checkout 就跑不動）。
_REPO = pathlib.Path(__file__).resolve().parents[2]
_PROTOTYPE_DIR = _REPO / "docs" / "v2" / "prototype"
_GENERATOR = _PROTOTYPE_DIR / "gen_today_v2.py"
#: repo 已 commit 的產物 —— 🔴 **本檔⛔ 絕不寫它**，只讀。
_ARTIFACT = _PROTOTYPE_DIR / "today_v2.html"

#: 刻意用一個⛔ 不會和任何真模組撞名的 key，且測完就從 `sys.modules` 拿掉。
_MODULE_NAME = "_gen_today_v2_under_test"


# ══════════════════════════════════════════════════════════════════
# 正規化：產物裡「只記錄這一次執行的環境」的四處
# ══════════════════════════════════════════════════════════════════
#: `(說明, pattern, 取代字串)`；每一項都必須在兩份文字裡各命中**恰好 1 次**。
#: 🔴 **⛔ 不得為了讓測試變綠而往這張表加東西** —— 每加一項就是拆掉一段比對範圍。
#:    加之前先問：這個欄位變了，代表「產生器與產物不同步」嗎？
#:    **代表 → ⛔ 不准加**（那正是本守衛要抓的）；**不代表（只是換了台機器／過了一天）→ 才可以加。**
_VOLATILE_FIELDS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "(a) 產生來源：repo 名／分支／src/ui_v2 的 commit 與日期",
        re.compile(r"^\(a\) 產生來源：.*$", re.MULTILINE),
        "(a) 產生來源：<正規化：repo 名／分支／ui_v2 commit 與日期>",
    ),
    (
        "產生當下 HEAD（原型缺口 K15：結構使然恆為父 commit）",
        re.compile(r"^(\s*)產生當下 HEAD ＝ [0-9a-f]{40}$", re.MULTILINE),
        r"\1產生當下 HEAD ＝ <正規化：HEAD>",
    ),
    (
        "(b) 產生日期",
        re.compile(r"^\(b\) 產生日期：\d{4}-\d{2}-\d{2}$", re.MULTILINE),
        "(b) 產生日期：<正規化：產生日期>",
    ),
    (
        # ⚠️ `sha256 <12 hex>` 用 capture group 原樣送回去 ⇒ **它仍然在比對範圍內**。
        "頁尾的 commit 短碼與產生日期（sha256 短碼刻意保留比對）",
        re.compile(
            r"由 src/ui_v2/（commit [0-9a-f]{7}、sha256 ([0-9a-f]{12})）"
            r"於 \d{4}-\d{2}-\d{2} 產生的靜態快照。"
        ),
        r"由 src/ui_v2/（commit <正規化>、sha256 \1）於 <正規化> 產生的靜態快照。",
    ),
)


def _normalise(text: str, *, origin: str) -> str:
    """把上表四處換成固定字串；**任何一處⛔ 沒有命中恰好 1 次就當場炸**。

    炸掉代表產生器改了那個欄位的措辭 —— 那時要做的是**更新這張表**，
    ⛔ 不是把命中次數的斷言拿掉（拿掉一道守衛就是弱化，見 `CLAUDE.md §-2`）。
    """
    for label, pattern, replacement in _VOLATILE_FIELDS:
        text, hits = pattern.subn(replacement, text)
        assert hits == 1, (
            f"正規化欄位「{label}」在 {origin} 命中 {hits} 次，應為 1 次。\n"
            "⇒ 產生器（或產物）改掉了這個欄位的措辭／位置。\n"
            "   修法：更新 tests/ui_v2/test_prototype_generator.py::_VOLATILE_FIELDS 的 pattern；\n"
            "   ⛔ 不得改成不檢查命中次數 —— 那會讓正規化器靜默吃掉一整段比對範圍。"
        )
    return text


#: 產生器寫進產物檔頭的那一行：`    src/ui_v2/ 工作區{乾淨（無未提交變更）|有未提交變更：…}`
_WORKTREE_LINE = re.compile(r"^\s*src/ui_v2/ 工作區(?P<state>.*)$", re.MULTILINE)


def _ui_v2_worktree_state(generated: str) -> str | None:
    """從**產生器自己寫進產物的那一行**讀 `src/ui_v2/` 的工作區狀態（只給失敗訊息當診斷）。

    ⛔ **刻意不自己再跑一次 `git status`**，兩個獨立的理由：
      ① 那會是**第二個真相源**（`CLAUDE.md §2.1`）—— 產生器量到的狀態才是寫進產物的那一份，
         測試另外量一次，兩者在競態下可能不一致，而不一致時診斷會指錯方向。
      ② `tests/test_zz_test_portability.py::test_no_external_shell_tools` **明文禁止**
         測試呼叫外部 shell 工具（Windows 沒有 `git` ⇒ `FileNotFoundError`），
         且該測試逐字寫「禁止改成『Windows 就 skip』—— 那是藏問題不是修問題」。

    回傳 `None` ＝ 產物裡找不到那一行（措辭被改了）⇒ 呼叫端據實說「判斷不出來」，
    ⛔ 不假裝工作區是乾淨的。
    """
    hit = _WORKTREE_LINE.search(generated)
    return None if hit is None else hit.group("state").strip()


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════
@pytest.fixture(scope="session")
def generator_module() -> types.ModuleType:
    """import `gen_today_v2.py` ＝ 跑它的**模組層**守衛。

    模組層在 import 當下就會跑 3 道 `assert`（量測日 2026-09-22）：
    `REPO` 路徑推導、`_BANNED_PAGE` 的 key 結構、`_BANNED_BLOCK` 的 key 結構。
    後兩道守的是「禁詞表的 key 打錯 ⇒ 那組禁詞**靜默失效而 CI 全綠**」。

    ⛔ **不改 `sys.path`**：產生器自己會 `sys.path.insert(0, REPO)`；本 fixture 只在
    teardown 把 `sys.path` 還原成 import 前的樣子，⛔ 不替它加任何路徑。
    """
    assert _GENERATOR.is_file(), (
        f"找不到產生器 {_GENERATOR} —— 它被搬走了嗎？"
        "本檔的整個存在理由就是讓 CI 跑得到它。"
    )
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _GENERATOR)
    assert spec is not None and spec.loader is not None, f"無法為 {_GENERATOR} 建 import spec"

    module = importlib.util.module_from_spec(spec)
    sys_path_before = list(sys.path)
    sys.modules[_MODULE_NAME] = module
    try:
        # 🔴 模組層的 assert 就在這一行跑；⛔ 不吞任何例外。
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(_MODULE_NAME, None)
        sys.path[:] = sys_path_before


@pytest.fixture(scope="session")
def generator_run(generator_module, tmp_path_factory) -> types.SimpleNamespace:
    """把 `OUT` 重導到 tmp 後跑 `main()` ＝ 跑 `main()` 與它呼叫到的全部守衛。

    🔴 三道自我保護，缺一不可：
      ① 重導**之前**先釘「`mod.OUT` 預設就是 repo 那一份」——
         產生器日後若改掉 `OUT` 的語意（改成函式／改成別的路徑／`main()` 不再讀它），
         重導就會**靜默失效而寫穿 repo**；這一道讓它當場紅。
      ② 跑完斷言 repo 產物**位元未變**（連 `main()` 炸掉的路徑也驗）。
      ③ 斷言 tmp 檔**真的被寫出來且非空** —— ①②③ 合起來才排除
         「`main()` 根本沒理會 `mod.OUT`」這種情形。
    """
    module = generator_module
    redirected = tmp_path_factory.mktemp("gen_today_v2") / "today_v2.html"

    artifact_before = _ARTIFACT.read_bytes()

    # ── 自我保護 ① ──────────────────────────────────────────────
    assert module.OUT == _ARTIFACT, (
        f"產生器的預設 OUT 不是 repo 的產物（實得 {module.OUT}）。\n"
        "⇒ 本檔「把 OUT 重導到 tmp」的前提不再成立，重導可能已經靜默失效。\n"
        "   先確認產生器的 OUT 語意，再決定本檔要怎麼改，"
        "⛔ 不得直接把這道斷言拿掉。"
    )

    module.OUT = redirected
    try:
        module.main()
    finally:
        module.OUT = _ARTIFACT
        # ── 自我保護 ②（放在 finally：main() 炸掉時也要驗）──────────
        artifact_after = _ARTIFACT.read_bytes()
        if artifact_after != artifact_before:
            raise AssertionError(
                "🔴 產生器寫穿了 repo 的 docs/v2/prototype/today_v2.html。\n"
                "本檔的重導失效了 —— 這會讓 CI 工作區變髒，並且**掩蓋產物漂移**"
                "（每跑一次測試就順手把產物改成最新，漂移守衛就永遠是綠的）。"
            )

    # ── 自我保護 ③ ──────────────────────────────────────────────
    assert redirected.is_file() and redirected.stat().st_size > 0, (
        f"main() 跑完了，但重導目標 {redirected} 不存在或是空的 —— "
        "代表 main() 根本沒有用模組層的 OUT 寫檔。"
    )

    return types.SimpleNamespace(
        module=module,
        path=redirected,
        text=redirected.read_text(encoding="utf-8"),
        artifact_before=artifact_before,
        artifact_after=artifact_after,
    )


# ══════════════════════════════════════════════════════════════════
# ① import 段
# ══════════════════════════════════════════════════════════════════
def test_generator_module_imports(generator_module) -> None:
    """產生器 import 得起來 ＝ 它的模組層守衛全過。

    ⚠️ 這一支⛔ 不是「有 import 到就好」的儀式：`gen_today_v2.py` 在 import 當下
    就會跑禁詞表的 key 結構守衛，key 打錯在本支就會炸。
    """
    assert callable(generator_module.main), "產生器沒有可呼叫的 main()"
    # `OUT` 是本檔重導手法的承重前提，在這裡也釘一次（fixture 內另有一道）。
    assert isinstance(generator_module.OUT, pathlib.Path), "OUT 不是 Path"


# ══════════════════════════════════════════════════════════════════
# ② main() 段
# ══════════════════════════════════════════════════════════════════
def test_generator_main_runs_clean(generator_run) -> None:
    """`main()` 從頭跑到尾 ＝ 它與它呼叫到的守衛全過。

    任何 `AssertionError`／例外都會讓本支紅 —— 那正是本檔要的：
    守衛從「靠人記得跑」變成「漏了就紅燈」。
    """
    text = generator_run.text
    assert text.startswith("<!DOCTYPE html>"), "產物不是一份完整的 HTML"
    assert text.rstrip().endswith("</html>"), "產物被截斷了（⛔ 沒有收尾的 </html>）"


def test_repo_artifact_is_never_overwritten(generator_run) -> None:
    """🔴 自我保護：跑完之後 repo 的 `today_v2.html` **位元未變**。"""
    assert generator_run.artifact_after == generator_run.artifact_before, (
        "repo 的 docs/v2/prototype/today_v2.html 被這支測試改掉了。"
    )
    assert generator_run.path != _ARTIFACT, "重導目標居然就是 repo 產物本身"


# ══════════════════════════════════════════════════════════════════
# ③ 漂移守衛
# ══════════════════════════════════════════════════════════════════
def test_generated_html_matches_committed_artifact(generator_run) -> None:
    """現跑的產物 vs repo 已 commit 的 `today_v2.html` —— 逐行必須相同。

    這道抓兩件事：
      · **有人手改了 HTML**（產物檔頭第一句就寫「⛔ 不要手改」，但那只是請求，⛔ 不是守衛）；
      · **改了產生器／`src/ui_v2/` 卻忘記重產**。
    正規化了哪四處、⛔ 為什麼不能多正規化，見本檔檔頭。
    """
    fresh = _normalise(generator_run.text, origin="現跑的產物")
    committed = _normalise(_ARTIFACT.read_text(encoding="utf-8"), origin="repo 已 commit 的產物")

    if fresh == committed:
        return

    diff = list(difflib.unified_diff(
        committed.splitlines(), fresh.splitlines(),
        fromfile="repo/docs/v2/prototype/today_v2.html（已 commit）",
        tofile="現跑 gen_today_v2.py 的產物",
        lineterm="", n=2,
    ))
    shown = "\n".join(diff[:80])
    if len(diff) > 80:
        shown += f"\n…（還有 {len(diff) - 80} 行差異未顯示）"

    worktree = _ui_v2_worktree_state(generator_run.text)
    if worktree is None:
        hint = (
            "⚠️ 產物裡找不到 `src/ui_v2/ 工作區…` 那一行 ⇒ **判斷不出**工作區是否乾淨"
            "（產生器把那個欄位的措辭改掉了？）。\n"
        )
    elif not worktree.startswith("乾淨"):
        hint = (
            "🔴 **你的 `src/ui_v2/` 有未提交變更**：\n"
            f"{worktree}\n"
            "⇒ 這**不是測試壞掉，是產物真的過期了** —— `src/ui_v2/` 改了，"
            "但 `today_v2.html` 還是舊的那一份（它的檔頭 sha256 與工作區狀態都會對不上）。\n"
            "   解法：`python docs/v2/prototype/gen_today_v2.py`，"
            "把 `src/ui_v2/` 的改動與重產的 `today_v2.html` **一起 commit**。\n"
            "   ⛔ 不要 skip 這支測試 —— 那等於把守衛關掉，正是本檔要修的病。\n"
        )
    else:
        hint = (
            "`src/ui_v2/` 工作區是乾淨的 ⇒ 差異來自\n"
            "  (a) 有人手改了 `docs/v2/prototype/today_v2.html`（它是機器產物，⛔ 不該手改），或\n"
            "  (b) 改了 `docs/v2/prototype/gen_today_v2.py` 卻沒有重跑它。\n"
            "   解法：`python docs/v2/prototype/gen_today_v2.py`，並把重產的 HTML 一起 commit。\n"
        )

    pytest.fail(
        "產生器的產物與 repo 已 commit 的 today_v2.html 不同步。\n\n"
        + hint
        + "\n差異（已正規化掉 HEAD／分支／commit／產生日期四處，見本檔檔頭）：\n"
        + shown
    )
