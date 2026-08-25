"""src/ui/tabs/tab_macro.py 共用純函式 — Phase 7A-Ext（2026-05-16）。

零 Streamlit / Plotly 依賴，純資料計算。從 tab_macro.render_tab_macro
抽出供 unit test 與未來模組共用。

設計原則：
- pure function：相同輸入恆等輸出
- 防呆優先：所有 helper 對 None / 空 dict / 缺欄位皆有 fallback
- 易測：對應 tests/test_macro_helpers.py 完整 coverage
"""
from __future__ import annotations

import sys
from typing import Any, Optional

import pandas as pd
from shared.colors import (
    TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW,
)
# v18.241 E1+E2: 抽 inline magic 到 shared SSOT（CLAUDE.md §3.3）
from shared.signal_thresholds import (
    HEALTH_WEIGHT_JQ, HEALTH_WEIGHT_SCORE, HEALTH_FNET_BONUS, CONFIDENCE_SOURCE_COUNT,
    CONFIDENCE_SOURCE_GROUPS,
)

# 季末日對照（DataFrame 內「季度標籤 2024Q4」→「2024-12-31」用）
_QE_MAP = {'1': '03-31', '2': '06-30', '3': '09-30', '4': '12-31'}

# v18.140 校準收斂門檻：health 低於此值觸發 🔴 防禦；regime=bull 需 score ≥ 此值才升 🟢
# v18.143+：優先讀 macro_thresholds.json（由季度 recalibrate workflow 經 PR 審閱後寫入），
# 缺檔則 fall back 至模組預設常數
# S-GRAY-1 v18.244:loader I/O 已下沉 `shared/macro_calibration.py`(L0 Infra),
# 本檔僅做 module-level call 後 expose 常數,符合 L2 「純函式 / 無 I/O」邊界。
from shared.macro_calibration import load_calibrated_thresholds as _load_calibrated_thresholds

HEALTH_DEFENSE_THRESHOLD, BULL_MIN_SCORE = _load_calibrated_thresholds()

# C1 v19.182:大盤 regime 唯一仲裁點（L2 → L0，合法下行依賴）。
# 以 module alias 引用是為了讓 `_TL_COPY_BY_SOURCE` 的 key 直接綁 SSOT 常數。
from shared import regime_arbiter as _RA  # noqa: E402

# ── v19.177 P1-B ②:信心來源標籤 —— 「站上均線比例」是捏造描述,已除役 ──────────
# 舊值:'旌旗指數 (站上均線比例)'。**全站沒有任何一行 code 在算「站上均線的
# 股票家數比」**(grep `站上|above_ma|pct_above` 的命中都是別的量:
# `tab_stock.py` 的 `_above_ma20` 是單檔個股比自己的均線;
# `daily_data_fetchers.py:445` 的 `adl_ma20` 是「ADL 累積線的 MA20」)。
# 真值:旌旗 = 上漲佔比(ad_ratio)的 5 日移動平均,見
#       `src/services/jingqi_calc.compute_and_store_jingqi` 的 ADL 主源那一行
#       `float(df_adl_raw['ad_ratio'].tail(5).mean())`(不寫行號 —— 行號會漂移)。
#
# 名詞 SSOT 是 `src/ui/render/ui_widgets.BREADTH_JINGQI`,但那是 L4 Render,
# L2 Compute 不得上行 import(§8.2 跨層上行 import 違憲)→ 這裡放字面值,
# 由 `tests/test_p1b_fabricated_defaults.py::test_conf_label_matches_breadth_ssot`
# 斷言與 SSOT 的 canonical / formula 一致,擋兩邊漂移。
_CONF_LABEL_JINGQI = '旌旗指數 (上漲佔比的 5 日均)'


# ── v19.175 P0:`cl_data['inst']` 型別收斂 SSOT ────────────────────────────────
# 全站有 4 個消費點對 `cl_data['inst']` 做 `next((k for k in inst if '外資' in k))`,
# 而它們清一色寫成 `cl_data.get('inst', {})` —— **dict.get 的預設值只在 key 不存在
# 時生效**;key 存在、值為 None 時原樣回 None,下一行 genexpr 立刻拋
# `TypeError: 'NoneType' object is not iterable`,把整個「🌍 總經」分頁炸掉。
#
# 4 個消費點(修前全部裸奔):
#   1. `macro_helpers.calc_traffic_light`            (L2,本檔)
#   2. `src/ui/tabs/macro/section_warroom.py:53`     (L5,今日作戰室)
#   3. `src/ui/tabs/macro/section_mid.py:448`        (L5,三環 E 條件)
#   4. `src/ui/tabs/macro/section_news_ai.py:142`    (L5,AI 量化脈絡)
# 只修其中一個,下一個 rerun 就換下一個炸 —— 故抽成本 helper 一次收齊。
def coerce_inst_dict(cl_data: Optional[dict], *, where: str) -> dict:
    """把 `cl_data['inst']` 收斂成 dict;契約違約時**大聲 log**,不靜默補值。

    §1 Fail Loud 的界線在哪
    -----------------------
    這**不是** `if x is None: x = []` 那種粉飾:`{}` 與 `None` 在下游語意完全相同
    —— 都代表「三大法人這份資料沒拿到」。所有消費點原本就以 falsy / `_fk is None`
    判缺並**照樣把缺失顯示出來**:

    - `calc_traffic_light`:`_conf_sources` 的「外資買賣超 (三大法人)」判 False
      → 信心分數下降 → `handlers._render_traffic_light` 在 conf<70 時直接擋掉燈號
      並逐項列出缺哪一份資料。
    - `section_warroom`:外資方向顯示「未知」。
    - `section_mid`:三環 E 條件顯示「E 外資未知」。
    - `section_news_ai`:AI 脈絡直接不列該行(不塞 0 給 LLM 腦補)。

    本函式唯一改變的是「不再把整頁炸掉」,並且把契約違約寫進 stderr 留跡。
    真正的修法在上游 —— `macro_fetch_orchestrator.fetch_macro_bundle` 已於同一版
    收斂回傳契約(inst 一律 dict);本函式是消費端的第二道防線(舊 session 裡可能
    還躺著上一版寫入的 None)。

    Args:
        cl_data: `st.session_state['cl_data']`(可為 None)。
        where:   呼叫點識別字串,寫進 log 方便定位(如 'calc_traffic_light')。

    Returns:
        dict —— 保證可安全迭代;拿不到資料時為空 dict。
    """
    _cd = cl_data or {}
    _raw = _cd.get('inst')
    if isinstance(_raw, dict):
        return _raw
    if _raw is not None:
        print(f"[{where}] ⚠️ cl_data['inst'] 型別違約:{type(_raw).__name__}"
              f"(契約要求 dict)→ 視為三大法人未載入,缺失會照常顯示",
              file=sys.stderr)
    elif 'inst' in _cd:
        # key 在但值為 None = 上游明確失敗(TWSE BFI82U 逾時 + FinMind rescue 未補到)。
        # key 根本不存在 = 冷啟動尚未抓,屬正常狀態,不需 log(避免洗版)。
        print(f"[{where}] ⚠️ cl_data['inst'] is None(上游三大法人 TWSE+FinMind 全敗)"
              f"→ 視為未載入;信心分數會下降並列入缺失來源", file=sys.stderr)
    return {}


# ── C1 v19.182:燈號文案表（key = `regime_arbiter` 的 `source`）────────────────
# 為什麼 key 是 `source` 而不是顏色 / regime：舊碼有**兩條 🔴 分支文案不同** ——
# 「空頭防禦｜降低部位」(總經惡化，分支 1/2) vs 「保守防禦｜縮減部位」(趨勢轉空，
# 分支 4)。只看 icon 或 regime 都無法還原該印哪一組字，這也正是舊碼要把整棵決策樹
# 展開寫在 if/elif 裡的原因。改以 `source` 當 key 後，判定（arbiter）與文案（本表）
# 才能真正分離而不失資訊。
#
# ⚠️ 文字一字未改（含全形標點與 emoji），對照 v19.181 原 if/elif 逐分支搬移。
# key 一律引用 arbiter 的 `SOURCE_*` 常數，**不寫字面值**（§3.3 反捏造：
# 兩處各抄一份字串 = 改一邊漏一邊）。
_TL_COPY_BY_SOURCE: dict = {
    # 分支 1 / 2：總經惡化凌駕技術面 → 同一組文案。
    # ── 2026-08-19 文案機率化(user 核准「只改文案、不動數字」)────────────────
    # 修的是什麼:原本兩條分支共用同一組文案,結尾是
    #   '建議持有現金，等待市場明確訊號，禁止追買任何個股'
    # 「禁止」「任何」是**對機率事件下的絕對化命令**。用修好的校準管線
    # (commit 84c519e,2007-2026 n=4,741)實測:此類訊號後 60 日出現 10% 以上
    # 路徑回撤的比例約 27%,而全樣本基準是 18% —— 有辨識力(lift≈1.5x),
    # 但遠不到「確定」。把 27% 講成 100% 會造成兩種後果,兩種都壞:照做的人
    # 承受假警報的機會成本;不照做的人建立「無視這個系統」的習慣。
    #
    # 兩條分支**分家**:證據來源不同(外資期貨是獨立於 health 的第二證據源,
    # 健康分是同源的趨勢面延伸),原本共用文案讓使用者無法分辨。
    # 色碼與 label 一律不動 —— `macro_state_locker.normalize_regime` 用
    # 「空頭防禦」中文子串把燈號還原成 `bear`,改字會斷掉 macro_state.json
    # 的 fallback 路徑(且 tests/test_macro_helpers、test_c1_regime_arbitration
    # 共 3 條斷言釘住)。
    #
    # ⚠️ 維護規則(tests/test_no_hardcoded_position_pct):本表任何一行,
    #    在「持股/曝險/倉位/部位/現金/水位/比重/降倉…」等關鍵詞之後、
    #    下一個全形逗號或句號之前,**不得出現 `N%` 或「N 成」**。
    #    要放數字就放在不含這些關鍵詞的那一行。
    _RA.SOURCE_DEFENSE_FUTURES: (
        TRAFFIC_RED,
        '空頭防禦｜降低部位',
        '🔻 外資期貨大額淨空 —— 獨立於健康分的第二證據源同步轉空',
        '此訊號在 2007-2026 約 20 次，多集中於 2008、2011、2020、2022 等急跌段；'
        '建議降低曝險，並優先確認手上部位的停損位置。'),
    _RA.SOURCE_DEFENSE_HEALTH: (
        TRAFFIC_RED,
        '空頭防禦｜降低部位',
        '🔻 總經健康分跌破防禦門檻 —— 趨勢轉弱訊號，非崩盤預警',
        '20 年校準：此訊號後 60 日出現 10% 以上路徑回撤的比例約 27%（全樣本基準 18%）；'
        '約四分之三的情況不會演變成大跌。建議降低曝險，不必清空。'),
    _RA.SOURCE_BULL_SCORE: (
        TRAFFIC_GREEN,
        '多頭市場｜積極操作',
        '✅ 市場健康，籌碼乾淨，可積極尋找強勢標的',
        '可積極尋找強勢標的，留意趨勢延續性'),
    _RA.SOURCE_BEAR_TREND: (
        TRAFFIC_RED,
        '保守防禦｜縮減部位',
        '⛔ 市場走弱，建議縮減持股比例，等待多頭確認',
        '降低風險暴露，避免新開倉，等待多頭重啟'),
    _RA.SOURCE_NEUTRAL_FALLTHROUGH: (
        TRAFFIC_YELLOW,
        '震盪整理｜謹慎觀望',
        '⚠️ 市場處於整理期，謹慎操作，降低部位',
        '持有現有倉位觀望，不追高，等待更明確信號'),
    # 健康分算不出來（極端情況：上游把 score 餵成 NaN）→ arbiter 回 unloaded。
    # §1：誠實說「算不出來」，不拿 🟡 震盪頂替（🟡 是一個**市場判斷**，不是缺值標記）。
    _RA.SOURCE_UNLOADED: (
        TRAFFIC_NEUTRAL,
        '總經未評估｜資料不足',
        '⬜ 健康評分無法計算（上游輸入缺失或非數值）',
        '請按「🚀 一鍵更新全部數據」重新抓取；在此之前不做多空判斷'),
}


