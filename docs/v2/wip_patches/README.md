# 暫停中的未提交工作（持久副本）

⛔ 這些不是規格、也不是已完成的程式；是**暫停中的半成品**，未 QA、未跑測試、未 commit 進任何分支。
現行狀態與「還缺什麼」以根目錄 `HANDOFF.md` 的「★ 進度總表」(c) c-1 為準。

| 檔 | 軌 | 內容（卡） | 動到的檔 |
|---|---|---|---|
| `S5-F_84f58ea.patch` | S5-F | `find.screen_result` 其餘歧義路徑 | L1 `src/data/stock/yield_pe_fetcher.py`、L3 `src/services/fundamental_screener_service.py`、`src/services/valuation_service.py`、L5 `src/ui/views/page_find.py`（無測試） |
| `S5-W_84f58ea.patch` | S5-W | `why.qa` 安全封鎖／格式錯被吞成「成功＋空」 | L3 `src/services/ai_qa_service.py`、L5 `src/ui/views/page_why.py`、新 `tests/test_v2_silent_fail_b5_why.py` |
| `S5-H_84f58ea.patch` | S5-H | `hold.vix` 抓不到被畫成灰「有效的結果」 | L3 `src/services/dividend_station_service.py`、L5 `src/ui/views/page_hold.py`、`tests/test_p04_hold_v2_cards.py`、新 `tests/test_v2_silent_fail_b5_vix.py` |

**基準**：`origin/main` `84f58ea`（PR #698 merge）。三份互不重疊。

**恢復**（須客戶先解除 2026-09-26 清點令的暫停）：

```
git switch -c <新分支> 84f58ea
git apply docs/v2/wip_patches/S5-H_84f58ea.patch   # 換成要恢復的那一份
```

2026-09-26 二組實測：三份在 `84f58ea` 上 `git apply --check` 皆通過；套用結果與當時的工作區 `/home/user/msd-{f,w,h}` 逐位元組相同。工作區是一次性的，換容器即消失 —— 本目錄才是持久副本。

**授權**：客戶 2026-09-26「【授權：逐卡修失敗源頭，連跑】」批（原文由總管轉述，見 `HANDOFF.md` c-1 表下）；其後被同日清點令（「⛔ 不修 code、⛔ 不開新工作，只清點」）暫停。

恢復並 merge 之後，刪除對應的 patch 檔，並在 `HANDOFF.md` 登記 merge hash。
