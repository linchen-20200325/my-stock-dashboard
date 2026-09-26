"""shared/secret_scrub.py — L0：要畫上畫面的錯誤字串，先洗掉金鑰／識別碼／路徑（2026-09-26）。

**純函式，零 I/O、零 streamlit、不 import 任何 L1+。**

═══ 為什麼有這一檔 ═══════════════════════════════════════════════════
上游例外以 `repr(e)` 一路傳到卡片的「為什麼」與「▸ 詳細」摺疊區。實證（2026-09-26，
「💼 我的持股」）：secrets.toml 裡有一個非 UTF-8 位元組時，L3 讀 Sheet 識別碼的 `repr(e)` 是
`UnicodeDecodeError('utf-8', b'<整份 secrets 檔原文>', …)` —— **金鑰原文直接上紅卡**。
全站原本唯一的洗法是 L3 `services/ai_qa_service._scrub_secrets`（私有、只洗 URL query 與
`AIza…` 金鑰），L5 不得跨層取私有符號，而且它不涵蓋上面那一種。故下沉成本檔的公開函式。

═══ 兩支，分工不同 ═══════════════════════════════════════════════════
- `scrub_query_secrets()`：**逐字**搬自 `ai_qa_service._scrub_secrets`（regex 一字未改）——
  `ai_qa_service` 改引用它，對任何輸入 **byte-identical**（它原本的行為不在本批改動範圍）。
- `scrub_secrets()`：要畫上畫面的錯誤字串用這一支。= 上一支 ＋ 下列各類（`_RULES` 的順序即執行順序）：
    1. 會把**原始內容**帶出來的例外 —— `UnicodeDecodeError` 等解碼例外（`repr` 含被解碼的整段位元組）、
       `TomlDecodeError`（訊息會串入已解析的整包內容）、Streamlit 的「Error parsing secrets file at …」——
       `型別名(` 或 `型別名:` 起到字串結尾全部拿掉，**只留型別名**（巢狀 `repr` 的跳脫不固定，⛔ 不賭括號配對）；
    2. PEM 私鑰區塊；
    3. `Authorization` 標頭值、`Bearer <token>`、JWT（`eyJ…`）；
    4. URL 的 `user:pass@` 密碼段；
    5. 秘密欄位的值，三種寫法：TOML／INI 賦值（`client_secret = "…"`，含 bytes repr 裡以 `\\n` 分行、
       跳脫引號）、`key: value`／dict／JSON（`'refresh_token': '…'`、`ValueError('password: …')`）、
       URL query（`password=…`）；欄位名含本 repo 真實的 secrets／環境變數名（`_FIELDS_REPO`）；
    6. 裸露的 Google 憑證字樣（`AIza…`、`ya29.…`、`1//…`、`GOCSPX-…`）、OAuth 授權碼（`4/…`）、
       Telegram bot token（`bot<數字>:<token>` 與裸露的 `<數字>:<token>`）；
    7. Google 文件／Drive 的識別碼路徑段（`/spreadsheets/d/<id>`、發佈網址 `/spreadsheets/d/e/<id>`、
       `/spreadsheets/<id>`、`/files/<id>` …）；
    8. 檔案系統路徑：`file://…`、Windows（磁碟機路徑 `C:\\…`／`C:/…`、UNC `\\\\server\\share\\…`）
       → **整段遮到引號／行尾**（路徑可含空白，結尾界定不了就寧可多遮）；
       POSIX 絕對路徑與 `~/…` → 目錄換成遮罩、保留**檔名**，而且**只在合理起點**才算路徑
       （行首、空白、引號、`(`、`=`、`:` 等分隔之後）—— `元/股/張` 這種中文之間的斜線 ⛔ 不動。
  遮罩一律沿用既有的 `***`（`MASK`）。**⛔ 不新增任何說明文字** —— 看得到 `***` 就知道有東西被遮。

⚠️ 據實揭露的邊界（**不是**全稱「洗乾淨了」）：
  · 裸露、沒有任何前後文的 Sheet ID（例如一句「找不到 1AbC…」）**分不出來**，不遮 ——
    硬遮任何 44 字元英數串會把一般訊息洗壞；Drive 的 `open?id=<id>` 同理（`id=` 太泛用）；
  · 相對路徑（`a/b/c.toml`）不遮；緊貼中文字的絕對路徑（`檔案/home/x`）也不遮（為了不誤遮 `元/股`）；
  · 帶主機名的 URL 路徑（`https://host/a/b`）不當檔案路徑遮；**不帶主機名**的路徑
    （例：requests 的 `…with url: /v4/…`）長得跟檔案路徑一樣，會被遮成 `***/<末段>`；
  · 兩層以上的巢狀 `repr` 裡、值本身又含同種引號時，引號配對可能提早結束（只剩值的後半段外露）；
  · 秘密欄位只認下面 `_FIELDS_*` 列出的名字；不在清單上的欄位名（例：自訂的 `my_api_pw`）不遮。

⚠️ 效能：全部規則都是線性掃描（量測見 `tests/test_v2_silent_fail_b11_hold_misc.py` 的 ReDoS 守衛）——
    有「前綴 ＋ 不定長 ＋ 必要結尾」形狀的都設了長度上限或以固定字面錨定起點。
"""
from __future__ import annotations

