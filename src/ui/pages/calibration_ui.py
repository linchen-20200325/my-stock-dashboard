"""src/ui/pages/calibration_ui.py — 紅綠燈系統校準的 Streamlit UI 面板

設計
----
- 嵌入「資料診斷」Tab 末段，預設折疊不污染主視覺。
- 按鈕觸發 → 走 NAS proxy 抓 ^TWII → 跑 `calibrate_macro_traffic`
  → markdown 渲染 + .md 下載。
- 結果暫存 `st.session_state['_calib_report']`，避免 rerun 重跑。
"""
from __future__ import annotations

import datetime as _dt
import streamlit as st


def _show_threshold_status():
    """顯示 macro_thresholds.json 內現行門檻 + 最後校準時間（季度排程寫入）。"""
    import json as _json
    import os as _os
    _path = _os.path.join(_os.path.dirname(__file__), 'macro_thresholds.json')
    if not _os.path.exists(_path):
        return
    try:
        with open(_path, 'r', encoding='utf-8') as _fp:
            _cfg = _json.load(_fp)
    except Exception:
        return
    _h = _cfg.get('HEALTH_DEFENSE_THRESHOLD', 35)
    _s = _cfg.get('BULL_MIN_SCORE', 4)
    _ts = _cfg.get('last_calibrated') or '尚未校準（使用預設）'
    _method = _cfg.get('method', '')
    st.caption(f'🤖 **現行門檻**：HEALTH `<{_h}` 觸發 🔴 防禦、SCORE `≥{_s}` 升 🟢 多頭　'
               f'|　**最後校準**：{_ts}　|　{_method}')


def render_calibration_panel():
    """渲染「🧪 紅綠燈系統校準」面板（折疊）。"""
    with st.expander('🧪 紅綠燈系統校準（進階）', expanded=False):
        st.markdown(
            '對 `macro_helpers.calc_traffic_light` 做歷史回測，'
            '量化每個燈號 🟢🟡🔴 在後 20/60 日 TWII 的真實 precision / recall，'
            '並提出門檻調整建議。')
        st.caption('⚠️ 本工具僅用於系統校準診斷，不影響日常選股 / AI 報告。')

        # v18.143+：顯示季度排程校準狀態（macro_thresholds.json）
        _show_threshold_status()

        _c1, _c2, _c3 = st.columns([1, 1, 1])
        with _c1:
            _range = st.selectbox(
                '回測期間',
                options=['1y', '2y', '5y', 'max'],
                index=1,
                help='抓 ^TWII 的歷史長度。建議 2y 起跳以涵蓋多空循環。')
        with _c2:
            st.markdown('&nbsp;', unsafe_allow_html=True)
            _run = st.button(
                '🚀 執行校準', type='primary', use_container_width=True,
                key='_calib_btn')
        with _c3:
            st.markdown('&nbsp;', unsafe_allow_html=True)
            _clear = st.button(
                '🗑️ 清除結果', use_container_width=True, key='_calib_clear')

        if _clear:
            st.session_state.pop('_calib_report', None)
            st.session_state.pop('_calib_ts', None)
            st.rerun()

        if _run:
            with st.spinner('抓 ^TWII 中（走 NAS proxy）...'):
                try:
                    from scripts.calibrate_macro_traffic import (
                        fetch_twii_ohlcv, run_backtest, compute_metrics,
                        build_report)
                    _df = fetch_twii_ohlcv(_range)
                except ImportError as _e:
                    st.error(f'匯入校準模組失敗：{_e}')
                    return
                except Exception as _e:
                    st.error(f'抓 ^TWII 異常：{type(_e).__name__}: {_e}')
                    return

            if _df is None or _df.empty:
                st.error('❌ 抓不到 ^TWII（NAS proxy 不可達或 Yahoo Chart 失敗）。'
                         '請至「🔎 資料診斷」上方確認 Proxy 與 Yahoo 連線狀態。')
                return

            st.success(f'✅ ^TWII {len(_df)} 筆 '
                       f'({_df.index[0].date()} ~ {_df.index[-1].date()})')

            with st.spinner('逐日重建燈號 + 計算 precision/recall ...'):
                try:
                    _bt = run_backtest(_df)
                    _metrics = compute_metrics(_bt)
                    _report = build_report(
                        _metrics, _df,
                        mode='TWII-only (Streamlit Cloud 真資料)')
                except Exception as _e:
                    st.error(f'回測異常：{type(_e).__name__}: {_e}')
                    return

            _ts = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            st.session_state['_calib_report'] = _report
            st.session_state['_calib_ts'] = _ts
            st.session_state['_calib_metrics_summary'] = {
                'n_total': _metrics['n_total'],
                'green_p': _metrics['green_precision'],
                'red_p': _metrics['red_precision'],
                'green_r': _metrics['green_recall'],
                'red_r': _metrics['red_recall'],
                'corr_20': _metrics['corr_score_ret20'],
                'corr_60': _metrics['corr_score_ret60'],
            }
            st.rerun()

        # ── 渲染結果 ───────────────────────────────────────────────
        _report = st.session_state.get('_calib_report')
        _ts = st.session_state.get('_calib_ts', '')
        if _report:
            _summary = st.session_state.get('_calib_metrics_summary', {})
            if _summary:
                _m1, _m2, _m3, _m4 = st.columns(4)
                _m1.metric('🟢 多頭 precision',
                           f"{_summary.get('green_p', 0):.1f}%",
                           f"recall {_summary.get('green_r', 0):.1f}%")
                _m2.metric('🔴 防禦 precision',
                           f"{_summary.get('red_p', 0):.1f}%",
                           f"recall {_summary.get('red_r', 0):.1f}%")
                _m3.metric('score ↔ ret_20d', f"{_summary.get('corr_20', 0):+.3f}")
                _m4.metric('score ↔ ret_60d', f"{_summary.get('corr_60', 0):+.3f}")
                st.caption(f'回測樣本：{_summary.get("n_total", 0)} 日　|　'
                           f'分析時間：{_ts}')

            st.download_button(
                '📥 下載 MACRO_CALIBRATION.md',
                data=_report.encode('utf-8'),
                file_name=f'MACRO_CALIBRATION_{_ts[:10]}.md',
                mime='text/markdown',
                use_container_width=False)

            st.markdown('---')
            st.markdown(_report)