def calc_traffic_light(
    mkt_info: Optional[dict],
    jingqi_info: Optional[dict],
    cl_data: Optional[dict],
    li_latest: Any,
    *,
    health_defense_threshold: Optional[int] = None,
    bull_min_score: Optional[int] = None,
) -> Optional[dict]:
    """根據當前數據計算紅綠燈狀態，回傳 dict。無數據時回傳 None。

    取代 tab_macro.render_tab_macro._calc_traffic_light closure。

    決策樹（v18.140 校準後收斂門檻，常數見模組 HEALTH_DEFENSE_THRESHOLD / BULL_MIN_SCORE）：
      1. 三來源全空 → None（由 placeholder 顯示等待）
      2~5. **C1 v19.182 起下沉至 `shared.regime_arbiter.arbitrate_regime()`**
           （全站唯一仲裁點；本函式只負責備料 + 貼文案）。分支順序與門檻
           一字未改，見該模組 docstring。

    Args:
        mkt_info:    market_regime() 回傳，含 'score' / 'regime'
        jingqi_info: 景氣指標，含 'avg'
        cl_data:     籌碼資料，含 'inst'（外資 net）/ 'adl'
        li_latest:   先行指標 DataFrame，含 '外資大小' / '韭菜指數' 欄

    Returns:
        dict (color, icon, label, action, sub, health, health_partial, defense,
              score, jqavg, leek, fnet, fk, fut_net, conf, missing_sources,
              regime, effective_regime, light, regime_source) 或 None

        ⚠️ v19.177 起 `jqavg` / `leek` / `fut_net` **可能為 None**(= 該來源沒拿到),
        消費端格式化前必須先判 None。詳見下方 P1-B 註解。

        ⚠️ C1 v19.182 **regime 三欄位契約**（消費端請務必看清楚）：
          - `regime`           = 趨勢面**輸入**（raw `mkt_info['regime']`），
                                 保留舊 key 舊語意，僅供揭露「被壓制的反向訊號」。
          - `effective_regime` = 本函式的**結論**（canonical，全站唯一真相）。
          - `light` / `regime_source` = 同一次仲裁的燈號與生效分支識別碼。
        取多空判斷一律用 `effective_regime`，**不得**用 `regime`，
        也**不得**再由 `icon` 反推（那正是 C1 修掉的破口）。
    """
    if not mkt_info and not jingqi_info and not cl_data:
        return None
    _mkt    = mkt_info   or {}
    _jq     = jingqi_info or {}
    _cd     = cl_data    or {}
    # ── P1 v19.470:`_mkt.get('score', 0)` 把「沒抓到大盤」寫成「大盤 0 分」──
    # `dict.get` 的預設值只在 key 不存在時生效,而 `get_market_assessment` 在
    # yfinance 抓取失敗 / 資料超過 7 天 / MA120 bar 不足時**整包回 None**
    # (`market_strategy.py` 的三個 return None),於是 `_mkt = {}` ⇒ score=0
    # ⇒ score_pct=0 ⇒ health 被硬生生拉低 40 個百分點(0.4×100),
    # 極易跌破 `HEALTH_DEFENSE_THRESHOLD` ⇒ 🔴 空頭防禦(文案見 _TL_COPY_BY_SOURCE;
    # 該文案已於 2026-08-19 機率化,原「禁止追買任何個股」已退役)。
    # **把缺資料靜默轉成最強利空**,正是 §1 明令禁止的「讓流程看起來成功」。
    #
    # 同一份 `shared/regime_arbiter.py` 對 `health=None` 早就有誠實的
    # `UNLOADED_VERDICT` 路徑 —— 這條防護原則本來就在,只是漏了 score 這條腿。
    # 改 `_safe_float(...)`:拿不到 → None → (a) 不進健康評分分子/分母
    # (權重重新歸一化,同 v19.177 對 jqavg 的做法)、(b) 以 None 傳進 arbiter
    # (`is_foreign_futures_defense` / 分支 3 都已有 None guard)、
    # (c) `health_partial=True` + 列入 `missing_sources` 讓畫面顯式降級。
    _score  = _safe_float(_mkt.get('score'))
    # ── v19.177 P1-B ①:`_jq.get('avg', 50)` 捏造中性值 → 改 None(§1 Fail Loud)──
    # 舊碼:`_jqavg = _jq.get('avg', 50)`。
    # 50 在旌旗 0~100% 的尺度上**確實**是中點,但它以 HEALTH_WEIGHT_JQ(0.6)的權重
    # 進健康評分 —— 拿不到廣度資料時捏一個 50,等於憑空製造「市場廣度剛好中性」
    # 這個結論,再讓它佔健康分 60% 的份量(§1「自行估一個合理值當常數」= 違憲)。
    #
    # 另有一個舊碼自己就踩到的坑:`dict.get` 的預設值**只在 key 不存在時生效**。
    # `section_inputs.load_section_inputs` 在 warroom 沒有 jingqi_avg 時會合成
    # `{'avg': None}`(section_inputs.py:97)—— key 在、值為 None ⇒ 舊碼拿到的是
    # None 而不是 50,下方乘法直接 TypeError。改成顯式 None + 權重重新歸一化後,
    # 「沒有 jingqi_info」與「有 dict 但 avg 是 None」兩種缺法行為一致。
    _jqavg = _safe_float(_jq.get('avg'))
    # ── v19.175 P0(實機 2/2 重現):`cl_data['inst']` 可能是 **None** ──────────
    # 型別收斂 + log 已抽至同檔 `coerce_inst_dict`(4 個消費點共用,詳見該 docstring)。
    #
    # None 從哪來:`macro_fetch_orchestrator.fetch_macro_bundle` 在 inst job
    # 逾時 / 例外時 `_results['inst'] = None` → `None or (None, None)` 解包成
    # `inst = None`,若 FinMind rescue 也沒補到就原樣回傳,再由
    # `tab_macro.py:355-358` 寫進 `session_state['cl_data']['inst']`。
    # 之後**每一次 rerun** 走 `section_traffic_light.render_traffic_light_top()`
    # → 本函式 → 炸;而 `warroom_summary` 是在本函式回傳**之後**才寫入
    # (`section_traffic_light.py:193`),於是全站 4 個消費點(置底常駐條 /
    # 建議持股油門 / ETF 與個股組合的總經連動配置)全部退化成
    # 「⬜ 總經未評估 / 建議持股 --」。
    _inst = coerce_inst_dict(_cd, where='calc_traffic_light')
    _fk     = next((k for k in _inst if '外資' in str(k)), None)
    # ── P1 v19.470:`.get('net', 0)` 同樣把「沒有數字」寫成「淨買賣 0」──
    # 上游 `fetch_institutional` 在部分失敗時會留下 key 但 `net=None`,
    # 而 `dict.get` 的預設值對「key 在、值為 None」無效 ⇒ 舊碼拿到 None
    # 後在 `_fnet > 0` 崩(或在 HEALTH_FNET_BONUS 非 0 的舊版靜默少加分)。
    # 更關鍵的是 `_conf_sources` 判的是 `bool(_fk)`(key 在不在),於是
    # 「key 在但沒數字」會**同時**顯示「信心 100%」與「⏰ 外資數據待更新」。
    # 三態化:None = 沒拿到(信心扣分 + 列缺失)、0.0 = 真的持平、其他 = 實值。
    _fnet   = _safe_float(_inst.get(_fk, {}).get('net')) if _fk else None

    # 先行指標：期貨外資大小、韭菜指數
    # ── v19.177 P1-B ①:兩者缺值一律 None,不再捏 0 / 50(§1 + §4.1)────────────
    # 舊碼:`_fut_net = 0` / `_leek = 50`,且 `.get(col, 50)` 又埋了第二層預設。
    #
    # `_leek = 50` 是本批**最嚴重**的一個:畫面「韭菜指數」欄實際餵進來的是
    # **小台法人空多比**,值域約 [-100, +100]、中位 **0**(定義見
    # `src/config/config.py`「韭菜指數門檻 SSOT」的 (B) 段;另一個值域 [0,100]
    # 中位 50 的「融資 5Y 標準化指數」是**同名不同義**的另一個量)。
    # 50 放在 ±100% 的尺度上是**極端偏空**,不是中性 —— 用它當 neutral default
    # 同時違反 §1(自行估一個合理值)與 §4.1(量綱/值域錯配)。
    #
    # `_fut_net = 0` 則讓下方 `_defense` 判定恆為假:把「不知道外資期貨部位」
    # 當成「外資期貨沒有大空單」,是把**缺資料當成安全訊號**。
    #
    # 缺失不會被吞:`_conf_sources` 的「先行指標」項會判 False → 信心分數下降 →
    # `handlers._render_traffic_light` 把缺項列在燈號卡上(v19.177 一併修好
    # 「只在 conf<70 才列」導致缺 1 項時 conf=80% 看不到的破口)。
    #
    # NaN 也算缺:`leading_indicators` 對沒抓到的日子會塞 None/NaN,舊碼
    # `float(None)` 拋 TypeError 被 except 吞掉 → 悄悄退回捏造值;`_safe_float`
    # 統一把 None / NaN / 非數字都收斂成 None。
    _fut_net = None
    _leek = None
    if li_latest is not None and not li_latest.empty:
        try:
            _li_row = li_latest.iloc[-1]
        except Exception as _e_li:  # noqa: BLE001 — 取末列失敗 = 兩值皆缺,照常降級
            print(f"[calc_traffic_light] li_latest 末列讀取失敗:"
                  f"{type(_e_li).__name__}: {_e_li} → 期貨/韭菜視為未取得",
                  file=sys.stderr)
            _li_row = None
        if _li_row is not None:
            if '外資大小' in li_latest.columns:
                _fut_net = _safe_float(_li_row.get('外資大小'))
            if '韭菜指數' in li_latest.columns:
                _leek = _safe_float(_li_row.get('韭菜指數'))

    # ⚠️ `_regime` 是**趨勢面輸入**（market_regime 的技術面判定），**不是本函式的結論**。
    # 決策樹的分支 1/2（外資期貨防禦 / 健康分跌破門檻）會直接覆蓋它 —— 這正是
    # C1 稽核抓到的矛盾根源：舊碼把它原樣塞進 `warroom_summary['regime']`，
    # 於是置底常駐條印「🟢 多頭」而同一頁上方的燈號卡印「🔴 空頭防禦」。
    # 本函式回傳的 canonical 結論改看 `effective_regime`（見下方 arbiter）。
    _regime  = _mkt.get('regime', 'neutral')
    # v18.241 E1: 健康評分權重從 SSOT 引入（原 0.4/0.4/20 inline）
    # v19.102 校準採納(方案 B,MACRO_HEALTH_WEIGHT_PROPOSAL.md AUC 0.753):
    # ① 權重 0.6/0.4/0(SSOT 已改);② score 正規化除數自 CONFIDENCE_SOURCE_COUNT(5,
    # 借用錯配)改用 market_regime 回傳的真 max_score(預設 4.0 = market_regime 基本
    # 滿分,ad_ratio/m1b_m2 有傳才升 5/6)— 修「預設模式 score 永遠到不了 100」。
    _max_score = float(_mkt.get('max_score') or 4.0)
    # P1 v19.470:`_score` 現為三態,None ⇒ 這條腿整條缺席(不是 0 分)。
    _score_pct = (min(_score / _max_score * 100, 100)
                  if _score is not None else None)
    # ── v19.177 P1-B:缺項改「權重重新歸一化」,不再用捏造的中性值頂替 ──────────
    # 舊式:health = jqavg×0.6 + score_pct×0.4 + fnet_bonus,jqavg 缺時塞 50。
    # 新式:只對**真的拿得到**的分項加權後歸一化 ——
    #     health = Σ(value_i × w_i) / Σ(w_i)        (i ∈ 有值的分項)
    # 語意是「用手上有的資料評分」,而不是「假裝缺的那項剛好中性」。
    # 降級不靜默:conf 同步下降(見下方 `_conf_sources`)、缺項列進 missing_sources、
    # 並回傳 `health_partial=True` 供畫面標示(§1「填補必須顯式呼叫 + 帶旗標」)。
    #
    # 零回歸保證:兩項都在時 Σw = HEALTH_WEIGHT_JQ + HEALTH_WEIGHT_SCORE = 1.0
    # (0.6 + 0.4 在 IEEE754 下正好 1.0),除以 1.0 為精確運算 → 與舊式逐位相同。
    _health_parts: list[tuple[float, float]] = []
    if _jqavg is not None:
        _health_parts.append((_jqavg, HEALTH_WEIGHT_JQ))
    # ── P1 v19.470:score 這條腿改與 jqavg **對稱**處理 ────────────────────
    # 原註解寫「score 恆有值」—— 那是 `_mkt.get('score', 0)` 造成的假象:
    # 值恆在,但缺資料時那個值是**捏造的 0**。改三態後兩條腿規則一致:
    # 有值才進分子/分母,缺了就重新歸一化,而不是拿 0(最強利空)頂替。
    if _score_pct is not None:
        _health_parts.append((_score_pct, HEALTH_WEIGHT_SCORE))
    _w_sum = sum(_w for _, _w in _health_parts)
    # 兩條腿都缺 ⇒ 沒有任何依據可言 ⇒ health=None,由 arbiter 回
    # `UNLOADED_VERDICT`(⬜ 總經未評估)。§1:誠實說「算不出來」,
    # **不是** 0 分(0 分會被判成最強利空),也不是 🟡(🟡 是一個市場判斷)。
    if _w_sum <= 0:
        _health = None
    else:
        _health = round(
            sum(_v * _w for _v, _w in _health_parts) / _w_sum
            # `_fnet` 三態後可能是 None;None 不代表「沒買超」,故不加分也不扣分。
            + (HEALTH_FNET_BONUS if (_fnet is not None and _fnet > 0) else 0), 1
        )
    # 任一條腿缺席都算 partial(原本只認 jqavg 缺席)。
    _health_partial = (_jqavg is None) or (_score_pct is None)

    # R-CALC-4 v18.412:Method A ↔ Method B 雙演算法對帳(§4.3)
    # 嵌入 production render 路徑(原只在 reconcile_panel diagnostic page);
    # drift_warning / extreme_divergence 走 stderr log,**不改 UI 行為**(觀測性升級)。
    #
    # v19.177 gate:jqavg 缺時 Method A 已改權重歸一化,而 Method B
    # (`health_reconcile.compute_method_b_health:96`)仍用它自己的 `jqavg or 50.0`
    # 預設 —— 兩者對「缺值」的定義不同,硬對帳只會產出恆定噪音告警。
    # 對帳屬觀測性而非主邏輯,故僅在**輸入齊全**時才跑(§4.3 精神:比的是演算法差異,
    # 不是比誰的缺值預設比較好)。Method B 的 50.0 預設本身屬另案(該檔不在本批範圍)。
    # P1 v19.470:gate 再加 `_score_pct`/`_health` —— score 缺席時 Method A 也走了
    # 權重歸一化,與 Method B 的預設同樣不可比;health=None 則根本無從對帳。
    if _jqavg is not None and _score_pct is not None and _health is not None:
        try:
            from src.compute.health.health_reconcile import reconcile_health_score as _reconcile
            _rec = _reconcile(_health, jqavg=_jqavg, score=_score, fnet=_fnet,
                              max_score=_max_score)
            if not _rec.within_tolerance:
                import sys as _sys_rec
                print(f'[health_reconcile] {_rec.reason} '
                      f'method_a={_rec.method_a} method_b={_rec.method_b:.1f} '
                      f'diff={_rec.diff:+.1f} abs_diff={_rec.abs_diff:.1f}',
                      file=_sys_rec.stderr)
        except Exception as _e_rec:
            # 對帳失敗不影響主路徑(§1 fail loud 範圍外:這是觀測性,主邏輯仍走 Method A)
            try:
                import sys as _sys_rec_err
                print(f'[health_reconcile] swallow: {type(_e_rec).__name__}: {_e_rec}',
                      file=_sys_rec_err.stderr)
            except Exception:
                pass
    else:
        print('[health_reconcile] skip:jqavg / 大盤評分 / health 任一未取得,'
              'Method A 已權重歸一化而 Method B 仍用固定預設,兩者不可比 → '
              '本輪不對帳(§4.3)', file=sys.stderr)

    # 校準腳本可注入測試門檻；正式呼叫不傳 → 用模組常數
    _h_thr = health_defense_threshold if health_defense_threshold is not None else HEALTH_DEFENSE_THRESHOLD
    _s_thr = bull_min_score if bull_min_score is not None else BULL_MIN_SCORE

    # ── C1 v19.182:決策樹下沉至唯一仲裁點 `shared.regime_arbiter` ─────────────
    # 修的是什麼:本函式的 if/elif 樹**才是**實際決定畫面燈號的那條規則,但它只吐
    # icon;下游 `section_traffic_light.py` 只好用 `{'🔴':'bear','🟢':'bull',
    # '🟡':'neutral'}.get(icon)` **反推** regime,而同一份 warroom 又把 raw
    # `mkt_info['regime']` 原樣塞進 `'regime'` key 給置底常駐條 / ETF 頁用
    # → 同一天兩個相反答案(§2.1 SSOT 破口)。
    # 現在燈色與 canonical regime **出自同一次 `arbitrate_regime()` 呼叫**,
    # 結構上不可能再分歧,而且 `source` 明講是哪條分支生效。
    # 判定邏輯逐分支等價,**行為零位移**(見 tests/test_c1_regime_arbitration.py
    # 的 legacy 決策樹對拍測試)。
    _verdict = _RA.arbitrate_regime(
        trend_regime=_regime, market_score=_score, health=_health,
        futures_net_lots=_fut_net,
        health_defense_threshold=_h_thr, bull_min_score=_s_thr,
    )
    _defense = _verdict.defense
    # 文案表以 `source`(哪條分支生效)為 key —— 舊碼兩條 🔴 分支的 label 不同
    # (空頭防禦 vs 保守防禦),不能只看顏色/icon 決定文字。
    _color, _label, _action, _sub = _TL_COPY_BY_SOURCE[_verdict.source]
    _icon = _verdict.light

    _conf_sources = [
        # ── P1 v19.470:原判 `bool(mkt_info)`(dict 空不空)——與 v19.177 修 jqavg
        # 時抓到的破口同型:`section_inputs` 會合成只有部分 key 的 dict,dict 非空
        # 但拿不到 score ⇒ 信心不降、缺項不列。改判「真的有評分」。
        ('大盤趨勢評分 (market_regime)', _score is not None, 'score'),
        # ── v19.177 P1-B ② 兩處同時修 ────────────────────────────────────
        # (a) 標籤反捏造:原文「旌旗指數 (站上均線比例)」—— **全站沒有任何一行
        #     在算「站上均線的家數比」**。真值 = 上漲佔比(ad_ratio)的 5 日移動
        #     平均(`jingqi_calc.compute_and_store_jingqi` 的 ADL 主源那一行:
        #     `df_adl_raw['ad_ratio'].tail(5).mean()`)。SSOT 定義在
        #     `src/ui/render/ui_widgets.BREADTH_JINGQI`,但那是 L4 Render,
        #     L2 不得上行 import(§8.2)→ 此處寫字面值,由
        #     `tests/test_p1b_fabricated_defaults.py` 釘住兩邊一致,擋漂移。
        # (b) 判定改吃「真的有沒有數值」:原 `bool(jingqi_info)` 在
        #     `section_inputs` 合成 `{'avg': None}`(section_inputs.py:97)時
        #     為 True(dict 非空)⇒ 明明沒有旌旗值,信心分數卻不降、缺項也不列
        #     = 缺失被吃掉。改判 `_jqavg is not None`。
        (_CONF_LABEL_JINGQI,              _jqavg is not None, 'jqavg'),
        # ── P1 v19.470:原判 `bool(_fk)`(key 在不在)——「key 在但 net 為 None」
        # 會判 True,於是畫面同時出現「信心 100%」與「⏰ 外資數據待更新」兩個
        # 互相矛盾的訊息且無告警。改判「真的拿到數字」,與 jqavg 那條一致。
        ('外資買賣超 (三大法人)',         _fnet is not None, 'fnet'),
        ('先行指標 (期貨/PCR/韭菜)',      bool(li_latest is not None and not li_latest.empty), 'li'),
        ('ADL 騰落指標',                  bool(_cd.get('adl') is not None), 'adl'),
    ]
    # v18.241 E2: confidence 分子分母從 SSOT 引入
    # ⚠️ `conf` 是**畫面顯示用的項數比**,刻意維持 n/5 不動(改分母會讓歷史截圖
    #    與使用者記憶對不上)。它**不適合**拿來做可用性判斷 —— 5 項只有 3 個
    #    獨立故障域,權重實際是 3:1:1(詳 `CONFIDENCE_SOURCE_GROUPS` docstring)。
    #    要判斷「資料夠不夠下結論」請用下面的 `conf_groups`。
    _conf = round(sum(_ok for _, _ok, _ in _conf_sources) / CONFIDENCE_SOURCE_COUNT * 100)
    _missing = [_name for _name, _ok, _ in _conf_sources if not _ok]
    # ── 2026-08-19 方案 C:獨立故障域可用性(schema-additive,`conf` 一字未改)──
    # 每組 True = 該故障域至少還有一項活著。消費端(handlers 擋燈 gate)據此判斷,
    # 不再用「數量門檻」—— 因為數量門檻會把「同一份 ^TWII 掉了 2 個視角」
    # 誤判成比「整個獨立來源全滅」更嚴重。
    _ok_by_key = {_k: _ok for _, _ok, _k in _conf_sources}
    _conf_groups = {
        _g: any(_ok_by_key.get(_k, False) for _k in _keys)
        for _g, _keys in CONFIDENCE_SOURCE_GROUPS.items()
    }
    return {
        'color': _color, 'icon': _icon, 'label': _label,
        'action': _action, 'sub': _sub, 'health': _health,
        # v19.177:True = 健康評分少了旌旗(廣度)那條腿,僅由大盤評分推算。
        # 畫面須據此標示(handlers._render_traffic_light),不可靜默(§1)。
        'health_partial': _health_partial,
        'defense': _defense, 'score': _score, 'jqavg': _jqavg,
        'leek': _leek, 'fnet': _fnet, 'fk': _fk, 'fut_net': _fut_net,
        'conf': _conf, 'missing_sources': _missing, 'conf_groups': _conf_groups,
        # ── C1 v19.182:regime 三欄位契約（schema-additive，既有 caller 無感）──
        # `regime`            = **趨勢面輸入**（raw `mkt_info['regime']`）。
        #                       保留原 key 原語意，供畫面揭露「被壓制的反向訊號」
        #                       （例：趨勢 bull 但健康分跌破 → 燈號仍 🔴）。
        #                       ⚠️ **不是**本函式的結論，消費端不得拿它當多空判斷。
        # `effective_regime`  = 本函式的 canonical 結論（全站唯一真相）。
        # `light` / `regime_source` = 同一次仲裁產生的燈號與生效分支。
        'regime': _regime,
        'effective_regime': _verdict.regime,
        'light': _verdict.light,
        'regime_source': _verdict.source,
    }


