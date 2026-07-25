# 台股資料 MCP Server（無頭第二前端）

把本專案**已過「資料完整性憲法」把關**的 L3 service 包成 [MCP](https://modelcontextprotocol.io) 工具，
讓 **Claude Desktop / Cursor** 這類 MCP client 用**對話**直接查台股 —— 數字來自我們多源 fallback +
provenance + fail-loud 的 fetcher，不是 AI 腦內舊記憶。

> 定位：這是 `app.py`（Streamlit 網頁）的 **sibling**，兩者都往下呼叫同一批 L3 service。
> 新增這扇門**不動**現有 L1/L2/L3/UI 任何一行 → 零回歸風險。它是「多開一扇對話門」，
> **不是**網頁上多一個按鈕。

## 工具（唯讀）

| 工具 | 作用 | 對應畫面 |
|---|---|---|
| `screen_stocks(factors, top_n)` | 全台股基本面選股綜合排名 | 選股網「🎯 開始選股」**同源**（`get_ranked_picks`） |
| `forward_test_reconcile()` | 凍結過的選股 vs 0050 事後對帳（零 lookahead） | 前進式驗證對帳面板（`reconcile_all`） |
| `stock_health(stock_id)` | 個股「老師財報體檢」總評（純規則、免金鑰） | 個股 →「財報體檢」（`analyze_financial_health`） |

- `screen_stocks` 的 `factors` 任選：`pe_low`(低估值)、`eps_high`(高EPS)、`shortage`(缺貨動能)、`rs_leader`(抗跌RS)、`trend`(跨季轉強)；留空＝全 5 因子。回傳含 `as_of`(UTC 抓取時間)、`picks`(代碼/名稱/綜合分/各因子分)。
- `stock_health` 回 `grade`(A+/A/B+/C/F) + `score_pct` + 生死指標 `pass_items`/`fail_items`。
- **全部 fail-loud**（§1）：季快照未就緒 / 財報缺料 / 尚無凍結紀錄 → `ok:false`（或空 + note），**不編造清單、不編造評級、不偽造績效**。

## 安裝

```bash
# 在已 pip install -r requirements.txt 的同一環境
pip install -r requirements-mcp.txt
```

## 掛載到 Claude Desktop

編輯設定檔（macOS：`~/Library/Application Support/Claude/claude_desktop_config.json`；
Windows：`%APPDATA%\Claude\claude_desktop_config.json`），加入：

```jsonc
{
  "mcpServers": {
    "台股資料台": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/絕對路徑/my-stock-dashboard"
    }
  }
}
```

> `cwd` 必須是專案根目錄（server 靠它 `import src.*`）。若用 venv，`command` 請填該 venv 的 python 絕對路徑。

重啟 Claude Desktop，即可對話：

- 「幫我用**高 EPS + 跨季轉強**選台股前 15 名」
- 「今天的基本面選股清單有哪些？」
- 「**2330** 的財報體檢結果如何？」
- 「我凍結過的選股，實際**贏 0050** 了嗎？」

## 本機自測（不進 Claude Desktop）

```bash
# 單元守衛（隔絕網路/快照，測 fail-loud 契約 + JSON 序列化）
python -m pytest tests/test_mcp_server_smoke.py -v

# 直接跑 server（stdio，會等 client 連入；Ctrl-C 結束）
python -m mcp_server.server
```

## 邊界與後續

- **唯讀**：只查，不下單、不寫入。
- **資料前提**：`screen_stocks` / `forward_test_reconcile` 需季財報快照（`data_cache/`，由 `update_fundamentals` cron 產）+ 網路可達 TWSE；`stock_health` 需網路可達 FinMind。缺任一 → 回 `ok:false` 說明，不炸。
- **已上線**（v20-MCP W1+W2）：`screen_stocks`、`forward_test_reconcile`、`stock_health`。
- **第三波候選**（未做，等有需求）：總經紅綠燈（`macro_state_locker`，需先補無頭編排：headless 跑 macro 抓取 + `calc_traffic_light` 產 `warroom_summary`，不靠 Streamlit `session_state`）。
