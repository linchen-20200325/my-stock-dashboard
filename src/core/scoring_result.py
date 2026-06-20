"""
src/core/scoring_result.py — 統一評分結果架構 (P1)

所有評分系統的輸出必須符合此 dataclass，確保系統間資料交換一致性。
支援多維度評分、缺項管理、動態權重調整、不同時間尺度融合。
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any, Tuple
from enum import Enum
import json


# ============================================================================
# 評分等級定義
# ============================================================================

class ScoringGrade(Enum):
    """評分等級標準化定義"""
    # 字母等級（股票/個別項目）
    A_PLUS = "A+"
    A = "A"
    A_MINUS = "A-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    C_PLUS = "C+"
    C = "C"
    C_MINUS = "C-"
    D = "D"
    F = "F"
    
    # 星等（ETF）
    STAR_5 = "⭐⭐⭐⭐⭐"
    STAR_4 = "⭐⭐⭐⭐"
    STAR_3 = "⭐⭐⭐"
    STAR_2 = "⭐⭐"
    STAR_1 = "⭐"
    
    # 文字等級（其他）
    EXCELLENT = "Excellent"
    GOOD = "Good"
    FAIR = "Fair"
    POOR = "Poor"
    
    # 特殊狀態
    UNKNOWN = "Unknown"
    NA = "N/A"


class DimensionStatus(Enum):
    """維度評分狀態"""
    AVAILABLE = "available"       # 完整計算
    PARTIAL = "partial"            # 部分資料缺失
    DEGRADED = "degraded"          # 降級計算（權重已調整）
    MISSING = "missing"            # 資料完全缺失
    NOT_APPLICABLE = "n/a"         # 不適用於此標的


# ============================================================================
# 核心 Dataclass
# ============================================================================

@dataclass
class Dimension:
    """單一維度評分"""
    name: str                       # 維度名稱（如 'trend', 'momentum', 'liquidity'）
    score: Optional[float]          # 維度分數（0-100 或 0-1，系統決定）
    weight: float                   # 此維度的權重（0-1）
    status: DimensionStatus = DimensionStatus.AVAILABLE
    details: Optional[Dict[str, Any]] = None  # 維度詳情（子指標）
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'score': self.score,
            'weight': self.weight,
            'status': self.status.value,
            'details': self.details
        }


@dataclass
class ScoringResult:
    """
    統一評分結果 — 所有評分系統的標準輸出
    
    設計原則：
    • 支援多維度：維度清單 + 總分（加權平均）
    • 支援等級映射：分數 → 字母/星等/標籤
    • 支援多時間尺度：日頻/月頻/季頻
    • 支援缺項管理：自動重新分配權重到有效維度
    • 支援向後相容：可序列化為原系統格式
    """
    
    # ── 核心評分 ────────────────────────────────────
    system_name: str                # 評分系統名稱（stock_score / etf_score / mj_health 等）
    target_id: str                  # 標的代碼（股票代碼 / ETF 代碼 / 標的名稱）
    score: Optional[float]          # 總分（0-100 或 0-1，系統決定）
    grade: Optional[ScoringGrade]   # 等級（A / ⭐⭐⭐ 等）
    
    # ── 維度分解 ────────────────────────────────────
    dimensions: List[Dimension] = field(default_factory=list)  # 所有維度詳情
    
    # ── 時間信息 ────────────────────────────────────
    as_of_date: str                 # 評分基準日（YYYY-MM-DD）
    time_scale: str = "daily"       # 時間尺度（daily / monthly / quarterly / annual）
    lag_days: int = 0               # 資料滯後天數（即時 vs T+1 vs T+N）
    
    # ── 品質信息 ────────────────────────────────────
    confidence: float               # 信心度（0-1；=有效維度比例或加權覆蓋率）
    data_points: int = 0            # 使用的數據點數
    missing_dimensions: List[str] = field(default_factory=list)  # 缺失維度清單
    
    # ── 元數據 ────────────────────────────────────
    metadata: Dict[str, Any] = field(default_factory=dict)  # 系統特定資訊
    
    # ── 履歷 ────────────────────────────────────
    notes: Optional[str] = None    # 計算備註
    errors: List[str] = field(default_factory=list)  # 計算過程中的警告/錯誤
    
    # ── 向後相容 ────────────────────────────────────
    legacy_format: Optional[Dict[str, Any]] = None  # 原格式（用於過渡期相容）
    
    # =========================================================================
    # 方法
    # =========================================================================
    
    def get_dimension(self, name: str) -> Optional[Dimension]:
        """取得特定維度的詳情"""
        for dim in self.dimensions:
            if dim.name.lower() == name.lower():
                return dim
        return None
    
    def get_dimension_score(self, name: str) -> Optional[float]:
        """快速取得特定維度分數"""
        dim = self.get_dimension(name)
        return dim.score if dim else None
    
    def add_dimension(self, dimension: Dimension) -> None:
        """新增維度"""
        self.dimensions.append(dimension)
    
    def add_error(self, error_msg: str) -> None:
        """記錄警告/錯誤"""
        self.errors.append(error_msg)
    
    def get_effective_dimensions(self) -> List[Dimension]:
        """取得有效維度（狀態非 MISSING）"""
        return [d for d in self.dimensions if d.status != DimensionStatus.MISSING]
    
    def get_effective_weight_sum(self) -> float:
        """計算有效維度的權重和"""
        effective = self.get_effective_dimensions()
        return sum(d.weight for d in effective)
    
    def recalculate_weights(self) -> None:
        """重新分配權重到有效維度（缺項時）"""
        effective = self.get_effective_dimensions()
        if not effective:
            return
        
        effective_sum = sum(d.weight for d in effective)
        if effective_sum <= 0:
            return
        
        # 正規化權重到有效維度
        factor = 1.0 / effective_sum
        for dim in self.dimensions:
            if dim.status != DimensionStatus.MISSING:
                dim.weight *= factor
    
    def recalculate_score(self) -> float:
        """重新計算加權總分"""
        effective = self.get_effective_dimensions()
        if not effective or all(d.score is None for d in effective):
            self.score = None
            return None
        
        total_weighted = 0.0
        total_weight = 0.0
        for dim in effective:
            if dim.score is not None:
                total_weighted += dim.score * dim.weight
                total_weight += dim.weight
        
        if total_weight > 0:
            self.score = total_weighted / total_weight
            return self.score
        
        self.score = None
        return None
    
    def to_dict(self, include_legacy: bool = False) -> Dict[str, Any]:
        """轉換為字典（JSON序列化友善）"""
        result = {
            'system_name': self.system_name,
            'target_id': self.target_id,
            'score': self.score,
            'grade': self.grade.value if self.grade else None,
            'as_of_date': self.as_of_date,
            'time_scale': self.time_scale,
            'lag_days': self.lag_days,
            'confidence': self.confidence,
            'data_points': self.data_points,
            'missing_dimensions': self.missing_dimensions,
            'dimensions': [d.to_dict() for d in self.dimensions],
            'metadata': self.metadata,
            'notes': self.notes,
            'errors': self.errors,
        }
        
        if include_legacy and self.legacy_format:
            result['_legacy'] = self.legacy_format
        
        return result
    
    def to_json(self, indent: int = 2) -> str:
        """轉換為 JSON 字串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)
    
    def to_legacy_dict(self) -> Optional[Dict[str, Any]]:
        """轉換回原格式（過渡期用）"""
        if self.legacy_format:
            return self.legacy_format
        return None
    
    @staticmethod
    def from_legacy_dict(data: Dict[str, Any], system_name: str, as_of_date: str) -> 'ScoringResult':
        """從原格式資料轉換成統一格式（向後相容）"""
        result = ScoringResult(
            system_name=system_name,
            target_id=data.get('id', data.get('target_id', 'unknown')),
            score=data.get('score'),
            grade=None,
            as_of_date=as_of_date,
            confidence=data.get('confidence', 0.8),
            legacy_format=data
        )
        
        # 簡單的等級映射（系統可自訂）
        if result.score is not None:
            if result.score >= 80:
                result.grade = ScoringGrade.A
            elif result.score >= 70:
                result.grade = ScoringGrade.B
            elif result.score >= 60:
                result.grade = ScoringGrade.C
            else:
                result.grade = ScoringGrade.D
        
        return result


# ============================================================================
# 便利函數
# ============================================================================

def create_scoring_result(
    system_name: str,
    target_id: str,
    as_of_date: str,
    dimensions_data: Optional[List[Tuple[str, float, float]]] = None,  # [(name, score, weight), ...]
    grade: Optional[ScoringGrade] = None,
    time_scale: str = "daily",
    **kwargs
) -> ScoringResult:
    """便利工廠函數建立 ScoringResult"""
    result = ScoringResult(
        system_name=system_name,
        target_id=target_id,
        as_of_date=as_of_date,
        grade=grade,
        time_scale=time_scale,
        **kwargs
    )
    
    if dimensions_data:
        for name, score, weight in dimensions_data:
            result.add_dimension(Dimension(
                name=name,
                score=score,
                weight=weight
            ))
    
    result.recalculate_score()
    if result.get_effective_dimensions():
        result.confidence = len([d for d in result.dimensions if d.score is not None]) / len(result.dimensions)
    
    return result
