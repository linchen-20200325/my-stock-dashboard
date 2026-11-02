"""New UI2（`src/ui2/`）—— 全新 Presentation Layer（L5）。

⚠️ **New UI2（`src/ui2/`）≠ Legacy New UI 的 `src/ui_v2/`**（一字之差，極易混淆）。

- 只吃 View Model（`shared/ui2_contract` 型別；由 `src/services/ui2` 產出）渲染。
- ⛔ 取數、⛔ 判態、⛔ cache、⛔ 聚合動作、⛔ 創造投資規則、⛔ 呼叫 producer（`*_apply`／LLM）。
- ⛔ import Legacy UI（`src.ui.*`、`src.ui_v2`、`app`）——Architecture Gate §9 G4。
- session key 一律 `ui2_` 前綴；CSS class 一律 `ui2-` 前綴。
"""
