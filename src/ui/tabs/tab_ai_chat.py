#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tab_ai_chat.py — AI 分析師 panel + 問答(L5 UI)

提供三個可直接嵌入的元件:
  render_tab_summary(tab_key, bundle)  — 每個 Tab 放一顆「🧬 AI 總結本頁」按鈕(輕量;Phase 2 逐 tab 接)
  render()                             — 自由問答聊天分頁

守則:權威數字由 bundle/工具結果用 st 元件渲染;AI 敘述帶 🧬 旗標(對齊 EX-AI-1 精神)。
     按鈕觸發 + session_state 快取 → 只在點擊時才呼叫 LLM,避免每次 rerun 重跑燒 token。
     L5 → L3(ai_qa_service),不直呼 L1(§8.2)。
"""
import os

import streamlit as st
from shared.secret_md import scrub_md_mask  # SEC-3：錯誤字串上畫面前先洗（只跳脫遮罩，保留 L3 刻意的 **粗體**）
# SEC-r11（2026-09-28）：問答散文（提問／AI 回答）比照 v2 `page_why`，走 L0 散文版清洗 ——
# 上畫面／寫紀錄用 Markdown 版 `scrub_qa_text`、送 `run_agent` 用純文字版 `scrub_prose_secrets`
# （⛔ 不 import v2 view 模組；兩邊都從 L0 取）。
from shared.secret_md import scrub_qa_text
from shared.secret_scrub import scrub_prose_secrets

try:
    from src.services.ai_qa_service import run_agent, summarize_tab
except Exception:  # pragma: no cover
    from ai_qa_service import run_agent, summarize_tab


# ---- secrets 橋接(L3 service 不 import streamlit,靠 env 讀 token)---------
def _secret(key: str):
    try:
        v = st.secrets.get(key)
        if v:
            return v
    except Exception:
        pass
    return os.environ.get(key)


def _bridge_secrets_to_env():
    for k in ("GEMINI_API_KEY", "FINMIND_TOKEN"):
        v = _secret(k)
        if v:
            os.environ.setdefault(k, v)


# ---- 渲染 -------------------------------------------------------------------
def _render_bundle(bundle: dict):
    """權威數字(來自工具/bundle,非 AI 字串)。"""
    for name, r in (bundle or {}).items():
        with st.expander(f"🔧 {name}", expanded=False):
            if not r.get("ok"):
                st.error(scrub_md_mask(r.get("error", "(缺資料)")))
                continue
            prov = r.get("provenance", {})
            cap = f"來源:{prov.get('source', '?')}　as_of:{prov.get('as_of', '?')}"
            if r.get("_stale_days"):
                cap += f"　⚠️ 過期 {r['_stale_days']} 天"
            st.caption(cap)
            data = r.get("data", {})
            if isinstance(data, dict) and data:
                st.table([{"欄位": k, "值": v} for k, v in data.items()])


def _render_panel(res):
    """渲染 panel 結果(分析師 → 辯論 → 風控 → 報告)。"""
    if not getattr(res, "ok", False):
        st.error(scrub_md_mask(getattr(res, "error", "(失敗)")))
        _render_bundle(getattr(res, "data_bundle", {}))
        return
    _render_bundle(res.data_bundle)                      # 1) 權威數字
    # SEC-r19（2026-10-01）：AI 產出的各段散文（分析師／多空辯論／風控／報告）上畫面前
    # 一律過 `scrub_qa_text`（同 SEC-r11 問答回答）：沒命中規則 → 原字串逐字回傳。
    if res.per_analyst:                                  # 2) 分析師觀點
        with st.expander("🧑‍💼 分析師觀點", expanded=False):
            for v in res.per_analyst:
                st.markdown(f"**{v['role']}**:{scrub_qa_text(v['text'])}")
    if res.debate:                                       # 3) 多空辯論
        with st.expander("⚖️ 多空辯論", expanded=False):
            st.markdown(f"**多方**:{scrub_qa_text(res.debate.get('bull', ''))}")
            st.markdown(f"**空方**:{scrub_qa_text(res.debate.get('bear', ''))}")
            st.markdown(f"**裁判**:{scrub_qa_text(res.debate.get('verdict', ''))}")
    if res.risk_review:                                  # 4) 風控
        st.caption(f"🛡️ 風控(資料完整度 {res.risk_review.get('data_ok', '')}):{scrub_qa_text(res.risk_review.get('text', ''))}")
    st.markdown(f"### 🧬 AI 總結｜使用模型:{res.model}\n\n{scrub_qa_text(res.text)}")   # 5) 報告(帶旗標)


# ---- ① 每個 Tab:AI 總結本頁(Phase 2 逐 tab 接)---------------------------
def render_tab_summary(tab_key: str, bundle: dict, *, context: str = "general",
                       mode: str = "lite", title: str = "🧬 AI 總結本頁"):
    """在任何 tab 底部呼叫。bundle = 該 tab 已載好的資料(挑重點欄位,勿丟整個大 DataFrame)。"""
    _bridge_secrets_to_env()
    key = _secret("GEMINI_API_KEY")
    if not key:
        st.caption("🧬 AI 未啟用(未設定 GEMINI_API_KEY)")
        return
    slot = f"_ai_sum_{tab_key}"
    if st.button(title, key=f"btn_sum_{tab_key}"):
        with st.spinner("分析師討論中…"):
            st.session_state[slot] = summarize_tab(tab_key, bundle=bundle, context=context, mode=mode, api_key=key)
    if st.session_state.get(slot):
        _render_panel(st.session_state[slot])


# ---- ② 個股:一鍵分析師討論(完整管線)------------------------------------
# v19.168 IMPL-C:render_stock_panel(個股「🧬 AI 分析師討論」)已移除。個股頁保留更完整的
# 「🤖 AI 首席顧問總結」(五維:技術+基本+財報+新聞)即可,不需並存兩顆個股 AI 按鈕。
# L3 discuss_stock service 仍保留於 ai_qa_service(有測試、可重用)。


# ---- ③ 自由問答聊天 --------------------------------------------------------
def render():
    st.subheader("🧬 AI 問答")
    st.caption("問任何關於你 dashboard 資料的問題;數字取自後端工具,AI 只負責解讀。")
    _bridge_secrets_to_env()
    key = _secret("GEMINI_API_KEY")
    if not key:
        st.info("AI 問答未啟用:未偵測到 GEMINI_API_KEY(設於 .streamlit/secrets.toml)。dashboard 其他功能不受影響。")
        return

    st.session_state.setdefault("ai_qa_history", [])
    for m in st.session_state.ai_qa_history:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    q = st.chat_input("例如:2330 評分多少?現在大盤多頭嗎?台積電財務健不健康?")
    if not q:                                              # 「這一輪有沒有問」仍以原文判斷
        return
    # SEC-r11(2026-09-28):提問原本以原文上畫面、存進 ai_qa_history、送給 run_agent,下一題又隨
    # history 再送一次 —— 貼進來的金鑰／帳密／家目錄路徑原樣出站。比照 v2 `page_why._render_qa_leaf`:
    # 畫面與紀錄用 Markdown 版(`scrub_qa_text`),送出用純文字版(`scrub_prose_secrets`);
    # 兩支都是散文版(⛔ 不截「為什麼出現 UnicodeDecodeError: …」這種引用解碼錯誤訊息的提問;
    # TomlDecodeError 的訊息會串入設定值,照舊整段截——見 L0 `_CONTENT_BEARING_EXC_PROSE_RE`)。沒命中規則的提問逐字不變。
    _shown_q = scrub_qa_text(q)
    with st.chat_message("user"):
        st.markdown(_shown_q)
    # run_agent 內部會自行把本次 question 當成新的 user turn 接在 history 之後
    #(ai_qa_service.run_agent: contents = _history_to_contents(history) + [question])。
    # 因此傳給 run_agent 的必須是「append 本次問題之前」的歷史快照,否則同一句會送兩次
    #(Gemini 收到連續兩個相同 user turn → 例如輸入「6239」被串成「62396239」)。
    _prior = list(st.session_state.ai_qa_history)          # 快照:不含本次 q
    st.session_state.ai_qa_history.append({"role": "user", "content": _shown_q})

    with st.chat_message("assistant"):
        with st.spinner("查詢中…"):
            res = run_agent(scrub_prose_secrets(q), _prior, api_key=key)  # 傳快照,q 只由 run_agent 接一次
        if res.tool_calls:
            _render_bundle({tc["name"]: tc["result"] for tc in res.tool_calls})
        if res.ok:
            # SEC-r11:AI 回答上畫面、存進紀錄(下一題隨 history 再送)前也洗(L3 只洗錯誤字串)。
            _text = scrub_qa_text((res.text or "").strip())
            # 空文字不可只留一個裸標題(否則畫面出現空的「🧬 AI 解讀」);顯式回報
            body = (f"### 🧬 AI 解讀｜使用模型:{res.model}\n\n{_text}" if _text
                    else "🧬 AI 已完成工具查詢,但未產生文字解讀;請見上方工具結果。")
        else:
            body = f"⚠️ {scrub_md_mask(res.error)}"
        st.markdown(body)
        st.session_state.ai_qa_history.append({"role": "assistant", "content": body})
