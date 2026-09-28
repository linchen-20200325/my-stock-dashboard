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
    9. 補洞（SEC-r1／SEC-r2-f1，2026-09-27，`_RULES_POST`，**最後才跑** ⇒ 不會比舊版少遮）：全形 `：`／`＝`、
       `%3D`、「欄位＋遮罩＋說明字＋權杖」、無 `/` 的 `bot<數字>:<token>`、`open?id=`、`//server/…`、
       `@`／`→`／`—` 起點的路徑。
   10. 補洞 S2-f2（2026-09-28，同樣排在 `_RULES_POST` 的最後 ⇒ 不會比舊版少遮）：
       (a) 目錄名含空白的 POSIX 路徑（`/Users/Jane Doe/app/…/secrets.toml` → 目錄整串遮、只留末段）；
       (b) 沒有標頭的 PEM／DER base64 本體（`MIIEvQ…`，`M[A-P]` 開頭、合計 ≥60 字，可跨行）→ 整段遮；
       (c) 深層巢狀的秘密欄位：引號前 5～32 個反斜線（`repr` 第 5～7 層、JSON 第 4～6 層）的
           `{'password': …}`／`"password" = …`，以及「`password=` 緊接深層跳脫引號」這種值外露的賦值。
  遮罩一律沿用既有的 `***`（`MASK`）。**⛔ 不新增任何說明文字** —— 看得到 `***` 就知道有東西被遮。

⚠️ 據實揭露的邊界（**不是**全稱「洗乾淨了」）：
  · 裸露、沒有任何前後文的 Sheet ID（例如一句「找不到 1AbC…」）**分不出來**，不遮 ——
    硬遮任何 44 字元英數串會把一般訊息洗壞；泛用的 `id=` 同理（`open?id=`／`uc?id=` 已由第 9 類遮）；
  · ~~SEC-r1 仍未處理（2026-09-27）：目錄名含空白的 POSIX 路徑、無標頭的 PEM 本體、第 5 層巢狀 `repr`；~~
    → S2-f2（2026-09-28）已補這三種（第 10 類），但各自仍有邊界：
    目錄名裡有連續空白、開頭／結尾是空白、超過 5 個字、或含 `'`／`,`／`;`／`:`／`[]{}` 等字元 → 那一段起仍外露；
    PEM／DER 只認得**從開頭**（`M[A-P]…`）起的本體 —— 只截到中間幾行、或非 DER 格式
    （OpenSSH 的 `b3BlbnNzaC1rZXkt…`、PGP）認不出來；貼成一行（空白分隔）時，最後一段若 <16 字
    又沒有 `=` 補位，分不出是不是說明字 → 那一段（≤15 字）外露；
    引號前的反斜線超過 32 個（`repr` 第 8 層、JSON 第 7 層起）仍外露；
    「`password=` 緊接深層跳脫引號」那一條只往後看 256 字找收尾；
  · 第 10 類 (a) 的反方向（多遮，安全側）：路徑後面 5 個字內又出現 `/` 時，中間那段會被當成目錄遮掉
    （`***/x.toml 或 y/z` → `***/z`）；(b) 的反方向：`M[A-P]` 開頭、≥60 字的 base64 形字串一律遮；
  · 相對路徑（`a/b/c.toml`）不遮；緊貼中文字的絕對路徑（`檔案/home/x`）也不遮（為了不誤遮 `元/股`）；
  · 帶主機名的 URL 路徑（`https://host/a/b`）不當檔案路徑遮；**不帶主機名**的路徑
    （例：requests 的 `…with url: /v4/…`）長得跟檔案路徑一樣，會被遮成 `***/<末段>`；
  · 兩層以上的巢狀 `repr` 裡、值本身又含同種引號時，引號配對可能提早結束（只剩值的後半段外露）；
  · 秘密欄位只認下面 `_FIELDS_*` 列出的名字；不在清單上的欄位名（例：自訂的 `my_api_pw`）不遮。

