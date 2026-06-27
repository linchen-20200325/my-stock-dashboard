"""tests/test_parse_helpers.py — parse_stocks(v18.302)

§8.3 app.py 拆檔測試 — parse_stocks 從 app.py 提至 shared/parse_helpers,
本檔守:regex pattern + 分隔符 + edge case + back-compat re-export。
"""
from __future__ import annotations

import pytest

from shared.parse_helpers import parse_stocks


# ════════════════════════════════════════════════════════════════
# 1. 合法格式
# ════════════════════════════════════════════════════════════════
class TestValidIds:
    def test_4_digit(self):
        assert parse_stocks("2330") == ["2330"]

    def test_5_digit_etf(self):
        assert parse_stocks("00878") == ["00878"]

    def test_6_digit(self):
        assert parse_stocks("123456") == ["123456"]

    def test_with_uppercase_suffix(self):
        """6660C / 2330R(可換股 / 可贖回)。"""
        assert parse_stocks("6660C") == ["6660C"]
        assert parse_stocks("2330R") == ["2330R"]


# ════════════════════════════════════════════════════════════════
# 2. 分隔符
# ════════════════════════════════════════════════════════════════
class TestSeparators:
    def test_comma(self):
        assert parse_stocks("2330,2454") == ["2330", "2454"]

    def test_comma_with_space(self):
        assert parse_stocks("2330, 2454") == ["2330", "2454"]

    def test_full_width_comma(self):
        assert parse_stocks("2330,2454") == ["2330", "2454"]

    def test_newline(self):
        assert parse_stocks("2330\n2454") == ["2330", "2454"]

    def test_full_width_semicolon(self):
        """全形分號 '；'(U+FF1B),原 app.py 用此(對齊 SSOT)。"""
        assert parse_stocks("2330；2454") == ["2330", "2454"]

    def test_half_width_semicolon_not_supported(self):
        """半形 ';' 非分隔符 → 整段視為單一 token,regex 過濾掉。
        對齊 app.py 原 SSOT 行為(不支援半形分號)。"""
        # "2330;2454" 沒分割 → 一個 token "2330;2454" → 不符 [4-6數字] pattern → 過濾
        assert parse_stocks("2330;2454") == []

    def test_mixed_separators(self):
        """半形逗號 + 全形分號 + 空白 + 換行 全部混用。"""
        assert parse_stocks("2330, 2454；  6660C\n00878") == [
            "2330", "2454", "6660C", "00878",
        ]


# ════════════════════════════════════════════════════════════════
# 3. 過濾非法
# ════════════════════════════════════════════════════════════════
class TestInvalidFiltered:
    def test_alphabetic_filtered(self):
        assert parse_stocks("abc, 2330") == ["2330"]

    def test_too_long_filtered(self):
        """7 位數字超出 6 位上限。"""
        assert parse_stocks("12345678, 2330") == ["2330"]

    def test_too_short_filtered(self):
        """3 位數字不足 4 位下限。"""
        assert parse_stocks("123, 2330") == ["2330"]

    def test_lowercase_suffix_filtered(self):
        """小寫 c 不符合 [A-Z] pattern。"""
        assert parse_stocks("2330c, 2454") == ["2454"]

    def test_two_letter_suffix_filtered(self):
        """雙字母後綴(如 2330RR)不合法。"""
        assert parse_stocks("2330RR, 2454") == ["2454"]


# ════════════════════════════════════════════════════════════════
# 4. Edge cases
# ════════════════════════════════════════════════════════════════
class TestEdgeCases:
    def test_empty_string(self):
        assert parse_stocks("") == []

    def test_whitespace_only(self):
        assert parse_stocks("   \n\t  ") == []

    def test_only_separators(self):
        """全形分號 + 半形逗號 + 換行 全部分隔符 → 空 list。"""
        assert parse_stocks(",,,；；；\n\n") == []

    def test_order_preserved(self):
        assert parse_stocks("6660, 2330, 00878") == ["6660", "2330", "00878"]

    def test_duplicates_not_dedup(self):
        """parse_stocks 不負責去重(caller 自決)。"""
        assert parse_stocks("2330, 2330") == ["2330", "2330"]


# ════════════════════════════════════════════════════════════════
# 5. Back-compat re-export
# ════════════════════════════════════════════════════════════════
class TestBackCompat:
    @pytest.mark.slow
    def test_app_reexport(self):
        """app.parse_stocks 應仍可 import(re-export shim)。

        以 **subprocess** 驗證,原因:
        1. `import app` 會跑整支 monolith(app.py 模組級即 render 全 app,~60s),
           本質是 e2e,故標記 @slow(對齊 pytest.ini「單測 >5s」定義)。
        2. 其他 test 檔(test_data_coverage / test_macro_classroom)在 collection
           時把 sys.modules['streamlit'] 換成不完整 stub,且 tab_macro 等子模組
           會 cache 該 stub 的 `st` 參照 → 同 process 內 import app 必炸。subprocess
           有乾淨 sys.modules + 真 streamlit,徹底避開污染(§5 冪等性/可重現性)。
        """
        import os
        import subprocess
        import sys
        import textwrap

        _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _code = textwrap.dedent("""
            from app import parse_stocks as a
            from shared.parse_helpers import parse_stocks as b
            assert a is b, 'app.parse_stocks 不是 shared.parse_helpers.parse_stocks'
            print('REEXPORT_OK')
        """)
        r = subprocess.run(
            [sys.executable, "-c", _code],
            cwd=_repo_root, capture_output=True, text=True, timeout=180,
        )
        assert r.returncode == 0 and "REEXPORT_OK" in r.stdout, (
            "app re-export shim 驗證失敗:\n"
            f"stdout: {r.stdout[-1000:]}\nstderr: {r.stderr[-2000:]}"
        )
