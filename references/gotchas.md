# 踩過的坑 (Gotchas) — 重構踩雷筆記

> 本檔為「漸進揭露」機制的一部分:CLAUDE.md / PROCESS.md 只寫核心規矩,
> **具體踩過的坑**收在這裡。動大檔拆分 / 搬移 / monkeypatch 前,先掃一遍本檔。
> 每條 = 一次真實付出代價的教訓(附 `file:symbol` 錨點,可追溯)。
>
> ⚠️ 收錄門檻:**真的踩過並修過**才寫(對齊 §-1「沒實際 bug 不要動」)。
> 禁止把假想風險 / 教科書通則塞進來充數。

---

## G1. AST 依賴分析會漏 `ast.AnnAssign`(帶型別註解的 module-state)

**場景**:大檔拆分前用 AST free-variable 分析算某函式的外部依賴,決定能否安全抽出。

**坑**:自製 AST 掃描器若只處理 `ast.Assign`,會**漏掉帶型別註解的 module 級變數**:
```python
_T86_DAY_CACHE: dict = {}   # ← ast.AnnAssign,不是 ast.Assign
_T86_FAIL_TS:   dict = {}
```
結果:函式(`_get_t86_day`)搬去新模組,但它依賴的**進程級快取狀態留在原檔** →
函式讀到的是新模組裡不存在 / 分裂的狀態。

**如何被逮**:`test_review_fixes_v19_80::test_transient_fail_uses_fail_ts_not_day_cache`
(負快取行為測試)當場抓包——搬完狀態沒跟著走,負快取窗失效。

**教訓**:
- AST 收集 module names 時,`ast.Assign` **和** `ast.AnnAssign` 都要算。
- 拆檔時,函式的**可變 module-state 必須跟著函式一起搬**,不能只搬函式體。
- 有負快取 / 進程級快取的模組,拆完務必跑其狀態相關測試。

**Evidence**:B8-b v19.156,`src/data/core/data_loader_inst_fetchers.py`
(`_T86_DAY_CACHE` / `_T86_FAIL_TS` 已隨 `_get_t86_day` 一起搬入)。

---

## G2. PEP 562 `__getattr__` 轉發套件 → monkeypatch 不能打套件本身

**場景**:`src/data/**` 各套件 `__init__.py` 用 PEP 562 lazy `__getattr__`
(`_SUBMODULES=(...)` + `def __getattr__(name)`)把子模組函式轉發到套件命名空間,
避免 eager import 造成的循環依賴。

**坑**:測試若 `monkeypatch.setattr('src.data.proxy.cached_dividends', ...)`,
會在**套件物件上建立一個實體屬性**,遮蔽掉 PEP 562 轉發 →
`test_zz_proxy_pollution_lock` 專門鎖這個(它斷言套件命名空間**不得**有實體屬性
遮蔽轉發),CI Fast-checks 直接紅。

**如何被逮**:CI Fast-checks `test_zz_proxy_pollution_lock::test_proxy_forwarding_not_shadowed_fast`
(commit 44ae223 紅 → 736eeb2 修)。錯誤訊息會直接點名該打哪裡。

**教訓**:
- monkeypatch 走 PEP 562 轉發的符號時,**patch 真正的持有者模組**
  (`src.data.proxy.yf_proxy.cached_dividends`),**不是**套件(`src.data.proxy.*`)。
- 消費端照樣 `from src.data.proxy import cached_dividends` 沒問題——那是**讀**取轉發;
  問題只出在對套件**寫**入實體屬性。

**Evidence**:`tests/test_picker_check_one_stock.py`(已改 patch `yf_proxy` 持有者)、
`tests/test_zz_proxy_pollution_lock.py`(守衛)。

---

## G3. 大檔拆分:共享可變 module-state 決定「哪些函式可安全抽出」

**場景**:B8 想把 data_loader 的一批 raw fetcher 抽去新模組。

**坑**:8 個候選裡,3 個 FinMind fetcher(`_fetch_finmind_*`)與
`_capture_finmind_meta` / `_FINMIND_META`(module 級可變 dict)**共享寫入狀態**——
writer 若搬走、reader 留在 `StockDataLoader`(或反之)→ **狀態分裂 = bug**。

**決策(誠實縮範圍)**:只抽**零共享狀態**的 5 個 TWSE/TPEX fetcher,
共享 `_FINMIND_META` 的那 3 個**刻意留在原檔**,不硬拆。

**教訓**:
- 拆檔前先問:候選函式群之間有沒有**共享可變 module-state**?
  有 → 該群是一個不可分割單元,要嘛整群搬、要嘛整群留。
- 藍圖範圍是**探針後才定案**的,不是動工前拍板的。誠實縮範圍 > 硬湊數量。

**Evidence**:B8-b v19.156 STATE.md 條目;`_FINMIND_META` 相關 fetcher 仍在
`src/data/core/data_loader.py`。

---

## G4. Guard test 常把 provenance 字串 / 行號釘死成 source-text 斷言

**場景**:搬檔 / 改 provenance log 字串。

**坑**:很多守衛測試不是測**行為**,而是 `assert '某字串' in open(檔).read()`——
釘死了:
- provenance 血緣字串(如 `'src.data.core.data_loader.X'`)
- 具體行號引用(如 `_normalize_inst_pivot L286`)
- SSOT-import marker

一搬檔,這些 source-text 斷言**全部**跟著碎,即使實際行為沒變。

**教訓**:
- 搬檔 / 改 log 字串時,**同步 grep 所有釘死該字串的 guard test** 一起改。
- 改完 provenance 字串,務必更新對應 `assertIn(...)`——這是誠實血緣的一部分,
  不是為了讓測試變綠而亂改。
- 新寫 guard test 時,能測行為就別測 source text;非測 source text 不可時,
  在測試裡註明它釘的是哪個檔的哪個字串,方便日後搬移時定位。

**Evidence**:B8 期間同步更新 `tests/test_pr_q5b_batch_provenance.py`、
`tests/test_pr_o1_foreign_buy_ssot.py`、`tests/test_review_fixes_v19_80.py`、
`tests/test_pr_q5c_singles.py`。
