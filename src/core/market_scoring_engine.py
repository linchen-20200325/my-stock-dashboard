"""
src/core/market_scoring_engine.py — 市場狀態評分遷移 (P1 Step 3)

將 market_strategy.py 的 market_regime() 遷移到統一框架
"""

from typing import Optional, Dict, Any, Tuple
from datetime import datetime

import pandas as pd
import numpy as np

from src.core.scoring_base import UnifiedScoringEngine, ScoreCalculator
from src.core.scoring_result import ScoringResult, DimensionStatus, ScoringGrade

from config import MARKET_SCORE_BULL, MARKET_SCORE_NEUTRAL


class MarketRegimeEngine(UnifiedScoringEngine):
    """
    市場狀態判斷引擎 (v4.1) — 統一框架版本
    
    判斷大盤 bull/neutral/bear 狀態，計算市場評分
    
    評分維度：
    • MA60 連 3 日確認（Hysteresis）
    • MA120 趨勢與斜率
    • 外資淨買賣方向
    • 市場廣度（A/D ratio）
    • M1B-M2 資金活水
    
    輸出範圍：0-100（映射到 regime label）
    """
    
    def __init__(self):
        super().__init__(
            system_name="market_regime",
            score_range=(0.0, 100.0),
            time_scale="daily"
        )
        
        # 市場評分閾值（來自 config.py）
        self.market_score_bull = MARKET_SCORE_BULL
        self.market_score_neutral = MARKET_SCORE_NEUTRAL
    
    def calculate(self, target_id: str = "TWII", **kwargs) -> ScoringResult:
        """
        計算市場狀態評分
        
        Args:
            target_id: 市場指數代碼（預設 TWII）
            index_close: 指數收盤價
            ma60: 60 日均線
            ma120: 120 日均線
            foreign_buy: 外資淨買賣金額
            ad_ratio: 漲跌家數比
            ma60_prev: 前期 MA60
            ma120_prev: 前期 MA120
            vol_today: 今日成交量
            avg_vol_20: 20 日均量
            m1b_m2_gap: M1B 年增 - M2 年增
            m1b_m2_prev: 上月 gap
            ma60_above_3d: 最近 3 日均站上 MA60
            ma60_below_3d: 最近 3 日均跌破 MA60
            ma120_above_3d: 最近 3 日均站上 MA120
            ma120_below_3d: 最近 3 日均跌破 MA120
            ma120_rising: MA120 向上
            ma120_falling: MA120 向下
            as_of_date: 基準日期
        
        Returns:
            ScoringResult（market regime 判定）
        """
        as_of_date = kwargs.get('as_of_date', datetime.now().strftime("%Y-%m-%d"))
        
        result = self._create_base_result(target_id, as_of_date=as_of_date)
        
        # 提取參數
        index_close = kwargs.get('index_close')
        ma60 = kwargs.get('ma60')
        ma120 = kwargs.get('ma120')
        foreign_buy = kwargs.get('foreign_buy', 0)
        ad_ratio = kwargs.get('ad_ratio', 1.0)
        ma60_prev = kwargs.get('ma60_prev')
        ma120_prev = kwargs.get('ma120_prev')
        vol_today = kwargs.get('vol_today', 0)
        avg_vol_20 = kwargs.get('avg_vol_20', 1)
        m1b_m2_gap = kwargs.get('m1b_m2_gap')
        m1b_m2_prev = kwargs.get('m1b_m2_prev')
        ma60_above_3d = kwargs.get('ma60_above_3d', False)
        ma60_below_3d = kwargs.get('ma60_below_3d', False)
        ma120_above_3d = kwargs.get('ma120_above_3d', False)
        ma120_below_3d = kwargs.get('ma120_below_3d', False)
        ma120_rising = kwargs.get('ma120_rising', False)
        ma120_falling = kwargs.get('ma120_falling', False)
        
        # ── 計算市場評分 ─────────────────────────────────
        score = 0.0
        signals = []
        
        # MA60 確認法則（Hysteresis）
        ma60_score = 0
        if ma60_above_3d:
            score += 1.0
            ma60_score = 1.0
            signals.append("✅ 站上MA60（連3日確認）")
            if ma60_prev and ma60 > ma60_prev:
                score += 0.5
                signals.append("✅ MA60向上彎折（真突破濾網）")
        elif ma60_below_3d:
            ma60_score = -1.0
            signals.append("❌ 跌破MA60（連3日確認）")
            if ma60_prev and ma60 < ma60_prev:
                signals.append("🔴 MA60向下彎折（季線走弱）")
        else:
            signals.append("⚠️ 站上MA60（未滿3日，觀察中）")
        
        # MA120 確認法則
        ma120_score = 0
        if ma120_above_3d:
            score += 1.0
            ma120_score = 1.0
            signals.append("✅ 站上MA120（連3日確認）")
            if ma120_rising:
                score += 0.5
                signals.append("✅ MA120向上彎折（真突破）")
        elif ma120_below_3d:
            ma120_score = -1.0
            signals.append("❌ 跌破MA120（連3日確認）")
            if ma120_falling:
                signals.append("🔴 MA120向下彎折（長期走弱）")
        else:
            signals.append("⚠️ 站上MA120（未滿3日，觀察中）")
        
        # 外資方向
        foreign_score = 0
        if foreign_buy is not None:
            if foreign_buy > 0:
                score += 1.0
                foreign_score = 1.0
                signals.append("✅ 外資買超")
            elif foreign_buy < 0:
                foreign_score = -1.0
                signals.append("❌ 外資賣超")
            else:
                signals.append("➖ 外資無方向")
        
        # 市場廣度
        breadth_score = 0
        if ad_ratio > 1.2:
            score += 1.0
            breadth_score = 1.0
            signals.append("✅ 漲家數>跌家數（市場廣度強）")
        elif ad_ratio < 0.8:
            breadth_score = -1.0
            signals.append("❌ 跌家數>漲家數（市場廣度弱）")
        
        # M1B-M2 資金活水
        m1b_m2_score = 0
        if m1b_m2_gap is not None:
            if m1b_m2_gap > m1b_m2_prev if m1b_m2_prev else m1b_m2_gap > 0:
                score += 0.5
                m1b_m2_score = 0.5
                signals.append("✅ M1B-M2缺口改善（資金活水向上）")
            elif m1b_m2_gap < (m1b_m2_prev if m1b_m2_prev else 0):
                m1b_m2_score = -0.5
                signals.append("❌ M1B-M2缺口惡化（資金流出）")
        
        # ── 添加各維度 ─────────────────────────────────
        self._add_dimension(result, 'ma60_regime', ma60_score * 50 + 50, 0.25)
        self._add_dimension(result, 'ma120_regime', ma120_score * 50 + 50, 0.25)
        self._add_dimension(result, 'foreign_flow', foreign_score * 50 + 50, 0.25)
        self._add_dimension(result, 'market_breadth', breadth_score * 50 + 50, 0.15)
        self._add_dimension(result, 'm1b_m2_gap', m1b_m2_score * 50 + 50, 0.10)
        
        # ── 完成計算 ─────────────────────────────────
        result = self._finalize_result(result)
        
        # ── 判定 regime ─────────────────────────────────
        if result.score is not None:
            if result.score >= self.market_score_bull:
                regime = "bull"
                regime_label = "🚀 強勢"
            elif result.score >= self.market_score_neutral:
                regime = "neutral"
                regime_label = "➖ 中性"
            else:
                regime = "bear"
                regime_label = "🔴 弱勢"
        else:
            regime = "unknown"
            regime_label = "❓ 未知"
        
        # ── 元數據 ─────────────────────────────────
        result.metadata = {
            'regime': regime,
            'regime_label': regime_label,
            'signals': signals,
            'score_components': {
                'ma60': score if ma60_score > 0 else 0,
                'ma120': score if ma120_score > 0 else 0,
                'foreign': foreign_score,
                'breadth': breadth_score,
                'm1b_m2': m1b_m2_score,
            }
        }
        
        # ── 向後相容 ─────────────────────────────────
        result.legacy_format = {
            'market_index': target_id,
            'regime': regime,
            'regime_label': regime_label,
            'score': result.score,
            'signals': signals,
        }
        
        return result
