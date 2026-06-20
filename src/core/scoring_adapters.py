"""
src/core/scoring_adapters.py — 8 個系統適配器包裹 (P1 Step 4)

無需修改原系統代碼，透過 Adapter Pattern 將 legacy 輸出轉換為統一 ScoringResult 格式
"""

from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass

import pandas as pd
import numpy as np

from src.core.scoring_base import UnifiedScoringEngine
from src.core.scoring_result import ScoringResult, DimensionStatus, ScoringGrade


# ============================================================================
# Adapter 1: MJ Trend Score (月+季雙頻率融合評分)
# ============================================================================

class MJTrendAdapter(UnifiedScoringEngine):
    """
    包裹 mj_trend_score.compute_trend_score()
    輸入：月營收 + MJ 季財報
    輸出：統一 ScoringResult [-2, +2] → 0-100 分數
    """
    
    def __init__(self):
        super().__init__(
            system_name="mj_trend",
            score_range=(-2.0, 2.0),
            time_scale="monthly"
        )
    
    def calculate(self, target_id: str, **kwargs) -> ScoringResult:
        """
        Args:
            target_id: 股票代碼
            monthly_revenue_3m: list[dict] - 近3月月營收
            mj_snapshots_3q: list[dict] - 近3季MJ體檢快照
            w_monthly: float - 月營收權重 (default 0.65)
            as_of_date: str - 基準日期
        """
        # 動態導入 avoid circular dependency
        from mj_trend_score import compute_trend_score as legacy_compute_trend_score
        
        as_of_date = kwargs.get('as_of_date', datetime.now().strftime("%Y-%m-%d"))
        monthly_revenue = kwargs.get('monthly_revenue_3m', [])
        mj_snapshots = kwargs.get('mj_snapshots_3q', [])
        w_monthly = kwargs.get('w_monthly', 0.65)
        
        result = self._create_base_result(target_id, as_of_date=as_of_date)
        
        try:
            # 調用原 legacy 函數
            legacy_result = legacy_compute_trend_score(
                monthly_revenue_3m=monthly_revenue,
                mj_snapshots_3q=mj_snapshots,
                w_monthly=w_monthly,
            )
            
            # 提取分數 [-2, +2] 並轉為 0-100
            raw_score = legacy_result.get('score', 0)
            normalized_score = (raw_score + 2.0) / 4.0 * 100  # [-2,2] → [0,100]
            
            # 添加維度
            self._add_dimension(result, 'monthly_subscore', 
                              (legacy_result.get('monthly_subscore', 0) + 2.5) / 5.0 * 100,
                              0.65)
            self._add_dimension(result, 'mj_subscore',
                              (legacy_result.get('mj_subscore', 0) + 2.0) / 4.0 * 100,
                              0.35)
            
            result = self._finalize_result(result)
            
            # 向後相容
            result.legacy_format = legacy_result
            result.metadata = {
                'label': legacy_result.get('label'),
                'label_code': legacy_result.get('label_code'),
            }
            
        except Exception as e:
            result.metadata = {'error': str(e)}
        
        return result


# ============================================================================
# Adapter 2: MJ Health Diff (跨期變化偵測)
# ============================================================================

class MJHealthDiffAdapter(UnifiedScoringEngine):
    """
    包裹 mj_health_diff.diff_mj_health()
    輸入：前期 + 當期 MJ 體檢結果
    輸出：統一 ScoringResult，judgment = improving/deteriorating/stable
    """
    
    def __init__(self):
        super().__init__(
            system_name="mj_health_diff",
            score_range=(0.0, 100.0),
            time_scale="quarterly"
        )
    
    def calculate(self, target_id: str, **kwargs) -> ScoringResult:
        """
        Args:
            target_id: 股票代碼
            prev_health: dict - 上期 analyze_financial_health() 結果
            curr_health: dict - 本期 analyze_financial_health() 結果
            min_net_delta: int - 淨變化門檻 (default 1)
            as_of_date: str - 基準日期
        """
        from mj_health_diff import diff_mj_health as legacy_diff_mj_health
        
        as_of_date = kwargs.get('as_of_date', datetime.now().strftime("%Y-%m-%d"))
        prev_health = kwargs.get('prev_health', {})
        curr_health = kwargs.get('curr_health', {})
        min_net_delta = kwargs.get('min_net_delta', 1)
        
        result = self._create_base_result(target_id, as_of_date=as_of_date)
        
        try:
            # 調用原 legacy 函數
            verdict = legacy_diff_mj_health(
                prev=prev_health,
                curr=curr_health,
                stock_id=target_id,
                min_net_delta=min_net_delta,
            )
            
            # 轉換 verdict 到分數
            verdict_to_score = {
                'improving': 75.0,
                'deteriorating': 25.0,
                'mixed': 50.0,
                'stable': 50.0,
            }
            score = verdict_to_score.get(verdict.verdict, 50.0)
            
            # 添加維度
            improve_count = len(verdict.improvements)
            deteriorate_count = len(verdict.deteriorations)
            
            self._add_dimension(result, 'improvements', 
                              min(100.0, improve_count * 10),
                              0.5)
            self._add_dimension(result, 'deteriorations',
                              100.0 - min(100.0, deteriorate_count * 10),
                              0.5)
            
            result = self._finalize_result(result)
            
            # 向後相容
            result.legacy_format = {
                'verdict': verdict.verdict,
                'is_turnaround': verdict.is_turnaround,
                'is_breakdown': verdict.is_breakdown,
                'net_delta': verdict.net_delta,
                'improvements': [(m.module, m.metric, m.delta) for m in verdict.improvements],
                'deteriorations': [(m.module, m.metric, m.delta) for m in verdict.deteriorations],
            }
            result.metadata = {
                'verdict': verdict.verdict,
                'is_turnaround': verdict.is_turnaround,
                'is_breakdown': verdict.is_breakdown,
            }
            
        except Exception as e:
            result.metadata = {'error': str(e)}
        
        return result


