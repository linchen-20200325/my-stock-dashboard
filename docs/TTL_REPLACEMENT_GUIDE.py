"""
TTL ?踵??芸?????(Day 2 Task 5)

?牧?瑼???P0 蝚砌??挾 TTL 蝯曹?????桀??芸?????
??19 ??獢?5+ ??@st.cache_data(ttl=...) ?閬?啜?

?蝙?冽撘?
1. ?瑁?甇斗?獢葉????PowerShell ?寥??踵??單
2. ???扼??撠????
3. ?湔敺? import data_config.py

??閬???
- ?湔?? commit ?嗅? branch嚗???皛暸?嚗?
- ?湔敺銵?`pytest tests/` 蝣箔??摰
- ???ttl ?澆??? CACHE_TTL 摮撘嚗?甇Ｙ′蝺函Ⅳ
"""

# ============================================================================
# ???撠”??
# ============================================================================

TTL_REPLACEMENT_MAP = {
    # ttl=900 蝘?(15 ??)
    900: {
        'new_const': "CACHE_TTL['tech_indicators']",  # 1800 蝘?
        'description': '?銵?璅?RSI?A 蝑?',
        'files': ['etf_calc.py'],
    },
    # ttl=1800 蝘?(30 ??)
    1800: {
        'new_const': "CACHE_TTL['financial_data']",
        'description': '璈?鞈???鞈??賂??仿嚗?,
        'files': ['app.py (?典?)', 'hot_money.py'],
    },
    # ttl=3600 蝘?(1 撠?)
    3600: {
        'new_const': "CACHE_TTL['price_data']",
        'description': '?∪???胯 K 蝺?,
        'files': [
            'app.py (?典?)', 'daily_checklist.py', 'data_loader.py',
            'etf_fetch.py', 'tab_etf_margin_simulator.py', 'yf_proxy.py'
        ],
    },
    # ttl=21600 蝘?(6 撠?) ???????daily_snapshot
    21600: {
        'new_const': "CACHE_TTL['daily_snapshot']",
        'description': '???嗚?港縑???仿霈?嚗?,
        'files': ['exit_signals.py', 'monthly_revenue_screener.py'],
    },
    # ttl=86400 蝘?(1 憭?
    86400: {
        'new_const': "CACHE_TTL['daily_snapshot']",
        'description': '?亦?甇瑕?瓷?晞?祈???,
        'files': [
            'chip_radar.py', 'etf_quality.py', 'etf_tab_grp_compare.py',
            'grape_ladder.py', 'health_inspector.py', 'tab_edu.py',
            'tab_stock.py', 'yield_screener.py'
        ],
    },
}

# ============================================================================
# ?owerShell ?芸????研?
# ============================================================================

POWERSHELL_BATCH_REPLACE = r"""
# ????????????????????????????????????????????????????????????????????
# TTL ?寥??踵??單 ???瑁?甇方?砌誑?芸??湔???@st.cache_data(ttl=...) 
# ????????????????????????????????????????????????????????????????????

$basePath = "C:\Users\chen1\.copilot\repos\copilot-worktrees\my-stock-dashboard\linchen-20200325-probable-umbrella"

# Step 1: 撱箇???銵?
$replacements = @{
    '@st\.cache_data\(ttl=900'    = '@st.cache_data(ttl=CACHE_TTL["tech_indicators"]'
    '@st\.cache_data\(ttl=1800'   = '@st.cache_data(ttl=CACHE_TTL["financial_data"]'
    '@st\.cache_data\(ttl=3600'   = '@st.cache_data(ttl=CACHE_TTL["price_data"]'
    '@st\.cache_data\(ttl=21600'  = '@st.cache_data(ttl=CACHE_TTL["daily_snapshot"]'
    '@st\.cache_data\(ttl=86400'  = '@st.cache_data(ttl=CACHE_TTL["daily_snapshot"]'
}

# Step 2: ?????.py 瑼?
Get-ChildItem -Path $basePath -Name "*.py" -Recurse | ForEach-Object {
    $filePath = Join-Path $basePath $_
    $content = Get-Content $filePath -Raw
    
    # ?芾????@st.cache_data(ttl= ??獢?
    if ($content -match '@st\.cache_data\(ttl=') {
        $updated = $content
        $modified = $false
        
        # ????踵?閬?
        foreach ($pattern in $replacements.Keys) {
            $replacement = $replacements[$pattern]
            if ($updated -match $pattern) {
                Write-Host "?? $_ ???菜葫??$pattern嚗??踵?"
                $updated = $updated -replace $pattern, $replacement
                $modified = $true
            }
        }
        
        # 憒?靽格鈭摰對?瑼Ｘ?臬撌?import data_config
        if ($modified) {
            if ($updated -notmatch 'from data_config import CACHE_TTL') {
                Write-Host "??  $_: 蝻箏? 'from data_config import CACHE_TTL'嚗??芸?瘛餃?"
                $updated = $updated -replace "(^import streamlit|\n.*import)", "`$1`nfrom data_config import CACHE_TTL"
            }
            
            # 撖怠?瑼?
            Set-Content -Path $filePath -Value $updated -Encoding UTF8
            Write-Host "??$_ 撌脫??
        }
    }
}

Write-Host "`n???寥??踵?摰?嚗??瑁? pytest 撽?"
"""

