"""降級畫面（#1204）的專用 streamlit 入口（僅供真瀏覽器 regression 使用；⛔ 不是產品入口）。

啟動前把 `src.ui2.shell.app.read_real_snapshot` 換成 raise（模擬 Real feed 整體讀取失敗），再執行 `app_ui2.py`。
shell 的 `run()` 從模組全域查 `read_real_snapshot`，monkeypatch 在 streamlit 每次 rerun 皆有效（模組已快取）。
"""
import os
import runpy
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

import src.ui2.shell.app as _shell  # noqa: E402


def _boom():
    raise RuntimeError("secret-token")


_shell.read_real_snapshot = _boom
runpy.run_path(os.path.join(_ROOT, "app_ui2.py"), run_name="__main__")