# ============================================================================
# Adapter 3: Flow Risk Engine (資金流向風險評分)
# ============================================================================

class FlowRiskAdapter(UnifiedScoringEngine):
    """
    包裹 flow_engine.compute_risk_score()
    輸入：區域 ETF + 跨資產收盤價序列
    輸出：統一 ScoringResult，risk-on/off 判定
    """
    
    def __init__(self):
        super().__init__(
            system_name="flow_risk",
            score_range=(-100.0, 100.0),
            time_scale="daily"
        )
    
    def calculate(self, target_id: str = "GLOBAL_FLOW", **kwargs) -> ScoringResult:
        """
        Args:
            target_id: 標的名稱 (default "GLOBAL_FLOW")
            close_map: dict[str, list] - {資產名: 收盤價序列}
            window: int - Z-score 窗口 (default 252)
            days: int - 區域排名窗口 (default 5)
            as_of_date: str - 基準日期
        """
        from flow_engine import compute_risk_score as legacy_compute_risk_score
        
        as_of_date = kwargs.get('as_of_date', datetime.now().strftime("%Y-%m-%d"))
        close_map = kwargs.get('close_map', {})
        window = kwargs.get('window', 252)
        days = kwargs.get('days', 5)
        
        result = self._create_base_result(target_id, as_of_date=as_of_date)
        
        try:
            # 調用原 legacy 函數
            legacy_result = legacy_compute_risk_score(close_map=close_map, window=window)
            
            # 轉換 [-100, 100] 到 [0, 100]
            raw_score = legacy_result.get('score', 0)
            if raw_score is None:
                normalized_score = 50.0
            else:
                normalized_score = (raw_score + 100.0) / 2.0  # [-100, 100] → [0, 100]
            
            # 判定 risk-on / risk-off
            label = legacy_result.get('label', '')
            if 'Risk-on' in label:
                risk_sentiment = 'risk_on'
                sentiment_score = normalized_score
            elif 'Risk-off' in label:
                risk_sentiment = 'risk_off'
                sentiment_score = 100.0 - normalized_score
            else:
                risk_sentiment = 'neutral'
                sentiment_score = 50.0
            
            # 添加維度（區域排名前 3）
            regional_rank = legacy_result.get('regional_rank', [])
            if regional_rank:
                top_region_score = (regional_rank[0][1] + 50.0) / 2.0  # 收益率 → score
                self._add_dimension(result, 'top_region_flow', top_region_score, 0.3)
            
            self._add_dimension(result, 'risk_sentiment', sentiment_score, 0.7)
            
            result = self._finalize_result(result)
            
            # 向後相容
            result.legacy_format = legacy_result
            result.metadata = {
                'label': label,
                'risk_sentiment': risk_sentiment,
                'regional_rank': regional_rank,
            }
            
        except Exception as e:
            result.metadata = {'error': str(e)}
        
        return result


# ============================================================================
# Adapter 4: Multi-Factor Optimization (多因子優化)
# ============================================================================