# ============================================================================
# ????????乩??喳銵?PowerShell ?單嚗?
# ============================================================================

MANUAL_REPLACEMENT_GUIDE = """
????郊撽?

1. ?冽???敶梢??獢??冽溶??import嚗?
   from data_config import CACHE_TTL

2. 撠?@st.cache_data(ttl=<value>) ?踵??箏??? CACHE_TTL ?蛛?

   蝭? 1嚗?
   # ?踵???
   @st.cache_data(ttl=CACHE_TTL["price_data"])
   def load_data():
       ...
   
   # ?踵?敺?
   @st.cache_data(ttl=CACHE_TTL['price_data'])
   def load_data():
       ...

   蝭? 2嚗??隞??賂?嚗?
   # ?踵???
   @st.cache_data(ttl=CACHE_TTL["financial_data"], max_entries=10)
   def fetch():
       ...
   
   # ?踵?敺?
   @st.cache_data(ttl=CACHE_TTL['financial_data'], max_entries=10)
   def fetch():
       ...

3. 璅∠?撅斤???TTL 撣豢?踵?嚗?憒?_PROXY_TTL = 60嚗?
   # ?踵???
   _PROXY_TTL = 60
   
   # ?踵?敺?
   from data_config import CACHE_TTL
   _PROXY_TTL = CACHE_TTL['proxy_fallback']  # 60 蝘?

4. ?踵?摰?敺??瑁?皜祈岫嚗?
   pytest tests/ -v

??獢??柴??????嚗?
Tier 1 (?詨?)嚗?
  - data_loader.py       (2 ??ttl=3600)
  - app.py               (瘛瑕? 1800/3600)
  - daily_checklist.py   (2 ??ttl=3600)

Tier 2 (?豢?撅?嚗?
  - etf_fetch.py         (1 ??ttl=3600)
  - yf_proxy.py          (1 ??ttl=3600)
  - hot_money.py         (1 ??ttl=1800)

Tier 3 (閮?撅?嚗?
  - etf_calc.py          (1 ??ttl=900)
  - exit_signals.py      (1 ??ttl=21600)
  - monthly_revenue_screener.py (1 ??ttl=21600)

Tier 4 (UI 撅?嚗?
  - tab_etf_margin_simulator.py (1 ??ttl=3600)
  - chip_radar.py        (1 ??ttl=86400)
  - etf_quality.py       (1 ??ttl=86400)
  - etf_tab_grp_compare.py (1 ??ttl=86400)
  - grape_ladder.py      (1 ??ttl=86400)
  - health_inspector.py  (1 ??ttl=86400)
  - tab_edu.py           (1 ??ttl=86400)
  - tab_stock.py         (1 ??ttl=86400)
  - yield_screener.py    (1 ??ttl=86400)
"""

if __name__ == '__main__':
    print("""
    ??????????????????????????????????????????????????????????
    ?? P0 Task 5: TTL 蝯曹??????芸?????                    ??
    ?? ??19 ??獢?5+ ??@st.cache_data ??湔              ??
    ??????????????????????????????????????????????????????????
    
    ???
    1. ?芸??寥??踵?嚗?佗?: 銴ˊ POWERSHELL_BATCH_REPLACE 隞?Ⅳ
    2. ?????踵?: ? MANUAL_REPLACEMENT_GUIDE ?瑁?
    
    ??銝甇乓?
    - ?踵?摰?敺??? pytest 蝣箔??甇?虜
    - ?瑁? git diff 瑼Ｚ?霈
    - ?漱 PR ?脰? code review
    """)

