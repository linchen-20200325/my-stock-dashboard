# 🏗️ 台股 AI 戰情室 — 技術架構 v2.0

> **版本**：2.0 (Reset)  
> **狀態**：Infrastructure Foundation  
> **最後更新**：2026-06-20  
>
> 本文件為系統架構師視角的**唯讀規格書**，定義物理隔離的模組邊界與依賴關係。

---

## 📋 快速導覽

- [目錄結構](#1-目錄結構)
- [分層架構](#2-分層架構)
- [模組邊界與責任](#3-模組邊界與責任)
- [依賴關係圖](#4-依賴關係圖)
- [資料流向](#5-資料流向)

---

## 1. 目錄結構

### 1.1 物理隔離的模組樹（Class 鐵盒分類法）

```
my-stock-dashboard/
├── src/                          # 應用核心層
│   ├── __init__.py               # Package entrypoint
│   ├── core/                     # 🟢 領域邏輯層 (Domain)
│   │   └── __init__.py           # 業務規則、計算引擎、狀態管理
│   ├── data/                     # 🔵 資料層 (Data Access)
│   │   └── __init__.py           # 資料源、緩存、同步邏輯
│   ├── ui/                       # 🟠 表現層 (Presentation)
│   │   └── __init__.py           # Streamlit 頁面、元件、事件處理
│   └── utils/                    # 🟡 公共工具層 (Common)
│       └── __init__.py           # Logger、Config、Exception、Helper
│
├── config/                       # 🔐 設定管理
│   ├── env.example               # 環境變數樣板
│   └── constants.py              # 全域常數（唯讀）
│
├── docs/                         # 📚 文件
│   ├── ARCHITECTURE.md           # 本檔案
│   ├── STATE.md                  # 進度狀態表
│   ├── API_SPEC.md               # 核心函式 IO 規格
│   └── DEPLOYMENT.md             # 部署指南
│
├── scripts/                      # 🔧 運維腳本
│   └── maintenance.sh            # 清理、初始化、遷移
│
├── tests/                        # ✅ 測試套件
│   ├── unit/                     # 單元測試
│   ├── integration/              # 集成測試
│   └── fixtures/                 # 測試數據
│
├── infra/                        # 🖥️ 基礎設施
│   ├── docker/                   # Docker 配置
│   ├── k8s/                      # Kubernetes 配置
│   └── logs/                     # 運行日誌（自動生成）
│
├── .github/                      # 🤖 CI/CD
│   └── workflows/                # GitHub Actions
│
├── requirements.txt              # Python 依賴
├── pytest.ini                    # 測試配置
├── ARCHITECTURE.md               # 📄 本檔案
├── STATE.md                      # 📄 進度狀態表
└── README.md                     # 快速開始指南
```

---

## 2. 分層架構

### 2.1 整體分層圖

```
┌─────────────────────────────────────────┐
│  🟠 表現層 (Presentation)                │
│     src/ui/ → Streamlit Pages            │
└──────────────┬──────────────────────────┘
               │ (render)
┌──────────────▼──────────────────────────┐
│  🟢 領域邏輯層 (Domain Logic)             │
│     src/core/ → Business Rules           │
│     - 計算引擎                           │
│     - 狀態管理                           │
│     - 決策引擎                           │
└──────────────┬──────────────────────────┘
               │ (fetch/sync)
┌──────────────▼──────────────────────────┐
│  🔵 資料層 (Data Access)                 │
│     src/data/ → Repositories             │
│     - API 集成                           │
│     - 快取管理                           │
│     - 資料轉換                           │
└──────────────┬──────────────────────────┘
               │ (external APIs/DB)
┌──────────────▼──────────────────────────┐
│  外部系統 (External Systems)              │
│  - Yahoo Finance, OpenAI, Database       │
└─────────────────────────────────────────┘

每層均具備：
  ✓ 單一責任原則 (SRP)
  ✓ 依賴注入接口
  ✓ 獨立測試能力
```

---

## 3. 模組邊界與責任

### 3.1 `src/core/` — 領域邏輯層

**責任**：
- ✅ 業務規則編碼
- ✅ 計算引擎（評分、回測、最佳化）
- ✅ 決策邏輯
- ✅ 狀態機管理
- ✅ 領域模型定義

**禁止事項**：
- ❌ 直接調用 API/資料庫
- ❌ UI 邏輯
- ❌ 外部依賴硬編碼

**對外接口**：
```python
# 純函數 + 領域模型
class StockScore:
    ticker: str
    score: float
    factors: Dict[str, float]

def calculate_stock_score(fundamentals: Dict) -> StockScore:
    """無副作用的純計算函式"""
    pass
```

---

### 3.2 `src/data/` — 資料層

**責任**：
- ✅ 外部 API 集成（Yahoo Finance、OpenAI）
- ✅ 資料庫連線管理
- ✅ 緩存策略實施
- ✅ 資料驗證與轉換
- ✅ Repository 模式實現

**禁止事項**：
- ❌ 業務邏輯計算
- ❌ UI 渲染
- ❌ 決策制定

**對外接口**：
```python
class StockRepository:
    def get_financial(self, ticker: str) -> FinancialData:
        """從 API 或緩存取得財務數據"""
        pass
    
    def cache_set(self, key: str, value: Any, ttl: int) -> None:
        """設定快取"""
        pass
```

---

### 3.3 `src/ui/` — 表現層

**責任**：
- ✅ Streamlit 頁面組織
- ✅ UI 元件構建
- ✅ 用戶交互事件處理
- ✅ 數據視覺化

**禁止事項**：
- ❌ 業務邏輯計算
- ❌ 直接 API 調用（應通過 `src.data` 代理）
- ❌ 複雜狀態管理（應通過 `src.core` 代理）

**對外接口**：
```python
def page_stock_detail(stock_repo: StockRepository, 
                      core: CoreEngine):
    """Streamlit 頁面函式"""
    pass
```

---

### 3.4 `src/utils/` — 公共工具層

**責任**：
- ✅ 日誌管理
- ✅ 例外定義
- ✅ 配置管理
- ✅ 通用 Helper 函式
- ✅ 常數定義

**禁止事項**：
- ❌ 業務邏輯
- ❌ 大型工具類（應屬於特定層）

---

## 4. 依賴關係圖

```
src/ui/
   ├─→ src/core/          [業務邏輯]
   ├─→ src/data/          [資料取得]
   ├─→ src/utils/         [工具函式]
   └─→ streamlit          [外部依賴]

src/core/
   ├─→ src/utils/         [工具函式]
   ├─→ numpy, pandas      [數值計算]
   └─→ ❌ 禁止依賴 src/ui/ 或 src/data/

src/data/
   ├─→ src/utils/         [工具函式]
   ├─→ yfinance, requests [外部 API]
   ├─→ redis, sqlalchemy  [持久化]
   └─→ ❌ 禁止依賴 src/ui/ 或 src/core/

src/utils/
   └─→ ❌ 禁止依賴任何層級

【核心規則】：沒有循環依賴。低層級模組對高層級無認知。
```

---

## 5. 資料流向

### 5.1 典型讀取流程

```
Streamlit UI 頁面
    ↓ (用戶查詢)
src/ui/pages/stock_detail.py
    ↓ (inject repositories & engines)
StockRepository.get_financial(ticker)
    ↓ (fetch or cache)
src/data/fetcher.py (Yahoo Finance API)
    ↓ (raw data)
StockRepository.transform(raw)
    ↓ (structured data)
CoreEngine.calculate_score(financial_data)
    ↓ (business logic)
StockScore (domain model)
    ↓ (render)
Streamlit charts & tables
    ↓ (display)
用戶瀏覽
```

### 5.2 典型寫入流程

```
Streamlit Form (用戶輸入)
    ↓
src/ui/handlers/form_handler.py
    ↓ (validate)
src/core/validators.py
    ↓ (if valid)
PortfolioRepository.save(portfolio)
    ↓
src/data/storage.py (DB/Cache)
    ↓
成功確認
    ↓
Streamlit toast message
    ↓
用戶反饋
```

---

## 6. 模組載入順序

```
1️⃣ src/utils/          # 無依賴，優先載入
   └─ Logger, Config, Exceptions

2️⃣ src/core/           # 取決於 src/utils/
   └─ Domain Logic, Engines

3️⃣ src/data/           # 取決於 src/utils/, src/core/
   └─ Repositories, Fetchers

4️⃣ src/ui/             # 取決於 2️⃣ 3️⃣
   └─ Streamlit Pages, Components

5️⃣ app.py              # 應用進入點
   └─ Streamlit entrypoint
```

---

## 7. 配置與常數管理

```
config/
├── env.example                 # 環境變數樣板
├── constants.py                # 全域常數
└── schema.json                 # 資料驗證規則

【使用方式】：
- 環境變數通過 src/utils/config.py 注入
- 常數定義在 config/constants.py（唯讀）
- 敏感信息絕不硬編碼
```

---

## 8. 測試策略

```
tests/
├── unit/
│   ├── test_core_engines.py     # 業務邏輯測試
│   ├── test_data_repos.py       # 資料層測試
│   └── test_utils.py            # 工具層測試
│
├── integration/
│   └── test_end2end.py          # E2E 流程測試
│
└── fixtures/
    └── sample_data.json         # 測試數據

【測試金字塔】：
單元測試 (70%)  ← 快速，隔離
集成測試 (20%)  ← 模組協作
E2E 測試 (10%)  ← 完整流程
```

---

## 9. 推薦依賴清單

```python
# 核心
- python 3.10+
- streamlit 1.28+
- pandas 2.0+
- numpy 1.24+

# 資料層
- yfinance                       # 股市數據
- requests, aiohttp              # HTTP 客戶端
- redis                          # 快取
- sqlalchemy 2.0+                # ORM

# 核心層
- scikit-learn                   # 機器學習
- numpy, scipy                   # 數值計算

# 測試
- pytest 7.0+
- pytest-cov, pytest-asyncio
- mock-data fixtures

# 運維
- python-dotenv                  # 環境配置
- structlog, loguru              # 日誌
```

---

## 10. 重要約定

| 項目 | 規範 |
|------|------|
| **模組命名** | 小寫 + 蛇型 (`stock_scorer.py`) |
| **類別命名** | 大駝峰 (`StockScore`, `DataRepository`) |
| **常數命名** | 全大寫 (`MAX_RETRIES`, `DEFAULT_CACHE_TTL`) |
| **函式命名** | 小寫 + 蛇型 (`calculate_score()`) |
| **檔案位置** | 嚴格按層級分類，禁止跨目錄 |
| **依賴方向** | 只能指向下層或同層，禁止逆向 |
| **循環依賴** | 零容忍 |

---

## 11. 快速檢查清單

每次提交前驗證：

- [ ] 沒有循環依賴
- [ ] 各層職責清晰
- [ ] 單元測試通過 ✅
- [ ] 型別檢查無誤 (`mypy` 或 `pyright`)
- [ ] 代碼遵循 PEP 8
- [ ] 敏感信息未硬編碼
- [ ] 文件已更新

---

**下一步**：見 `STATE.md` 瞭解當前進度與待辦項目。