import re

#: 遮罩字元（沿用 `ai_qa_service._scrub_secrets` 既有的 `***`）。
MASK: str = "***"

# ── 1. 逐字搬自 `services/ai_qa_service.py`（v19.128 修 429 把 ?key=API_KEY 印到 UI）──────
# requests 的 HTTPError str 含完整 URL(含 ?key=<GEMINI_KEY>);直接把 exception 塞進 UI 錯誤字串
# = 金鑰洩漏。⛔ 兩條 regex 一字不改（`ai_qa_service` 引用它們必須 byte-identical）。
QUERY_SECRET_RE = re.compile(r"\b(key|token|api[_-]?key|access[_-]?token)=[^&\s\"'<>]+", re.IGNORECASE)
GOOGLE_API_KEY_RE = re.compile(r"AIza[0-9A-Za-z_\-]{10,}")


def scrub_query_secrets(s) -> str:
    """移除錯誤訊息可能夾帶的金鑰:URL query 的 key=/token=/api_key= 值 + 裸露的 AIza… 金鑰。

    ⛔ 逐字搬自 `ai_qa_service._scrub_secrets`（函式體一字未改），該檔改以本函式為實作。
    """
    out = QUERY_SECRET_RE.sub(lambda m: m.group(1) + "=***", str(s))
    return GOOGLE_API_KEY_RE.sub("AIza***", out)


# ══════════════════════════════════════════════════════════════════
# 2. `scrub_secrets()` 的各類規則
# ══════════════════════════════════════════════════════════════════
_I = re.IGNORECASE
#: 「一個記號的開頭」：前一個字元不是英數／底線，**或**前面是 repr 裡的 `\n`／`\r`／`\t` 跳脫
#: （`b'…\npassword = …'` 的 `password` 前面是字母 `n`，只用 `\b` 會漏掉）。
_TB: str = r"(?:(?<![A-Za-z0-9_])|(?<=\\[nrt]))"
#: 同上，但允許前面是底線（欄位名：`my_password = …` 也算）。
_TB_FIELD: str = r"(?:(?<![A-Za-z0-9])|(?<=\\[nrt]))"

# ── (1) 會帶出原始內容的例外 ─────────────────────────────────────────
_CONTENT_BEARING_EXC_RE = re.compile(
    r"(Unicode(?:Decode|Encode|Translate)Error|TomlDecodeError)[ \t]*[(:].*", re.DOTALL)
#: Streamlit `SecretErrorMessages.error_parsing_file_at_path` 的預設措辭（訊息本文含路徑與 TOML 錯誤）。
_STREAMLIT_PARSE_RE = re.compile(r"(Error parsing secrets file)\b.*", re.DOTALL)

# ── (2) PEM ──────────────────────────────────────────────────────────
_PEM_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)",
    re.DOTALL)

# ── (3) Authorization / Bearer / JWT ─────────────────────────────────
_AUTH_HEADER_RE = re.compile(
    r"(" + _TB + r"Authorization(\\{0,4}[\"'])?[ \t]{0,16}[:=][ \t]{0,16}(?:\\{0,4}[\"'])?)"
    r"((?:Bearer|Basic|Token|Digest|Bot)[ \t]{1,16})?[^\s'\"\\,;}]+", _I)
