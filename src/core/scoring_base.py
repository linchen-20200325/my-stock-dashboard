"""
src/core/scoring_base.py — 統一評分引擎基類 (P1)

所有評分系統（股票/ETF/MJ等）都應繼承此基類，實現：
• 通用的維度正規化邏輯
• 缺項動態權重重新分配
• 統一的等級映射
• 多時間尺度支援
• 完整的異常處理與日誌
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Tuple, Any, Callable
from dataclasses import dataclass
import logging
from datetime import datetime

import pandas as pd
import numpy as np

from src.core.scoring_result import (
    ScoringResult, Dimension, DimensionStatus, ScoringGrade
)

logger = logging.getLogger(__name__)


# ============================================================================
# 正規化工具
# ============================================================================

class Normalizer:
    """維度值正規化工具"""
    
    @staticmethod
    def linear_normalize(
        value: Optional[float],
        min_val: float,
        max_val: float,
        reverse: bool = False,
        clip: bool = True
    ) -> Optional[float]:
        """
        線性正規化：value → [0, 1]
        
        Args:
            value: 原始值
            min_val: 最小值（目標 0 分）
            max_val: 最大值（目標 1 分）
            reverse: 是否反轉（值越低分越高）
            clip: 是否 clip 到 [0, 1]
        
        Returns:
            正規化後的值 [0, 1]，或 None if value is None
        """
        if value is None or np.isnan(value) or np.isinf(value):
            return None
        
        if max_val == min_val:
            return 1.0 if not reverse else 0.0
        
        normalized = (value - min_val) / (max_val - min_val)
        
        if reverse:
            normalized = 1.0 - normalized
        
        if clip:
            normalized = np.clip(normalized, 0.0, 1.0)
        
        return float(normalized)
    
    @staticmethod
    def zscore_normalize(series: pd.Series, clip: bool = True) -> Optional[float]:
        """
        Z-score 正規化：(x - mean) / std → [-∞, +∞]，clip 到 [-3, 3] 後映射到 [0, 1]
        """
        if series is None or len(series) < 2 or series.isna().all():
            return None
        
        mean = series.mean()
        std = series.std()
        
        if std == 0:
            return 0.5
        
        latest = series.iloc[-1]
        if np.isnan(latest) or np.isinf(latest):
            return None
        
        z = (latest - mean) / std
        
        if clip:
            z = np.clip(z, -3.0, 3.0)
            # 映射 [-3, 3] → [0, 1]
            normalized = (z + 3.0) / 6.0
        else:
            # 不 clip：使用 sigmoid
            normalized = 1.0 / (1.0 + np.exp(-z))
        
        return float(normalized)
    
    @staticmethod
    def percentile_rank(value: Optional[float], series: pd.Series) -> Optional[float]:
        """
        百分位排名：value 在 series 中的百分位數 [0, 1]
        """
        if value is None or series is None or len(series) < 2:
            return None
        
        if np.isnan(value) or np.isinf(value):
            return None
        
        rank = (series <= value).sum() / len(series)
        return float(np.clip(rank, 0.0, 1.0))


# ============================================================================
# 等級映射規則
# ============================================================================

@dataclass
class GradeRule:
    """等級映射規則"""
    min_score: float
    max_score: float
    grade: ScoringGrade


class GradeMapper:
    """等級映射邏輯"""
    
    # 預設等級映射表
    DEFAULT_LETTER_GRADES = [
        GradeRule(90.0, 100.0, ScoringGrade.A_PLUS),
        GradeRule(85.0, 90.0, ScoringGrade.A),
        GradeRule(80.0, 85.0, ScoringGrade.A_MINUS),
        GradeRule(75.0, 80.0, ScoringGrade.B_PLUS),
        GradeRule(70.0, 75.0, ScoringGrade.B),
        GradeRule(65.0, 70.0, ScoringGrade.B_MINUS),
        GradeRule(60.0, 65.0, ScoringGrade.C_PLUS),
        GradeRule(55.0, 60.0, ScoringGrade.C),
        GradeRule(50.0, 55.0, ScoringGrade.C_MINUS),
        GradeRule(0.0, 50.0, ScoringGrade.D),
    ]
    
    DEFAULT_STAR_GRADES = [
        GradeRule(0.80, 1.00, ScoringGrade.STAR_5),
        GradeRule(0.65, 0.80, ScoringGrade.STAR_4),
        GradeRule(0.50, 0.65, ScoringGrade.STAR_3),
        GradeRule(0.35, 0.50, ScoringGrade.STAR_2),
        GradeRule(0.00, 0.35, ScoringGrade.STAR_1),
    ]
    
    @classmethod
    def map_score_to_grade(
        cls,
        score: Optional[float],
        rules: Optional[List[GradeRule]] = None
    ) -> Optional[ScoringGrade]:
        """根據分數映射等級"""
        if score is None:
            return None
        
        if rules is None:
            rules = cls.DEFAULT_LETTER_GRADES
        
        for rule in rules:
            if rule.min_score <= score < rule.max_score:
                return rule.grade
        
        # 最後一個規則作為備援
        if rules:
            return rules[-1].grade
        
        return None


# ============================================================================
# 抽象基類
# ============================================================================

class UnifiedScoringEngine(ABC):
    """
    統一評分引擎抽象基類
    
    所有具體評分系統應繼承此類，並實現 calculate() 方法。
    
    設計特性：
    • 自動維度正規化（0-1 或 0-100）
    • 自動缺項檢測與動態權重調整
    • 自動等級映射
    • 統一的異常處理與日誌記錄
    • 支援多時間尺度（日/月/季/年）
    """
    
    def __init__(
        self,
        system_name: str,
        score_range: Tuple[float, float] = (0.0, 100.0),
        grade_rules: Optional[List[GradeRule]] = None,
        time_scale: str = "daily",
        lag_days: int = 0,
        logger_name: Optional[str] = None
    ):
        """
        初始化基類
        
        Args:
            system_name: 系統名稱（用於 ScoringResult）
            score_range: 分數範圍（預設 0-100）
            grade_rules: 自訂等級映射規則
            time_scale: 時間尺度（daily/monthly/quarterly）
            lag_days: 資料滯後天數
            logger_name: 日誌器名稱
        """
        self.system_name = system_name
        self.score_range = score_range
        self.grade_rules = grade_rules or GradeMapper.DEFAULT_LETTER_GRADES
        self.time_scale = time_scale
        self.lag_days = lag_days
        self.logger = logging.getLogger(logger_name or system_name)
        
        # 執行時快取
        self._last_result: Optional[ScoringResult] = None
    
    @abstractmethod
    def calculate(self, target_id: str, **kwargs) -> ScoringResult:
        """
        計算評分（子類必須實現）
        
        Args:
            target_id: 標的代碼
            **kwargs: 系統特定的引數
        
        Returns:
            ScoringResult 統一結果
        """
        pass
    
    def _create_base_result(
        self,
        target_id: str,
        as_of_date: Optional[str] = None,
        **kwargs
    ) -> ScoringResult:
        """建立基礎 ScoringResult"""
        if as_of_date is None:
            as_of_date = datetime.now().strftime("%Y-%m-%d")
        
        return ScoringResult(
            system_name=self.system_name,
            target_id=target_id,
            as_of_date=as_of_date,
            time_scale=self.time_scale,
            lag_days=self.lag_days,
            **kwargs
        )
    
    def _add_dimension(
        self,
        result: ScoringResult,
        name: str,
        value: Optional[float],
        weight: float = 1.0,
        normalize_fn: Optional[Callable[[float], float]] = None,
        status: DimensionStatus = DimensionStatus.AVAILABLE,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """添加維度到結果"""
        
        score = value
        
        # 應用正規化函數
        if normalize_fn and value is not None:
            score = normalize_fn(value)
        
        # 偵測缺失
        if score is None or np.isnan(score) or np.isinf(score):
            status = DimensionStatus.MISSING
            result.missing_dimensions.append(name)
        
        dimension = Dimension(
            name=name,
            score=score,
            weight=weight,
            status=status,
            details=details
        )
        
        result.add_dimension(dimension)
    
    def _finalize_result(self, result: ScoringResult) -> ScoringResult:
        """
        完成結果計算
        
        1. 重新分配權重到有效維度
        2. 重新計算加權總分
        3. 映射等級
        4. 計算信心度
        """
        
        # 重新分配權重
        result.recalculate_weights()
        
        # 重新計算總分
        result.recalculate_score()
        
        # 映射等級
        if result.score is not None:
            result.grade = GradeMapper.map_score_to_grade(result.score, self.grade_rules)
        
        # 計算信心度（有效維度 / 總維度）
        if result.dimensions:
            effective_count = len([d for d in result.dimensions if d.status != DimensionStatus.MISSING])
            result.confidence = effective_count / len(result.dimensions)
            result.data_points = effective_count
        
        self._last_result = result
        
        return result
    
    def get_last_result(self) -> Optional[ScoringResult]:
        """取得最後一次計算結果"""
        return self._last_result


# ============================================================================
# 快速評分工廠
# ============================================================================

class ScoreCalculator:
    """評分計算的便利工具"""
    
    @staticmethod
    def weighted_average(
        scores: List[Tuple[float, float]],  # [(score, weight), ...]
        handle_missing: str = "skip"  # skip | zero | interpolate
    ) -> float:
        """
        加權平均
        
        Args:
            scores: 分數與權重的列表
            handle_missing: 缺失值處理方式
                - skip：忽略 None，重新正規化權重
                - zero：None 視為 0 分
                - interpolate：使用相鄰值補全
        
        Returns:
            加權平均分數
        """
        if not scores:
            return 0.0
        
        if handle_missing == "skip":
            valid_scores = [(s, w) for s, w in scores if s is not None]
            if not valid_scores:
                return 0.0
            scores = valid_scores
        
        total_weighted = sum(s * w for s, w in scores if s is not None)
        total_weight = sum(w for s, w in scores if s is not None)
        
        if total_weight > 0:
            return total_weighted / total_weight
        
        return 0.0
    
    @staticmethod
    def clamp_score(score: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
        """限制分數到指定範圍"""
        return np.clip(score, min_val, max_val)
    
    @staticmethod
    def smooth_score(current: float, previous: Optional[float], alpha: float = 0.7) -> float:
        """指數平滑：避免分數劇烈波動"""
        if previous is None:
            return current
        return alpha * current + (1 - alpha) * previous
