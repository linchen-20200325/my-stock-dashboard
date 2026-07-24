"""tests/test_screener_copy_fix.py — v19.167 守衛:選股網過時 / 誤導文案修。

選股網現行流程是「按🎯開始選股時自動掃缺貨/RS」,且缺料因子「不計分、不影響其他因子」
(v19.90)。原字串殘留舊流程假設,會誤導使用者:
- F1:multiselect label 寫「需先於下方掃描」— 與 auto-scan 流程 + 旁邊 help 自相矛盾。
- F2:live note 寫「該因子暫記 0 分」— 與實際「缺料不計分(None 空白)」相反,且引用已移除的
      「下方進階主題選股」區塊。
本測試釘住這兩處誤導字串不得復活,且正確語意在位。
"""
from __future__ import annotations

from pathlib import Path

from src.services.fundamental_screener_service import SCREEN_ANGLE_LABELS

_SVC = (Path(__file__).resolve().parents[1]
        / "src/services/fundamental_screener_service.py").read_text(encoding="utf-8")


def test_angle_labels_no_stale_scan_workflow_text():
    """F1:因子 label 不得再出現與 auto-scan 矛盾的「需先於下方掃描」。"""
    for label in SCREEN_ANGLE_LABELS:
        assert "需先於下方掃描" not in label, f"過時 label 未修:{label}"
    # angle key 契約不變(改的是顯示 label,不是 value)
    assert set(SCREEN_ANGLE_LABELS.values()) == {
        "pe_low", "eps_high", "shortage", "rs_leader", "trend"}


def test_shortage_rs_labels_describe_factor_not_workflow():
    """label 改為描述因子本身(對齊『估值便宜(本益比低)』風格),而非流程步驟。"""
    _by_val = {v: k for k, v in SCREEN_ANGLE_LABELS.items()}
    assert "缺貨動能" in _by_val["shortage"]
    assert "抗跌 RS" in _by_val["rs_leader"]


def test_live_note_no_zero_score_lie_and_no_removed_region():
    """F2:live note 不得說「暫記 0 分」(與實際 None 不計分相反),不得引用已移除區塊。"""
    # 只驗 live 路徑的 note(composite_rank_candidates 的 return out, note 區塊)。
    # 「暫記 0 分」整字串在全檔(含 dead build_candidate_frame)都不該出現。
    assert "暫記 0 分" not in _SVC, "誤導字串『暫記 0 分』與實際計算相反,未修"
    # live note 應改成正確語意
    assert "不計分、不影響其他因子排序" in _SVC


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
