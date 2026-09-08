"""根因防護 —— repo 根目錄預設**不得**有 `packages.txt`(2026-09-08 倒站事故)。

事故
────
Streamlit Cloud 2026-09-08 起「Error installing requirements.」,部署倒站。
使用者取得的雲端日誌實錘(不是推論):

    [02:15:14] 📦 Apt dependencies were installed from
               /mount/src/my-stock-dashboard/packages.txt using apt-get.
    E: Release file for http://deb.debian.org/debian-security/dists/
       bullseye-security/InRelease is expired (invalid since 5h 2min 11s).
    [02:15:17] ❗️ installer returned a non-zero exit code
    [02:15:17] ❗️ Error during processing dependencies!

倒在 **apt 階段**;`pip` 從頭到尾一次都沒有執行。機制:
Streamlit Cloud **只要 repo 根目錄有 `packages.txt` 就會先跑 `apt-get`**,
而 base image 的 Debian **bullseye-security** 已終止安全支援、Release 檔過期,
`apt-get` 回非零 → 整個相依安裝流程中止,連 pip 都輪不到。

當時那個 `packages.txt` 的內容只有兩行:`libxml2-dev` / `libxslt1-dev` ——
**而且兩行都是沒有作用的**:
  • 編譯期用不到:lxml 6.1.3 在 PyPI 備有 cp314 manylinux/musllinux x86_64
    wheel,pip 一律優先取 wheel,不會走原始碼編譯;
  • 執行期也用不到:該 wheel 的 `etree.cpython-314-x86_64-linux-gnu.so`
    DT_NEEDED **只有** librt / libm / libpthread / libc —— libxml2 與 libxslt
    是靜態連進去的。
也就是說:整個 repo 為了兩個誰也用不到的標頭檔,把**每一次部署**都綁在
「Debian 官方源今天健不健康」這個我們完全無法控制的外部相依上,綁了兩週,
然後在 2026-09-08 付了一次倒站的代價。

本守衛的契約
────────────
`packages.txt` **預設不存在** → 綠。
若有人加回來,必須先寫下理由,而且理由要回答那個真正的問題:
**這個 apt 套件為什麼無法用 wheel 取代?**

理由可以寫在兩個地方任一(取聯集):
  (a) `docs/APT_PACKAGES.md`(建議放這裡);
  (b) `packages.txt` 自己的 `#` 註解行。
⚠️ 之所以不強制 (b):**Streamlit Cloud 的 apt 安裝器吃不吃得下 `#` 註解,
本組沒有查證**(依 CLAUDE.md §-2 規則 6 據實標明)。萬一它把註解行原樣丟給
`apt-get install`,強制寫註解等於逼出另一次倒站 —— 所以留 (a) 這條安全路。

為什麼這不是恆真式
──────────────────
判定邏輯抽成純函式 `audit_apt_manifest(pkgs_text, rationale_text)`,
`TestGuardItself` 直接餵它合成輸入驗證兩個方向:
  • 把 2026-09-08 那份原始 `packages.txt`(兩行、零註解、零說明檔)餵進去
    → **必須**產生違規;
  • 補上點名兩個套件並說明「無法用 wheel 取代」的理由 → **必須**放行。
真正的守衛 `test_packages_txt_absent_or_justified` 讀的是 repo 的實況,
檔案一旦被加回來就會走進同一條判定 —— 「檔案不在 → 綠」是這個 repo 現在
真實的狀態,不是把斷言寫成永遠成立。
"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]

# Streamlit Cloud 認得的 apt 清單檔(存在即觸發 apt-get)
_PACKAGES_TXT = _REPO / "packages.txt"

# 選用的說明檔;`packages.txt` 存在時,理由可以寫在這裡
_RATIONALE_DOC = _REPO / "docs" / "APT_PACKAGES.md"

# 理由裡必須出現的字串 —— 逼作者正面回答「為什麼不能用 wheel」,
# 而不是只寫「需要 libxml2」這種沒有回答問題的句子。
_WHY_NO_WHEEL_MARKER = "無法用 wheel 取代"


def _apt_packages(text: str) -> list[str]:
    """從 packages.txt 內容取出真正會被丟給 apt-get 的套件名。"""
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        # `libxml2-dev=2.9.10` 這種帶版本的寫法,取套件名那半
        out.append(line.split("=", 1)[0].strip())
    return out


def _comment_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.lstrip().startswith("#")]


def audit_apt_manifest(pkgs_text: str, rationale_text: str = "") -> list[str]:
    """回傳違規清單(空 list = 合格)。純函式,不碰檔案系統,便於自我驗證。

    `pkgs_text`      —— `packages.txt` 的內容。
    `rationale_text` —— `docs/APT_PACKAGES.md` 的內容(沒有就傳空字串)。
    """
    problems: list[str] = []
    pkgs = _apt_packages(pkgs_text)

    if not pkgs:
        problems.append(
            "packages.txt 存在但沒有宣告任何 apt 套件 —— 這是純風險零收益:"
            "空檔一樣會觸發 Streamlit Cloud 跑 apt-get。請直接刪掉這個檔。"
        )
        return problems

    # 理由文本 = 說明檔 + packages.txt 自己的註解(取聯集)
    justification = "\n".join([rationale_text, *_comment_lines(pkgs_text)])

    if not justification.strip():
        problems.append(
            "packages.txt 宣告了 apt 套件卻沒有留下任何理由:"
            f"`{_RATIONALE_DOC.name}` 不存在,packages.txt 裡也沒有註解行。"
        )

    if _WHY_NO_WHEEL_MARKER not in justification:
        problems.append(
            f"理由裡找不到「{_WHY_NO_WHEEL_MARKER}」這句話。"
            "每個 apt 套件都要正面回答『為什麼不能改用 PyPI wheel』——"
            "2026-09-08 那兩個套件之所以是白付代價,正是因為沒有人問過這個問題。"
        )

    unnamed = [p for p in pkgs if p not in justification]
    if unnamed:
        problems.append(
            "下列 apt 套件沒有在理由裡被點名(不能靠一段舊理由夾帶新套件):\n    "
            + "\n    ".join(unnamed)
        )

    return problems


_HOW_TO_FIX = f"""
Streamlit Cloud 只要 repo 根目錄有 `packages.txt` 就會在 pip 之前先跑 `apt-get`,
而那是一個我們**無法控制**的外部相依 —— 2026-09-08 就是這樣倒站的:
base image 的 Debian bullseye-security 源 Release 檔過期 → `apt-get` 非零退出
→ 整個安裝流程中止,`pip` 從頭到尾**沒有執行**。當時那兩個套件
(libxml2-dev / libxslt1-dev)還是完全用不到的:lxml 有 cp314 wheel,
且其 .so 靜態連了 libxml2/libxslt,DT_NEEDED 只有 libc 家族。

