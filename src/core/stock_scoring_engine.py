"""
src/core/stock_scoring_engine.py — 股票多因子評分遷移 (P1 Step 1)

將 scoring_engine.py 的 stock_score() 遷移到 UnifiedScoringEngine 框架
保持現有 API 向後相容，同時輸出統一的 ScoringResult
"""

from typing import Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

from src.core.scoring_base import UnifiedScoringEngine, Normalizer, ScoreCalculator
from src.core.scoring_result import ScoringResult, DimensionStatus, ScoringGrade, ScoringGrade

from shared.constants import (
    RSI_OVERBOUGHT, RSI_OVERSOLD,
    MA_SHORT, MA_MID, MA_LONG, MA_ANNUAL
)
from src.core.technical_indicators import calc_rsi


# ============================================================================
# Stock Score 遷移到統一框架
# ============================================================================

class StockScoringEngine(UnifiedScoringEngine):
    """
    台股股票多因子評分引擎 (v3.0) — 統一框架版本
    
    5 維度評分：
    • 趨勢面（30%）— MA5/20/60/120 站上 + 均線多頭排列
    • 動能面（25%）— RSI 區間 + Sharpe-like 波動調整報酬
    • 籌碼面（20%）— 外資/投信/自營買超
    • 量價面（15%）— 量能放大 + 量增價漲
    • 風險面（10%）— 波動率 + RSI 不超買 + 站上 MA60
    
    向後相容：現有 API 保持不變
    """
    
    def __init__(self):
        super().__init__(
            system_name="stock_score",
            score_range=(0.0, 100.0),
            time_scale="daily"
        )
        
        # 維度權重配置（來自 config.py）
        from config import WEIGHT_TREND, WEIGHT_MOMENTUM, WEIGHT_CHIP, WEIGHT_VOLUME, WEIGHT_RISK
        self.weights = {
            'trend': WEIGHT_TREND,
            'momentum': WEIGHT_MOMENTUM,
            'chip': WEIGHT_CHIP,
            'volume': WEIGHT_VOLUME,
            'risk': WEIGHT_RISK,
        }
    
    def calculate(self, target_id: str, **kwargs) -> ScoringResult:
        """
        計算股票評分
        
        Args:
            target_id: 股票代碼（如 '2330'）
            df: OHLCV DataFrame
            foreign_buy: 外資買超 (optional)
            trust_buy: 投信買超 (optional)
            dealer_buy: 自營商買超 (optional)
            regime: 'bull'/'neutral'/'bear' (optional，用於動態權重)
        
        Returns:
            ScoringResult
        """
        df = kwargs.get('df')
        as_of_date = kwargs.get('as_of_date', datetime.now().strftime("%Y-%m-%d"))
        regime = kwargs.get('regime', 'neutral')
        
        result = self._create_base_result(target_id, as_of_date=as_of_date)
        
        # 資料驗證
        if df is None or df.empty or len(df) < 60:
            result.add_error("Insufficient data: require minimum 60 bars")
            return self._finalize_result(result)
        
        close = df['close']
        
        # ── Step 1：趨勢分數 ──────────────────────────────────
        try:
            trend_score = self._calc_trend_score(df)
            self._add_dimension(
                result,
                name='trend',
                value=trend_score,
                weight=self.weights['trend'],
                status=DimensionStatus.AVAILABLE if trend_score is not None else DimensionStatus.MISSING
            )
        except Exception as e:
            result.add_error(f"Trend calculation failed: {str(e)}")
            self._add_dimension(result, 'trend', None, self.weights['trend'], 
                              status=DimensionStatus.MISSING)
        
        # ── Step 2：動能分數 ──────────────────────────────────
        try:
            momentum_score = self._calc_momentum_score(df)
            self._add_dimension(
                result,
                name='momentum',
                value=momentum_score,
                weight=self.weights['momentum'],
                status=DimensionStatus.AVAILABLE if momentum_score is not None else DimensionStatus.MISSING
            )
        except Exception as e:
            result.add_error(f"Momentum calculation failed: {str(e)}")
            self._add_dimension(result, 'momentum', None, self.weights['momentum'],
                              status=DimensionStatus.MISSING)
        
        # ── Step 3：籌碼分數 ──────────────────────────────────
        try:
            foreign_buy = kwargs.get('foreign_buy', 0)
            trust_buy = kwargs.get('trust_buy', 0)
            dealer_buy = kwargs.get('dealer_buy', 0)
            
            chip_score = self._calc_chip_score(df, foreign_buy, trust_buy, dealer_buy)
            self._add_dimension(
                result,
                name='chip',
                value=chip_score,
                weight=self.weights['chip'],
                status=DimensionStatus.AVAILABLE if chip_score is not None else DimensionStatus.MISSING
            )
        except Exception as e:
            result.add_error(f"Chip calculation failed: {str(e)}")
            self._add_dimension(result, 'chip', None, self.weights['chip'],
                              status=DimensionStatus.MISSING)
        
        # ── Step 4：量價分數 ──────────────────────────────────
        try:
            volume_score = self._calc_volume_score(df)
            self._add_dimension(
                result,
                name='volume',
                value=volume_score,
                weight=self.weights['volume'],
                status=DimensionStatus.AVAILABLE if volume_score is not None else DimensionStatus.MISSING
            )
        except Exception as e:
            result.add_error(f"Volume calculation failed: {str(e)}")
            self._add_dimension(result, 'volume', None, self.weights['volume'],
                              status=DimensionStatus.MISSING)
        
        # ── Step 5：風險分數 ──────────────────────────────────
        try:
            risk_score = self._calc_risk_score(df)
            self._add_dimension(
                result,
                name='risk',
                value=risk_score,
                weight=self.weights['risk'],
                status=DimensionStatus.AVAILABLE if risk_score is not None else DimensionStatus.MISSING
            )
        except Exception as e:
            result.add_error(f"Risk calculation failed: {str(e)}")
            self._add_dimension(result, 'risk', None, self.weights['risk'],
                              status=DimensionStatus.MISSING)
        
        # ── 完成計算 ──────────────────────────────────────────
        result = self._finalize_result(result)
        
        # ── 向後相容：記錄原格式 ──────────────────────────────
        result.legacy_format = {
            'stock_id': target_id,
            'score': result.score,
            'grade': result.grade.value if result.grade else None,
            'trend': result.get_dimension_score('trend'),
            'momentum': result.get_dimension_score('momentum'),
            'chip': result.get_dimension_score('chip'),
            'volume': result.get_dimension_score('volume'),
            'risk': result.get_dimension_score('risk'),
        }
        
        return result
    
    # ========================================================================
    # 私有方法：各維度計算
    # ========================================================================
    
    def _calc_trend_score(self, df: pd.DataFrame) -> Optional[float]:
        """趨勢分數（0-100）"""
        if df is None or df.empty or 'close' not in df.columns:
            return 0.0
        
        close = df['close']
        score = 0
        total = 5
        
        # 計算 MA
        for period in [5, 20, 60, 120]:
            col = f'MA{period}'
            if col not in df.columns:
                df[col] = close.rolling(period).mean()
        
        latest = df.iloc[-1]
        c = float(latest['close'])
        
        # 條件1：價格站上各均線
        ma5 = latest.get('MA5', 0) or 0
        ma20 = latest.get('MA20', 0) or 0
        ma60 = latest.get('MA60', 0) or 0
        ma120 = latest.get('MA120', 0) or 0
        
        if ma5 > 0 and c > ma5:
            score += 1
        if ma20 > 0 and c > ma20:
            score += 1
        if ma60 > 0 and c > ma60:
            score += 1
        
        # 條件2：均線多頭排列
        if ma20 > 0 and ma60 > 0 and ma20 > ma60:
            score += 1
        if ma60 > 0 and ma120 > 0 and ma60 > ma120:
            score += 1
        
        return round(score / total * 100, 1)
    
    def _calc_momentum_score(self, df: pd.DataFrame) -> Optional[float]:
        """動能分數（0-100）"""
        if df is None or len(df) < 20:
            return 0.0
        
        close = df['close']
        
        # RSI 評分
        if 'RSI' not in df.columns:
            df['RSI'] = calc_rsi(close)
        
        rsi = df['RSI'].iloc[-1]
        rsi_score = 2 if RSI_OVERSOLD < rsi < RSI_OVERBOUGHT else (1 if rsi <= RSI_OVERSOLD else 0)
        
        # Sharpe-like 動能
        ret20 = (close.iloc[-1] / close.iloc[-20] - 1) if len(close) >= 20 else 0
        sigma20 = close.pct_change().rolling(20).std().iloc[-1] if len(close) >= 20 else 0.01
        sharpe_20 = ret20 / (sigma20 * (20 ** 0.5) + 1e-10)
        sharpe_score = 2 if sharpe_20 > 0.5 else (1 if sharpe_20 > 0 else 0)
        
        # ATR 波動
        if 'ATR' not in df.columns:
            high = df['high']
            low = df['low']
            tr = pd.concat([
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs()
            ], axis=1).max(axis=1)
            df['ATR'] = tr.rolling(14).mean()
        
        atr_ratio = df['ATR'].iloc[-1] / close.iloc[-1] if close.iloc[-1] > 0 else 0
        atr_score = 2 if atr_ratio < 0.02 else (1 if atr_ratio < 0.03 else 0)
        
        total_score = (rsi_score + sharpe_score + atr_score) / 6 * 100
        return round(total_score, 1)
    
    def _calc_chip_score(
        self,
        df: pd.DataFrame,
        foreign_buy: float = 0,
        trust_buy: float = 0,
        dealer_buy: float = 0
    ) -> Optional[float]:
        """籌碼分數（0-100）"""
        # 明確傳入參數優先
        if foreign_buy or trust_buy or dealer_buy:
            score = 0
            if foreign_buy > 0:
                score += 2
            if trust_buy > 0:
                score += 2
            if dealer_buy > 0:
                score += 1
            return round(score / 5 * 100, 1)
        
        # 嘗試從 df 計算
        if df is not None and not df.empty:
            fb_col = next((c for c in ('外資買超', '外資') if c in df.columns), None)
            if fb_col:
                f5d = float(df[fb_col].tail(5).sum())
                raw_score = 2 if f5d > 0 else 0
                return round(raw_score / 5 * 100, 1)
        
        return 50.0  # 中性
    
    def _calc_volume_score(self, df: pd.DataFrame) -> Optional[float]:
        """量價分數（0-100）"""
        if df is None or len(df) < 20:
            return 50.0
        
        close = df['close']
        volume = df['volume']
        vol20 = volume.rolling(20).mean()
        
        score = 0
        total = 3
        
        # 量能放大
        if volume.iloc[-1] > vol20.iloc[-1]:
            score += 1
        
        # 量增價漲
        if len(df) >= 3:
            price_up = close.iloc[-1] > close.iloc[-3]
            vol_up = volume.iloc[-1] > volume.iloc[-3]
            if price_up and vol_up:
                score += 1
        
        # 5D 均量 > 20D 均量
        if volume.tail(5).mean() > vol20.iloc[-1]:
            score += 1
        
        return round(score / total * 100, 1)
    
    def _calc_risk_score(self, df: pd.DataFrame) -> Optional[float]:
        """風險分數（0-100）"""
        if df is None or len(df) < 20:
            return 0.0
        
        close = df['close']
        score = 0
        total = 3
        
        # 波動率分級
        vol_pct = close.pct_change().rolling(20).std().iloc[-1]
        if vol_pct < 0.02:
            score += 1
        elif vol_pct < 0.035:
            score += 1
        
        # RSI 不超買
        if 'RSI' not in df.columns:
            df['RSI'] = calc_rsi(close)
        
        rsi_val = df['RSI'].iloc[-1]
        if not (rsi_val != rsi_val):  # NaN check
            if rsi_val < RSI_OVERBOUGHT:
                score += 1
        
        # 站上 MA60
        if 'MA60' not in df.columns:
            df['MA60'] = close.rolling(60).mean()
        
        ma60_val = df['MA60'].iloc[-1]
        if ma60_val != ma60_val:  # NaN
            score += 0.5
        elif close.iloc[-1] >= ma60_val:
            score += 1
        
        return round(min(score / total * 100, 100), 1)
