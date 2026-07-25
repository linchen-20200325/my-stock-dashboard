"""mcp_server — 台股資料 MCP Server(無頭第二前端;CasualMarket 啟發,v20 首波)。

把已過「資料完整性憲法」把關的 L3 service 包成 MCP 工具,讓 Claude Desktop /
Cursor 等 MCP client 用對話查台股。定位:app.py(L6 UI)的 sibling —— 兩者都往下
呼叫 L3,現有 L1/L2/L3/UI 一行不動(純新增 orchestrator adapter,零回歸)。

啟動:python -m mcp_server.server   (stdio;供 Claude Desktop 掛載)
依賴:pip install -r requirements-mcp.txt(fastmcp,不進 Streamlit Cloud 部署)
"""