_BEARER_RE = re.compile(_TB + r"(Bearer)[ \t]{1,16}[A-Za-z0-9\-._~+/]{8,}=*", _I)
_JWT_RE = re.compile(_TB + r"eyJ[A-Za-z0-9_\-]{8,}(?:\.[A-Za-z0-9_\-]*){0,2}")

# ── (4) URL userinfo 密碼段 ────────────────────────────────────────────
#: 只在 `://` 之後才看（固定字面錨定起點 ⇒ 不會對每個字元位置重掃）；長度設上限防回溯。
_USERINFO_RE = re.compile(r"(?<=://)([^\s/:@'\"]{0,256}):[^\s/@'\"]{1,256}@")

# ── (5) 秘密欄位的值 ─────────────────────────────────────────────────
#: 真的是秘密的欄位名（三種寫法都認）。長的放前面（`private_key_id` 先於 `private_key`）。
#: 本 repo 真實用到的 secrets／環境變數名（量測 2026-09-26：grep `st.secrets[…]`／`.secrets.get(…)`／
#: `_safe_secret(…)`／`os.environ…` ＋ 兩份 `secrets.toml.example`）。值是金鑰、帳密、Sheet ID、
#: 聊天對象 ID、或內含 Sheet ID 的發佈網址。⚠️ `[gcp_service_account]`／`[google_oauth]` 是表格名，
#: 值是一整個 dict —— 不列在這裡，靠表內的 `private_key`／`client_secret`… 各欄位擋。
_FIELDS_REPO: str = (
    r"line[_-]?channel[_-]?access[_-]?token|telegram[_-]?bot[_-]?token|telegram[_-]?chat[_-]?id|"
    r"line[_-]?user[_-]?id|gemini[_-]?api[_-]?key(?:[_-]?\d{1,2})?|fred[_-]?api[_-]?key|"
    r"nas[_-]?api[_-]?key|finmind[_-]?token|finmind[_-]?password|finmind[_-]?user|fm[_-]?token|"
    r"stock[_-]?portfolio[_-]?sheet[_-]?id|portfolio[_-]?sheet[_-]?id|"
    r"weekly[_-]?watch[_-]?csv[_-]?url|watchlist[_-]?csv[_-]?url|nas[_-]?proxy[_-]?url|"
    r"proxy[_-]?(?:url|user|pass(?:word)?|host)")
_FIELDS_STRICT: str = (
    _FIELDS_REPO + "|"
    r"refresh[_-]?token|id[_-]?token|access[_-]?token|auth[_-]?token|client[_-]?secret|"
    r"private[_-]?key[_-]?id|private[_-]?key|api[_-]?key|secret|password|passwd")
#: 另外只在「欄位名被引號包住」（dict／JSON）或 TOML 賦值時才認的泛用名。
_FIELDS_QUOTED_EXTRA: str = r"token|spreadsheet[_-]?id|file[_-]?id"
#: URL query：`ai_qa` 那條已涵蓋 key/token/api_key/access_token（`\b` 使它比對不到 `refresh_token=`）。
_EXTRA_QUERY_SECRET_RE = re.compile(
    _TB_FIELD + r"(" + _FIELDS_STRICT + r"|spreadsheet[_-]?id|file[_-]?id|key|token)=[^&\s\"'<>]+", _I)

#: 值的形狀（`key: value` 寫法用）。各分支互斥（反斜線只在 `\\.` 分支出現）⇒ 線性。
#: ⚠️ 所有「一串反斜線」都設上限 `{0,4}`／`{1,4}`，且起點要求前一個字元不是反斜線 ——
#: 不設上限時，100 萬個反斜線的輸入會讓每個起點都回溯整串（實測 O(n²)，跑不完）。
_VALUE: str = (
    r"(?:(?P<dq>\"(?:\\.|[^\"\\\r\n])*\")"
    r"|(?P<sq>'(?:\\.|[^'\\\r\n])*')"
    r"|(?P<eq>(?P<bs>\\{1,4})(?P<qc>[\"'])(?:(?!(?P=bs)(?P=qc))[^\r\n])*(?P=bs)(?P=qc))"
    r"|(?P<open>[\"'\\][^\r\n]*)"
    r"|(?P<bare>[^\s,;&'\"<>(){}\[\]\\]+))")