def rp_ts(df: Any) -> str:
    """取 DataFrame 最新日期字串（與 _reg_add 邏輯一致）。

    支援來源（依序嘗試）：
      1. DatetimeIndex → 直接取 max
      2. 「季度標籤」欄（'2024Q4' → '2024-12-31'，依 _QE_MAP）
      3. 「年度」欄（int → 'YYYY-12-31'）
      4. _date / date / datetime / timestamp / 日期 / quarter / period 欄
         （_date 強制 '%Y%m%d' format，其他自動推斷）

    任何例外或無法解析 → 回 'N/A'。
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return 'N/A'
    if isinstance(df.index, pd.DatetimeIndex):
        try:
            return pd.Timestamp(df.index.max()).strftime('%Y-%m-%d')
        except Exception:
            pass
    for c in df.columns:
        cl = str(c)
        cll = cl.lower()
        if cl == '季度標籤':
            try:
                lq = str(df[c].dropna().iloc[-1])
                yr_q, qn = lq.split('Q')
                return f'{yr_q}-{_QE_MAP.get(qn, "12-31")}'
            except Exception:
                pass
        if cl == '年度':
            try:
                yr = int(df[c].dropna().iloc[-1])
                return f'{yr}-12-31'
            except Exception:
                pass
        fmt = '%Y%m%d' if cll == '_date' else None
        if cll in ('_date', 'date', 'datetime', 'timestamp', '日期', 'quarter', 'period'):
            try:
                lat = pd.to_datetime(df[c], format=fmt, errors='coerce').max()
                if lat is not None and not pd.isna(lat):
                    return lat.strftime('%Y-%m-%d')
            except Exception:
                pass
    return 'N/A'


def rp_entry(df: Any, cat: str, freq: str) -> dict:
    """DataFrame → registry entry dict（last_updated + rows + cat + freq）。

    空 / None → missing=True；有資料 → 用 rp_ts 取最後日期。
    """
    if isinstance(df, pd.DataFrame) and not df.empty:
        return {'last_updated': rp_ts(df), 'rows': len(df), 'category': cat, 'frequency': freq}
    return {'last_updated': 'N/A', 'rows': 0, 'category': cat, 'frequency': freq, 'missing': True}


def rp_scalar(val: Any, cat: str, freq: str, proxy_date: str) -> dict:
    """純量值（健康度評分 / RSI / 殖利率等）→ registry entry dict。

    有值（非 None）→ rows=1 + last_updated=proxy_date（呼叫端傳入今天或總經更新時間）
    None → missing=True。
    """
    if val is not None:
        return {'last_updated': proxy_date, 'rows': 1, 'category': cat, 'frequency': freq}
    return {'last_updated': 'N/A', 'rows': 0, 'category': cat, 'frequency': freq, 'missing': True}


# v18.169: CPI × Fed Funds 雙頂回落 — 純函式 helper
# ── v19.173 正名(命名不實技術債)──────────────────────────────────────────
# 原名 `detect_mk_golden_inflection`,UI 顯示「MK 黃金拐點」。
# 「MK」在統計文獻是 Mann-Kendall 的通用縮寫,而本函式**不是** Mann-Kendall:
#   它只做「本月 vs 上月」兩點差分 + 固定門檻,沒有 S 統計量、沒有 Var(S)、
#   沒有 Z、沒有 p-value、也沒有 tie 修正(全 repo `grep -i mann` = 0 hit)。
# 舊名會讓讀者以為這條規則有無母數趨勢檢定背書 → 誇大確信度,故正名。
# (v19.174 去識別化前,本 repo 別處的「MK」曾指某 ETF 存股框架的作者代號,兩者撞名更添誤讀;
#  該處已一併改為「存股框架」中性描述。)
# 真正的 Mann-Kendall 實作見 `shared/mk_test.py::mann_kendall`,
# 用於 UI 上的**並列佐證**;本函式的判定邏輯 v19.173 一律不動(零行為變更)。
def detect_cpi_fed_double_top(
    cpi_yoy: Optional[float],
    cpi_prev_yoy: Optional[float],
    fed_rate: Optional[float],
    fed_prev_rate: Optional[float],
) -> Optional[dict]:
    """CPI YoY × Fed Funds Rate「雙頂回落」偵測（鏡像 fund _detect_inflection）。

    ⚠️ 這是什麼 / 不是什麼（v19.173 誠實揭露）
    ------------------------------------------
    **是**：對「最新月」與「上一月」兩個純量做差分，再比對固定 ppt 門檻的
            經驗規則。輸入只有 4 個數字，沒有時間序列。
    **不是**：Mann-Kendall 無母數趨勢檢定。本函式沒有 S 統計量、沒有 Var(S)、
            沒有 Z、沒有 p-value、沒有 tie 修正，也沒有做任何顯著性宣稱。
            若需要真正的趨勢檢定，請用 `shared.mk_test.mann_kendall()`
            （它吃整條序列，回 Z / p / Sen's slope）。
    ⚠️ v19.173 現況：兩者**尚未**在 UI 並列 —— `mann_kendall()` 目前
    **零 production caller**。原因是 `macro_snapshot.fetch_cpi_block()` /
    `fetch_fed_funds_block()` 只回「本月 + 上月」兩個純量，全 repo 沒有
    CPI/Fed 的歷史序列可餵給檢定（n=2 時 `mann_kendall()` 本來就回 None）。
    **規劃**是等序列 fetcher 到位後並列呈現：本規則負責「拐點事件」判讀、
    Mann-Kendall 負責「這段期間有沒有統計上的趨勢」佐證，**互不覆寫**。
    接序列屬新資料流，§7 需先對齊 endpoint／單位／發布延遲／PIT 鍵
    （FRED CPI 必須用 release_date 而非 observation_date）。

    參數
    ----
    cpi_yoy        : 最新月度美國核心 CPI 年增率（%）
    cpi_prev_yoy   : 上月度美國核心 CPI 年增率（%）
    fed_rate       : 最新月度 Fed Funds Rate（%，月均有效利率）
    fed_prev_rate  : 上月度 Fed Funds Rate（%）

    回傳
    ----
    None  — 資料不足（任一參數為 None）或無訊號
    dict  — {'label', 'icon', 'color', 'detail', 'strength'}
            strength: 'strong'（雙明確回落）/ 'weak'（CPI 弱降+Fed 持平）

    判讀規則（防雜訊：±0.05ppt 視為持平）
    --------
    - CPI 月降 ≥ 0.2ppt AND Fed 持平或月降      → ⭐ 強訊號（CPI×Fed 雙頂回落）
    - CPI 月降 ∈ [0.05, 0.2)ppt AND Fed 持平或月降 → ✅ 弱訊號（回落觀察中）
    - 任一上升 (> 0.05ppt) 或 CPI 未降          → None（無訊號）
    """
    if cpi_yoy is None or cpi_prev_yoy is None:
        return None
    if fed_rate is None or fed_prev_rate is None:
        return None

    try:
        cpi_delta = float(cpi_yoy) - float(cpi_prev_yoy)      # 負值 = 通膨降溫
        fed_delta = float(fed_rate) - float(fed_prev_rate)    # 負/零 = 降息或暫停
    except (TypeError, ValueError):
        return None

    # 任一指標明確上升 → 無訊號
    if cpi_delta > 0.05 or fed_delta > 0.05:
        return None
    # CPI 須至少出現降溫（>= 0.05ppt 月降）
    if cpi_delta > -0.05:
        return None

    _fed_desc = '持平' if abs(fed_delta) < 0.05 else f'月降 {abs(fed_delta):.2f}ppt'

    if cpi_delta <= -0.2:
        return {
            # v19.173 正名:原 'MK 黃金拐點 ⭐'(見上方函式註解:MK ≠ Mann-Kendall)
            'label': 'CPI×Fed 雙頂回落 ⭐',
            'icon': '⭐',
            'color': TRAFFIC_GREEN,
            'detail': (
                f'核心 CPI {cpi_prev_yoy:+.2f}% → {cpi_yoy:+.2f}% '
                f'（月降 {abs(cpi_delta):.2f}ppt） + Fed Funds '
                f'{fed_prev_rate:.2f}% → {fed_rate:.2f}% （{_fed_desc}） '
                f'→ ⭐ 通膨+利率雙頂回落，景氣多頭最佳買點（歷史勝率最高）'
            ),
            'strength': 'strong',
        }
    return {
        # v19.173 正名:原 'MK 拐點觀察中'
        'label': 'CPI×Fed 回落觀察中',
        'icon': '✅',
        'color': TRAFFIC_YELLOW,
        'detail': (
            f'核心 CPI {cpi_prev_yoy:+.2f}% → {cpi_yoy:+.2f}% + '
            f'Fed Funds {fed_prev_rate:.2f}% → {fed_rate:.2f}% '
            f'→ 通膨初步降溫，待 CPI 加速回落或 Fed 確認暫停升息'
        ),
        'strength': 'weak',
    }


# ── v19.173 向後相容 alias（DEPRECATED，勿用於新程式碼）────────────────────
# 舊名 `detect_mk_golden_inflection` 命名不實（「MK」= Mann-Kendall 的通用縮寫，
# 但本規則只是兩點差分）。正名後保留 alias 是為了**不破壞既有 caller**。
# v19.173 當下仍以舊名呼叫的地方（全 repo 掃描結果）：
#   - src/ui/tabs/macro/section_long_term.py:43  （長期 regime 的 mk_signal 輸入）
#     ← 該檔本輪不在授權改動範圍內，故 alias 不刪。
#   - tests/test_macro_helpers.py                 （刻意保留，兼測 alias 未斷）
# 已遷移到新名的：src/ui/tabs/macro/section_state.py（拐點面板第 7 項）。
# 新程式碼一律改用 `detect_cpi_fed_double_top`；待全部 caller 遷移完成後移除本行。
detect_mk_golden_inflection = detect_cpi_fed_double_top


# v18.170: 長期總經位階分類（12M 視角，景氣大循環）— 純函式 helper
def _safe_float(x: Any) -> Optional[float]:
    """容錯轉浮點：None/字串/NaN → None。"""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN guard
        return None
    return f


def classify_long_term_regime(
    cpi_yoy: Any,
    fed_rate: Any,
    fed_prev_rate: Any,
    ndc_score: Any,
    pmi: Any,
    mk_signal: Optional[dict] = None,
) -> dict:
    """長期總經位階判讀（12M 視角，景氣大循環）。

    參數
    ----
    cpi_yoy        : 美國核心 CPI YoY（%）
    fed_rate       : 最新 Fed Funds Rate（%）
    fed_prev_rate  : 上月 Fed Funds Rate（%）
    ndc_score      : 台灣景氣對策信號分數（9-45）
    pmi            : 台灣製造業 PMI 指數（CIER）
    mk_signal      : detect_cpi_fed_double_top() 回傳值（None 或 dict）
                     ⚠️ v19.173：參數名維持 `mk_signal` 是為了不破壞既有
                     keyword caller（section_long_term.py:66）；語意上它是
                     「CPI×Fed 雙頂回落」訊號，**與 Mann-Kendall 無關**。

    回傳
    ----
    dict 含 regime / score / color / detail / suggest_pct / components
    components 為 list[tuple(name, score_pts, weight_pct)]，便於 UI 拆解顯示

    評分（每項 ∈ [-2, +2]，加權加總）
    --------
    - CPI YoY (25%)：≤2%+2 / 2-3%+1 / 3-4% 0 / 4-5%-1 / ≥5%-2
    - Fed 方向 (20%)：月降+2 / 持平+1 / 月升-2
    - NDC (20%)：紅(≥38)+2 / 黃紅(32-37)+1 / 綠(23-31) 0 / 黃藍(17-22)-1 / 藍(<17)-2
    - PMI (20%)：≥55+2 / 52-55+1 / 50-52 0 / 48-50-1 / <48-2
    - CPI×Fed 雙頂 (15%)：⭐強+2 / ✅弱+1 / None 0（v19.173 正名，原「MK 拐點」）
    """
    cpi_v = _safe_float(cpi_yoy)
    fed_v = _safe_float(fed_rate)
    fed_p = _safe_float(fed_prev_rate)
    ndc_v = _safe_float(ndc_score)
    pmi_v = _safe_float(pmi)

    components: list = []
    weighted_sum = 0.0
    weight_total = 0.0

    # 1. CPI YoY 趨勢（25%）
    if cpi_v is not None:
        if cpi_v <= 2.0:
            cpi_pts = 2
        elif cpi_v <= 3.0:
            cpi_pts = 1
        elif cpi_v <= 4.0:
            cpi_pts = 0
        elif cpi_v <= 5.0:
            cpi_pts = -1
        else:
            cpi_pts = -2
        components.append(('美 CPI YoY', cpi_pts, 25))
        weighted_sum += cpi_pts * 25
        weight_total += 25

    # 2. Fed Funds 方向（20%）
    if fed_v is not None and fed_p is not None:
        fed_delta = fed_v - fed_p
        if fed_delta < -0.05:
            fed_pts = 2
        elif fed_delta <= 0.05:
            fed_pts = 1
        else:
            fed_pts = -2
        components.append(('Fed 方向', fed_pts, 20))
        weighted_sum += fed_pts * 20
        weight_total += 20

    # 3. NDC 景氣對策（20%）
    if ndc_v is not None:
        if ndc_v >= 38:
            ndc_pts = 2
        elif ndc_v >= 32:
            ndc_pts = 1
        elif ndc_v >= 23:
            ndc_pts = 0
        elif ndc_v >= 17:
            ndc_pts = -1
        else:
            ndc_pts = -2
        components.append(('NDC 景氣燈號', ndc_pts, 20))
        weighted_sum += ndc_pts * 20
        weight_total += 20

    # 4. PMI 水準（20%）
    if pmi_v is not None:
        if pmi_v >= 55:
            pmi_pts = 2
        elif pmi_v >= 52:
            pmi_pts = 1
        elif pmi_v >= 50:
            pmi_pts = 0
        elif pmi_v >= 48:
            pmi_pts = -1
        else:
            pmi_pts = -2
        components.append(('台 PMI', pmi_pts, 20))
        weighted_sum += pmi_pts * 20
        weight_total += 20

    # 5. CPI×Fed 雙頂回落訊號（15%）— 僅當至少一個主指標存在時才計入
    # v19.173 正名：原「MK 黃金拐點」。components 目前無 production render
    # （v18.190 已移除雙視角 UI 區塊，僅 _lt['score'] / ['regime'] 被下游取用），
    # 故改名不影響任何畫面；改的是未來讀 code 的人不會再被「MK」誤導。
    if weight_total > 0:
        if mk_signal is not None and isinstance(mk_signal, dict):
            _s = mk_signal.get('strength')
            mk_pts = 2 if _s == 'strong' else (1 if _s == 'weak' else 0)
        else:
            mk_pts = 0
        components.append(('CPI×Fed 雙頂', mk_pts, 15))
        weighted_sum += mk_pts * 15
        weight_total += 15

    if weight_total == 0:
        return {
            'regime': '⚪ 資料不足',
            'score': 0.0,
            'color': '#8b949e',
            'detail': '所有長期指標皆缺失，無法判讀',
            'suggest_pct': 'N/A',
            'components': components,
        }

    score = weighted_sum / weight_total  # ∈ [-2, +2]

    if score >= 1.0:
        regime, color, suggest = '🟢 成長期', TRAFFIC_GREEN, '80%+'
        detail = '景氣擴張+通膨溫和+資金寬鬆 → 多頭主升段，可積極做多'
    elif score >= 0.0:
        regime, color, suggest = '🔵 復甦期', '#58a6ff', '60-80%'
        detail = '景氣由谷底回升 → 加碼基本面好的標的，留意通膨變化'
    elif score >= -1.0:
        regime, color, suggest = '🟡 過熱/震盪期', TRAFFIC_YELLOW, '40-60%'
        detail = '景氣高檔震盪或通膨壓力 → 謹慎觀望，等待方向確認'
    else:
        regime, color, suggest = '🔴 衰退期', TRAFFIC_RED, '<30%'
        detail = '景氣下行+通膨壓力或政策緊縮 → 保守減倉，現金為王'

    return {
        'regime': regime,
        'score': round(score, 2),
        'color': color,
        'detail': detail,
        'suggest_pct': suggest,
        'components': components,
    }


# v18.170: 短期總經分類（1Q 視角，對齊台股財報季）— 純函式 helper
def classify_short_term_regime(
    export_yoy: Any,
    pmi: Any,
    vix_current: Any,
    fi_streak_days: Any,
    cpi_yoy: Any,
    cpi_prev_yoy: Any,
) -> dict:
    """短期總經偏向判讀（1Q 視角，對齊台股財報季 Q1/Q2/Q3/Q4）。

    參數
    ----
    export_yoy      : 台灣出口 YoY（%）
    pmi             : 台灣製造業 PMI（CIER 指數）
    vix_current     : VIX 收盤
    fi_streak_days  : 外資連續買賣超天數（+正=連買，負=連賣）
    cpi_yoy         : 美 CPI YoY（%）
    cpi_prev_yoy    : 上月 CPI YoY（%）

    回傳
    ----
    dict 含 regime / score / color / detail / action / components

    評分（每項 ∈ [-2, +2]，加權加總）
    --------
    - 出口 YoY (25%)：≥15%+2 / 5-15%+1 / 0-5% 0 / -5-0%-1 / <-5%-2
    - PMI 水準 (25%)：≥55+2 / 52-55+1 / 50-52 0 / 48-50-1 / <48-2
    - VIX 水準 (15%)：<15+2 / 15-20+1 / 20-25 0 / 25-30-1 / ≥30-2
    - 外資連續 (20%)：連買≥5+2 / 1-4+1 / 0 0 / 連賣1-4-1 / 連賣≥5-2
    - CPI 月降 (15%)：降≥0.3+2 / 0.1-0.3+1 / ±0.1 0 / 升0.1-0.3-1 / 升≥0.3-2
    """
    exp_v = _safe_float(export_yoy)
    pmi_v = _safe_float(pmi)
    vix_v = _safe_float(vix_current)
    fi_v  = _safe_float(fi_streak_days)
    cpi_v = _safe_float(cpi_yoy)
    cpi_p = _safe_float(cpi_prev_yoy)

    components: list = []
    weighted_sum = 0.0
    weight_total = 0.0

    # 1. 出口 YoY（25%）
    if exp_v is not None:
        if exp_v >= 15:
            exp_pts = 2
        elif exp_v >= 5:
            exp_pts = 1
        elif exp_v >= 0:
            exp_pts = 0
        elif exp_v >= -5:
            exp_pts = -1
        else:
            exp_pts = -2
        components.append(('出口 YoY', exp_pts, 25))
        weighted_sum += exp_pts * 25
        weight_total += 25

    # 2. PMI 水準（25%）
    if pmi_v is not None:
        if pmi_v >= 55:
            pmi_pts = 2
        elif pmi_v >= 52:
            pmi_pts = 1
        elif pmi_v >= 50:
            pmi_pts = 0
        elif pmi_v >= 48:
            pmi_pts = -1
        else:
            pmi_pts = -2
        components.append(('台 PMI', pmi_pts, 25))
        weighted_sum += pmi_pts * 25
        weight_total += 25

    # 3. VIX 水準（15%）
    if vix_v is not None:
        if vix_v < 15:
            vix_pts = 2
        elif vix_v < 20:
            vix_pts = 1
        elif vix_v < 25:
            vix_pts = 0
        elif vix_v < 30:
            vix_pts = -1
        else:
            vix_pts = -2
        components.append(('VIX 波動', vix_pts, 15))
        weighted_sum += vix_pts * 15
        weight_total += 15

    # 4. 外資連續日數（20%）
    if fi_v is not None:
        if fi_v >= 5:
            fi_pts = 2
        elif fi_v >= 1:
            fi_pts = 1
        elif fi_v > -1:
            fi_pts = 0
        elif fi_v > -5:
            fi_pts = -1
        else:
            fi_pts = -2
        components.append(('外資籌碼', fi_pts, 20))
        weighted_sum += fi_pts * 20
        weight_total += 20

    # 5. CPI 月降幅（15%）
    if cpi_v is not None and cpi_p is not None:
        cpi_delta = cpi_v - cpi_p   # 負值 = 通膨降溫
        if cpi_delta <= -0.3:
            cpi_pts = 2
        elif cpi_delta <= -0.1:
            cpi_pts = 1
        elif cpi_delta <= 0.1:
            cpi_pts = 0
        elif cpi_delta <= 0.3:
            cpi_pts = -1
        else:
            cpi_pts = -2
        components.append(('CPI 月降', cpi_pts, 15))
        weighted_sum += cpi_pts * 15
        weight_total += 15

    if weight_total == 0:
        return {
            'regime': '⚪ 資料不足',
            'score': 0.0,
            'color': '#8b949e',
            'detail': '所有短期指標皆缺失，無法判讀',
            'action': 'N/A',
            'components': components,
        }

    score = weighted_sum / weight_total  # ∈ [-2, +2]

    if score >= 0.8:
        regime, color = '⚡ 偏多', TRAFFIC_GREEN
        detail = '下個財報季正向動能 → 加碼績優股、波段佈局好時機'
        action = '建議：擇強做多、留意外資連續買超的個股'
    elif score >= -0.3:
        regime, color = '⚖️ 中性', TRAFFIC_YELLOW
        detail = '訊號分歧或多空交織 → 觀望為主、留意個股輪動'
        action = '建議：區間操作、避免追高殺低、續抱長期持股'
    else:
        regime, color = '⚠️ 偏空', TRAFFIC_RED
        detail = '下個財報季承壓 → 防守為主、現金為王'
        action = '建議：減碼高估值、停利出場、留意外資連續賣超'

    return {
        'regime': regime,
        'score': round(score, 2),
        'color': color,
        'detail': detail,
        'action': action,
        'components': components,
    }


# ════════════════════════════════════════════════════════════════════════════
# v18.270 — TW 央行政策階段衍生函式
# Spec(§7 對齊):純函式無 I/O,搭配 tw_macro.fetch_* 上游
# ════════════════════════════════════════════════════════════════════════════

def calc_real_rate(rate_pct: Optional[float],
                   cpi_yoy_pct: Optional[float]) -> Optional[float]:
    """實質利率(%) = 名目政策利率(%) − CPI YoY(%)。

    Args
    ----
    rate_pct: CBC 重貼現率或銀行間隔夜拆款 (% level)
    cpi_yoy_pct: CPI 年增率 (% YoY)

    Returns
    -------
    float | None
        實質利率;任一輸入為 None / NaN → None(§1 不偽造)。

    Notes
    -----
    經濟學上,實質利率為負(rate < CPI)= 寬鬆;為正且 > 1% = 緊縮。
    """
    if rate_pct is None or cpi_yoy_pct is None:
        return None
    try:
        rr = float(rate_pct) - float(cpi_yoy_pct)
        if pd.isna(rr):
            return None
        return round(rr, 3)
    except (TypeError, ValueError):
        return None


def classify_rate_cycle(rate_series: Optional[pd.Series],
                        lookback_months: int = 6,
                        epsilon: float = 0.05) -> str:
    """依政策利率近 N 月變化分類「升息中 / 持平 / 降息中」。

    Args
    ----
    rate_series: 時間序 % level(date index ascending),最少需 2 筆。
    lookback_months: 比較窗口,預設 6 月(對齊台灣央行季度理監事會節奏)。
    epsilon: 視為「持平」的容差(% pts),預設 0.05% = 5bp。

    Returns
    -------
    str: '🟢 升息中' / '⚪ 持平' / '🔴 降息中' / '⬜ 資料不足'
    """
    if rate_series is None:
        return '⬜ 資料不足'
    try:
        s = pd.Series(rate_series).dropna()
    except (TypeError, ValueError):
        return '⬜ 資料不足'
    if len(s) < 2:
        return '⬜ 資料不足'
    s_tail = s.tail(min(lookback_months, len(s)))
    delta = float(s_tail.iloc[-1]) - float(s_tail.iloc[0])
    if abs(delta) < epsilon:
        return '⚪ 持平'
    return '🟢 升息中' if delta > 0 else '🔴 降息中'


def calc_china_credit_impulse_proxy(m2_series: Optional[pd.Series],
                                    lag_months: int = 12) -> Optional[float]:
    """中國信貸脈衝 proxy:M2 YoY 與 N 月前 M2 YoY 的差(% pts)。

    真正信貸脈衝 = Δ(信貸/GDP),需社融存量 + GDP,無乾淨 FRED 來源;
    M2 YoY 變化是粗略貨幣寬鬆代理。對稱 Fund 端同名函式。

    Args
    ----
    m2_series: M2 YoY % 月頻時間序(date index ascending,**需已 YoY**)。
    lag_months: 比較期,預設 12 月。

    Returns
    -------
    float | None
        正值 = 12 月內 M2 加速(寬鬆中)、負值 = 緊縮中;
        資料不足 N+1 筆 → None(§1 不偽造)。
    """
    if m2_series is None:
        return None
    try:
        s = pd.Series(m2_series).dropna()
    except (TypeError, ValueError):
        return None
    if len(s) < lag_months + 1:
        return None
    cur = float(s.iloc[-1])
    prev = float(s.iloc[-(lag_months + 1)])
    return round(cur - prev, 3)


def calc_twd_trend(usdtwd_series: Optional[pd.Series],
                   window_days: int = 60) -> Optional[dict]:
    """USDTWD 60 日趨勢:回 latest / 60D MA / 斜率(% pts/月)。

    Args
    ----
    usdtwd_series: USD/TWD 日序列(數字越大 = 台幣越貶)。
    window_days: 滾動窗口,預設 60(約 2 個月)。

    Returns
    -------
    dict | None
        {
          'latest': float,                # 最新匯率
          'ma_60d': float | None,         # 60 日均線(資料不足回 None)
          'slope_per_month': float|None,  # 線性斜率 (TWD/USD per 月,正=台幣貶)
          'direction': str,               # '🔴 台幣貶' / '🟢 台幣升' / '⚪ 持平'
        }
        輸入無效回 None。
    """
    if usdtwd_series is None:
        return None
    try:
        s = pd.Series(usdtwd_series).dropna()
    except (TypeError, ValueError):
        return None
    if s.empty:
        return None
    latest = float(s.iloc[-1])
    out: dict = {
        'latest': round(latest, 4),
        'ma_60d': None,
        'slope_per_month': None,
        'direction': '⚪ 持平',
    }
    if len(s) < window_days:
        return out
    tail = s.tail(window_days)
    out['ma_60d'] = round(float(tail.mean()), 4)
    # 線性斜率(per trading day → per month ≈ 21 交易日)
    xs = list(range(len(tail)))
    ys = tail.values
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    if den == 0:
        return out
    slope_per_day = num / den
    slope_per_month = slope_per_day * 21
    out['slope_per_month'] = round(slope_per_month, 4)
    # 月斜率 > 0.1 (~0.3%) 算貶值方向;< -0.1 算升值
    if slope_per_month > 0.1:
        out['direction'] = '🔴 台幣貶'
    elif slope_per_month < -0.1:
        out['direction'] = '🟢 台幣升'
    return out


# ════════════════════════════════════════════════════════════════════════════
# v18.272 — China 副盤(snapshot + sub-score + sub-regime)
# 對稱 Fund v19.114 的 services/macro_service.py 同名函式,演算法 100% 一致
#
# 設計決策(對齊 §-1 + §8.1 step 6):
# - 副盤獨立,**不**接入主 compute_macro_health(避免改變既有評分歷史可信度)
# - 5 因子等權 0.20 each(CLI/PMI/CPI/M2/USDCNY)
# - 4 級 regime + USDCNY > 7.4 fx_alert 獨立 flag
# - 全缺 → return None(§1 fail loud,不偽 50 中性)
# ════════════════════════════════════════════════════════════════════════════

# China zone(對齊 §3.2 合理範圍 + macro_core.MACRO_THRESHOLDS v18.271 5 項)
_CHINA_SUBSCORE_THRESHOLDS = {
    "CHN_CLI":   {"green_above": 100.0, "yellow_below": 99.0, "red_below": 98.0},
    "CHN_BCI":   {"green_above": 100.0, "yellow_below": 99.0, "red_below": 98.0},  # v18.459: renamed from CHN_PMI
    "CHN_CPI":   {"green_low": 1.0, "green_high": 3.0, "yellow_above": 4.0, "red_above": 5.0},
    "CHN_M2":    {"red_below": 5.0, "green_above": 9.0},
    "USDCNY":    {"green_below": 7.0, "yellow_above": 7.2, "red_above": 7.4},
}


def _classify_china_zone(value: Optional[float], rules: dict) -> str:
    """通用 traffic 分類:依 rules dict → 字串。"""
    if value is None or pd.isna(value):
        return "⬜ 無資料"
    v = float(value)
    if "red_above" in rules and v > rules["red_above"]:
        return "🔴 紅"
    if "red_below" in rules and v < rules["red_below"]:
        return "🔴 紅"
    if "yellow_above" in rules and v > rules["yellow_above"]:
        return "🟡 黃"
    if "yellow_below" in rules and v < rules["yellow_below"]:
        return "🟡 黃"
    if "green_above" in rules and v > rules["green_above"]:
        return "🟢 綠"
    if "green_below" in rules and v < rules["green_below"]:
        return "🟢 綠"
    if "green_low" in rules and "green_high" in rules:
        if rules["green_low"] <= v <= rules["green_high"]:
            return "🟢 綠"
    return "⚪ 中性"


def china_macro_snapshot(china_dict: dict) -> dict:
    """組裝 tw_macro.fetch_china_macro 結果為簡單 snapshot。

    Args
    ----
    china_dict: dict[series_id, DataFrame]
        tw_macro.fetch_china_macro() 回傳;每個 DataFrame 含
        [date, value, source, fetched_at] 至少欄位。

    Returns
    -------
    dict 包含 5 個 key:cli/pmi/cpi_yoy/m2_yoy/usdcny,
    每個對應 {"value", "date", "zone", "source"};
    + "credit_impulse_proxy"(M2 YoY 12 月變化,§4.3 衍生)。

    v18.273 校正(§4.1 量綱):
    - `FRED_CHN_M2`(`MABMM301CNM189S`)FRED 回的是 **M3 level (兆 CNY)**,
      非 YoY %。本函式內部先 `pct_change(12) * 100` 轉 YoY 才進 scorer。
    - `m2_yoy["value"]` 為轉換後 YoY %,可直接餵 `_score_china_m2`(門檻 5/9%)
    - `credit_impulse_proxy` 輸入也用 YoY 序列,而非 level
    """
    # SSOT 從 shared/fred_series 引入(對應 tw_macro._china_fred_specs)
    from shared.fred_series import (  # noqa: PLC0415
        FRED_CHN_CPI,
        FRED_CHN_M2,
        FRED_CHN_OECD_CLI,
        FRED_CHN_PMI,
        FRED_USDCNY,
    )

    def _extract(sid: str, threshold_key: str) -> dict:
        df = china_dict.get(sid) if china_dict else None
        out = {"value": None, "date": None, "zone": "⬜ 無資料", "source": None}
        if df is None or df.empty:
            return out
        try:
            last = df.iloc[-1]
            v = float(last["value"])
            d = pd.Timestamp(last["date"]).strftime("%Y-%m-%d")
            out["value"] = round(v, 4)
            out["date"] = d
            out["zone"] = _classify_china_zone(v, _CHINA_SUBSCORE_THRESHOLDS.get(threshold_key, {}))
            out["source"] = str(last.get("source", f"FRED:{sid}"))
        except (KeyError, ValueError, TypeError) as e:
            print(f"[china_macro_snapshot/{sid}] extract 失敗: {e}")
        return out

    # v18.273 校正:M2(實 M3 level)先轉 YoY series 再進 _extract 路徑
    # 避免直接吃 level 餵 _score_china_m2(門檻 5/9%)造成評分恆 100 的 bug
    m2_yoy_df = None
    m2_df_raw = china_dict.get(FRED_CHN_M2) if china_dict else None
    if m2_df_raw is not None and not m2_df_raw.empty:
        try:
            tmp = m2_df_raw.copy()
            # A4 v18.384:抽 shared/calc_helpers.pct_change_yoy SSOT
            from shared.calc_helpers import pct_change_yoy as _pcy
            tmp["value"] = _pcy(tmp["value"].astype(float))
            tmp = tmp.dropna(subset=["value"])
            if not tmp.empty:
                m2_yoy_df = tmp
        except (KeyError, ValueError, TypeError) as e:
            print(f"[china_macro_snapshot/m2_yoy_conv] {e}")

    def _extract_m2_yoy() -> dict:
        out = {"value": None, "date": None, "zone": "⬜ 無資料", "source": None}
        if m2_yoy_df is None:
            return out
        try:
            last = m2_yoy_df.iloc[-1]
            v = float(last["value"])
            d = pd.Timestamp(last["date"]).strftime("%Y-%m-%d")
            out["value"] = round(v, 4)
            out["date"] = d
            out["zone"] = _classify_china_zone(v, _CHINA_SUBSCORE_THRESHOLDS.get("CHN_M2", {}))
            out["source"] = str(last.get("source", f"FRED:{FRED_CHN_M2}"))
        except (KeyError, ValueError, TypeError) as e:
            print(f"[china_macro_snapshot/m2_yoy] {e}")
        return out

    snapshot = {
        "cli":     _extract(FRED_CHN_OECD_CLI, "CHN_CLI"),
        "pmi":     _extract(FRED_CHN_PMI, "CHN_PMI"),
        "cpi_yoy": _extract(FRED_CHN_CPI, "CHN_CPI"),
        "m2_yoy":  _extract_m2_yoy(),
        "usdcny":  _extract(FRED_USDCNY, "USDCNY"),
    }

    # 衍生:信貸脈衝 proxy(M2 YoY 12 月變化)— 用已轉換的 YoY series
    if m2_yoy_df is not None:
        try:
            m2_yoy_series = m2_yoy_df["value"].astype(float)
            snapshot["credit_impulse_proxy"] = calc_china_credit_impulse_proxy(m2_yoy_series)
        except (KeyError, ValueError, TypeError) as e:
            print(f"[china_macro_snapshot/credit_impulse] {e}")
            snapshot["credit_impulse_proxy"] = None
    else:
        snapshot["credit_impulse_proxy"] = None

    return snapshot


# ── 5 因子各自打分(0/25/50/100,對應紅/黃綠 zone)──
def _score_china_cli(v: Optional[float]) -> Optional[float]:
    """CLI 評分:>100 擴張 100 / 99-100 中性 50 / 98-99 收縮 25 / <98 衰退 0"""
    if v is None or pd.isna(v):
        return None
    v = float(v)
    if v > 100.0:  return 100.0
    if v >= 99.0:  return 50.0
    if v >= 98.0:  return 25.0
    return 0.0


def _score_china_pmi(v: Optional[float]) -> Optional[float]:
    """PMI proxy 評分:同 CLI 結構"""
    return _score_china_cli(v)


def _score_china_cpi(v: Optional[float]) -> Optional[float]:
    """CPI YoY 評分:1-3% 理想 100 / 0-1 或 3-4 中性 50 / >4 過熱 0 / <0 通縮 0"""
    if v is None or pd.isna(v):
        return None
    v = float(v)
    if 1.0 <= v <= 3.0:  return 100.0
    if 0.0 <= v < 1.0 or 3.0 < v <= 4.0:  return 50.0
    return 0.0


def _score_china_m2(v: Optional[float]) -> Optional[float]:
    """M2 YoY 評分:>=9% 寬鬆 100 / 5-9% 中性 50 / <5% 緊縮 0"""
    if v is None or pd.isna(v):
        return None
    v = float(v)
    if v >= 9.0:  return 100.0
    if v >= 5.0:  return 50.0
    return 0.0


def _score_china_usdcny(v: Optional[float]) -> Optional[float]:
    """USDCNY 評分:<7.0 強勢 100 / 7.0-7.2 中性 50 / 7.2-7.4 偏弱 25 / >7.4 大貶 0"""
    if v is None or pd.isna(v):
        return None
    v = float(v)
    # C-3 v18.382:7.2 / 7.4 補抽(P2-3 已抽 7.0)
    from shared.signal_thresholds import (
        CHINA_USDCNY_STRONG, CHINA_USDCNY_NEUTRAL, CHINA_USDCNY_WEAK,
    )
    if v < CHINA_USDCNY_STRONG: return 100.0
    if v <= CHINA_USDCNY_NEUTRAL: return 50.0
    if v <= CHINA_USDCNY_WEAK: return 25.0
    return 0.0


def compute_china_subscore(snapshot: dict) -> Optional[dict]:
    """5 因子等權 0.20 each 計算 China 副盤分數。

    Args
    ----
    snapshot: china_macro_snapshot() 回傳結果

    Returns
    -------
    dict | None:
        {"score": float|None, "factors": {...}, "n_available": int, "n_total": 5}
        全缺 → None(§1 fail loud,**不**偽 50 中性)。
    """
    if not snapshot:
        return None
    scorers = [
        ("cli",    "cli",     _score_china_cli),
        ("pmi",    "pmi",     _score_china_pmi),
        ("cpi",    "cpi_yoy", _score_china_cpi),
        ("m2",     "m2_yoy",  _score_china_m2),
        ("usdcny", "usdcny",  _score_china_usdcny),
    ]
    factors = {}
    scores = []
    for short, snap_key, scorer in scorers:
        entry = snapshot.get(snap_key, {})
        val = entry.get("value") if isinstance(entry, dict) else None
        s = scorer(val)
        factors[short] = {"value": val, "score": s}
        if s is not None:
            scores.append(s)
    n_avail = len(scores)
    if n_avail == 0:
        return None
    avg = round(sum(scores) / n_avail, 2)
    return {"score": avg, "factors": factors, "n_available": n_avail, "n_total": 5}


def classify_china_regime(snapshot: dict) -> dict:
    """從 China snapshot 推導 4 級 regime + USDCNY 警示 flag。

    Levels(BCI = OECD 商業信心 BSCICP03CNM665S，基準值 100，≠ PMI 50 榮枯線):
      🟢 擴張:CLI > 100 AND BCI > 100
      🟡 減速:CLI < 99 OR BCI < 99(但非衰退)
      🔴 衰退/緊縮:(CLI < 98 AND BCI < 98) OR M2 < 5%
      ⚪ 中性:其餘
      🚨 fx_alert flag(獨立):USDCNY > 7.4

    Returns:
        {"regime": str, "fx_alert": bool, "reason": str}
    """
    if not snapshot:
        return {"regime": "⬜ 資料不足", "fx_alert": False, "reason": "snapshot 空"}

    def _val(k: str):
        entry = snapshot.get(k, {})
        return entry.get("value") if isinstance(entry, dict) else None

    cli = _val("cli")
    pmi = _val("pmi")
    m2 = _val("m2_yoy")
    usdcny = _val("usdcny")

    fx_alert = (usdcny is not None and not pd.isna(usdcny) and float(usdcny) > 7.4)

    if cli is None and pmi is None:
        return {"regime": "⬜ 資料不足", "fx_alert": fx_alert,
                "reason": "CLI/PMI 雙缺"}

    cli_red = (cli is not None and float(cli) < 98.0)
    pmi_red = (pmi is not None and float(pmi) < 98.0)
    m2_tight = (m2 is not None and float(m2) < 5.0)
    if (cli_red and pmi_red) or m2_tight:
        reasons = []
        if cli_red and pmi_red:
            reasons.append(f"CLI={cli:.1f} & BCI={pmi:.1f} 雙紅")
        if m2_tight:
            reasons.append(f"M2={m2:.1f}% 緊縮")
        return {"regime": "🔴 衰退/緊縮", "fx_alert": fx_alert,
                "reason": "; ".join(reasons)}

    cli_green = (cli is not None and float(cli) > 100.0)
    pmi_green = (pmi is not None and float(pmi) > 100.0)
    if cli_green and pmi_green:
        return {"regime": "🟢 擴張", "fx_alert": fx_alert,
                "reason": f"CLI={cli:.1f} & BCI={pmi:.1f} 雙綠"}

    cli_slow = (cli is not None and float(cli) < 99.0)
    pmi_slow = (pmi is not None and float(pmi) < 99.0)
    if cli_slow or pmi_slow:
        which = []
        if cli_slow:  which.append(f"CLI={cli:.1f}")
        if pmi_slow:  which.append(f"BCI={pmi:.1f}")
        return {"regime": "🟡 減速", "fx_alert": fx_alert,
                "reason": " / ".join(which) + " <99"}

    return {"regime": "⚪ 中性", "fx_alert": fx_alert,
            "reason": f"CLI={cli}, BCI={pmi} 皆 99-100 區間"}


# ════════════════════════════════════════════════════════════════════════════
# v18.274 — China 副盤 → 主分 乘法 modifier(對稱 Fund v19.116)
# 設計:composite = main × (0.7 + 0.3 × china/100)
#   - china=100(全綠)→ multiplier=1.0 → composite=main(不加成)
#   - china=50 (中性)→ multiplier=0.85 → composite=0.85×main(15% 懲罰)
#   - china=0  (全紅)→ multiplier=0.7 → composite=0.7×main(30% 懲罰)
# 哲學:不對「中國好」主觀加成(避免主分高估),只對「中國壞」做風險溢價懲罰。
# 台股 ~30% 營收 China exposure → 中國弱 = 確定 tail risk,連續線性折扣。
#
# 用法(caller 自行選用,本檔不強制套用):
#   from macro_helpers import (
#       china_macro_snapshot, compute_china_subscore, apply_china_modifier,
#       compute_macro_health,
#   )
#   main = compute_macro_health(macro_dict)["score"]
#   china = compute_china_subscore(china_macro_snapshot(china_dict))
#   composite = apply_china_modifier(main, china["score"] if china else None)
# ════════════════════════════════════════════════════════════════════════════

CHINA_MODIFIER_FLOOR: float = 0.7  # China 全紅時的最低折扣(70% × main)
CHINA_MODIFIER_RANGE: float = 0.3  # 0.7 ~ 1.0 之間擺動


def apply_china_modifier(main_score: Optional[float],
                         china_subscore: Optional[float]) -> Optional[dict]:
    """套用 China 副盤對主分的乘法 modifier。

    公式:composite = main × (CHINA_MODIFIER_FLOOR + CHINA_MODIFIER_RANGE × china/100)
    範圍:multiplier ∈ [0.7, 1.0],只懲罰不加成。

    Args
    ----
    main_score: 主 macro 健康分,[0, 100] 或 None
    china_subscore: China 副盤分數,[0, 100] 或 None(無資料)

    Returns
    -------
    dict | None:
      - main_score=None 或 非數值 → None(無主分可乘)
      - 否則 dict 含:
          composite:  float [0,100],套用 modifier 後的分數(若 china=None 則=main)
          main:       float [0,100],主分(已 clip)
          china:      float [0,100] | None,使用的 china 副盤分數(None 表無資料)
          multiplier: float [0.7, 1.0],實際使用的乘子(china=None 時為 1.0,fail-safe)

    §1 fail loud:中國資料缺失時 multiplier=1.0(不懲罰)但欄位明示 china=None,
    caller 從 china==None 即知「modifier 未實際啟用」,UI 可條件渲染。
    """
    if main_score is None:
        return None
    try:
        m = float(main_score)
    except (TypeError, ValueError):
        return None
    # main clip 到 [0,100] 防越界帶來的結果越界
    m_clipped = max(0.0, min(100.0, m))

    if china_subscore is None:
        # Fail-safe:無中國資料 → multiplier=1.0,composite=main
        return {
            "composite": round(m_clipped, 2),
            "main": round(m_clipped, 2),
            "china": None,
            "multiplier": 1.0,
        }
    try:
        c = float(china_subscore)
    except (TypeError, ValueError):
        return None
    # clip china 到 [0, 100] 防越界
    c_clipped = max(0.0, min(100.0, c))
    multiplier = CHINA_MODIFIER_FLOOR + CHINA_MODIFIER_RANGE * (c_clipped / 100.0)
    composite = max(0.0, min(100.0, m_clipped * multiplier))
    return {
        "composite": round(composite, 2),
        "main": round(m_clipped, 2),
        "china": round(c_clipped, 2),
        "multiplier": round(multiplier, 4),
    }


def get_china_snapshot(fred_api_key: str) -> dict:
    """v18.276 L2 一站式 wrapper:抓取 + 組裝 China macro snapshot。

    對稱 Fund v19.118 `services.macro_service.get_china_snapshot`。
    存在意義:讓 L5 UI(tab_macro)用單一 L2 介面取 China 資料,**無需**
    擴充 EX-PASSTHRU-1 例外清單(此前該例外僅含 data_loader / etf_fetch)。
    本函式 thin wrapper,僅串接 L1 tw_macro.fetch_china_macro + 本檔
    china_macro_snapshot,5 行邏輯。

    Args
    ----
    fred_api_key: FRED API key,空字串或 <30 字元 → 回空 dict(AppTest 守衛)

    Returns
    -------
    dict: snapshot 結構同 china_macro_snapshot(),5 key + credit_impulse_proxy;
          fred_api_key 缺時回 {} ,caller 應檢查 truthy 後再 compute_china_subscore。
    """
    if not fred_api_key or len(str(fred_api_key).strip()) < 30:
        return {}
    from src.data.macro import fetch_china_macro  # noqa: PLC0415
    return china_macro_snapshot(fetch_china_macro(fred_api_key))


# ════════════════════════════════════════════════════════════════════════════
# I2（2026-08-10）— `bias_240` 估算旗標的「揭露」SSOT（**只揭露，不改判定**）
#
# 【修的是什麼】`src/data/macro/macro_snapshot.compute_twii_bias` 在 TWII 歷史
# 不足 240 個交易日時，是用「手上全部資料的均值」當 MA240
# （`_cs.tail(min(240, _n)).mean()`），並誠實回傳 `is_estimated=True` + `data_days=N`。
# 但 2026-08-10 盤點：全 repo 讀 `bias_240` 的 10 個消費點裡，**只有
# `src/ui/tabs/macro/section_long.py` 一處**讀那個旗標；其餘（五桶燈號、今日作戰室
# 紅線、中期策略矩陣、個股即時操作建議、以及**兩處實際餵給 Gemini 的 prompt**）
# 拿到的都是裸數字 —— 一個「距 90 日均線的乖離」被當成年線乖離講給人與 LLM 聽。
# 對 LLM 尤其危險：prompt 裡只有數字時，模型沒有任何依據能分辨，只能當實測值寫進建議
# （§1「錯誤的數字比沒有數字更危險」）。
#
# 【本批的範圍限制（§-1）】只做揭露 —— 顯示文字 + prompt 文字。
# **不得**讓 `is_estimated` 影響任何燈號 / 門檻 / 分數 / 桶判定：那是行為變更，
# 需 user 明確指派範圍。故本區塊全部是「產生字串」，**沒有任何一個函式回傳布林
# 以外的判定結果**，也沒有任何 caller 拿它做分支判斷。
#
# 【為何放 L2】本區塊只做純字串組裝（無 I/O、無 streamlit），而消費端橫跨
# L3（`src/services/app_ai_service.py`）與 L5（4 個 macro section + 1 個 stock
# section）。L3 / L5 都能合法下行 import L2（§8.2）；放進其中任一個 L5 檔會立刻
# 變成第 2~6 份逐字複本（§3.3 反捏造：同一句揭露文案不得有兩份真相）。
#
# 【標記語法沿用 G1，不另發明第二套】`[ESTIMATED:...] ` 為**行首**、方括號、
# 結尾一個空格 —— 形狀與 `src/services/ai_structured_summary.py` 的
# `macro_stale_prefix()` / `MACRO_STALE_LEGEND`（`[STALE:67d] `）完全一致，
# 且同樣附一段「圖例」把標記的意思講給 LLM 聽（不解釋 = 等於沒標）。
# ════════════════════════════════════════════════════════════════════════════

#: 「年線」成形所需的交易日數。
#: ⚠️ 這**不是新門檻** —— 它必須與 `macro_snapshot.compute_twii_bias` 的
#: `is_estimated = _n < 240` 是同一個數字。兩邊一致性由
#: `tests/test_i2_bias_estimated_disclosure.py` 以**行為**釘住
#: （239 天 → is_estimated True、240 天 → False），不靠掃描原始碼字面。
BIAS_MA240_FULL_WINDOW_DAYS: int = 240

#: 餵給 LLM 的估算標記圖例。`[ESTIMATED:...]` 對模型不是自明的，不解釋等於沒標。
MACRO_ESTIMATED_LEGEND = (
    '⚠️ 估算標記說明（務必遵守）：行首 `[ESTIMATED:MA<實際>/<名目>]` 代表該指標名稱裡的'
    '均線長度**尚未成形** —— 系統手上的大盤歷史只有 <實際> 個交易日，'
    '所謂「年線（MA240）」實際上是用這 <實際> 日算出來的均線。'
    '這是**估算值**：只能敘述成「以目前僅有的 <實際> 日均線估算」，'
    '**不得**當成真正的年線乖離率陳述、不得據此判斷長期位階或多空循環位置，'
    '也不得拿它推論「站上／跌破年線」。'
    '沒有標記的行才是足額 240 個交易日的真實年線。'
)


def bias_is_estimated(bias_info) -> bool:
    """`bias_info['bias_240']` 是否為「資料不足 240 天」下的估算值。

    §1：旗標缺席 → `False`。理由：唯一的 producer（`compute_twii_bias`）**一定**
    會帶這個 key，缺席代表這份 dict 不是它產的（例：測試 fixture、舊快照），
    此時**不猜、不反推**（不從 `data_days` 倒推，那會變成第二套判定）。

    Parameters
    ----------
    bias_info : dict | None
        `st.session_state['bias_info']` 或 `compute_twii_bias()` 的回傳。
    """
    if not isinstance(bias_info, dict):
        return False
    return bool(bias_info.get('is_estimated'))


def bias_data_days(bias_info):
    """估算時實際用了幾個交易日；取不到 → `None`。

    §1：取不到時回 `None` 而**不是 0** —— 0 會被下游格式化成「0 天資料」，
    那是一個具體但假的讀數。
    """
    if not isinstance(bias_info, dict):
        return None
    try:
        _d = int(bias_info['data_days'])
    except (KeyError, TypeError, ValueError):
        return None
    return _d if _d > 0 else None


def bias_estimated_badge(bias_info) -> str:
    """畫面用短徽章：估算 → `'（估算）'`；否則 `''`（可直接串在數字/標題後）。"""
    return '（估算）' if bias_is_estimated(bias_info) else ''


def bias_estimated_note(bias_info) -> str:
    """畫面用完整揭露句（`st.caption` 等）；非估算 → `''`。

    刻意把「判定沒有跟著調整」也講出來：本批只揭露不改判定，若只寫「這是估算」
    而不寫「燈號仍照它判」，使用者會誤以為系統已經對估算值做了特別處理。
    """
    if not bias_is_estimated(bias_info):
        return ''
    _d = bias_data_days(bias_info)
    if _d is not None:
        _head = (f'目前只有 {_d} 個交易日的大盤歷史，'
                 f'而年線需要 {BIAS_MA240_FULL_WINDOW_DAYS} 個交易日')
    else:
        # §1:天數缺席時不得填 0（那是一個具體但假的讀數），照實說「不明」。
        _head = (f'系統手上的大盤歷史天數不明（有標估算、但沒帶 data_days），'
                 f'總之未達年線所需的 {BIAS_MA240_FULL_WINDOW_DAYS} 個交易日')
    return (f'⚠️ 年線乖離是**估算值**：{_head} —— '
            '畫面上的「MA240／年線」實際是用手上這些天數算出來的均線，'
            '不是真正的年線位階。'
            '（目前燈號與門檻仍直接套用這個估算值判定，尚未針對估算另設規則。）')


def bias_estimated_prompt_prefix(bias_info) -> str:
    """LLM prompt 的行首估算標記：`'[ESTIMATED:MA90/240] '`；非估算 → `''`。

    形狀對齊 `ai_structured_summary.macro_stale_prefix()` 的 `'[STALE:67d] '`
    （行首、方括號、結尾一個空格，可直接串在指標名稱前），不另發明第二套語法。
    天數不明時實際天數寫 `?`（§1：不留白、不假裝知道）。
    """
    if not bias_is_estimated(bias_info):
        return ''
    _d = bias_data_days(bias_info)
    _actual = str(_d) if _d is not None else '?'
    return f'[ESTIMATED:MA{_actual}/{BIAS_MA240_FULL_WINDOW_DAYS}] '


def macro_estimated_legend(context_text: str) -> str:
    """`context_text` 內含任何 `[ESTIMATED:` → 回圖例；否則 `''`。

    判斷方式與 `ai_structured_summary.macro_stale_legend()` 一致（子字串偵測）：
    沒有任何估算行時不加圖例 —— 免得 LLM 因為「有人跟我解釋過估算」而腦補出
    根本不存在的估算值。
    """
    return MACRO_ESTIMATED_LEGEND if '[ESTIMATED:' in (context_text or '') else ''


# ════════════════════════════════════════════════════════════════
# v18.284 — 總經五桶總結（長期/中期/短線急殺/籌碼/新聞）純函式
#   閾值全讀 shared.macro_buckets SSOT；本函式只負責「取值 → 分級 → 聚合」。
# ════════════════════════════════════════════════════════════════
def compute_five_bucket_summary(
    macro_info: Optional[dict] = None,
    mkt_info: Optional[dict] = None,
    warroom_summary: Optional[dict] = None,
    m1b_m2_info: Optional[dict] = None,
    bias_info: Optional[dict] = None,
    cl_data: Optional[dict] = None,
    li_latest: Any = None,
    jingqi_info: Optional[dict] = None,
    news_items: Optional[list] = None,
    *,
    readiness_out: Optional[dict] = None,
) -> dict:
    """總經五桶總結純函式。

    吃各 session_state 片段 → 回五桶 summary，每桶含燈號 + headline + 指標明細。
    門檻全部讀 `shared.macro_buckets.BUCKET_DANGER_SPECS`（SSOT），**不在此 inline**。

    Returns
    -------
    dict: {bucket: {level, label, headline, color, emoji, details:[...]}}，
          bucket ∈ long/mid/short/chips/news。

    §1 Fail Loud：缺值 → 該指標 gray（未載入），桶全 gray → ⬜，**不**偽綠。
    §4.1：foreign_net 因 inst net 單位待確認，v1 暫不接（保持 gray 不誤判）。

    v19.175 P0-B（**行為變更**）：`us10y` / `dxy` 兩條 spec 自 v18.286 註冊起
    就沒有對應取值（values dict 無此 key）→ 永久 ⬜ gray。本版接上
    macro_info['us10y'] / cl_data['intl'] 兩條真實來源，並依 §3.2 加合理範圍
    守衛。副作用：**「中期」桶從 4 盞燈變 6 盞**，桶燈號取 worst-of 可能改變
    （詳見 tests/test_p0b_spec_wiring.py 與 PR 說明的線上實測值代入結果）。
    """
    # v19.172：BUCKET_LEVEL_LABEL 改由 bucket_level_label() 取用(紅燈依觸發方向
    #   分流過熱 / 惡化)；danger_exceedance 用來在同桶多盞同色燈時挑主因。
    # v19.175：us10y / dxy 接線 → 需 CL_INTL_KEY_* 鏡像 key 與 within_valid_range。
    from shared.macro_buckets import (
    BUCKET_DANGER_SPECS,
    MISSING_NOT_LOADED, MISSING_NO_VALUE, MISSING_OUT_OF_RANGE,
    MISSING_NOT_WIRED, MISSING_NO_EXTRACTION,
        BUCKET_ORDER, LEVEL_COLOR, LEVEL_EMOJI, SPECS_BY_KEY,
        CL_INTL_KEY_DXY, CL_INTL_KEY_US10Y,
        specs_for_bucket, classify_danger, aggregate_level, fmt_value,
        bucket_level_label, danger_exceedance, within_valid_range,
    )

    macro_info = macro_info or {}

    def _g(d, *keys):
        cur = d
        for k in keys:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        return cur

    def _num(x):
        if x is None:
            return None
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    def _df_last(df, col):
        """DataFrame 末列某欄 → float / None。"""
        try:
            if (df is not None and hasattr(df, "empty") and not df.empty
                    and col in df.columns):
                return float(df[col].iloc[-1])
        except Exception:
            return None
        return None

    # ── v19.175 P0-B：us10y / dxy 取值 helper ────────────────────────
    # 【修的是什麼】這兩條在 macro_buckets 早於 v18.286 就註冊了 DangerSpec，
    #   但 values dict **從來沒有這兩個 key** → `values.get(s.key)` 恆為 None
    #   → classify_danger(None) → **永久 ⬜ gray**，與當日資料無關。
    #   實機證據:五桶明細印「⬜ 10Y 公債殖利率：—」，同一頁國際指標卡卻印
    #   「10Y公債殖利率 4.63 %」、總經警示印「🟢 DXY 美元指數 99.75」。
    #
    # 【資料來源與量綱】(§2.1 5-Tier + §4.1 量綱陷阱)
    #   us10y: ① T1 FRED DGS10 —— macro_info['us10y']['current']
    #             (macro_snapshot.fetch_us10y_block，單位=百分點，如 4.63)
    #          ② T2 Yahoo ^TNX —— cl_data['intl']['10Y公債殖利率'] 收盤價
    #             (daily_data_fetchers.fetch_single，欄位已 lower-case 為 'close')
    #          **T1 優先、取第一個命中，不平均**(同 §2.1 PMI 多源賽跑規則)。
    #   dxy:   僅 T2 Yahoo DX-Y.NYB —— cl_data['intl']['美元指數 DXY'] 收盤價。
    #          (macro_info 無 dxy 區塊；macro_alert 的 ma_snap['dxy'] 不在本函式
    #           入參內，硬要接需改兩個 L5 caller 的簽章 → 不在本次範圍。)
    #
    # 【為何一定要配 §3.2 範圍檢查】fetch_single 對 'DX-Y.NYB' 有備援鏈
    #   DX-Y.NYB → DX=F → **UUP**(ETF ~27 美元)。落到 UUP 時欄位名不變但尺度差
    #   4 倍，27 < 105 會判成「🟢 綠」= **假綠**(§1:錯的數字比沒有數字更危險)。
    #   同理 ^TNX 若改回「殖利率×10」慣例(46.3)會判成「🔴 紅」= 假紅。
    #   → 越界一律回 None(gray) + log，**絕不**自行乘除 10 去猜尺度。
    def _intl_close(name):
        """cl_data['intl'][name] 末列收盤價。欄名對齊 calc_stats 的 close/Close 解析。"""
        _df_intl = _g(cl_data, "intl", name)
        for _col in ("close", "Close"):
            _v_intl = _df_last(_df_intl, _col)
            if _v_intl is not None:
                return _v_intl
        return None

    _SENTINEL = object()   # 「沒傳 container」與「傳了 None」要分得開

    # ── readiness 側車(2026-08-20)──────────────────────────────────────
    # 設計選擇:side-car out-param 而非改回傳型別。既有 3 個 caller 傳 None
    # 行為零變化(同 Fund repo `calculate_composite_score(provenance_out=)` 先例)。
    _rd: dict = readiness_out if isinstance(readiness_out, dict) else {}

    def _rec(key, *, state, reason=None, hit=None, candidates=None, rejected=None):
        """記一盞燈的取值結果。**恆為 16 筆** —— 缺席也要有紀錄,否則就是隱形。"""
        _sp = SPECS_BY_KEY.get(key)
        # 2026-08-25:鑑別力旗標與 `wired` 同層 —— 兩者都是「別信這盞燈」,
        # 但 wired=False 是「沒值」、discriminative=False 是「有值但門檻失效」。
        # ⚠️ 刻意**不**排除出分母:這盞燈是真的會亮,只是判讀沒意義。
        _disc = bool(getattr(_sp, "discriminative", True))
        if _sp is not None and not _disc and not getattr(_sp, "degraded_reason", ""):
            print(f"[五桶/{key}] ⚠️ 標記 discriminative=False 但沒填 degraded_reason")
        _rd[key] = {
            "key": key,
            "label": getattr(_sp, "label", key),
            "bucket": getattr(_sp, "bucket", ""),
            "wired": bool(getattr(_sp, "wired", True)),
            "discriminative": _disc,
            "state": state,               # ok | missing
            "reason": reason,             # MISSING_* (state=missing 時)
            "hit_source": hit,            # 命中的那一源;None = 全敗
            "candidates": list(candidates or []),
            "rejected": list(rejected or []),
        }

    def _traced(key, label, raw, container=_SENTINEL):
        """單源取值 + 記錄。等價於原本的 `_num(raw)`(單源、無 valid range 時)。

        `container`:該值所在的 session 容器。用來分辨兩種**處置完全不同**的缺值:
          - 容器不在/空  → `not_loaded`,按「🚀 一鍵更新全部數據」就會好
          - 容器在、值空 → `no_value`,上游該源失敗,要去看 API 根因診斷
        不傳 container 時退回 `no_value`(保守:不宣稱「按更新就好」)。
        """
        _v = _first_sane(key, (label, raw))
        if _v is None and container is not _SENTINEL and not container:
            _r = _rd.get(key)
            if _r is not None and _r.get("reason") == MISSING_NO_VALUE:
                _r["reason"] = MISSING_NOT_LOADED
        return _v

    def _unwired(key):
        """決策端刻意未接線 —— 不是失敗,不計入分母。"""
        _sp = SPECS_BY_KEY.get(key)
        _rec(key, state="missing", reason=MISSING_NOT_WIRED,
             hit=None, candidates=[], rejected=[])
        if _sp is not None and not _sp.unwired_reason:
            print(f"[五桶/{key}] ⚠️ 標記 wired=False 但沒填 unwired_reason")
        return None

    def _first_sane(key, *sources):
        """多源賽跑取第一個「有值且通過 §3.2 合理範圍」者；全不過 → None(gray)。

        sources: (來源標籤, 原始值) tuple 序列，依權威分級由高到低排列。

        2026-08-20:順帶把「試了哪些源、命中哪個、為什麼跳過」記進 `_rd`
        (readiness 側車)。**記錄寫在取值這一行**,不是另一份對照表 ——
        所以「新增一盞燈」與「新增一筆 readiness」在物理上是同一個動作,
        沒有第二份東西可以漂移。
        """
        _spec_fs = SPECS_BY_KEY.get(key)
        _cands = [_lbl for _lbl, _ in sources]
        _rejected: list = []
        for _src_label, _raw in sources:
            _v_fs = _num(_raw)
            if _v_fs is None:
                continue
            if _spec_fs is not None and not within_valid_range(_v_fs, _spec_fs):
                _rejected.append((_src_label, _v_fs,
                                  f"out_of_range[{_spec_fs.valid_min},{_spec_fs.valid_max}]"))
                # §1:出聲不吞。這行 log 就是「上游換標的 / 換慣例」的偵測點。
                print(f"[五桶/{key}] ⚠️ 來源 {_src_label} 值 {_v_fs} 超出合理範圍 "
                      f"[{_spec_fs.valid_min}, {_spec_fs.valid_max}] → 跳過此源(§3.2)。"
                      f"常見主因:上游 fallback 換成不同尺度標的(如 DXY→UUP)"
                      f"或報價慣例改變(如 ^TNX 殖利率×10)。**不猜換算**。")
                continue
            _rec(key, state="ok", hit=_src_label, candidates=_cands, rejected=_rejected)
            return _v_fs
        # 全不過:區分「有值但全被範圍擋下」與「根本沒值」—— 處置完全不同
        _rec(key, state="missing",
             reason=(MISSING_OUT_OF_RANGE if _rejected else MISSING_NO_VALUE),
             hit=None, candidates=_cands, rejected=_rejected)
        return None

    _news_sys = None
    if news_items is not None:
        try:
            _news_sys = float(sum(1 for h in news_items
                                  if isinstance(h, dict) and h.get("is_systemic")))
        except Exception:
            _news_sys = None

    values = {
        "health":        _traced("health", "warroom_summary.health_score (calc_traffic_light)", _g(warroom_summary, "health_score"), warroom_summary),
        "ndc_signal":    _traced("ndc_signal", "macro_info.ndc_signal.score (FinMind TaiwanBusinessIndicator)", _g(macro_info, "ndc_signal", "score"), macro_info),
        "m1b_m2_gap":    _traced("m1b_m2_gap", "m1b_m2_info.gap (CBC ms1 → FRED → IMF → ^TWII proxy)", _g(m1b_m2_info, "gap"), m1b_m2_info),
        "ism_pmi":       _traced("ism_pmi", "macro_info.ism_pmi.value (PMI_SOURCE_REGISTRY 多源賽跑)", _g(macro_info, "ism_pmi", "value"), macro_info),
        "us_core_cpi":   _traced("us_core_cpi", "macro_info.us_core_cpi.yoy (FRED CPILFESL)", _g(macro_info, "us_core_cpi", "yoy"), macro_info),
        "tw_export":     _traced("tw_export", "macro_info.tw_export.yoy (MOF 進出口)", _g(macro_info, "tw_export", "yoy"), macro_info),
        # ⚠️ H2 2026-08 揭露 → I2 2026-08-10 接線（**判定仍不變**）：
        #   `bias_info` 由 `src/data/macro/macro_snapshot.compute_twii_bias` 產生，
        #   它在 TWII 歷史 < 240 天時**用現有天數的均值當 MA240**
        #   （`_cs.tail(min(240, _n)).mean()`），並回傳 `data_days` + `is_estimated=True`。
        #   也就是說 `bias_240` 有可能其實是「距 MA90 的乖離」。
        #   H2 當時：全 repo 只有 `section_long.py` 一處顯示該旗標，其餘消費點靜默丟掉。
        #   I2 已補上揭露 —— 但**只補在顯示字串與 prompt 文字**（見下方 `_bias_badge`
        #   與各 caller），本行取值一字未改：`values["bias_240"]` 仍是原始數值，
        #   `classify_danger` / `aggregate_level` 逐位不變。
        #   → 若改成「is_estimated 時回 None」會**改變五桶燈號**（行為變更），
        #     依 §-1 需 user 指派才動；本批明確不做（見 PR 說明的「若要改判定」清單）。
        "bias_240":      _traced("bias_240", "bias_info.bias_240 (compute_twii_bias ← ^TWII)", _g(bias_info, "bias_240"), bias_info),
        # v19.175 P0-B:接線(原本 values 完全沒有這兩個 key → 永久 gray)。
        # 單位皆與 spec 門檻同刻度:us10y=百分點(4.5/5.0)、dxy=指數點(105/110)。
        "us10y":         _first_sane(
            "us10y",
            ("FRED:DGS10(macro_info)", _g(macro_info, "us10y", "current")),
            ("FRED:DGS10(macro_info.value)", _g(macro_info, "us10y", "value")),
            ("Yahoo:^TNX(cl_data.intl)", _intl_close(CL_INTL_KEY_US10Y)),
        ),
        "dxy":           _first_sane(
            "dxy",
            ("Yahoo:DX-Y.NYB(cl_data.intl)", _intl_close(CL_INTL_KEY_DXY)),
        ),
        "vix":           _traced("vix", "macro_info.vix.current (Yahoo ^VIX → FRED VIXCLS)", _g(macro_info, "vix", "current"), macro_info),
        "adl":           _traced("adl", "cl_data.adl[ad_ratio] (fetch_adl ← ^TWII 估算)", _df_last(_g(cl_data, "adl"), "ad_ratio"), cl_data),
        "fut_net":       _traced("fut_net", "li_latest[外資大小] (FinMind 期貨 + TAIFEX)", _df_last(li_latest, "外資大小"), li_latest),
        "margin":        _traced("margin", "cl_data.margin (TWSE → HiStock → Wearn)", _g(cl_data, "margin"), cl_data),
        "jingqi":        _traced("jingqi", "jingqi_info.avg (ad_ratio 5 日均)", _g(jingqi_info, "avg"), jingqi_info),
        # §4.1 inst net 單位待確認 → 故意回 None(§1 fail-safe:寧缺勿錯)。
        # v18.436 #20:此為「外部資訊阻斷」項,非程式 bug。啟用前置條件:
        #   確認 FinMind TaiwanStockInstitutionalInvestorsBuySell 的 buy/sell 單位
        #   (股 vs 千股 vs 億元)→ 才能對齊 spec 門檻判讀。在確認前 None 是正解,
        #   不可猜單位填值(會誤判紅綠燈)。ForeignFlowSchema(71b310c)已備 schema。
        "foreign_net":   _unwired("foreign_net"),
        "news_systemic": _traced("news_systemic", "_macro_news_items (RSS 系統性風險掃描)", _news_sys, news_items),
    }

    # ── no_extraction 掃描(2026-08-20)──────────────────────────────────
    # spec 註冊在 BUCKET_DANGER_SPECS、但上面的 values dict 根本沒有它 ⇒
    # 這盞燈永遠是灰的,而**沒有任何生產端能回報這種病** —— 上游可能一直抓得
    # 好好的。實例:`us10y` 自 v18.286 註冊、v19.175 才接線,中間 4 個版本
    # 永久灰燈,而 `fetch_us10y_block` 全程成功。
    # 這裡把它從「靜靜的灰」變成具名的程式 bug;
    # `tests/test_decision_readiness.py` 有 CI 守衛。
    for _sp_all in BUCKET_DANGER_SPECS:
        if _sp_all.key not in _rd:
            _rec(_sp_all.key, state="missing", reason=MISSING_NO_EXTRACTION)
            print(f"[五桶/{_sp_all.key}] 🐛 spec 已註冊但 values 沒有取值 → 永久灰燈")

    # I2：`bias_240` 為估算值時，只在**顯示字串**後綴徽章（「+32.7%（估算）」）。
    # `classify_danger` 吃的仍是 `values[...]` 原始數值 → 燈號 / 桶等級 / headline
    # 的主因挑選逐位不變。非估算（或 producer 沒帶旗標）時 badge 為空字串，
    # 輸出與本次改動前**逐字元相同**。
    _bias_badge = bias_estimated_badge(bias_info)

    out: dict = {}
    for bucket in BUCKET_ORDER:
        details = []
        for s in specs_for_bucket(bucket):
            v = values.get(s.key)
            _value_str = fmt_value(v, s)
            if s.key == "bias_240" and v is not None and _bias_badge:
                # v is None 時 fmt_value 已回「—」，再貼「（估算）」只會變成
                # 「—（估算）」這種沒有意義的組合 → 只在真有數字時貼。
                _value_str = f"{_value_str}{_bias_badge}"
            details.append({
                "key": s.key, "label": s.label,
                "value_str": _value_str,
                "danger": classify_danger(v, s), "note": s.note,
            })
        blevel = aggregate_level([d["danger"] for d in details])
        d0 = None
        if blevel == "gray":
            headline = "尚未載入（按更新 / 執行 AI 裁決）"
        elif blevel == "green":
            _n_ok = sum(1 for d in details if d["danger"] == "green")
            headline = f"{_n_ok} 項指標全綠"
        else:
            # v19.172：原本 `next(...)` 取「註冊順序第一個同色燈」當主因，
            #   註冊順序純屬歷史，同桶多盞紅時顯示的常不是最嚴重那盞，
            #   而它同時決定下方標籤的方向 → 一起收斂。
            #   改取「超標幅度」最大者（以黃→紅帶寬為單位，見 danger_exceedance
            #   docstring 說明為何不用倍數）。幅度平手時 max() 保留先出現者，
            #   完全退回原註冊順序，行為不退步。
            _hits = [d for d in details if d["danger"] == blevel]
            d0 = max(_hits, key=lambda d: danger_exceedance(
                values.get(d["key"]), SPECS_BY_KEY[d["key"]], blevel))
            headline = f"{d0['label']} {d0['value_str']}｜{d0['note']}"
        out[bucket] = {
            "level": blevel,
            # v19.172：紅燈標籤依「觸發該桶紅燈的 spec 方向」分流
            #   （high_bad → 結構/循環過熱；low_bad → 結構防禦/循環惡化），
            #   修實機「🔴 循環惡化」配同頁「主升段狂熱…順勢作多」的自相矛盾。
            "label": bucket_level_label(
                bucket, blevel,
                spec=SPECS_BY_KEY[d0["key"]] if d0 is not None else None,
                value=values.get(d0["key"]) if d0 is not None else None,
            ),
            "headline": headline,
            "color": LEVEL_COLOR[blevel],
            "emoji": LEVEL_EMOJI[blevel],
            "details": details,
        }
    return out


# ════════════════════════════════════════════════════════════════════════════
# v19.173 — 拐點訊號「分群 + 分母」聚合（修「4 個空頭訊號」誇大確信度）
#
# 【問題一：共線性 —— 把同一個因子數成好幾個獨立證據】
# 舊寫法是 `sum(1 for ... if color == TRAFFIC_RED)`，等於假設每盞紅燈都是
# **一份獨立證據**。實際上拐點面板的訊號高度相關：
#   - 「年線乖離過大 / 外資期貨大量空單 / 散戶極度看多」本質是同一個
#     「多頭末端擁擠度」因子的三種量測；
#   - 「景氣對策連 2 月翻空 / 領先指標 6M 由正轉負」同屬國發會**同一份資料集**
#     （領先指標本身就是景氣對策信號的構成項之一），幾乎必然同號。
#
# 等相關（equicorrelated）近似下的有效獨立訊號數：
#
#       n_eff = n / ( 1 + (n − 1) · ρ̄ )
#
#   （推導：n 個單位變異數、兩兩相關 ρ̄ 的訊號，其和的變異數為
#     Var(Σ) = n + n(n−1)ρ̄；若改用 n_eff 個**獨立**訊號要有同樣的
#     「平均訊號」精度，需 n_eff = n²/Var(Σ) = n / (1 + (n−1)ρ̄)。）
#
#   代 n = 4、ρ̄ = 0.7 →  n_eff = 4 / (1 + 3×0.7) = 4 / 3.1 ≈ 1.29
#   也就是「4 個空頭訊號」實際只值 ~1.3 個獨立訊號，確信度被誇大約 3 倍。
#
#   ⚠️ 誠實揭露：ρ̄ = 0.7 是**量級假設**，不是本專案實測值（要實測需要各訊號
#   的歷史觸發序列，目前沒有落地）。因此本模組**不把 n_eff 當數字印到畫面**
#   （§3.3 反捏造），只用它說明「為什麼要分群」。真正落地的是下面的分群規則。
#
# 【問題二：對資訊集非單調 —— 少抓到一個來源，結論反而反轉】
# 舊門檻 `_bear_pts >= 2` 是**絕對計數、沒有分母**。面向 6 需 FinMind token、
# 面向 7 需 CPI + Fed，任一 fetch 失敗 → 可評估訊號數下降 →
# 同一個市場可能從「🔴 4 個空頭」變成「⚪ 訊號分歧」。使用者只會看到
# 「昨天紅燈、今天變白燈」而找不到原因。
# 這與 `src/services/allocation_service.py:178-212`（v19.170 修好的三環第一環）
# 是同一類 bug，本次把該處的處理原則推廣過來：
#   **未知 ≠ 不利，也 ≠ 有利** —— 資料拿不到的群從分母剔除並標「未評估」，
#   不計入偏多也不計入偏空，且**分母一定顯示給使用者看**。
#
# 【落地規則】
#   1. 每個訊號歸入一個 family（同一個潛在因子 → 同一群）。
#   2. 群內**取最壞、不累加**：只要有一盞空 → 該群 = 偏空（一群最多算一次）。
#   3. 顯示改為「N 群中 M 群偏空（可評估 K/N 群）」，比例 + 分母同時揭露。
# ════════════════════════════════════════════════════════════════════════════

#: 拐點訊號分群（key, 顯示名）。分群原則：**同一個潛在因子放同一群**。
#: 順序即 UI 顯示順序，與 section_state.py 面板 1~7 的敘事順序對齊。
PIVOT_FAMILIES: tuple[tuple[str, str], ...] = (
    ('trend',     '趨勢（均線結構）'),
    ('level',     '位階（乖離率）'),
    ('liquidity', '資金（M1B-M2 / 台幣）'),
    ('chips',     '籌碼（外資期貨 / 韭菜 / 外資連續）'),
    ('cycle',     '景氣（NDC 對策 / 領先指標）'),
    ('inflation', '通膨利率（CPI × Fed）'),
)

#: family key → 顯示名
PIVOT_FAMILY_NAME: dict = dict(PIVOT_FAMILIES)

#: 訊號 label → family key（SSOT）。
#: label 必須與 `section_state.py` 的 `pivot_signals.append((label, ...))` 逐字一致；
#: 對不上的 label 會被歸入回傳值的 `unknown_labels`（**不靜默吞掉**，§1）。
PIVOT_FAMILY_OF: dict = {
    # 1. 均線方向（同一條指數的多條均線，彼此相關極高）
    '均線多頭確認': 'trend',
    '均線初步翻多': 'trend',
    '均線空頭確認': 'trend',
    '整理區間':     'trend',
    # 2. 乖離率（年線 / 月線同為「離均線多遠」的量測）
    '年線乖離過大': 'level',
    '年線深度低估': 'level',
    '月線過熱':     'level',
    '月線超賣':     'level',
    # 3. 資金面（M1B-M2 與台幣同屬「錢往哪流」）
    'M1B>M2 黃金交叉': 'liquidity',
    'M1B<M2 死亡交叉': 'liquidity',
    '台幣升值':        'liquidity',
    '台幣貶值':        'liquidity',
    # 4. 籌碼（外資期貨 / 韭菜 / 外資現貨連續 —— 都是「外資 vs 散戶」同一齣戲）
    '外資期貨大量空單':   'chips',
    '外資空單縮減':       'chips',
    '外資期貨多方':       'chips',
    '散戶極度看多（危險）': 'chips',
    '散戶極度悲觀（機會）': 'chips',
    '外資由連賣轉買':     'chips',
    '外資由連買轉賣':     'chips',
    '外資連續買超':       'chips',
    '外資連續賣超':       'chips',
    # 5. 景氣（NDC 景氣對策信號與領先指標同屬國發會**同一資料集**，必然同號）
    '景氣對策連2月翻多':   'cycle',
    '景氣對策連2月翻空':   'cycle',
    '景氣對策連3月上升':   'cycle',
    '景氣對策連3月下降':   'cycle',
    '領先指標 6M 由負轉正': 'cycle',
    '領先指標 6M 由正轉負': 'cycle',
    '領先指標持續擴張':     'cycle',
    '領先指標持續收縮':     'cycle',
    # 6. 通膨利率（CPI×Fed 雙頂回落，v19.173 正名前為「MK 黃金拐點」）
    'CPI×Fed 雙頂回落 ⭐': 'inflation',
    'CPI×Fed 回落觀察中':  'inflation',
}

#: 判定方向所需的最少「群」數。
#: 新舊等價性推導（為何仍是 2）：
#:   舊規則 `_bear_pts >= 2` 的單位是「**訊號**」，新規則的單位是「**群**」。
#:   - 兩訊號**分屬不同群** → 新舊同時成立，**行為完全等價**。
#:   - 兩訊號**擠在同一群**（如「外資期貨大量空單」+「散戶極度看多」都在籌碼群）
#:     → 舊規則成立、新規則不成立。這正是共線性修正要擋掉的誤判：
#:       同一個因子的兩種量測不構成兩份獨立證據。
#:   故常數值不動（2），只改單位；沒有引入新的魔術數字。
PIVOT_MIN_SIDE_FAMILIES: int = 2

#: 可評估群數低於此值 → 不宣稱方向（分母太小，比例沒有意義）。
PIVOT_MIN_EVALUABLE_FAMILIES: int = 2


def aggregate_pivot_families(
    pivot_signals: Optional[list] = None,
    evaluable: Any = None,
) -> dict:
    """把拐點訊號依 family 收斂，回「群比例 + 分母」而非「訊號絕對計數」。

    參數
    ----
    pivot_signals : list[tuple[label, icon, color, detail]] | None
        `section_state.py` 累積的訊號清單。形狀不符的元素會被略過。
    evaluable : Iterable[str] | None
        **有資料、有能力判定**的 family key 集合（即使該群這次沒觸發任何訊號）。
        沒被列入且也沒有任何訊號的 family → 標記 'unevaluated'，
        **從分母剔除**、不計入偏多也不計入偏空（§1 誠實揭露 + 資訊單調性）。

    回傳
    ----
    dict::

        {
          'families':    {key: {'name', 'side', 'labels'}},   # side ∈ bull/bear/neutral/unevaluated
          'n_bull' / 'n_bear' / 'n_neutral': int,             # 單位 = 群
          'n_evaluable': int,   # 分母（= bull + bear + neutral）
          'n_total':     int,   # 群總數
          'unevaluated': list[str],      # 未評估群的顯示名
          'unknown_labels': list[str],   # 對不上 PIVOT_FAMILY_OF 的 label
          'verdict':  'bull' | 'bear' | 'mixed' | 'insufficient',
          'headline': str,   # 直接可印的結論句（含分母）
          'color':    str,   # traffic hex
          'note':     str,   # 未評估群的說明（無則空字串）
        }

    判定
    ----
    - 群內取最壞：一群裡只要有一盞 `TRAFFIC_RED` → 該群 = 'bear'（**不累加**）；
      否則有 `TRAFFIC_GREEN` → 'bull'；其餘（黃/灰/無訊號）→ 'neutral'。
    - verdict='bear'  ⟺ n_bear > n_bull 且 n_bear >= PIVOT_MIN_SIDE_FAMILIES
    - verdict='bull'  ⟺ 對稱條件
    - n_evaluable < PIVOT_MIN_EVALUABLE_FAMILIES → 'insufficient'（不宣稱方向）
    - 其餘 → 'mixed'

    ⚠️ 已知落差（v19.173 誠實揭露，本輪**刻意不改**）
    ------------------------------------------------
    `section_state.py` 的「月線過熱 / 月線超賣」用的是 `#da3633` / `#2ea043`，
    **不是** `TRAFFIC_RED` / `TRAFFIC_GREEN`。舊的計數邏輯同樣漏算它們，
    本函式維持一致（嚴格比對 traffic 常數），避免在「正名 + 去共線」這次改動裡
    夾帶一個沒被核准、也無法在此驗證的行為變更。若日後要修，請單獨提案：
    把那兩處色碼改成 traffic SSOT 常數（那是 `section_state.py` 端的修正）。

    效能
    ----
    O(len(pivot_signals))，單次線性掃描，無巢狀迴圈。
    """
    _eval_keys = set()
    if evaluable:
        try:
            _eval_keys = {str(k) for k in evaluable}
        except TypeError:
            _eval_keys = set()

    _fam_side: dict = {}
    _fam_labels: dict = {k: [] for k, _ in PIVOT_FAMILIES}
    unknown_labels: list = []

    for _sig in (pivot_signals or []):
        try:
            _label, _icon, _color, _detail = _sig
        except (TypeError, ValueError):
            # 形狀不符（非 4-tuple）→ 略過但不吞：計入 unknown_labels 供診斷
            unknown_labels.append(repr(_sig)[:40])
            continue
        _fam = PIVOT_FAMILY_OF.get(str(_label))
        if _fam is None:
            unknown_labels.append(str(_label))
            continue
        _fam_labels[_fam].append(str(_label))
        if _color == TRAFFIC_RED:
            _fam_side[_fam] = 'bear'          # 取最壞：空一旦成立就不被多蓋掉
        elif _color == TRAFFIC_GREEN:
            if _fam_side.get(_fam) != 'bear':
                _fam_side[_fam] = 'bull'
        else:
            _fam_side.setdefault(_fam, 'neutral')

    families: dict = {}
    n_bull = n_bear = n_neutral = 0
    unevaluated: list = []
    for _key, _name in PIVOT_FAMILIES:
        _has_signal = bool(_fam_labels[_key])
        # 有訊號 ⇒ 必定可評估（防呼叫端漏登記）；否則看 evaluable 名單
        if not (_has_signal or _key in _eval_keys):
            _side = 'unevaluated'
            unevaluated.append(_name)
        else:
            _side = _fam_side.get(_key, 'neutral')
            if _side == 'bull':
                n_bull += 1
            elif _side == 'bear':
                n_bear += 1
            else:
                n_neutral += 1
        families[_key] = {'name': _name, 'side': _side, 'labels': _fam_labels[_key]}

    n_total = len(PIVOT_FAMILIES)
    n_evaluable = n_bull + n_bear + n_neutral

    if n_evaluable < PIVOT_MIN_EVALUABLE_FAMILIES:
        verdict, color = 'insufficient', TRAFFIC_YELLOW
        headline = (f'⚪ 拐點資料不足：{n_total} 群僅 {n_evaluable} 群可評估 '
                    f'→ 不宣稱方向')
    elif n_bull > n_bear and n_bull >= PIVOT_MIN_SIDE_FAMILIES:
        verdict, color = 'bull', TRAFFIC_GREEN
        headline = (f'🟢 綜合拐點：{n_total} 群中 {n_bull} 群偏多'
                    f'（可評估 {n_evaluable}/{n_total} 群）→ 偏向底部起漲')
    elif n_bear > n_bull and n_bear >= PIVOT_MIN_SIDE_FAMILIES:
        verdict, color = 'bear', TRAFFIC_RED
        headline = (f'🔴 綜合拐點：{n_total} 群中 {n_bear} 群偏空'
                    f'（可評估 {n_evaluable}/{n_total} 群）→ 偏向頂部起跌')
    else:
        verdict, color = 'mixed', TRAFFIC_YELLOW
        headline = (f'⚪ 訊號分歧：偏多 {n_bull} 群 vs 偏空 {n_bear} 群'
                    f'（可評估 {n_evaluable}/{n_total} 群），方向待確認')

    note = ''
    if unevaluated:
        note = ('⚠️ 未評估：' + '、'.join(unevaluated)
                + '（資料未取得 → 已排除於分母外，既不計入偏多也不計入偏空）')

    return {
        'families': families,
        'n_bull': n_bull,
        'n_bear': n_bear,
        'n_neutral': n_neutral,
        'n_evaluable': n_evaluable,
        'n_total': n_total,
        'unevaluated': unevaluated,
        'unknown_labels': unknown_labels,
        'verdict': verdict,
        'headline': headline,
        'color': color,
        'note': note,
    }