class MultiFactorAdapter(UnifiedScoringEngine):
    """
    包裹 multi_factor_optimization.compute_composite_score()
    輸入：7 個台股本地因子時間序列
    輸出：統一 ScoringResult，轉折信號 + F1 評估
    """
    
    def __init__(self):
        super().__init__(
            system_name="multi_factor",
            score_range=(0.0, 100.0),
            time_scale="daily"
        )
    
    def calculate(self, target_id: str = "TWII_MULTIFACTOR", **kwargs) -> ScoringResult:
        """
        Args:
            target_id: 標的名稱 (default "TWII_MULTIFACTOR")
            factor_series_by_key: dict[str, pd.Series] - 因子時間序列
            weights: dict[str, float] - 因子權重 (∑w=1)
            threshold: float - 轉折信號門檻 (default 1.0)
            as_of_date: str - 基準日期
        """
        from multi_factor_optimization import compute_composite_score as legacy_compute_score
        
        as_of_date = kwargs.get('as_of_date', datetime.now().strftime("%Y-%m-%d"))
        factor_series = kwargs.get('factor_series_by_key', {})
        weights = kwargs.get('weights', {})
        threshold = kwargs.get('threshold', 1.0)
        
        result = self._create_base_result(target_id, as_of_date=as_of_date)
        
        try:
            # 調用原 legacy 函數
            composite_series = legacy_compute_score(
                factor_series_by_key=factor_series,
                weights=weights,
            )
            
            # 獲取最新分數
            if isinstance(composite_series, pd.Series) and len(composite_series) > 0:
                latest_score = composite_series.iloc[-1]
                # 正規化到 0-100（假設原分數在 [-5, 5] 範圍）
                normalized_score = (latest_score + 5.0) / 10.0 * 100
                normalized_score = max(0.0, min(100.0, normalized_score))
            else:
                normalized_score = 50.0
            
            # 轉折信號判定
            if len(composite_series) >= 2:
                prev_score = composite_series.iloc[-2]
                curr_score = composite_series.iloc[-1]
                if (prev_score < threshold and curr_score >= threshold):
                    signal = 'bullish_crossing'
                elif (prev_score >= threshold and curr_score < threshold):
                    signal = 'bearish_crossing'
                else:
                    signal = 'no_crossing'
            else:
                signal = 'insufficient_data'
            
            # 添加維度
            self._add_dimension(result, 'composite_score', normalized_score, 0.6)
            self._add_dimension(result, 'signal_strength',
                              75.0 if signal != 'no_crossing' else 50.0,
                              0.4)
            
            result = self._finalize_result(result)
            
            # 向後相容
            result.legacy_format = {
                'latest_score': latest_score if 'latest_score' in locals() else None,
                'signal': signal,
            }
            result.metadata = {
                'signal': signal,
                'threshold': threshold,
                'latest_composite': normalized_score,
            }
            
        except Exception as e:
            result.metadata = {'error': str(e)}
        
        return result


# ============================================================================
# Adapter 5: Technical Health Score (技術面健康度)
# ============================================================================

class TechHealthAdapter(UnifiedScoringEngine):
    """
    包裹 scoring_helpers.calc_health_score()
    輸入：技術指標 (RSI, IBS, VR, KD, Bollinger)
    輸出：統一 ScoringResult，6 因子細節
    """
    
    def __init__(self):
        super().__init__(
            system_name="tech_health",
            score_range=(0.0, 100.0),
            time_scale="daily"
        )
    
    def calculate(self, target_id: str, **kwargs) -> ScoringResult:
        """
        Args:
            target_id: 股票代碼
            df: pd.DataFrame - OHLCV DataFrame
            rsi: float - RSI 值
            ibs: float - Inside Bar Score
            vr: float - 量比
            k_val: float - KD K 值
            d_val: float - KD D 值
            bb: dict - 布林數據
            as_of_date: str - 基準日期
        """
        from scoring_helpers import calc_health_score as legacy_calc_health_score
        
        as_of_date = kwargs.get('as_of_date', datetime.now().strftime("%Y-%m-%d"))
        df = kwargs.get('df')
        rsi = kwargs.get('rsi', 50.0)
        ibs = kwargs.get('ibs', 0.5)
        vr = kwargs.get('vr', 1.0)
        k_val = kwargs.get('k_val', 50.0)
        d_val = kwargs.get('d_val', 50.0)
        bb = kwargs.get('bb', {})
        
        result = self._create_base_result(target_id, as_of_date=as_of_date)
        
        try:
            # 調用原 legacy 函數
            health_score, details = legacy_calc_health_score(
                df=df,
                rsi=rsi,
                ibs=ibs,
                vr=vr,
                k_val=k_val,
                d_val=d_val,
                bb=bb,
            )
            
            # 添加各因子維度
            factor_list = ['趨勢', 'RSI', '量比', 'IBS', 'KD', '布林']
            weights_per_factor = 1.0 / len(factor_list)
            
            for factor_name in factor_list:
                if factor_name in details:
                    label, score, max_score = details[factor_name]
                    normalized = (score / max_score * 100) if max_score > 0 else 0.0
                    self._add_dimension(result, factor_name, normalized, weights_per_factor)
            
            result = self._finalize_result(result)
            
            # 向後相容
            result.legacy_format = {
                'health_score': health_score,
                'details': details,
            }
            result.metadata = {
                'health_score': health_score,
                'factors': {k: v[1] for k, v in details.items()},
            }
            
        except Exception as e:
            result.metadata = {'error': str(e)}
        
        return result