_COLON_QUOTED_RE = re.compile(
    r"(?P<pre>(?P<fq>(?<!\\)\\{0,4}[\"'])(?:" + _FIELDS_STRICT + "|" + _FIELDS_QUOTED_EXTRA + r")(?P=fq)"
    r"[ \t]{0,16}:[ \t]{0,16})" + _VALUE, _I)
#: 欄位名**沒有**被引號包住（`password: X`、`ValueError('password: X')` —— 前面可以是引號，
#: 只要欄位名後面直接接冒號；`'password': …` 那種由上一條處理，這一條比對不到它）。
_COLON_BARE_RE = re.compile(
    r"(?P<pre>" + _TB_FIELD + r"(?:" + _FIELDS_STRICT + r")[ \t]{0,16}:[ \t]{0,16})" + _VALUE, _I)
#: TOML／INI 賦值：`=` 兩側至少一側有空白，或 `=` 後面緊接引號（純 `a=b` 留給 URL query 那條）。
#: 值 ＝ 三引號字串（到收尾或字串結尾），否則到**這一行的結尾**：真換行、或 repr 裡的 `\n`／`\r`
#: 跳脫（`\\\\` 成對吃掉，所以值裡的字面反斜線不會被誤判成行尾）。
_ASSIGN_RE = re.compile(
    r"(?P<pre>" + _TB_FIELD + r"(?P<fq>(?:(?<!\\)\\{1,4})?[\"']?)(?:" + _FIELDS_STRICT + "|" + _FIELDS_QUOTED_EXTRA
    + r")(?P=fq)(?:[ \t]{1,16}=[ \t]{0,16}|=[ \t]{1,16}|=(?=\\{0,4}[\"'])))"
    r"(?:(?P<tq>\"\"\"|''')[\s\S]*?(?:(?P=tq)|\Z)|(?:\\[^nr\r\n]|[^\\\r\n])*)", _I)

# ── (6) 裸露的 Google 憑證字樣 ────────────────────────────────────────
_GOOGLE_TOKEN_RES: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(_TB + r"ya29\.[0-9A-Za-z_\-.]{10,}"), "ya29." + MASK),
    (re.compile(r"(?:(?<![0-9A-Za-z/])|(?<=\\[nrt]))1//[0-9A-Za-z_\-]{10,}"), "1//" + MASK),
    (re.compile(_TB + r"GOCSPX-[0-9A-Za-z_\-]{10,}"), "GOCSPX-" + MASK),
    #: OAuth 授權碼（`code=4/0Af…`，實際長度約 70）。前面是英數／斜線就不算（`/v4/…`、`Q4/…`、日期）。
    (re.compile(r"(?:(?<![0-9A-Za-z/._\-])|(?<=\\[nrt]))4/[0-9A-Za-z_\-]{20,}"), "4/" + MASK),
    #: Telegram bot token：`https://api.telegram.org/bot<數字>:<35 字>/…`（本 repo `telegram_notify._API`），
    #: 以及裸露的 `<數字>:<30+ 字>`（`14:30` 這類時間只有兩位，碰不到下限）。
    (re.compile(r"(?:(?<![0-9A-Za-z])|(?<=/bot)|(?<=\\[nrt]))\d{5,12}:[A-Za-z0-9_\-]{30,}"), MASK),
)

# ── (7) Google 文件／Drive 識別碼路徑段 ────────────────────────────────
#: 字元集同 `oauth_state._SHEET_ID_RE`（[A-Za-z0-9_-]）；至少 10 字元 —— 不遮 `/spreadsheets/d/edit`。
#: `/d/e/<id>` 是「發佈到網路」的 CSV 網址（本 repo `WATCHLIST_CSV_URL` 類）。
_DOC_ID_RE = re.compile(
    r"(/(?:(?:spreadsheets|document|presentation|forms|file)/d(?:/e)?|spreadsheets|files|folders)/)"
    r"[A-Za-z0-9_\-]{10,}")

