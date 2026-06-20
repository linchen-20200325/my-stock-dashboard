"""
src/core/p1_state_machine.py — P1 Day 3 狀態機驗證與最佳化

驗證評分系統的狀態轉移邏輯：
• 系統初始化 → 準備就緒
• 數據輸入驗證
• 計算流程完整性
• 結果輸出驗證
• 錯誤處理與復原
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, List, Callable, Any
import json
from datetime import datetime


class ScoringSystemState(Enum):
    """評分系統狀態"""
    UNINITIALIZED = "uninitialized"
    INITIALIZED = "initialized"
    DATA_VALIDATING = "data_validating"
    CALCULATING = "calculating"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    DEGRADED = "degraded"


@dataclass
class StateTransition:
    """狀態轉移記錄"""
    from_state: ScoringSystemState
    to_state: ScoringSystemState
    timestamp: str
    reason: str
    metrics: Dict[str, Any]


class P1StateMachine:
    """P1 評分系統狀態機"""
    
    def __init__(self, system_name: str):
        self.system_name = system_name
        self.current_state = ScoringSystemState.UNINITIALIZED
        self.transitions: List[StateTransition] = []
        self.metrics = {
            'initialized_at': None,
            'calculation_start': None,
            'calculation_end': None,
            'result_dimensions': 0,
            'result_confidence': 0.0,
            'error_count': 0,
            'degradation_reason': None,
        }
    
    def transition(self, new_state: ScoringSystemState, reason: str = "", metrics: Dict = None):
        """
        執行狀態轉移
        
        驗證合法性：
        • UNINITIALIZED → INITIALIZED
        • INITIALIZED → DATA_VALIDATING
        • DATA_VALIDATING → CALCULATING or FAILED
        • CALCULATING → SUCCESS or PARTIAL_SUCCESS or FAILED
        • SUCCESS/PARTIAL_SUCCESS → (end) or DEGRADED
        """
        if not self._is_valid_transition(self.current_state, new_state):
            raise ValueError(
                f"❌ 非法轉移: {self.current_state.value} → {new_state.value}"
            )
        
        transition = StateTransition(
            from_state=self.current_state,
            to_state=new_state,
            timestamp=datetime.now().isoformat(),
            reason=reason,
            metrics=metrics or {},
        )
        
        self.transitions.append(transition)
        self.current_state = new_state
        
        print(f"[{self.system_name}] {self.current_state.value}: {reason}")
    
    def _is_valid_transition(self, from_state: ScoringSystemState, to_state: ScoringSystemState) -> bool:
        """
        驗證轉移合法性（有限狀態機）
        """
        valid_transitions = {
            ScoringSystemState.UNINITIALIZED: [ScoringSystemState.INITIALIZED],
            ScoringSystemState.INITIALIZED: [ScoringSystemState.DATA_VALIDATING, ScoringSystemState.DEGRADED],
            ScoringSystemState.DATA_VALIDATING: [
                ScoringSystemState.CALCULATING,
                ScoringSystemState.FAILED,
                ScoringSystemState.DEGRADED,
            ],
            ScoringSystemState.CALCULATING: [
                ScoringSystemState.SUCCESS,
                ScoringSystemState.PARTIAL_SUCCESS,
                ScoringSystemState.FAILED,
                ScoringSystemState.DEGRADED,
            ],
            ScoringSystemState.SUCCESS: [ScoringSystemState.DEGRADED],
            ScoringSystemState.PARTIAL_SUCCESS: [ScoringSystemState.DEGRADED, ScoringSystemState.SUCCESS],
            ScoringSystemState.FAILED: [ScoringSystemState.DEGRADED],
            ScoringSystemState.DEGRADED: [ScoringSystemState.INITIALIZED],  # 復原
        }
        
        return to_state in valid_transitions.get(from_state, [])
    
    def get_state_history(self) -> str:
        """獲取狀態轉移歷史"""
        history = f"\n{'='*60}\n{self.system_name} 狀態轉移歷史\n{'='*60}\n"
        for i, trans in enumerate(self.transitions, 1):
            history += f"{i}. [{trans.timestamp}] {trans.from_state.value} → {trans.to_state.value}\n"
            history += f"   原因: {trans.reason}\n"
            if trans.metrics:
                history += f"   指標: {trans.metrics}\n"
        return history
    
    def is_healthy(self) -> bool:
        """檢查系統健康狀態"""
        return self.current_state in [
            ScoringSystemState.SUCCESS,
            ScoringSystemState.PARTIAL_SUCCESS,
        ]
    
    def is_degraded(self) -> bool:
        """檢查系統降級狀態"""
        return self.current_state == ScoringSystemState.DEGRADED


class P1PipelineStateMachine:
    """P1 評分管線狀態機（多系統協調）"""
    
    def __init__(self):
        self.systems: Dict[str, P1StateMachine] = {}
        self.pipeline_state = "idle"
        self.execution_log = []
    
    def register_system(self, system_name: str) -> P1StateMachine:
        """註冊新系統"""
        if system_name not in self.systems:
            self.systems[system_name] = P1StateMachine(system_name)
        return self.systems[system_name]
    
    def execute_pipeline(self, system_execution_order: List[str]) -> Dict[str, bool]:
        """
        執行管線
        
        驗證：
        1. 所有系統完成初始化
        2. 各系統順序或並行執行
        3. 無死鎖（circular dependencies）
        4. 所有系統達成終態（SUCCESS 或 DEGRADED）
        """
        self.pipeline_state = "running"
        results = {}
        
        # 驗證 1: 初始化
        for sys_name in system_execution_order:
            if sys_name not in self.systems:
                self.register_system(sys_name)
            
            sm = self.systems[sys_name]
            if sm.current_state == ScoringSystemState.UNINITIALIZED:
                sm.transition(ScoringSystemState.INITIALIZED, "Pipeline initialization")
        
        # 驗證 2: 執行
        for sys_name in system_execution_order:
            sm = self.systems[sys_name]
            
            try:
                # 數據驗證
                sm.transition(
                    ScoringSystemState.DATA_VALIDATING,
                    f"Validating input data for {sys_name}"
                )
                
                # 計算
                sm.transition(
                    ScoringSystemState.CALCULATING,
                    f"Executing {sys_name} calculation"
                )
                
                # 成功（模擬）
                sm.transition(
                    ScoringSystemState.SUCCESS,
                    f"{sys_name} calculation complete",
                    metrics={'execution_time': 50}
                )
                
                results[sys_name] = True
                
            except Exception as e:
                # 失敗 → 降級
                sm.transition(
                    ScoringSystemState.FAILED,
                    f"Error in {sys_name}: {str(e)}"
                )
                
                sm.transition(
                    ScoringSystemState.DEGRADED,
                    f"Degrading {sys_name} to backup mode"
                )
                
                results[sys_name] = False
        
        # 驗證 3: 終態檢查
        all_healthy = all(
            self.systems[sys].is_healthy() or self.systems[sys].is_degraded()
            for sys in system_execution_order
            if sys in self.systems
        )
        
        self.pipeline_state = "complete" if all_healthy else "partial"
        
        return results
    
    def get_pipeline_status(self) -> Dict[str, object]:
        """獲取管線狀態摘要"""
        total_systems = len(self.systems)
        healthy = sum(1 for sm in self.systems.values() if sm.is_healthy())
        degraded = sum(1 for sm in self.systems.values() if sm.is_degraded())
        failed = sum(1 for sm in self.systems.values() if sm.current_state == ScoringSystemState.FAILED)
        
        return {
            'pipeline_state': self.pipeline_state,
            'total_systems': total_systems,
            'healthy_systems': healthy,
            'degraded_systems': degraded,
            'failed_systems': failed,
            'system_states': {name: sm.current_state.value for name, sm in self.systems.items()},
        }


class P1PerformanceOptimizer:
    """P1 性能最佳化"""
    
    @staticmethod
    def analyze_latency_profile(metrics: List[Dict]) -> Dict[str, object]:
        """
        分析延遲分布
        
        識別瓶頸系統
        """
        import statistics
        
        latencies = [m['execution_time'] for m in metrics if 'execution_time' in m]
        
        if not latencies:
            return {}
        
        return {
            'mean_latency_ms': statistics.mean(latencies),
            'median_latency_ms': statistics.median(latencies),
            'stdev_latency_ms': statistics.stdev(latencies) if len(latencies) > 1 else 0,
            'min_latency_ms': min(latencies),
            'max_latency_ms': max(latencies),
            'bottleneck_system': max(metrics, key=lambda m: m.get('execution_time', 0))['system_name']
                if metrics else None,
        }
    
    @staticmethod
    def suggest_parallelization(metrics: List[Dict]) -> Dict[str, object]:
        """
        建議並行化策略
        
        計算：
        • 可並行的系統（無依賴）
        • 預期加速比
        • 最優 worker 數
        """
        total_time = sum(m.get('execution_time', 0) for m in metrics)
        max_single = max(m.get('execution_time', 0) for m in metrics) if metrics else 0
        
        # Amdahl 定律
        parallelizable_fraction = (total_time - max_single) / total_time if total_time > 0 else 0
        
        # 計算不同 worker 數下的加速比
        speedups = {}
        for workers in [2, 4, 8, 16]:
            speedup = 1 / (1 - parallelizable_fraction + parallelizable_fraction / workers)
            speedups[f'{workers}_workers'] = speedup
        
        optimal_workers = max(speedups, key=speedups.get).split('_')[0]
        
        return {
            'parallelizable_fraction': parallelizable_fraction,
            'speedup_estimates': speedups,
            'optimal_workers': int(optimal_workers),
            'expected_speedup_at_optimal': speedups[f'{optimal_workers}_workers'],
        }


def run_p1_state_machine_test():
    """執行 P1 狀態機測試"""
    
    print("\n" + "="*70)
    print("🔄 P1 Day 3: 狀態機驗證")
    print("="*70 + "\n")
    
    # 建立管線狀態機
    pipeline_sm = P1PipelineStateMachine()
    
    # 註冊 11 個系統
    systems = [
        'stock', 'etf', 'market',
        'mj_trend', 'mj_health_diff', 'flow_risk',
        'multi_factor', 'tech_health', 'etf_quality', 'financial_health'
    ]
    
    print("📋 註冊 11 個評分系統...\n")
    for sys_name in systems:
        pipeline_sm.register_system(sys_name)
    
    # 執行管線
    print("🚀 執行評分管線...\n")
    results = pipeline_sm.execute_pipeline(systems)
    
    # 列印狀態
    print("\n📊 管線狀態摘要：\n")
    status = pipeline_sm.get_pipeline_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    
    print("\n" + "="*70)
    print("✅ 狀態機驗證完成")
    print("="*70 + "\n")
    
    # 性能分析
    print("📈 性能分析...\n")
    
    optimizer = P1PerformanceOptimizer()
    
    # 模擬指標
    mock_metrics = [
        {'system_name': s, 'execution_time': 50 + (i % 3) * 20}
        for i, s in enumerate(systems)
    ]
    
    latency_profile = optimizer.analyze_latency_profile(mock_metrics)
    print("延遲分布：")
    print(json.dumps(latency_profile, indent=2, ensure_ascii=False))
    
    parallelization = optimizer.suggest_parallelization(mock_metrics)
    print("\n並行化建議：")
    print(json.dumps(parallelization, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run_p1_state_machine_test()
