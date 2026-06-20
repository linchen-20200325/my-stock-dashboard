"""
src/core/scoring_pipeline.py — 評分管線協調器 (P1)

統一多個評分系統為單一管線，支援：
• 串聯執行多個評分系統
• 自動缺項補全與降級
• 跨系統結果合成與融合
• 多時間尺度融合
• 完整的狀態追蹤與日誌
"""

from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime, timedelta

from src.core.scoring_result import ScoringResult, ScoringGrade
from src.core.scoring_base import UnifiedScoringEngine

logger = logging.getLogger(__name__)


# ============================================================================
# 管線狀態與定義
# ============================================================================

class ExecutionStatus(Enum):
    """執行狀態"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineStage:
    """管線階段"""
    stage_id: str
    system: UnifiedScoringEngine
    enabled: bool = True
    required: bool = False  # True：失敗會中止管線
    timeout_seconds: int = 30
    fallback_score: Optional[float] = None  # 失敗時的備援分數
    params: Dict[str, Any] = field(default_factory=dict)
    
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: Optional[ScoringResult] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0


@dataclass
class PipelineConfig:
    """管線配置"""
    pipeline_id: str
    description: str = ""
    stages: List[PipelineStage] = field(default_factory=list)
    
    # 融合策略
    fusion_method: str = "weighted_average"  # weighted_average / consensus / majority_vote
    fusion_weights: Optional[Dict[str, float]] = None
    
    # 降級策略
    allow_partial: bool = True  # 允許部分系統失敗
    min_systems: int = 1  # 最少需要成功的系統數
    
    # 執行策略
    parallel: bool = False  # 是否並行執行（需要 asyncio）
    stop_on_first_failure: bool = False
    
    # 時間配置
    cache_ttl_seconds: int = 3600
    as_of_date: Optional[str] = None


# ============================================================================
# 管線執行器
# ============================================================================

class ScoringPipeline:
    """
    評分管線協調器
    
    典型用法：
    1. 建立多個 UnifiedScoringEngine 子系統
    2. 建立 PipelineConfig 定義管線階段
    3. 建立 ScoringPipeline 執行器
    4. 調用 run() 執行評分
    5. 調用 fuse_results() 合成結果
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = logging.getLogger(f"Pipeline:{config.pipeline_id}")
    
    def run(self, target_id: str, **kwargs) -> Dict[str, ScoringResult]:
        """
        執行評分管線
        
        Args:
            target_id: 標的代碼
            **kwargs: 傳遞給各階段的參數
        
        Returns:
            {stage_id: ScoringResult, ...}
        """
        self.logger.info(f"🚀 開始執行管線: {self.config.pipeline_id} for {target_id}")
        
        results = {}
        failed_count = 0
        
        for stage in self.config.stages:
            if not stage.enabled:
                self.logger.debug(f"⏭️  跳過階段: {stage.stage_id} (disabled)")
                stage.status = ExecutionStatus.SKIPPED
                continue
            
            try:
                self.logger.debug(f"▶️  執行階段: {stage.stage_id}")
                
                import time
                start_time = time.time()
                
                # 合併參數
                params = {**stage.params, **kwargs}
                
                # 執行評分系統
                result = stage.system.calculate(target_id, **params)
                
                elapsed_ms = (time.time() - start_time) * 1000
                
                # 更新狀態
                stage.status = ExecutionStatus.SUCCESS
                stage.result = result
                stage.execution_time_ms = elapsed_ms
                
                results[stage.stage_id] = result
                
                self.logger.debug(f"✅ {stage.stage_id}: score={result.score}, time={elapsed_ms:.0f}ms")
            
            except Exception as e:
                failed_count += 1
                stage.status = ExecutionStatus.FAILED
                stage.error = str(e)
                
                self.logger.error(f"❌ {stage.stage_id}: {stage.error}")
                
                if stage.required and not self.config.allow_partial:
                    self.logger.error(f"❌ 必需階段失敗，中止管線")
                    raise
                
                if self.config.stop_on_first_failure:
                    self.logger.warning(f"⚠️  停止執行後續階段")
                    break
        
        # 檢查最少系統數
        successful_count = len(results)
        if successful_count < self.config.min_systems:
            self.logger.error(
                f"❌ 成功系統數({successful_count}) < 最少需求({self.config.min_systems})"
            )
            if not self.config.allow_partial:
                raise RuntimeError(f"管線失敗：系統不足")
        
        self.logger.info(f"✅ 管線執行完成: {successful_count}/{len(self.config.stages)} 個系統成功")
        
        return results
    
    def fuse_results(
        self,
        results: Dict[str, ScoringResult],
        target_id: str,
        as_of_date: Optional[str] = None
    ) -> ScoringResult:
        """
        融合多個評分系統的結果為統一評分
        
        Args:
            results: {stage_id: ScoringResult, ...}
            target_id: 標的代碼
            as_of_date: 基準日期
        
        Returns:
            融合後的 ScoringResult
        """
        if not results:
            self.logger.error("❌ 無結果可融合")
            raise ValueError("No results to fuse")
        
        if as_of_date is None:
            as_of_date = datetime.now().strftime("%Y-%m-%d")
        
        self.logger.debug(f"🔄 融合 {len(results)} 個系統的結果")
        
        # 建立融合結果
        fused = ScoringResult(
            system_name=f"Pipeline:{self.config.pipeline_id}",
            target_id=target_id,
            as_of_date=as_of_date,
            time_scale="composite"
        )
        
        # 根據融合方法計算總分
        if self.config.fusion_method == "weighted_average":
            fused_score = self._fuse_weighted_average(results)
        elif self.config.fusion_method == "consensus":
            fused_score = self._fuse_consensus(results)
        elif self.config.fusion_method == "majority_vote":
            fused_score = self._fuse_majority_vote(results)
        else:
            fused_score = self._fuse_weighted_average(results)
        
        fused.score = fused_score
        
        # 映射等級
        if fused_score is not None:
            from src.core.scoring_base import GradeMapper
            fused.grade = GradeMapper.map_score_to_grade(fused_score)
        
        # 計算信心度
        valid_results = [r for r in results.values() if r.score is not None]
        fused.confidence = len(valid_results) / len(results) if results else 0
        
        # 記錄元數據
        fused.metadata = {
            'fusion_method': self.config.fusion_method,
            'systems_used': list(results.keys()),
            'systems_count': len(results),
            'valid_systems_count': len(valid_results),
            'component_scores': {
                stage_id: result.score
                for stage_id, result in results.items()
            }
        }
        
        self.logger.info(
            f"✅ 融合完成: score={fused.score}, confidence={fused.confidence:.2%}"
        )
        
        return fused
    
    def _fuse_weighted_average(self, results: Dict[str, ScoringResult]) -> Optional[float]:
        """加權平均融合"""
        scores = []
        weights = self.config.fusion_weights or {}
        
        default_weight = 1.0 / len(results) if results else 0
        
        for stage_id, result in results.items():
            if result.score is not None:
                weight = weights.get(stage_id, default_weight)
                scores.append((result.score, weight))
        
        if not scores:
            return None
        
        total_weighted = sum(s * w for s, w in scores)
        total_weight = sum(w for s, w in scores)
        
        return total_weighted / total_weight if total_weight > 0 else None
    
    def _fuse_consensus(self, results: Dict[str, ScoringResult]) -> Optional[float]:
        """共識融合（尋找等級級別的共識）"""
        grades = [r.grade for r in results.values() if r.grade is not None]
        
        if not grades:
            return None
        
        # 簡單共識：最常見的等級
        from collections import Counter
        grade_counts = Counter(grades)
        consensus_grade, _ = grade_counts.most_common(1)[0]
        
        # 轉回分數（使用中點）
        score_ranges = {
            ScoringGrade.A_PLUS: 95,
            ScoringGrade.A: 87.5,
            ScoringGrade.A_MINUS: 82.5,
            ScoringGrade.B_PLUS: 77.5,
            ScoringGrade.B: 72.5,
            ScoringGrade.B_MINUS: 67.5,
            ScoringGrade.C_PLUS: 62.5,
            ScoringGrade.C: 57.5,
            ScoringGrade.C_MINUS: 52.5,
            ScoringGrade.D: 25,
        }
        
        return score_ranges.get(consensus_grade, 50.0)
    
    def _fuse_majority_vote(self, results: Dict[str, ScoringResult]) -> Optional[float]:
        """多數投票融合（超過 50% 系統同意則為 True）"""
        # 簡單實現：計算等級投票
        above_threshold = sum(1 for r in results.values() if r.score is not None and r.score >= 70)
        total = len([r for r in results.values() if r.score is not None])
        
        if total == 0:
            return None
        
        # 返回多數派的分數
        if above_threshold > total / 2:
            return 75.0  # 投票通過：高分
        else:
            return 50.0  # 投票失敗：中性
    
    def print_summary(self, results: Dict[str, ScoringResult], fused: Optional[ScoringResult] = None):
        """打印管線執行摘要"""
        print(f"\n{'='*80}")
        print(f"🎯 管線執行摘要: {self.config.pipeline_id}")
        print(f"{'='*80}")
        
        print(f"\n【各系統結果】")
        for stage_id, result in results.items():
            status_icon = "✅" if result.score is not None else "❌"
            print(f"  {status_icon} {stage_id}")
            print(f"     Score: {result.score}, Grade: {result.grade}, Confidence: {result.confidence:.2%}")
        
        if fused:
            print(f"\n【融合結果】")
            print(f"  🔄 Method: {self.config.fusion_method}")
            print(f"  📊 Fused Score: {fused.score}")
            print(f"  🏆 Grade: {fused.grade}")
            print(f"  💪 Confidence: {fused.confidence:.2%}")
        
        print(f"\n{'='*80}\n")


