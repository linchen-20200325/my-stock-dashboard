"""
src/core/etf_scoring_engine.py — ETF 多維度評分遷移 (P1 Step 2)

將 etf_scoring_helpers.py 的 compute_etf_composite_score() 遷移到統一框架
"""

from typing import Optional, Dict, Any
from datetime import datetime
import math
import pandas as pd
import numpy as np

from src.core.scoring_base import UnifiedScoringEngine, Normalizer, GradeMapper, GradeRule
from src.core.scoring_result import ScoringResult, DimensionStatus, ScoringGrade


class ETFScoringEngine(UnifiedScoringEngine):
    """
    ETF 7 維度綜合評分引擎
    
    維度：
    • 1Y 累積回報（25%）
    • 3Y CAGR（20%）
    • 夏普比（15%）
    • MDD（15%）
    • 費用率（12%）
    • AUM log（8%）
    • 殖利率穩定度 CV（5%）
    
    輸出範圍：0-1（對應星等映射）
    """
    
    # 星等映射規則（0-1 分數 → 1-5 星）
    STAR_GRADES = [
        GradeRule(0.80, 1.00, ScoringGrade.STAR_5),
        GradeRule(0.65, 0.80, GradeRule(0.65, 0.80, ScoringGrade.STAR_4),
        GradeRule(0.50, 0.65, ScoringGrade.STAR_3),
        GradeRule(0.35, 0.50, ScoringGrade.STAR_2),
        GradeRule(0.00, 0.35, ScoringGrade.STAR_1),
    ]
    
    def __init__(self):
        super().__init__(
            system_name="etf_score",
            score_range=(0.0, 1.0),
            grade_rules=self.STAR_GRADES,
            time_scale="daily"
        )
        
        # 維度權重
        self.weights = {
            'return_1y': 0.25,
            'cagr_3y': 0.20,
            'sharpe': 0.15,
            'mdd': 0.15,
            'expense_ratio': 0.12,
            'aum': 0.08,
            'yield_cv': 0.05,
        }
        
        # 正規化參數
        self.thresholds = {
            'return_1y': {'good': 0.10, 'bad': -0.05},  # 10% vs -5%
            'cagr_3y': {'good': 0.08, 'bad': 0.00},     # 8% vs 0%
            'sharpe': {'good': 1.0, 'bad': 0.2},        # 1.0 vs 0.2
            'mdd': {'good': -0.15, 'bad': -0.50},       # -15% vs -50%
            'expense_ratio': {'good': 0.003, 'bad': 0.015},  # 0.3% vs 1.5%
            'aum': {'good': 1e10, 'bad': 1e9},          # 100B vs 10B
            'yield_cv': {'good': 0.15, 'bad': 0.6},     # 0.15 vs 0.6
        }
    
    def calculate(self, target_id: str, **kwargs) -> ScoringResult:
        """
        計算 ETF 評分
        
        Args:
            target_id: ETF 代碼
            return_1y: 1 年累積回報
            cagr_3y: 3 年 CAGR
            sharpe: 夏普比
            mdd: 最大回撤
            expense_ratio: 費用率
            aum: 資產規模 (TWD)
            yield_cv: 殖利率標準差係數
            as_of_date: 基準日期 (optional)
        
        Returns:
            ScoringResult（0-1 分數 + 星等）
        """
        as_of_date = kwargs.get('as_of_date', datetime.now().strftime("%Y-%m-%d"))
        
        result = self._create_base_result(target_id, as_of_date=as_of_date)
        
        # 提取各維度
        return_1y = kwargs.get('return_1y')
        cagr_3y = kwargs.get('cagr_3y')
        sharpe = kwargs.get('sharpe')
        mdd = kwargs.get('mdd')
        expense_ratio = kwargs.get('expense_ratio')
        aum = kwargs.get('aum')
        yield_cv = kwargs.get('yield_cv')
        
        # ── 1Y 累積回報 ─────────────────────────────────
        score_1y = self._normalize_return_1y(return_1y)
        self._add_dimension(
            result, 'return_1y', score_1y, self.weights['return_1y'],
            status=DimensionStatus.AVAILABLE if score_1y is not None else DimensionStatus.MISSING
        )
        
        # ── 3Y CAGR ─────────────────────────────────
        score_3y = self._normalize_cagr_3y(cagr_3y)
        self._add_dimension(
            result, 'cagr_3y', score_3y, self.weights['cagr_3y'],
            status=DimensionStatus.AVAILABLE if score_3y is not None else DimensionStatus.MISSING
        )
        
        # ── 夏普比 ─────────────────────────────────
        score_sharpe = self._normalize_sharpe(sharpe)
        self._add_dimension(
            result, 'sharpe', score_sharpe, self.weights['sharpe'],
            status=DimensionStatus.AVAILABLE if score_sharpe is not None else DimensionStatus.MISSING
        )
        
        # ── MDD ─────────────────────────────────
        score_mdd = self._normalize_mdd(mdd)
        self._add_dimension(
            result, 'mdd', score_mdd, self.weights['mdd'],
            status=DimensionStatus.AVAILABLE if score_mdd is not None else DimensionStatus.MISSING
        )
        
        # ── 費用率 ─────────────────────────────────
        score_expense = self._normalize_expense_ratio(expense_ratio)
        self._add_dimension(
            result, 'expense_ratio', score_expense, self.weights['expense_ratio'],
            status=DimensionStatus.AVAILABLE if score_expense is not None else DimensionStatus.MISSING
        )
        
        # ── AUM ─────────────────────────────────
        score_aum = self._normalize_aum(aum)
        self._add_dimension(
            result, 'aum', score_aum, self.weights['aum'],
            status=DimensionStatus.AVAILABLE if score_aum is not None else DimensionStatus.MISSING
        )
        
        # ── 殖利率 CV ─────────────────────────────────
        score_yield_cv = self._normalize_yield_cv(yield_cv)
        self._add_dimension(
            result, 'yield_cv', score_yield_cv, self.weights['yield_cv'],
            status=DimensionStatus.AVAILABLE if score_yield_cv is not None else DimensionStatus.MISSING
        )
        
        # ── 完成 ─────────────────────────────────
        result = self._finalize_result(result)
        
        # ── 向後相容：記錄原格式 ──────────────────────────────
        result.legacy_format = {
            'etf_id': target_id,
            'composite_score': result.score,
            'stars': result.grade.value if result.grade else None,
            'components': {
                'return_1y': result.get_dimension_score('return_1y'),
                'cagr_3y': result.get_dimension_score('cagr_3y'),
                'sharpe': result.get_dimension_score('sharpe'),
                'mdd': result.get_dimension_score('mdd'),
                'expense_ratio': result.get_dimension_score('expense_ratio'),
                'aum': result.get_dimension_score('aum'),
                'yield_cv': result.get_dimension_score('yield_cv'),
            }
        }
        
        return result
    
    # ========================================================================
    # 正規化函數
    # ========================================================================
    
    def _normalize_return_1y(self, value: Optional[float]) -> Optional[float]:
        """正規化 1Y 累積回報"""
        if value is None:
            return None
        return Normalizer.linear_normalize(
            value,
            self.thresholds['return_1y']['bad'],
            self.thresholds['return_1y']['good']
        )
    
    def _normalize_cagr_3y(self, value: Optional[float]) -> Optional[float]:
        """正規化 3Y CAGR"""
        if value is None:
            return None
        return Normalizer.linear_normalize(
            value,
            self.thresholds['cagr_3y']['bad'],
            self.thresholds['cagr_3y']['good']
        )
    
    def _normalize_sharpe(self, value: Optional[float]) -> Optional[float]:
        """正規化夏普比"""
        if value is None:
            return None
        return Normalizer.linear_normalize(
            value,
            self.thresholds['sharpe']['bad'],
            self.thresholds['sharpe']['good']
        )
    
    def _normalize_mdd(self, value: Optional[float]) -> Optional[float]:
        """正規化 MDD（越低越好，所以反轉）"""
        if value is None:
            return None
        # MDD 是負數；-15% 最好（1 分），-50% 最差（0 分）
        return Normalizer.linear_normalize(
            value,
            self.thresholds['mdd']['bad'],   # -50%
            self.thresholds['mdd']['good'],  # -15%
            reverse=False  # 不反轉，因為本身邏輯是 -50 → -15
        )
    
    def _normalize_expense_ratio(self, value: Optional[float]) -> Optional[float]:
        """正規化費用率（越低越好）"""
        if value is None:
            return None
        return Normalizer.linear_normalize(
            value,
            self.thresholds['expense_ratio']['bad'],   # 1.5%
            self.thresholds['expense_ratio']['good'],  # 0.3%
            reverse=True  # 反轉：費用低 = 高分
        )
    
    def _normalize_aum(self, value: Optional[float]) -> Optional[float]:
        """正規化 AUM"""
        if value is None or value <= 0:
            return None
        log_aum = math.log10(value)
        return Normalizer.linear_normalize(
            log_aum,
            math.log10(self.thresholds['aum']['bad']),   # log10(1e9)
            math.log10(self.thresholds['aum']['good'])   # log10(1e10)
        )
    
    def _normalize_yield_cv(self, value: Optional[float]) -> Optional[float]:
        """正規化殖利率穩定度 CV（越低越穩定，越好）"""
        if value is None:
            return None
        return Normalizer.linear_normalize(
            value,
            self.thresholds['yield_cv']['bad'],   # 0.6
            self.thresholds['yield_cv']['good'],  # 0.15
            reverse=True  # 反轉：CV 低 = 高分
        )