# ============================================================================
# Adapter 6: ETF Quality Score
# ============================================================================

class ETFQualityAdapter(UnifiedScoringEngine):
    """
    包裹 etf_quality.compute_etf_quality()
    輸入：ETF 代碼
    輸出：統一 ScoringResult，星等 + 4 因子細節
    """
    
    def __init__(self):
        super().__init__(
            system_name="etf_quality",
            score_range=(0.0, 1.0),  # 星等映射需調整
            time_scale="daily"
        )
    
    def calculate(self, target_id: str, **kwargs) -> ScoringResult:
        """
        Args:
            target_id: ETF 代碼 (如 "SPY", "VTI")
            as_of_date: str - 基準日期
        """
        from etf_quality import compute_etf_quality as legacy_compute_etf_quality
        
        as_of_date = kwargs.get('as_of_date', datetime.now().strftime("%Y-%m-%d"))
        
        result = self._create_base_result(target_id, as_of_date=as_of_date)
        
        try:
            # 調用原 legacy 函數
            legacy_result = legacy_compute_etf_quality(target_id)
            
            # 提取分數
            score = legacy_result.get('score', 0.5)
            factors = legacy_result.get('factors', {})
            
            # 添加各因子維度
            for factor_name, factor_data in factors.items():
                if isinstance(factor_data, dict):
                    factor_score = factor_data.get('score', 0.5)
                    self._add_dimension(result, factor_name, factor_score * 100, 0.25)
            
            result = self._finalize_result(result)
            
            # 向後相容
            result.legacy_format = legacy_result
            result.metadata = {
                'stars': legacy_result.get('stars', 3),
                'factors': factors,
            }
            
        except Exception as e:
            result.metadata = {'error': str(e)}
        
        return result


# ============================================================================
# Adapter 7: Financial Health Engine (完整版)
# ============================================================================

class FinancialHealthAdapter(UnifiedScoringEngine):
    """
    包裹 financial_health_engine.analyze_financial_health()
    輸入：股票代碼 + 財務數據 + Gemini API Key
    輸出：統一 ScoringResult，6 模塊體檢結果
    """
    
    def __init__(self):
        super().__init__(
            system_name="financial_health",
            score_range=(0.0, 100.0),
            time_scale="quarterly"
        )
    
    def calculate(self, target_id: str, **kwargs) -> ScoringResult:
        """
        Args:
            target_id: 股票代碼
            api_key: str - Gemini API 密鑰
            fin_data: dict - 財務報表數據
            use_ai: bool - 是否使用 AI (default True)
            as_of_date: str - 基準日期
        """
        from financial_health_engine import analyze_financial_health as legacy_analyze
        
        as_of_date = kwargs.get('as_of_date', datetime.now().strftime("%Y-%m-%d"))
        api_key = kwargs.get('api_key', '')
        fin_data = kwargs.get('fin_data', {})
        use_ai = kwargs.get('use_ai', False)  # 預設關閉 AI 以加快速度
        
        result = self._create_base_result(target_id, as_of_date=as_of_date)
        
        try:
            # 調用原 legacy 函數
            legacy_result = legacy_analyze(
                api_key=api_key,
                stock_id=target_id,
                fin_data=fin_data,
                use_ai=use_ai,
            )
            
            # 提取 6 模塊雷達分數
            radar_scores = legacy_result.get('radar_scores', {})
            for module_name, score in radar_scores.items():
                if isinstance(score, (int, float)):
                    self._add_dimension(result, module_name, float(score), 1.0/6)
            
            result = self._finalize_result(result)
            
            # 向後相容
            result.legacy_format = legacy_result
            result.metadata = {
                'radar_scores': radar_scores,
                'red_flags': legacy_result.get('red_flags'),
                'ai_insight': legacy_result.get('ai_insight', ''),
            }
            
        except Exception as e:
            result.metadata = {'error': str(e)}
        
        return result
