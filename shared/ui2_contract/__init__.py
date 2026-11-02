"""New UI2（`src/ui2/`）View Model 契約 —— L0。

⚠️ **New UI2（`src/ui2/`）≠ Legacy New UI 的 `src/ui_v2/`**（一字之差，極易混淆）。
本套件是 New UI2 的 Presentation Contract：frozen dataclass 型別、三軸語意（資料語意五態／判定結果／
capability；DEC-124）、chip 語意色調、
L1 字樣常數。依據：`docs/vnext/NEWUI2_ARCHITECTURE_GATE_2026-11-02.md` §4／§6、
`docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md` §4／§5／§9。

⛔ 本套件**只放呈現契約**：零 I/O、零 streamlit、不依賴 L1+、不放任何投資語意
（沒有門檻、沒有分支、沒有公式、沒有動作聚合）。
"""