# ============================================================================
# 管線構建器（流暢 API）
# ============================================================================

class PipelineBuilder:
    """管線構建器（流暢接口）"""
    
    def __init__(self, pipeline_id: str):
        self.pipeline_id = pipeline_id
        self.stages: List[PipelineStage] = []
        self.fusion_method = "weighted_average"
        self.fusion_weights: Dict[str, float] = {}
        self.allow_partial = True
        self.min_systems = 1
    
    def add_stage(
        self,
        stage_id: str,
        system: UnifiedScoringEngine,
        enabled: bool = True,
        required: bool = False,
        weight: float = 1.0,
        **params
    ) -> 'PipelineBuilder':
        """添加評分系統到管線"""
        stage = PipelineStage(
            stage_id=stage_id,
            system=system,
            enabled=enabled,
            required=required,
            params=params
        )
        self.stages.append(stage)
        self.fusion_weights[stage_id] = weight
        return self
    
    def set_fusion_method(self, method: str, weights: Optional[Dict[str, float]] = None) -> 'PipelineBuilder':
        """設定融合方法"""
        self.fusion_method = method
        if weights:
            self.fusion_weights.update(weights)
        return self
    
    def allow_partial_failure(self, allow: bool = True, min_systems: int = 1) -> 'PipelineBuilder':
        """設定是否允許部分失敗"""
        self.allow_partial = allow
        self.min_systems = min_systems
        return self
    
    def build(self) -> Tuple[ScoringPipeline, PipelineConfig]:
        """建立管線"""
        config = PipelineConfig(
            pipeline_id=self.pipeline_id,
            stages=self.stages,
            fusion_method=self.fusion_method,
            fusion_weights=self.fusion_weights,
            allow_partial=self.allow_partial,
            min_systems=self.min_systems
        )
        
        return ScoringPipeline(config), config