⚠️ 效能：全部規則都是線性掃描（量測見 `tests/test_v2_silent_fail_b11_hold_misc.py` 的 ReDoS 守衛；
    第 10 類另見 `tests/test_sec_s3_0928.py`）——
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
#: SEC-r2（2026-09-27）：`neg` 分支 —— 值是 `not set`／`no key` 這類「not／no ＋ 一個英文字」時，
#: **整段**遮成遮罩。原本只遮第一個字（`api_key: not set` → `api_key: *** set`），
#: 畫面讀起來像「金鑰已設定」、方向相反。⛔ 不放行（放行 = 放寬遮罩）；只把遮罩範圍擴大到那個字。
#: 長度皆有上限（`{1,4}`／`{1,32}`）⇒ 線性。
#: ⚠️ 結尾的否定前瞻：那個字後面若還接著英數／`-._:/\\=`（例 `no AIza…`、`not ya29.…`、`no C:\\…`），
#: 它是**真秘密的開頭**、不是說明字 → ⛔ 不走本分支（否則吃掉前綴字母，後面的權杖／路徑規則就對不上）。
#: ⚠️ 所有「一串反斜線」都設上限 `{0,4}`／`{1,4}`，且起點要求前一個字元不是反斜線 ——
#: 不設上限時，100 萬個反斜線的輸入會讓每個起點都回溯整串（實測 O(n²)，跑不完）。
_VALUE: str = (
    r"(?:(?P<dq>\"(?:\\.|[^\"\\\r\n])*\")"
    r"|(?P<sq>'(?:\\.|[^'\\\r\n])*')"
    r"|(?P<eq>(?P<bs>\\{1,4})(?P<qc>[\"'])(?:(?!(?P=bs)(?P=qc))[^\r\n])*(?P=bs)(?P=qc))"
    r"|(?P<open>[\"'\\][^\r\n]*)"
    r"|(?P<neg>(?:not|no)[ \t]{1,4}[A-Za-z]{1,32}(?![A-Za-z0-9_\-.:/\\=]))"
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


#: 恰好兩個 `*`（`***` 遮罩不算粗體標記）。
_BOLD_RE = re.compile(r"(?<!\*)\*\*(?!\*)")
_BOLD_LOOKBACK: int = 512


def _mask_assign(m: re.Match) -> str:
    """TOML／INI 賦值：值換成遮罩。

    SEC-r10（2026-09-27）：值一路吃到行尾，會把同行的**收尾粗體標記**一起吃掉
    （`- **client_secret = abc** — 說明` → `- **client_secret = ***`，粗體沒收尾）。
    只在「欄位名前、同一行裡有一個**未收尾**的 `**`」時，把值裡的第一個 `**` 當收尾標記留下：
    `遮罩 ＋ ** ＋（後面若還有字 → 遮罩；只剩空白 → 原樣）`。
    ⛔ **不放寬**：`**` 與空白以外的字一個都不露（`**` 後面的字仍整段遮）；值是引號字串時，
    `**` 必須在收尾引號之後（引號內的 `**` 可能是秘密本身）→ 否則照舊整段遮。
    """
    _pre, _val = m.group("pre"), m.group(0)[len(m.group("pre")):]
    if m.group("tq") is None:
        _s, _p = m.string, m.start()
        #: 這一行的起點（真換行，或 repr 裡的 `\n`／`\r` 跳脫）。⚠️ 只往回看 `_BOLD_LOOKBACK` 字 ——
        #: 不設上限時，同一行上百萬字、每個賦值都往回掃到行首 ⇒ O(n²)（實測 2MB 跑 100 秒）。
        #: 看不到行首就以視窗起點為準；算錯頂多多留／少留一個 `**`，秘密字元照樣全遮。
        _lo = max(0, _p - _BOLD_LOOKBACK)
        _line0 = max([_s.rfind(_c, _lo, _p) + len(_c) for _c in ("\n", "\r", "\\n", "\\r")
                      if _s.rfind(_c, _lo, _p) >= 0] or [_lo])
        if len(_BOLD_RE.findall(_s, _line0, _p)) % 2 == 1:
            _b = _BOLD_RE.search(_val)
            if _b is not None:
                _a, _rest = _val[:_b.start()].rstrip(" \t"), _val[_b.end():]
                _body = _a.lstrip("\\")
                _q = _body[:1]
                if _body and (_q not in "\"'" or (len(_body) >= 2 and _body.endswith(_q))):
                    _ws = _rest[:len(_rest) - len(_rest.lstrip(" \t"))]
                    return _pre + MASK + "**" + (_rest if _ws == _rest else _ws + MASK)
    return _pre + MASK


#: （規則, 取代）—— 依序套用。
_RULES: tuple[tuple[re.Pattern, object], ...] = (
    (_CONTENT_BEARING_EXC_RE, r"\1"),
    (_STREAMLIT_PARSE_RE, r"\1"),
    (_PEM_RE, MASK),
    (_AUTH_HEADER_RE, lambda m: m.group(1) + (m.group(3) or "") + MASK),
    (_BEARER_RE, lambda m: m.group(1) + " " + MASK),
    (_JWT_RE, MASK),
    (_USERINFO_RE, lambda m: m.group(1) + ":" + MASK + "@"),
    (_ASSIGN_RE, _mask_assign),
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


# ══════════════════════════════════════════════════════════════════
# 3. 補洞規則（SEC-r1／SEC-r2-f1，2026-09-27）—— **在上面全部跑完之後**才套用
# ══════════════════════════════════════════════════════════════════
#: ⚠️ 為什麼放在最後、而不是塞進上面的規則：新規則若先搶走一段字，原本會由後面規則
#: 「遮到行尾／遮到引號」的較大範圍就對不上，結果反而**遮得比以前少**（語料實測踩過）。
#: 放在最後 ⇒ 輸入就是舊版的輸出，每一條只會把字換成遮罩 ⇒ 不會比舊版少遮。
#: 全形分隔（`password：X`、`password＝X`）—— 同上面三條，只是分隔符換成全形。
_FW_ASSIGN_RE = re.compile(
    r"(?P<pre>" + _TB_FIELD + r"(?P<fq>(?:(?<!\\)\\{1,4})?[\"']?)(?:" + _FIELDS_STRICT + "|" + _FIELDS_QUOTED_EXTRA
    + r")(?P=fq)[ \t]{0,16}＝[ \t]{0,16})"
    r"(?:(?P<tq>\"\"\"|''')[\s\S]*?(?:(?P=tq)|\Z)|(?:\\[^nr\r\n]|[^\\\r\n])*)", _I)
_FW_COLON_QUOTED_RE = re.compile(
    r"(?P<pre>(?P<fq>(?<!\\)\\{0,4}[\"'])(?:" + _FIELDS_STRICT + "|" + _FIELDS_QUOTED_EXTRA + r")(?P=fq)"
    r"[ \t]{0,16}：[ \t]{0,16})" + _VALUE, _I)
_FW_COLON_BARE_RE = re.compile(
    r"(?P<pre>" + _TB_FIELD + "(?:" + _FIELDS_STRICT + r")[ \t]{0,16}：[ \t]{0,16})" + _VALUE, _I)
#: URL 編碼的等號（`password%3Dhunter2`）。
_PCT_QUERY_SECRET_RE = re.compile(
    _TB_FIELD + r"(" + _FIELDS_STRICT + r"|spreadsheet[_-]?id|file[_-]?id|key|token)(%3[Dd])[^&\s\"'<>]+", _I)
#: SEC-r2-f1：`password: no bot123456789:<token>` —— 舊版只把第一個說明字遮掉（`password: *** bot…`），
#: 後面的權杖外露。「欄位名＋分隔＋遮罩」之後 ≤3 個短英文字，再接一個「像權杖」的字串
#: （16～256 字、含數字）→ 整段併進遮罩。長度皆有上限 ⇒ 線性。
_CRED_AFTER_MASK_RE = re.compile(
    r"(" + _TB_FIELD + r"(?:" + _FIELDS_STRICT + r")[\"']?[ \t]{0,16}[:：=＝][ \t]{0,16}[\"']?)"
    + re.escape(MASK) + r"(?!\*)[ \t]{1,4}(?:[A-Za-z]{1,16}[ \t]{1,4}){0,3}"
    r"(?=[A-Za-z0-9_\-.:+/=]{0,256}\d)[A-Za-z0-9_\-.:+/=]{16,256}(?![A-Za-z0-9_\-.:+/=])", _I)
#: 不帶 `/` 的 `bot<數字>:<token>`（舊版只認 `/bot` 與前面非英數兩種起點；`/bot` 仍由舊規則負責）。
_TG_BOT_PREFIX_RE = re.compile(r"(?<=[Bb][Oo][Tt])(?<!/[Bb][Oo][Tt])[0-9]{5,12}:[0-9A-Za-z_\-]{30,}")
#: Drive 的 `open?id=<id>`／`uc?id=<id>`（只認這兩個固定字面，`id=` 本身太泛用）。
_DRIVE_OPEN_ID_RE = re.compile(r"(?<![A-Za-z0-9_])((?:open|uc)\?id=)[A-Za-z0-9_\-]{10,}")
#: 正斜線 UNC `//server/share/…` → 同 POSIX：目錄遮、留末段。起點**不含** `:`／`/`
#: （`https://host/…` 的 `//` 前面是 `:`，⛔ 不動）。
_FWD_UNC_RE = re.compile(
    r"(?:^|(?<=[\s'\"(\[{=,;<>|`@])|(?<=\\[nrt])|(?<=[：（「『，、；→—]))"
    r"//[A-Za-z0-9][A-Za-z0-9_.$\-]{0,255}(?:/" + _PATH_SEG + r"){0,64}/(" + _PATH_SEG + r")?",
    re.MULTILINE)
#: `@`／`→`／`—` 之後的 POSIX 路徑（`see @/home/…`、`→/etc/…`）。
_POSIX_PATH_EXTRA_RE = re.compile(
    r"(?<=[@→—])(?:~[0-9A-Za-z_.\-]{0,64})?/(?:" + _PATH_SEG + r"/)+(" + _PATH_SEG + r")?")

# ── 補洞 S2-f2（2026-09-28）：三種少遮形態 —— 同樣排在最後，輸入就是上面全部跑完的輸出 ──
#: (c) 深層巢狀 `repr`／JSON 的 `{'password': …}`：每多包一層，引號前的反斜線變成 2n+1 個
#: （0、1、3、7、15、31…）。上面的規則只認 ≤4 個 ⇒ 7 個起（`repr` 第 5 層、JSON 第 4 層）整段外露。
#: 本條只認「5～32 個反斜線＋引號」包住的欄位名（上限 32 ⇒ 多涵蓋 3 層；再深仍外露，見檔頭邊界），
#: 分隔 `:`／`：`／`=`／`＝`；值 ＝ 同一串「反斜線＋引號」包住的字串，找不到收尾就遮到行尾。
#: 收尾必須是**剛好**同長的反斜線串（前一個字不是反斜線）—— 值裡更深一層的引號（反斜線更多）不算收尾。
#: 線性：起點要求前一個字不是反斜線、反斜線串長度有上限；值掃到收尾或行尾就整段吃掉，不會重掃。
_DEEP_QUOTED_FIELD_RE = re.compile(
    r"(?P<pre>(?<!\\)(?P<bs>\\{5,32})(?P<qc>[\"'])(?:" + _FIELDS_STRICT + "|" + _FIELDS_QUOTED_EXTRA
    + r"|authorization)(?P=bs)(?P=qc)[ \t]{0,16}[:：=＝][ \t]{0,16})"
    r"(?:(?P<eq>(?P=bs)(?P=qc)(?:(?!(?<!\\)(?P=bs)(?P=qc))[^\r\n])*(?<!\\)(?P=bs)(?P=qc))|[^\r\n]*)", _I)
#: (c) 同一類的 `password=\\\\\\\'x\\\\\\\'`（欄位名不加引號、`=` 兩側無空白、值的引號是深層跳脫）：
#: `_ASSIGN_RE` 的前瞻只認 ≤4 個反斜線 → 落到 URL query 那條，它只吃到引號前（`password=***'x…`），值外露。
#: 本條認「欄位＝遮罩＋引號」之後、256 字內以「5～32 個反斜線＋同一種引號」收尾的那一段 → 併進遮罩。
#: 256 字上限 ⇒ 每個起點最多掃 256 字 ⇒ 線性。
_DEEP_ASSIGN_TAIL_RE = re.compile(
    r"(" + _TB_FIELD + r"(?:" + _FIELDS_STRICT + r"|spreadsheet[_-]?id|file[_-]?id|key|token)(?:=|%3[Dd]))"
    + re.escape(MASK) + r"(?P<qc>[\"'])[^\r\n]{0,256}?(?<!\\)\\{5,32}(?P=qc)", _I)
#: (b) 沒有 `-----BEGIN …-----` 標頭的 PEM／DER base64 本體（`MIIEvQIBADANBgkq…`）。
#: DER 一律以 SEQUENCE（0x30）開頭 ⇒ base64 第一個字必為 `M`、第二個字落在 `A`～`P`。
#: 可跨行：真換行、`repr`／JSON 的 `\n` 跳脫（反斜線 ≤32 個）、或貼成一行時「空白＋下一段」（條件見下）。
#: base64 字元合計 ≥ `_DER_B64_MIN` 才遮（`MACD`、`MA20` 這類短字原樣）；整段換成一個遮罩。
#: ⚠️ 本體裡**已經被前面規則換成遮罩的片段**（`***`）也算本體的一部分：base64 含 `/`，某一行剛好以 `/`
#: 開頭（每行約 1/64）時，前面的路徑規則會先把它遮成 `***/…`；不把 `***` 收進來，本體就在那裡斷掉、
#: 後面各行外露（`1//…`、`4/…`、`eyJ…`、`AIza…` 同理）。
#: 空白續行（貼成一行）的下一段須「≥16 個 base64 字」、「前 16 字內有 `***`」（`4/***`、`1//***`）、
#: 或「短段以 `=` 補位收尾」（最後一行）—— 否則當成後面的說明字，不吃。
#: 線性：每一輪的開頭（換行／反斜線／空白）都不在本體字元（base64 或 `***`）裡 ⇒ 切法唯一，沒有回溯分岔；
#: 空白續行的前瞻最多看 18 字。
_DER_B64_MIN: int = 60
_B64_CHUNK: str = r"(?:[A-Za-z0-9+/]|\*\*\*)"
_DER_B64_RE = re.compile(
    r"(?:(?<![A-Za-z0-9+/])|(?<=\\[nrt]))M[A-P]" + _B64_CHUNK + r"*"
    r"(?:(?:\r?\n|(?:\\{1,32}r)?\\{1,32}n)[ \t]{0,16}" + _B64_CHUNK + r"+"
    r"|[ \t]{1,4}(?=[A-Za-z0-9+/]{16}|[A-Za-z0-9+/]{0,15}\*\*\*|[A-Za-z0-9+/]{1,15}=)" + _B64_CHUNK + r"+)*"
    r"={0,2}")
_DER_B64_SEP_RE = re.compile(r"\\+[nr]|[\s=*]")
#: (a) 目錄名含空白的 POSIX 路徑（`/Users/Jane Doe/app/.streamlit/secrets.toml`）：舊版路徑段不收空白，
#: 只遮到第一個空白（`***/Jane Doe/app/.streamlit/secrets.toml`）。本條在「路徑遮罩 `***` 之後」
#: 或「合理起點」（同 `_PATH_START`，另加 `@`／`→`／`—`）接一串**以 `/` 收尾**的段 —— 段內可有
#: 單一半形空白隔開的 ≤5 個字 —— 整串併進遮罩、只留末段（末段不吃空白：`***/x.toml 讀取失敗` 不動）。
#: 目錄段的字另外允許 `(`／`)`（`Dropbox (Personal)`、`Program Files (x86)`）；末段仍用 `_PATH_SEG`，
#: 所以 `(see /a/b)` 的 `)` 照舊不算進路徑。`@`／`→`／`—` 不算字（它們是上面 `_POSIX_PATH_EXTRA_RE`
#: 的路徑起點：`x.toml @/home/…` 的 `@` 後面是另一條路徑，⛔ 不是「`x.toml @`」這個目錄名）。
#: ⚠️ 只在「某個目錄段真的含空白」時才遮（`_mask_space_dirs`）；沒有空白的路徑原樣交還 ——
#: 那是上面各條路徑規則的職責，本條 ⛔ 不重複遮（否則拔掉舊規則也看不出外露，舊規則的守衛就失效）。
#: 線性：字裡沒有空白與 `/` ⇒「空白＋字」與段尾的 `/` 開頭互斥，切法唯一；比對一律成功並吃掉整段，不會重掃。
_SP_DIR_WORD: str = r"[^\s/\\'\"<>|:;,\[\]{}*?@→—]+"
_SP_DIR_SEG: str = _SP_DIR_WORD + r"(?: " + _SP_DIR_WORD + r"){0,4}"
_POSIX_SPACE_DIR_RE = re.compile(
    r"(?:(?:(?<![*A-Za-z0-9_])|(?<=\\[nrt]))" + re.escape(MASK) + r"|(?:" + _PATH_START
    + r"|(?<=[@→—]))(?:~[A-Za-z0-9_.\-]{0,64})?)"
    r"/(?:" + _SP_DIR_SEG + r"/)+(" + _PATH_SEG + r")?", re.MULTILINE)


def _mask_deep_value(m: re.Match) -> str:
    """`_DEEP_QUOTED_FIELD_RE`：保留欄位名與分隔；值有收尾 → 保留同一串反斜線＋引號，否則遮到行尾。"""
    if m.group("eq"):
        _q = m.group("bs") + m.group("qc")
        return m.group("pre") + _q + MASK + _q
    return m.group("pre") + MASK


def _mask_der_b64(m: re.Match) -> str:
    """`_DER_B64_RE`：去掉換行／跳脫／空白／`=`／遮罩後的 base64 字元數 ≥ `_DER_B64_MIN` 才整段遮，否則原樣。"""
    _body = m.group(0)
    return MASK if len(_DER_B64_SEP_RE.sub("", _body)) >= _DER_B64_MIN else _body


def _mask_space_dirs(m: re.Match) -> str:
    """`_POSIX_SPACE_DIR_RE`：目錄段含空白 → 目錄整串換成遮罩、留末段；否則原樣（末段本身不含空白）。"""
    _body = m.group(0)
    return MASK + "/" + (m.group(1) or "") if " " in _body else _body


_RULES_POST: tuple[tuple[re.Pattern, object], ...] = (
    (_FW_ASSIGN_RE, _mask_assign),
    (_FW_COLON_QUOTED_RE, _mask_value),
    (_FW_COLON_BARE_RE, _mask_value),
    (_PCT_QUERY_SECRET_RE, lambda m: m.group(1) + m.group(2) + MASK),
    (_CRED_AFTER_MASK_RE, lambda m: m.group(1) + MASK),
    (_TG_BOT_PREFIX_RE, MASK),
    (_DRIVE_OPEN_ID_RE, lambda m: m.group(1) + MASK),
    (_FWD_UNC_RE, lambda m: MASK + "/" + (m.group(1) or "")),
    (_POSIX_PATH_EXTRA_RE, lambda m: MASK + "/" + (m.group(1) or "")),
    (_DEEP_QUOTED_FIELD_RE, _mask_deep_value),
    (_DEEP_ASSIGN_TAIL_RE, lambda m: m.group(1) + MASK),
    (_DER_B64_RE, _mask_der_b64),
    (_POSIX_SPACE_DIR_RE, _mask_space_dirs),
)
#: 預先過濾：字串裡連必要字面都沒有，就不必讓該條規則掃一遍（純效能；有字面才跑，行為不變）。
_POST_NEEDLES: dict[re.Pattern, tuple[str, ...]] = {
    _FW_ASSIGN_RE: ("＝",), _FW_COLON_QUOTED_RE: ("：",), _FW_COLON_BARE_RE: ("：",),
    _PCT_QUERY_SECRET_RE: ("%3",), _CRED_AFTER_MASK_RE: (MASK,), _DRIVE_OPEN_ID_RE: ("id=",),
    _FWD_UNC_RE: ("//",), _POSIX_PATH_EXTRA_RE: ("@", "→", "—"),
    _DEEP_QUOTED_FIELD_RE: ("\\" * 5,), _DEEP_ASSIGN_TAIL_RE: (MASK + "'", MASK + '"'),
    _DER_B64_RE: ("M",), _POSIX_SPACE_DIR_RE: ("/",),
}


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
    for _re, _rep in _RULES_POST:
        _needles = _POST_NEEDLES.get(_re)
        if _needles is None or any(_n in out for _n in _needles):
            out = _re.sub(_rep, out)
    return out