先問三個問題,答得出來再加:
  1. 這個 apt 套件對應的 Python 套件,PyPI 上真的沒有 cp3xx manylinux wheel 嗎?
     (實測:`pip install --dry-run --only-binary=:all: --python-version 3.14
      --implementation cp --abi cp314 --platform manylinux_2_28_x86_64 ...`)
  2. 如果有 wheel,它的 .so 是不是已經把該系統函式庫靜態連進去了?
     (實測:`readelf -d <ext>.so | grep NEEDED`)
  3. 願意接受「每次部署都賭 Debian 源今天是健康的」這個風險嗎?

真的非加不可時,把理由寫進 `docs/APT_PACKAGES.md`(建議)或 packages.txt 的
`#` 註解,內容必須點名每一個套件,並且寫明「{_WHY_NO_WHEEL_MARKER}」的具體原因。
"""


def test_packages_txt_absent_or_justified():
    """repo 根目錄不該有 `packages.txt`;真要有,理由必須寫下來。"""
    if not _PACKAGES_TXT.exists():
        return  # 2026-09-08 之後的正常狀態

    rationale = (
        _RATIONALE_DOC.read_text(encoding="utf-8")
        if _RATIONALE_DOC.exists() else ""
    )
    problems = audit_apt_manifest(
        _PACKAGES_TXT.read_text(encoding="utf-8"), rationale
    )
    assert not problems, (
        "`packages.txt` 被加回 repo 根目錄,但沒有通過理由檢查:\n  - "
        + "\n  - ".join(problems)
        + "\n"
        + _HOW_TO_FIX
    )


# ══════════════════════════════════════════════════════════════
# 守衛的自我驗證 —— 證明它抓得到真違規,也證明它不是恆真式
# (§6:守衛自己也要有幾個最容易讓它出錯的輸入)
# ══════════════════════════════════════════════════════════════

# 2026-09-08 被刪掉的那份 packages.txt,逐字。
_INCIDENT_PACKAGES_TXT = "libxml2-dev\nlibxslt1-dev\n"


class TestGuardItself:
    def test_the_2026_09_08_file_would_be_rejected(self):
        """把當時那份檔原樣加回來 → 必須紅。這是本守衛存在的唯一理由。"""
        problems = audit_apt_manifest(_INCIDENT_PACKAGES_TXT, "")
        assert problems, "2026-09-08 那份 packages.txt 竟然被判合格 —— 守衛失效"
        assert any(_WHY_NO_WHEEL_MARKER in p for p in problems)
        assert any("libxml2-dev" in p for p in problems)

    def test_empty_file_is_rejected(self):
        """空檔 / 只有註解的檔一樣會觸發 apt-get = 純風險零收益。"""
        assert audit_apt_manifest("", "")
        assert audit_apt_manifest("# 只有註解,沒有套件\n", "")

    def test_fully_justified_file_passes(self):
        """理由寫齊(點名每個套件 + 說明為什麼不能用 wheel)→ 必須綠。

        沒有這條,本守衛就等於「packages.txt 一律禁止」,那會逼下一個真的
        需要 apt 套件的人去繞過測試,而不是把理由寫下來。
        """
        doc = (
            "# apt 套件理由\n"
            "## libfoo-dev\n"
            f"上游只發 sdist,{_WHY_NO_WHEEL_MARKER};編譯需要它的標頭檔。\n"
        )
        assert audit_apt_manifest("libfoo-dev\n", doc) == []

    def test_justification_may_live_in_the_manifest_comments(self):
        """理由寫在 packages.txt 註解裡也算數(取聯集,不是二選一)。"""
        text = (
            f"# libfoo-dev:上游只發 sdist,{_WHY_NO_WHEEL_MARKER}\n"
            "libfoo-dev\n"
        )
        assert audit_apt_manifest(text, "") == []

    def test_old_rationale_cannot_carry_a_new_package(self):
        """夾帶防護:舊理由只講 A,偷偷多加一個 B → 必須紅。"""
        doc = f"libfoo-dev:上游只發 sdist,{_WHY_NO_WHEEL_MARKER}。\n"
        problems = audit_apt_manifest("libfoo-dev\nlibbar-dev\n", doc)
        assert problems, "夾帶的新套件沒有被抓到"
        assert any("libbar-dev" in p for p in problems)
        assert all("libfoo-dev" not in p for p in problems), (
            "已經寫過理由的套件不該被重複點名"
        )

    def test_versioned_package_line_is_matched_by_name(self):
        """`libfoo-dev=1.2.3` 這種寫法要用套件名比對,不能因為版本號就判不出來。"""
        doc = f"libfoo-dev:上游只發 sdist,{_WHY_NO_WHEEL_MARKER}。\n"
        assert audit_apt_manifest("libfoo-dev=1.2.3\n", doc) == []