# ── (8) 檔案系統路徑 ─────────────────────────────────────────────────
_FILE_URL_RE = re.compile(r"(file://)(?:[^\s'\"<>]*/)?([^\s/'\"<>]*)")
#: Windows 磁碟機路徑（`\`、repr 的 `\\`、或 `/`）與 UNC：整段遮到引號／行尾（可含空白）。
_WIN_PATH_RE = re.compile(
    r"(?:(?<![0-9A-Za-z])|(?<=\\[nrt]))[A-Za-z]:(?:\\{1,2}|/)[^'\"<>|\r\n]*"
    r"|(?:(?<![\\0-9A-Za-z_])|(?<=\\[nrt]))\\{2,4}[A-Za-z0-9][A-Za-z0-9_.$\-]*\\{1,2}[^'\"<>|\r\n]*")
#: POSIX 路徑的「合理起點」：行首、ASCII 分隔、repr 的 `\n`/`\r`/`\t` 跳脫、全形標點。
#: ⛔ 中文字（及英數）緊貼的斜線不算起點 —— `元/股/張`、`80/20`、`TW/US`、`https://host/a` 都不動。
_PATH_START: str = (r"(?:^|(?<=[\s'\"(\[{=:,;<>|`])|(?<=\\[nrt])"
                    r"|(?<=[：（「『，、；]))")
_PATH_SEG: str = r"[^\s/\\'\"<>|:;,()\[\]{}*?]+"
_POSIX_PATH_RE = re.compile(
    _PATH_START + r"(?:~[A-Za-z0-9_.\-]{0,64})?/(?:" + _PATH_SEG + r"/)+(" + _PATH_SEG + r")?",
    re.MULTILINE)


def _mask_value(m: re.Match) -> str:
    """`key: value` 寫法：保留欄位名與分隔、值換成遮罩；有引號就保留同一種引號。"""
    if m.group("dq"):
        return m.group("pre") + '"' + MASK + '"'
    if m.group("sq"):
        return m.group("pre") + "'" + MASK + "'"
    if m.group("eq"):
        _q = m.group("bs") + m.group("qc")
        return m.group("pre") + _q + MASK + _q
    return m.group("pre") + MASK


#: （規則, 取代）—— 依序套用。
_RULES: tuple[tuple[re.Pattern, object], ...] = (
    (_CONTENT_BEARING_EXC_RE, r"\1"),
    (_STREAMLIT_PARSE_RE, r"\1"),
    (_PEM_RE, MASK),
    (_AUTH_HEADER_RE, lambda m: m.group(1) + (m.group(3) or "") + MASK),
    (_BEARER_RE, lambda m: m.group(1) + " " + MASK),
    (_JWT_RE, MASK),
    (_USERINFO_RE, lambda m: m.group(1) + ":" + MASK + "@"),
    (_ASSIGN_RE, lambda m: m.group("pre") + MASK),
    (_COLON_QUOTED_RE, _mask_value),
    (_COLON_BARE_RE, _mask_value),
    (_EXTRA_QUERY_SECRET_RE, lambda m: m.group(1) + "=" + MASK),
)
_RULES_AFTER_QUERY: tuple[tuple[re.Pattern, object], ...] = (
    *_GOOGLE_TOKEN_RES,
    (_DOC_ID_RE, lambda m: m.group(1) + MASK),
    (_FILE_URL_RE, lambda m: m.group(1) + MASK + "/" + m.group(2)),
    (_WIN_PATH_RE, MASK),
    (_POSIX_PATH_RE, lambda m: MASK + "/" + (m.group(1) or "")),
)


def scrub_secrets(text) -> str:
    """要畫上畫面的錯誤字串 → 洗掉金鑰／識別碼／路徑後的字串（純函式）。

    `None` → 空字串（⛔ 不印成 `"None"`）；其餘先 `str()`。各類的定義與邊界見檔頭。
    沒有命中任何一類的字串**原樣回傳**（逐字不動）。
    """
    if text is None:
        return ""
    out = str(text)
    for _re, _rep in _RULES:
        out = _re.sub(_rep, out)
    out = scrub_query_secrets(out)
    for _re, _rep in _RULES_AFTER_QUERY:
        out = _re.sub(_rep, out)
    return out
