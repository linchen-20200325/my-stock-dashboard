"""shared/secret_scrub.py — L0：要畫上畫面的錯誤字串，先洗掉金鑰／識別碼／路徑（2026-09-26）。

**純函式，零 I/O、零 streamlit、不 import 任何 L1+。**

═══ 為什麼有這一檔 ═══════════════════════════════════════════════════
上游例外以 `repr(e)` 一路傳到卡片的「為什麼」與「▸ 詳細」摺疊區。實證（2026-09-26，
「💼 我的持股」）：secrets.toml 裡有一個非 UTF-8 位元組時，L3 讀 Sheet 識別碼的 `repr(e)` 是
`UnicodeDecodeError('utf-8', b'<整份 secrets 檔原文>', …)` —— **金鑰原文直接上紅卡**。
全站原本唯一的洗法是 L3 `services/ai_qa_service._scrub_secrets`（私有、只洗 URL query 與
`AIza…` 金鑰），L5 不得跨層取私有符號，而且它不涵蓋上面那一種。故下沉成本檔的公開函式。

═══ 三支，分工不同 ═══════════════════════════════════════════════════
- `scrub_query_secrets()`：**逐字**搬自 `ai_qa_service._scrub_secrets`（regex 一字未改）——
  `ai_qa_service` 改引用它，對任何輸入 **byte-identical**（它原本的行為不在本批改動範圍）。
- `scrub_prose_secrets()`（SEC-r12，2026-09-28）：**問答散文**（使用者的提問、AI 的回答）用這一支。
  ＝ 下一支一字不差（同一份規則表、同一個順序），**只有第 1 類的解碼例外那一條依型別分流**：
  三種 `Unicode*Error` 改為只截 repr 形（型別名＋左括號），散文形（型別名＋冒號）保留後文、照樣過其餘
  每一條規則；`TomlDecodeError` 兩種形都照舊整段截（它的訊息本身會串入內容；批 Q QA）。
  錯誤字串 ⛔ 不要用它。少遮的確切範圍見該函式的 docstring。
- `scrub_secrets()`：要畫上畫面的錯誤字串用這一支。= 第一支 ＋ 下列各類（`_RULES` 的順序即執行順序）：
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
           含空白的目錄名只認「≤5 個字、每字 ≤40、⛔ 不含中文與全形標點」（批 S QA N1：路徑後的說明字不吞）；
       (b) 沒有標頭的 PEM／DER base64 本體（`MIIEvQ…`，`M[A-P]` 開頭、合計 ≥60 字，可跨行）→ 整段遮；
           另須通過行結構與 DER 標頭解碼驗證（批 S QA N2：均線／代號清單、搜尋網址、大寫長字不遮）；
       (c) 深層巢狀的秘密欄位：引號前 5～32 個反斜線（`repr` 第 5～7 層、JSON 第 4～6 層）的
           `{'password': …}`／`"password" = …`，以及「`password=` 緊接深層跳脫引號」這種值外露的賦值。
   11. 補洞 批 S3（SEC-r13／SEC-r14／SEC-r17，2026-09-28 派工；2026-10-01 重做；同樣排在 `_RULES_POST` 的最後
       ⇒ 不會比舊版少遮）：
       (a) 方括號取值的 `Authorization`（`headers['Authorization'] = '…'`、`h[b"Authorization"] == …`、`+=`、
           三引號值、`'Bearer ' + tok` 這種 `+` 串接）→ 值與串接的各段遮掉；
       (b) 目錄名含 tab 的 POSIX 路徑（真 tab，或 `repr` 裡 1～32 個反斜線＋`t`）→ **整條路徑一起判**：
           任一目錄段含 tab，就把整串目錄換成一個遮罩、只留末段；
       (c) 第二道無標頭 DER（`_DER_B64_LOOSE_RE`）：與第 10 類 (b) **在同一份輸入上各自判、遮罩範圍取聯集**
           （`_DerPass`；第 10 類 (b) 遮的範圍一字不少），以較寬的排版認一次
           （換行寬度 16～39、第一行被前綴折短、行尾空白、只用 CR、JSON 的 `\/`），並**依宣告長度逐段判**：
           只遮宣告涵蓋到的行、其餘各行另判（後面接著的憑證／憑證鏈各自再判；不是 DER 的長 base64 照原樣）——
           「金鑰後接長 base64」「私鑰＋憑證相接」不再整把外露（SEC-r14）；一行一把的清單（Ed25519）每一把各自判、最後一把也遮。
           逐行走一次、⛔ 不遞迴（S3 QA F1：舊寫法每段遞迴一層，500 把就 RecursionError）。
           起點也可以是前面規則（路徑等）留下的 `***`；開頭 16 字判不了標頭時，只在「≥3 行同寬 ≥40 字」的整齊
           本體才整段遮（批 S3 QA F1）。附帶效果：欄位名後面直接接多行金鑰（`private_key: MIIE…`，SEC-r22 的
           形態）時，第一行被第 5 類遮掉後，其餘整齊的行（≥3 行同寬 ≥40 字）也會一併遮；SEC-r22 其餘形態未處理。
  遮罩一律沿用既有的 `***`（`MASK`）。**⛔ 不新增任何說明文字** —— 看得到 `***` 就知道有東西被遮。

⚠️ 據實揭露的邊界（**不是**全稱「洗乾淨了」）：
  · 裸露、沒有任何前後文的 Sheet ID（例如一句「找不到 1AbC…」）**分不出來**，不遮 ——
    硬遮任何 44 字元英數串會把一般訊息洗壞；泛用的 `id=` 同理（`open?id=`／`uc?id=` 已由第 9 類遮）；
  · ~~SEC-r1 仍未處理（2026-09-27）：目錄名含空白的 POSIX 路徑、無標頭的 PEM 本體、第 5 層巢狀 `repr`；~~
    → S2-f2（2026-09-28）已補這三種（第 10 類），但各自仍有邊界：
    目錄名裡有連續空白、開頭／結尾是空白、超過 5 個字、單字超過 40 字元、含中文或全形標點（`王 小明`）、
    或含 `'`／`,`／`;`／`:`／`[]{}`／反引號等字元 → 那一段起仍外露（同 d61a1fd；為了不吞說明字）；
    PEM／DER 只認得**從開頭**（`M[A-P]…`）起、開頭 16 字完好、解得出 DER 標頭的本體 —— 只截到中間幾行、
    非 DER 格式（OpenSSH 的 `b3BlbnNzaC1rZXkt…`、PGP）~~、或換行寬度 <40 字的多行本體~~認不出來；
    （~~換行寬度 <40~~ 那半句自批 S3 起不成立：第 11 類 (c) 認得 16～39；**現行邊界見下方「批 S3 之後仍然外露」**）
    貼成一行（空白分隔）時，最後一段若 <16 字又沒有 `=` 補位，分不出是不是說明字 → 那一段（≤15 字）外露；
    引號前的反斜線超過 32 個（`repr` 第 8 層、JSON 第 7 層起）仍外露；
    「`password=` 緊接深層跳脫引號」那一條只往後看 256 字找收尾；
  · 第 10 類 (a) 的反方向（多遮，安全側）：路徑後面 5 個英文字內又出現 `/` 時，中間那段會被當成目錄遮掉
    （`***/x.toml or y/z` → `***/z`；中文說明字不會，見 N1）；(b) 的反方向：`M[A-P]` 開頭、≥60 字、
    開頭剛好解得出合法 DER 標頭的 base64 形字串會被遮（一般文字做成的 base64 極少同時滿足）；
  · 相對路徑（`a/b/c.toml`）不遮；緊貼中文字的絕對路徑（`檔案/home/x`）也不遮（為了不誤遮 `元/股`）；
  · 帶主機名的 URL 路徑（`https://host/a/b`）不當檔案路徑遮；**不帶主機名**的路徑
    （例：requests 的 `…with url: /v4/…`）長得跟檔案路徑一樣，會被遮成 `***/<末段>`；
  · 兩層以上的巢狀 `repr` 裡、值本身又含同種引號時，引號配對可能提早結束（只剩值的後半段外露）；
  · 秘密欄位只認下面 `_FIELDS_*` 列出的名字；不在清單上的欄位名（例：自訂的 `my_api_pw`）不遮。
  · 批 S3 之後仍然外露（據實揭露；皆與舊版相同、不是本批引入）：
    - 沒有結尾斜線、最後一段含空白的路徑（`/Users/Jane Doe`）→ `***/Jane Doe`：末段一律當檔名保留（設計如此，
      同 d61a1fd）—— 使用者名稱會留在畫面上（SEC-r13 (c)）；
    - BER 不定長格式（`30 80` 開頭，例：`openssl cms -stream`、部分 PKCS#12 匯出檔）兩道 DER 規則都認不出
      （DER 不允許不定長，`_der_length` 回 `None`；SEC-r15）；
    - 第 11 類 (c) 仍認不出：換行寬度 <16、第一行只剩 1 個字（`M` 之後就換行）、行首縮排超過 16 個空白
      （SEC-r27）、base64url 編碼；
    - 方括號取值只認 `[…]` 內**直接**是 `Authorization` 字串的寫法（`headers[AUTH_KEY] = …` 這種變數取值不認）；
      值被括號包住（`= ( 'tok' )`）、`=` 後面先換行、`headers.__setitem__('Authorization', 'tok')` 這三種仍外露
      （S3 QA F3；與舊版相同）；
      目錄名 tab 規則只認合理起點（同 `_POSIX_SPACE_DIR_RE`）之後的路徑。
  · 批 S3 的多遮方向（安全側）：
    - 方括號取值的裸值（`headers['Authorization'] = token_var`）連變數名一起遮；
    - tab 規則以整條路徑判：`/a/x.toml<tab>note/b` 這種「路徑後面接 tab 再接含 `/` 的字」會被當成目錄遮成 `***/b`；
    - 第 11 類 (c)：一行一個的 base64 清單裡，**任何一行**（不限第一行）以 `M[A-P]` 開頭、開頭 16 字又解得出
      DER 標頭 → 那一行起、宣告長度涵蓋到的幾行被遮；遮罩 `***` 後面接著「≥3 行同寬 ≥40 字」的 base64 形
      字串（雜湊清單等）會整段遮。

⚠️ 效能：全部規則都是線性掃描（量測見 `tests/test_v2_silent_fail_b11_hold_misc.py` 的 ReDoS 守衛；
    第 10 類另見 `tests/test_sec_s3_0928.py`，第 11 類另見 `tests/test_sec_s3_batch_s3.py`）——
    有「前綴 ＋ 不定長 ＋ 必要結尾」形狀的都設了長度上限或以固定字面錨定起點。
⚠️ 記憶體（SEC-r13 (d)，據實揭露；**只對量過的輸入形態成立，⛔ 不是上限**）：`re` 對「迴圈本體不是單一字元類別」的
    重複會逐圈留回溯點，峰值隨輸入長度成長。舊規則（批 S3 未改）40 萬字時實測：第 10 類 (c) 深層巢狀的未收尾值
    +47 MB、第 5 類 `'password': '` 未收尾 +93 MB（批 S QA 量到 33～96 MB，同一族）。
    第 11 類的迴圈改用佔有型量詞（`_POSS`）：40 萬字、本批自選 21 種形態，峰值比 e23ff2f 多 ≤ 2 MB（`tracemalloc`）；
    Python 3.10 沒有佔有型量詞 → 退回一般量詞（比對結果相同），同樣形態實測最多多 ~120 MB（未收尾的
    方括號 `Authorization` 值、目錄名夾 tab 的長路徑）。
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
#: SEC-r12（2026-09-28；批 Q QA 依型別分流）：**問答散文版**（`scrub_prose_secrets`）專用的第 1 類。
#: 依型別分流：
#:   · 三種 `Unicode*Error`（`_PROSE_RELAXED_EXC`）→ **只截 repr 形**（型別名＋可有空白＋左括號起到字串結尾；
#:     repr 才帶被解碼／編碼的原始內容）；散文形（型別名＋冒號…）⛔ 不截 —— 它們的 `str()` 只有編碼名、
#:     位置與至多一個字元／位元組值（實測），而使用者引用它們發問、AI 回答寫出它們時，冒號後面是問題本身與解法。
#:   · `TomlDecodeError`（以及放寬清單以外、日後新增進上一條的任何型別）→ **兩種形都照舊整段截**
#:     （同 `scrub_secrets`）：toml 0.10.2 的訊息會串入內容 —— 重複表錯誤串入已解析的整包 dict、
#:     數字轉換失敗（`could not convert string to float: '<值>'`／`invalid literal for int() …: '<值>'`）
#:     帶出出錯那一行的原始值（批 Q QA 以真實 `toml.loads` 重現）；還沒列舉到的訊息也一併擋。
#: 推導：上一條的 pattern 前面加一個「放寬清單＋冒號」的否定前瞻 —— 型別名清單仍只有一份，
#: 不在放寬清單上的型別一律照截（安全側）；推導結果由 `tests/test_sec_r12_r11_prose_scrub.py` 逐字釘住。
#: ⚠️ `_STREAMLIT_PARSE_RE` 散文版**照用、不放寬**（它沒有「型別名＋冒號」這種散文形；見 `scrub_prose_secrets`）。
_PROSE_RELAXED_EXC: str = r"Unicode(?:Decode|Encode|Translate)Error"
_CONTENT_BEARING_EXC_PROSE_RE = re.compile(
    r"(?!" + _PROSE_RELAXED_EXC + r"[ \t]*:)" + _CONTENT_BEARING_EXC_RE.pattern, _CONTENT_BEARING_EXC_RE.flags)

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
#: 可跨行：真換行、`repr`／JSON 的 `\n` 跳脫（反斜線 ≤32 個）、或貼成一行時「空白＋下一段」。
#: base64 字元合計 ≥ `_DER_B64_MIN` 才遮；整段換成一個遮罩。另有兩道結構判別（批 S QA N2，2026-09-28），
#: 排除「`M[A-P]` 開頭、湊滿 60 字」的一般文字（均線／代號清單、搜尋網址、大寫長字、文字做成的 base64）：
#:   (i) 行結構（寫在規則裡）：多行時，除了最後一行，每行都要 ≥ `_DER_B64_LINE_MIN` 字
#:       —— 一行太短就停在那裡，後面不再接（`MAR\nAAPL\n…` 只比對到 `MAR`）。
#:       行內有前面規則留下的遮罩 `***` → 原本多長已不可知，一律算夠長（實作時實際踩過：以 `/` 開頭的那一行
#:       先被路徑規則遮成 `***/…`、只剩幾個字，本體就在那裡斷掉、後面各行外露）；
#:   (ii) 解碼驗證（`_looks_like_der`）：第一行開頭解得出 DER 的 SEQUENCE 標頭，見該函式。
#: ⚠️ 本體裡**已經被前面規則換成遮罩的片段**（`***`）也算本體的一部分：base64 含 `/`，某一行剛好以 `/`
#: 開頭（每行約 1/64）時，前面的路徑規則會先把它遮成 `***/…`；不把 `***` 收進來，本體就在那裡斷掉、
#: 後面各行外露（`1//…`、`4/…`、`eyJ…`、`AIza…` 同理）。
#: 空白續行（貼成一行）的最後一段須「≥16 個 base64 字」、「前 16 字內有 `***`」（`4/***`、`1//***`）、
#: 或「短段以 `=` 補位收尾」—— 否則當成後面的說明字，不吃。
#: 線性：每一輪的開頭（換行／反斜線／空白）都不在本體字元（base64 或 `***`）裡 ⇒ 切法唯一，沒有回溯分岔；
#: 空白續行的前瞻最多看 18 字。
_DER_B64_MIN: int = 60
_DER_B64_LINE_MIN: int = 40
_B64_CHUNK: str = r"(?:[A-Za-z0-9+/]|\*\*\*)"
_B64_NL: str = r"(?:\r?\n|(?:\\{1,32}r)?\\{1,32}n)[ \t]{0,16}"
_B64_SP: str = r"[ \t]{1,4}"
_B64_SP_LAST: str = _B64_SP + r"(?=[A-Za-z0-9+/]{16}|[A-Za-z0-9+/]{0,15}\*\*\*|[A-Za-z0-9+/]{1,15}=)"


def _b64_long_line(n: int) -> str:
    """「夠長的一行」：開頭連續 ≥n 個 base64 字，或行內有遮罩；之後同一行剩下的字照收。"""
    return r"(?:[A-Za-z0-9+/]{%d,}|[A-Za-z0-9+/]*\*\*\*)" % n + _B64_CHUNK + r"*"


_DER_B64_RE = re.compile(
    r"(?:(?<![A-Za-z0-9+/])|(?<=\\[nrt]))M[A-P]"
    r"(?:" + _b64_long_line(_DER_B64_LINE_MIN - 2)                              # 第一行夠長，才准接下一行
    + r"(?:(?:" + _B64_NL + "|" + _B64_SP + r")" + _b64_long_line(_DER_B64_LINE_MIN) + r")*"
    r"(?:" + _B64_NL + _B64_CHUNK + r"+|" + _B64_SP_LAST + _B64_CHUNK + r"+)?"   # 最後一行可以短
    r"|" + _B64_CHUNK + r"*)"                                                   # 或只有一行
    r"={0,2}")
#: 把比對到的本體切成一行一行（真換行、跳脫換行、空白）。
_B64_LINE_SPLIT_RE = re.compile(r"(?:\r?\n|(?:\\+r)?\\+n)[ \t]*|[ \t]+")
_B64_HEAD_RE = re.compile(r"[A-Za-z0-9+/]*")
#: (ii) 只解第一行開頭 16 個 base64 字（12 位元組）：外層標籤＋長度（≤6）＋內層標籤＋長度（≤6）剛好判得完。
_B64_HEAD_CHARS: int = 16
_B64_VALUE: dict[str, int] = {
    _c: _i for _i, _c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")}
#: 第一個內層元素的標籤：INTEGER（私鑰的版本號）、OID（PKCS#7）、SEQUENCE（加密私鑰、憑證）。
_DER_INNER_TAGS: frozenset[int] = frozenset({0x02, 0x06, 0x30})
#: (a) 目錄名含空白的 POSIX 路徑（`/Users/Jane Doe/app/.streamlit/secrets.toml`）：舊版路徑段不收空白，
#: 只遮到第一個空白（`***/Jane Doe/app/.streamlit/secrets.toml`）。本條在「路徑遮罩 `***` 之後」
#: 或「合理起點」（同 `_PATH_START`，另加 `@`／`→`／`—`）接一串**以 `/` 收尾**的目錄段，整串併進遮罩、
#: 只留末段（末段不吃空白：`***/x.toml 讀取失敗` 不動）。目錄段兩種：
#:   · 不含空白 → 同舊規則的 `_PATH_SEG`（什麼字都收，行為與舊版路徑規則一致）；
#:   · 含空白 → 2～5 個「字」、單一半形空白隔開；每個字 ≤ `_SP_DIR_WORD_MAX` 字元，而且
#:     ⛔ 不收 CJK 字元、全形標點（`_CJK_PUNCT`）與反引號（批 S QA N1，2026-09-28）——
#:     否則一整句中文說明（`… 顯示殖利率 4.5%，配息 3 元/股`）會被算成一個「字」、當成目錄名吞掉。
#:     字可以含 `(`／`)`（`Dropbox (Personal)`、`Program Files (x86)`）；末段仍用 `_PATH_SEG`，
#:     所以 `(see /a/b)` 的 `)` 照舊不算進路徑。`@`／`→`／`—` 不算字（它們是上面 `_POSIX_PATH_EXTRA_RE`
#:     的路徑起點：`x.toml @/home/…` 的 `@` 後面是另一條路徑，⛔ 不是「`x.toml @`」這個目錄名）。
#: ⚠️ 只在「某個目錄段真的含空白」時才遮（`_mask_space_dirs`）；沒有空白的路徑原樣交還 ——
#: 那是上面各條路徑規則的職責，本條 ⛔ 不重複遮（否則拔掉舊規則也看不出外露，舊規則的守衛就失效）。
#: 線性：兩種目錄段互斥（有沒有空白），段內「空白＋字」與段尾的 `/` 開頭互斥，每個字有長度上限；
#: 比對一律成功並吃掉整段，不會重掃。
#: CJK 字元與全形標點：一般標點與箭頭（含 `—`／`→`／`…`／彎引號）、CJK 部首～統一表意文字（含假名、注音、
#: `、。「」` 等全形標點）、韓文、相容表意文字、直排／小型／全形字形（`，：；（）％` 等）、擴充 B 以後。
_CJK_PUNCT: str = (r"\u2000-\u206F\u2190-\u21FF\u2E80-\u9FFF\uA960-\uA97F\uAC00-\uD7AF\uF900-\uFAFF"
                   r"\uFE10-\uFE1F\uFE30-\uFE6F\uFF00-\uFFEF\U00020000-\U0003FFFF")
_SP_DIR_WORD_MAX: int = 40
_SP_DIR_WORD: str = r"[^\s/\\'\"<>|:;,\[\]{}*?@`" + _CJK_PUNCT + r"]{1,%d}" % _SP_DIR_WORD_MAX
_SP_DIR_MULTI: str = _SP_DIR_WORD + r"(?: " + _SP_DIR_WORD + r"){1,4}"
_POSIX_SPACE_DIR_RE = re.compile(
    r"(?:(?:(?<![*A-Za-z0-9_])|(?<=\\[nrt]))" + re.escape(MASK) + r"|(?:" + _PATH_START
    + r"|(?<=[@→—]))(?:~[A-Za-z0-9_.\-]{0,64})?)"
    r"/(?:(?:" + _PATH_SEG + r"|" + _SP_DIR_MULTI + r")/)+(" + _PATH_SEG + r")?", re.MULTILINE)


def _mask_deep_value(m: re.Match) -> str:
    """`_DEEP_QUOTED_FIELD_RE`：保留欄位名與分隔；值有收尾 → 保留同一串反斜線＋引號，否則遮到行尾。"""
    if m.group("eq"):
        _q = m.group("bs") + m.group("qc")
        return m.group("pre") + _q + MASK + _q
    return m.group("pre") + MASK


def _der_length(b: bytes, i: int) -> tuple[int, int] | None:
    """讀 `b[i]` 起的 DER 長度欄位 → `(內容長度, 長度欄位之後的位置)`。

    不合 DER 的一律 `None`：不定長（`0x80`）、超過 4 位元組、位元組不夠、非最短編碼
    （長格式卻 <0x80，或有前導 0）。
    """
    if i >= len(b):
        return None
    if b[i] < 0x80:
        return b[i], i + 1
    _n = b[i] & 0x7F
    if not 1 <= _n <= 4 or i + 1 + _n > len(b):
        return None
    _v = int.from_bytes(b[i + 1:i + 1 + _n], "big")
    if b[i + 1] == 0 or _v < 0x80:
        return None
    return _v, i + 1 + _n


def _looks_like_der(head_b64: str, seen: int) -> bool:
    """(ii) 解碼驗證：`head_b64`（第一行開頭的 base64）解得出 DER 的 SEQUENCE 標頭嗎？

    條件全部成立才算：首位元組 `0x30`；長度欄位合 DER；**宣告的總長 ≥ 實際看到的長度 `seen`**
    （截斷的本體可以，宣告得比看到的還短就不是）；第一個內層元素的標籤在 `_DER_INNER_TAGS`，
    而且它的長度欄位合 DER、裝得進外層。只解開頭 `_B64_HEAD_CHARS` 個字（12 位元組）就判得完；
    不到這麼長 → 判不了 → 不是。
    自己查表解碼（本檔只准 import `re`）：`head_b64` 只含 base64 字元（`_B64_HEAD_RE` 取出）⇒ 查表不會落空。
    """
    if len(head_b64) < _B64_HEAD_CHARS:
        return False
    _b = bytearray()
    for _i in range(0, _B64_HEAD_CHARS, 4):
        _v = 0
        for _c in head_b64[_i:_i + 4]:
            _v = (_v << 6) | _B64_VALUE[_c]
        _b += _v.to_bytes(3, "big")
    if _b[0] != 0x30:
        return False
    _outer = _der_length(_b, 1)
    if _outer is None:
        return False
    _total = _outer[1] + _outer[0]
    _pos = _outer[1]
    if _total < seen or _pos >= len(_b) or _b[_pos] not in _DER_INNER_TAGS:
        return False
    _inner = _der_length(_b, _pos + 1)
    return _inner is not None and _inner[1] + _inner[0] <= _total


def _mask_der_b64(m: re.Match) -> str:
    """`_DER_B64_RE`：base64 字元（不算換行／跳脫／空白／`=`／遮罩）合計 ≥ `_DER_B64_MIN`，
    而且通過 (ii) 解碼驗證 → 整段遮；否則原樣。

    「實際看到的長度」＝最後一行以外各行解碼後的位元組數（只有一行就算那一行）——
    最後一行可能是被一起吃進來的說明字（例如金鑰後面換行接著 `What`）；拿它來比，
    會讓「宣告長度 < 實際長度」把真金鑰判成不是、整段外露。
    """
    _body = m.group(0)
    _lines = _B64_LINE_SPLIT_RE.split(_body.rstrip("="))
    _counts = [len(_l.replace("*", "")) for _l in _lines]
    if sum(_counts) < _DER_B64_MIN:
        return _body
    _seen = sum(_counts[:-1] if len(_counts) > 1 else _counts) * 3 // 4
    return MASK if _looks_like_der(_B64_HEAD_RE.match(_lines[0]).group(0), _seen) else _body


def _mask_space_dirs(m: re.Match) -> str:
    """`_POSIX_SPACE_DIR_RE`：目錄段含空白 → 目錄整串換成遮罩、留末段；否則原樣（末段本身不含空白）。"""
    _body = m.group(0)
    return MASK + "/" + (m.group(1) or "") if " " in _body else _body


# ── 補洞 批 S3（SEC-r13／SEC-r14／SEC-r17，2026-09-28；重做 2026-10-01）：同樣排在最後 ⇒ 不會比舊版少遮 ──
#: 佔有型量詞（`*+`／`++`，Python 3.11 起）：只用在「迴圈本體與迴圈之後的字面互斥」的位置（回溯不會
#: 找到別的切法 ⇒ 比對結果相同），作用是讓 `re` 不必為每一圈留回溯點 —— 40 萬字輸入的記憶體峰值
#: 不隨長度膨脹（量測見 `tests/test_sec_s3_batch_s3.py`）。Python 3.10 編譯 `*+` 會直接報錯
#: （使用者本機的 MCP server 未釘版本）→ 以**實際編譯**探測（本檔只准 import `re`，不讀 `sys.version_info`），
#: 不支援就退回一般量詞：比對結果相同，只是記憶體峰值較高。
try:
    re.compile(r"a*+")
    _POSS: str = "+"
except re.error:  # pragma: no cover —— Python 3.10 以前
    _POSS = ""
#: SEC-r13 (a) 方括號取值的 `Authorization`（`headers['Authorization'] = '…'`、`h[b"Authorization"] == …`）：
#: `_AUTH_HEADER_RE` 要求欄位名後面直接接 `:`／`=`，中間夾了 `]` 就比對不到。
#: 起點是固定字面 `[`；欄位名與值的引號前都可有 Python 字串前綴（`b`／`r`／`u`／`f`、兩字組合），
#: 前綴只在**緊接引號**時才算（`[ b'…` 不收 `b` 以外的字 ⇒ `headers[name]` 這類一般取值不動）。
#: 分隔 `=`／`==`／`!=`；值同 `_VALUE`（引號字串只遮引號內、找不到收尾就遮到行尾、裸值遮到空白）。
_STR_PFX: str = r"(?:[bBrRuUfF]{1,2}(?=\\{0,4}[\"']))?"
#: 值：同 `_VALUE` 的引號／跳脫引號／未收尾／裸值四種（不收 `neg`：方括號取值不會寫成「not set」），
#: 但引號字串的迴圈用 `_POSS`（佔有型量詞，見下）—— 40 萬字的未收尾值不再逐字留回溯點。
_AUTH_VALUE: str = (
    r"(?:(?P<tq3>\"\"\"[^\r\n]{0,4096}?(?:\"\"\"|(?=[\r\n]|\Z))|'''[^\r\n]{0,4096}?(?:'''|(?=[\r\n]|\Z)))"   # S3 QA F3：三引號
    r"|(?P<dq>\"(?:\\.|[^\"\\\r\n])*" + _POSS + r"\")"
    r"|(?P<sq>'(?:\\.|[^'\\\r\n])*" + _POSS + r"')"
    r"|(?P<eq>(?P<bs>\\{1,4})(?P<qc>[\"'])(?:(?!(?P=bs)(?P=qc))[^\r\n])*" + _POSS + r"(?P=bs)(?P=qc))"
    r"|(?P<open>[\"'\\][^\r\n]*)"
    r"|(?P<bare>[^\s,;&'\"<>(){}\[\]\\]+))")
_AUTH_SUBSCRIPT_RE = re.compile(
    r"(?P<pre>\[[ \t]{0,16}" + _STR_PFX + r"(?P<fq>(?<!\\)\\{0,4}[\"'])Authorization(?P=fq)[ \t]{0,16}\]"
    r"[ \t]{0,16}(?:[=!]=|\+=|=)[ \t]{0,16}" + _STR_PFX + r")" + _AUTH_VALUE
    #: S3 QA F3：值後面再用 `+` 串接的各段（`'Bearer ' + 'tok'`、`'Bearer ' + tok_var`）也遮，每段有長度上限。
    + r"(?P<cat>(?:[ \t]{0,16}\+[ \t]{0,16}" + _STR_PFX
    + r"(?:'[^'\r\n]{0,4096}'|\"[^\"\r\n]{0,4096}\"|[A-Za-z0-9_.]{1,256})){1,16})?", _I)


def _mask_auth_subscript(m: re.Match) -> str:
    """`_AUTH_SUBSCRIPT_RE`：同 `_mask_value`；後面有 `+` 串接時，串接的部分整段換成「 + 遮罩」。"""
    return _mask_value(m) + (" + " + MASK if m.group("cat") else "")

#: SEC-r13 (b) 目錄名含 tab 的 POSIX 路徑（`/home/u/my<tab>dir/secrets.toml`；`repr` 裡是 `\t`，
#: 每多包一層 `repr` 反斜線變多 → 收 1～32 個反斜線＋`t`）：舊路徑段不收空白與反斜線，只遮到 tab 之前。
#: ⚠️ **整條路徑一起判**：只要比對到的目錄段裡**任一段**含 tab，就把整串目錄換成一個遮罩、只留末段
#: （同 `_POSIX_SPACE_DIR_RE` 的處置）；沒有任何目錄段含 tab → 原樣交還（那是舊路徑規則的職責）。
#: 起點同 `_POSIX_SPACE_DIR_RE`（前面規則留下的 `***`、`_PATH_START`、`@`／`→`／`—`）；目錄段也收
#: `_POSIX_SPACE_DIR_RE` 的「含空白的目錄名」（tab 與空白目錄夾在同一條路徑裡時，兩條規則各遮一半會留下中間那段）。
#: 線性：段內「路徑字元串」與「tab」互斥（`_PATH_SEG` 不收空白與反斜線），反斜線串有上限。
_TAB_ESC: str = r"(?:\t|\\{1,32}t)"
_TAB_SEG: str = r"(?:" + _TAB_ESC + r")?" + _PATH_SEG + r"(?:" + _TAB_ESC + _PATH_SEG + r")*" + _POSS
_POSIX_TAB_DIR_RE = re.compile(
    r"(?:(?:(?<![*A-Za-z0-9_])|(?<=\\[nrt]))" + re.escape(MASK) + r"|(?:" + _PATH_START
    + r"|(?<=[@→—]))(?:~[A-Za-z0-9_.\-]{0,64})?)"
    r"/(?P<dirs>(?:(?:" + _TAB_SEG + "|" + _SP_DIR_MULTI + r")/)+" + _POSS + r")(" + _PATH_SEG + r")?", re.MULTILINE)
_TAB_IN_DIR_RE = re.compile(r"\t|\\{1,32}t")


def _mask_tab_dirs(m: re.Match) -> str:
    """`_POSIX_TAB_DIR_RE`：任一目錄段含 tab → 目錄整串換成遮罩、留末段；否則原樣。"""
    if _TAB_IN_DIR_RE.search(m.group("dirs")) is None:
        return m.group(0)
    return MASK + "/" + (m.group(2) or "")


#: SEC-r14／SEC-r17 第二道無標頭 DER（`_DER_B64_LOOSE_RE`）：與上面 `_DER_B64_RE` 在**同一份輸入**上各自判
#: （`_DerPass` 取聯集），用較寬的排版再認一次，並**依宣告長度逐段判**：
#:   · 排版：換行寬度 ≥ `_DER_LOOSE_LINE_MIN`（16）字、第一行被前綴折短（第一行只要 `M[A-P]` 起頭即可）、
#:     行尾空白、只用 CR 換行、JSON 的 `\/` 跳脫、行首縮排 ≤16 個空白；
#:   · 判法：開頭 16 個 base64 字（跨行串起來）解得出 DER 標頭（`_der_head_total`，條件同 `_looks_like_der`、
#:     但**不比「宣告 ≥ 實際」**）→ 只遮**宣告長度涵蓋到的那幾行**（含涵蓋終點所在的那一整行），
#:     其餘各行**另判**（例如後面接著的憑證／憑證鏈各自從 `M[A-P]` 再判一次；不是 DER 的長 base64 照原樣）——
#:     「金鑰後接長 base64」「私鑰＋憑證相接」不再因為「宣告 < 實際」整把外露（SEC-r14）；
#:     宣告長度比看到的還長（截短的本體）→ 看到的整段都遮；
#:   · 開頭 16 字內已有前面規則留下的遮罩（判不了標頭）→ 只有在「≥3 行、同寬 ≥40 字」的整齊本體時整段遮
#:     （批 S3 QA F1：前兩行先被路徑等規則遮成 `***…`、第一行又短於 16 字時整把外露）—— **只加遮罩**；
#:   · 共同下限：涵蓋到的 base64 字合計 ≥ `_DER_B64_MIN`（宣告只涵蓋第一行也算：一行的 Ed25519 金鑰後面接著
#:     別的 base64 時，第一道規則因「宣告 < 實際」放行，這裡只遮那一行）；中間各行（第一行與涵蓋終點那行以外、
#:     沒有遮罩的行）必須同寬 —— 一般文字（清單、說明）幾乎不會同時滿足「同寬多行」與「解得出 DER 標頭」。
#: 線性：每行用單一字元類別吃（`\/` 與換行以反斜線後一字區分），行數有上限；逐段判是對比對結果的後處理。
_DER_LOOSE_LINE_MIN: int = 16
_DER_LOOSE_TIDY_MIN: int = 40
_DERL_RUN: str = r"[A-Za-z0-9+/*]*(?:\\/[A-Za-z0-9+/*]*)*" + _POSS
_DERL_LINE: str = (r"(?=(?:[A-Za-z0-9+/*]|\\/){%d}|(?:[A-Za-z0-9+/]|\\/){0,4096}\*\*\*)" % _DER_LOOSE_LINE_MIN
                   + _DERL_RUN)
_DERL_NL: str = r"[ \t]{0,16}(?:\r\n|\r|\n|(?:\\{1,32}r)?\\{1,32}n)[ \t]{0,16}"
_DER_B64_LOOSE_RE = re.compile(
    r"(?:(?<![A-Za-z0-9+/*])|(?<=\\[nrt]))(?:M[A-P]|\*\*\*)" + _DERL_RUN
    + r"(?:" + _DERL_NL + _DERL_LINE + r"){1,4096}" + _POSS
    + r"(?:" + _DERL_NL + r"(?:[A-Za-z0-9+/]|\\/){1,15}(?![A-Za-z0-9+/*\\]))?={0,2}")
_DERL_NL_RE = re.compile(_DERL_NL)


def _der_head_total(head_b64: str) -> int | None:
    """開頭 16 個 base64 字解得出 DER 標頭 → 宣告的總長（位元組，含外層標籤與長度欄位）；否則 `None`。

    條件同 `_looks_like_der`（首位元組 `0x30`、長度欄位合 DER、內層標籤在 `_DER_INNER_TAGS` 且裝得進外層），
    只是**不比「宣告 ≥ 實際看到的長度」** —— 那一項由 `_der_loose_block` 改成「只遮宣告涵蓋的行」。
    """
    if len(head_b64) < _B64_HEAD_CHARS:
        return None
    _b = bytearray()
    for _i in range(0, _B64_HEAD_CHARS, 4):
        _v = 0
        for _c in head_b64[_i:_i + 4]:
            _v = (_v << 6) | _B64_VALUE[_c]
        _b += _v.to_bytes(3, "big")
    if _b[0] != 0x30:
        return None
    _outer = _der_length(_b, 1)
    if _outer is None:
        return None
    _total, _pos = _outer[1] + _outer[0], _outer[1]
    if _pos >= len(_b) or _b[_pos] not in _DER_INNER_TAGS:
        return None
    _inner = _der_length(_b, _pos + 1)
    return _total if _inner is not None and _inner[1] + _inner[0] <= _total else None


def _der_strict_block(body: str) -> list[tuple[int, int]]:
    """第一道（`_DER_B64_RE`）的判法不變（`_mask_der_b64`）；判為金鑰 → 整段一個遮罩範圍。"""
    return [(0, len(body))] if body != MASK and _mask_der_b64(_WholeMatch(body)) == MASK else []


class _WholeMatch:
    """讓 `_mask_der_b64` 能吃一段字串（它只讀 `group(0)`）。"""
    __slots__ = ("_s",)

    def __init__(self, s: str) -> None:
        self._s = s

    def group(self, _i: int = 0) -> str:
        return self._s


def _is_der_start(line: str) -> bool:
    return line.startswith(MASK) or (line[:1] == "M" and "A" <= line[1:2] <= "P")


def _der_loose_block(body: str) -> list[tuple[int, int]]:
    """`_DER_B64_LOOSE_RE` 比對到的一整塊 → 要遮的範圍（相對 `body`）。⛔ 不遞迴：逐行往下走一次。

    每個可能的起點（`M[A-P]` 或 `***` 開頭的行）各自判一段：解得出標頭 → 宣告涵蓋到的行；判不了標頭
    （開頭 16 字內有遮罩）→ 只在整齊本體時遮；判完跳到該段之後繼續。涵蓋終點以二分搜尋前綴和找，
    「中間各行同寬」以事先算好的「同寬延伸到哪一行」查表 ⇒ 每個起點 O(log n)，整塊 O(n log n)。
    """
    _ends, _starts = [], [0]
    for _sep in _DERL_NL_RE.finditer(body):
        _ends.append(_sep.start())
        _starts.append(_sep.end())
    _ends.append(len(body))
    _lines = [body[_a:_b].replace("\\/", "/").rstrip("=") for _a, _b in zip(_starts, _ends)]
    _n = len(_lines)
    _masked = ["*" in _l for _l in _lines]
    _len = [len(_l) for _l in _lines]
    _ps, _mc = [0] * (_n + 1), [0] * (_n + 1)
    for _x in range(_n):
        _ps[_x + 1] = _ps[_x] + (0 if _masked[_x] else _len[_x])
        _mc[_x + 1] = _mc[_x] + _masked[_x]
    #: `_run[x]`：從第 x 行起，「沒有遮罩的行都同寬」一路延伸到哪一行（有遮罩的行不論寬度）；`_pw[x]`：那個寬度。
    _run, _pw, _np = [0] * _n, [None] * _n, [_n] * (_n + 1)
    for _x in range(_n - 1, -1, -1):
        _np[_x] = _np[_x + 1] if _masked[_x] else _x
        _nx_pw = _pw[_x + 1] if _x + 1 < _n else None
        _nx_run = _run[_x + 1] if _x + 1 < _n else _x
        if _masked[_x]:
            _run[_x], _pw[_x] = _nx_run, _nx_pw
        elif _nx_pw is None or _nx_pw == _len[_x]:
            _run[_x], _pw[_x] = _nx_run, _len[_x]
        else:
            _run[_x], _pw[_x] = _np[_x + 1] - 1, _len[_x]
    _out: list[tuple[int, int]] = []
    _i = 0
    while _i < _n:
        if not _is_der_start(_lines[_i]):
            _i += 1
            continue
        #: 被前面規則遮掉的行，原本多寬已不可知 → 以附近（本行起 4 行內）沒遮罩的行的**最大**寬度估：
        #: 中間行一定是滿行（最寬），首行可能被前綴折短、末行可能是短行；高估只會讓涵蓋提早一點結束在
        #: 「本來就該是最後一行」的那行，低估才會吃進下一段的第一行（S3 QA F2 實例）。
        _near = [_len[_x] for _x in range(_i, min(_i + 4, _n)) if not _masked[_x]]
        _w = max(_near) if _near else (_pw[_i] or _len[_i])
        _head, _x = "", _i
        while _x < _n and len(_head) < _B64_HEAD_CHARS:
            _seg, _star, _ = _lines[_x].partition("*")
            _head += _seg
            if _star:
                break
            _x += 1
        _head = _head[:_B64_HEAD_CHARS]
        if len(_head) < _B64_HEAD_CHARS:
            #: 判不了標頭（批 S3 QA F1）：從下一行起「≥3 行沒遮罩、同寬 ≥40」的整齊本體 → 連同最後一行短行一起遮。
            #: （除了「開頭 16 字內有遮罩」，只有本行就是整塊最後一行時才會不到 16 字 —— 下一行起的行都 ≥16 字。）
            if _i + 1 >= _n:
                _i += 1
                continue
            _re = _run[_i + 1]
            _top = min(_re, _n - 2)                    # 整塊的最後一行不算（可能是說明字或短行）
            _plain = (_top - _i) - (_mc[_top + 1] - _mc[_i + 1])
            if _plain < 3 or _w < _DER_LOOSE_TIDY_MIN:
                _i += 1
                continue
            _k = _re + 1 if _re + 1 < _n and not _masked[_re + 1] and _len[_re + 1] < _w else _re
            _out.append((_starts[_i], _ends[_k]))
            _i += 1
            continue
        _total = _der_head_total(_head)
        if _total is None:
            _i += 1
            continue
        _need = -(-_total * 4 // 3)

        def _cum(_k: int) -> int:
            return _ps[_k + 1] - _ps[_i] + _w * (_mc[_k + 1] - _mc[_i])

        _lo, _hi = _i, _n - 1
        if _cum(_hi) >= _need:
            while _lo < _hi:
                _mid = (_lo + _hi) // 2
                if _cum(_mid) >= _need:
                    _hi = _mid
                else:
                    _lo = _mid + 1
        _k = _hi
        if _cum(_k) < _DER_B64_MIN or (_k - 1 >= _i + 1 and _run[_i + 1] < _k - 1):
            _i += 1
            continue
        _out.append((_starts[_i], _ends[_k]))
        #: 下一個起點從**下一行**找（不是跳到涵蓋終點之後）：涵蓋終點若因行寬估錯而吃進下一段的第一行，
        #: 那一段仍會從它自己的第一行再判一次；重疊的範圍在 `_DerPass` 取聯集。每行至多當一次起點 ⇒ 仍是 O(n log n)。
        _i += 1
    return _out


class _DerPass:
    """無標頭 DER 的兩道規則**在同一份輸入上各自判**，遮罩範圍取聯集（S3 QA 意見 F1／F2 之後的寫法）。

    為什麼不再「第一道跑完、第二道吃第一道的輸出」：第一道常常只遮到第一行（行尾空白、JSON `\\/` 讓它在第一行
    就收尾），第二道接手時標頭已被遮掉、判不了宣告長度，金鑰其餘各行外露。各自在原文上判 ⇒ 第二道看得到標頭；
    取聯集 ⇒ 第一道遮的範圍一個字都不少（**不會比舊版少遮**）。
    與 `re.Pattern` 同介面（`sub(rep, text)`），以便照舊放在 `_RULES_POST` 裡依序執行；`rep` 不用。
    """

    def sub(self, _rep, text: str) -> str:
        _spans: list[tuple[int, int]] = []
        for _rx, _block in _DER_PARTS:
            for _m in _rx.finditer(text):
                _spans.extend((_m.start() + _a, _m.start() + _b) for _a, _b in _block(_m.group(0)))
        if not _spans:
            return text
        _spans.sort()
        _parts, _pos, _cur = [], 0, None
        for _a, _b in _spans:
            if _cur is not None and _a <= _cur[1]:
                _cur = (_cur[0], max(_cur[1], _b))
                continue
            if _cur is not None:
                _parts += [text[_pos:_cur[0]], MASK]
                _pos = _cur[1]
            _cur = (_a, _b)
        _parts += [text[_pos:_cur[0]], MASK, text[_cur[1]:]]
        return "".join(_parts)


#: 兩道各自的（規則, 判段函式）。拿掉任一行 ＝ 拿掉那一道（突變測試用的錨點）。
_DER_PARTS: tuple[tuple[re.Pattern, object], ...] = (
    (_DER_B64_RE, _der_strict_block),
    (_DER_B64_LOOSE_RE, _der_loose_block),
)
_DER_PASS = _DerPass()


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
    (_DER_PASS, None),
    (_POSIX_SPACE_DIR_RE, _mask_space_dirs),
    (_POSIX_TAB_DIR_RE, _mask_tab_dirs),
    (_AUTH_SUBSCRIPT_RE, _mask_auth_subscript),
)
#: 預先過濾：字串裡連必要字面都沒有，就不必讓該條規則掃一遍（純效能；有字面才跑，行為不變）。
_POST_NEEDLES: dict[re.Pattern, tuple[str, ...]] = {
    _FW_ASSIGN_RE: ("＝",), _FW_COLON_QUOTED_RE: ("：",), _FW_COLON_BARE_RE: ("：",),
    _PCT_QUERY_SECRET_RE: ("%3",), _CRED_AFTER_MASK_RE: (MASK,), _DRIVE_OPEN_ID_RE: ("id=",),
    _FWD_UNC_RE: ("//",), _POSIX_PATH_EXTRA_RE: ("@", "→", "—"),
    _DEEP_QUOTED_FIELD_RE: ("\\" * 5,), _DEEP_ASSIGN_TAIL_RE: (MASK + "'", MASK + '"'),
    _DER_PASS: ("M", MASK), _POSIX_SPACE_DIR_RE: ("/",),
    _POSIX_TAB_DIR_RE: ("\t", "\\t"), _AUTH_SUBSCRIPT_RE: ("]",),
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


def scrub_prose_secrets(text) -> str:
    """SEC-r12（2026-09-28）：**問答散文**（使用者的提問、AI 的回答）→ 洗掉金鑰／識別碼／路徑（純函式）。

    ⛔ **錯誤字串不要用這一支**（仍用 `scrub_secrets`）。

    與 `scrub_secrets` **完全相同** —— 同一份 `_RULES`／`_RULES_AFTER_QUERY`／`_RULES_POST`（執行時才讀，
    與 `scrub_secrets` 讀的是同一批物件）、同一個順序、同一個 `scrub_query_secrets` —— **只差一條**：
    第 1 類的解碼例外那一條（`_CONTENT_BEARING_EXC_RE`）換成 `_CONTENT_BEARING_EXC_PROSE_RE`，**依型別分流**：
      · 三種 `Unicode*Error`（`_PROSE_RELAXED_EXC`）：**只截 repr 形**（左括號）；散文形（冒號）**保留後文**；
      · `TomlDecodeError`（與放寬清單以外的任何型別）：兩種形都照舊整段截，同 `scrub_secrets`。
    實證（SEC-r12）：提問「為什麼出現 型別名＋冒號＋錯誤訊息，怎麼解？」原本在畫面、紀錄、送出三處都被截成
    「為什麼出現 型別名」；AI 回答「你看到的是 型別名＋冒號＋…解法：…」整段解法消失。
    分流理由（批 Q QA，2026-09-28）：`Unicode*Error` 只有 repr 形帶原始內容；`TomlDecodeError` 的訊息本身就會
    串入內容（重複表錯誤串入已解析的整包 dict、數字轉換失敗帶出那一行的原始值），詳見該 regex 的註解。

    ⚠️ 據實揭露（比 `scrub_secrets` 少遮的**確切範圍**，只限 `Unicode*Error` 的散文形）：
      只有一種輸入會不同 ——「**第一個**命中第 1 類的位置是 `Unicode*Error` 的散文形（型別名＋可有空白＋冒號）」；
      其餘輸入逐字相同（那一條在這些輸入上取代結果相同 ⇒ 之後每一步吃到的字串都一樣）。
      不同的那一種：輸出 ＝ `scrub_secrets` 把「那些 `Unicode*Error` 散文形的型別名」當成普通字時的輸出 ——
      (a) 冒號起到下一個照截的位置（repr 形、或任何 `TomlDecodeError`；沒有就到字串結尾）⛔ 不再整段拿掉，
          改由其餘每一條規則處理（金鑰、帳密、路徑、Sheet ID、權杖照遮），但**不在任何規則裡的內容會留在畫面上**
          （例：引用的 `UnicodeDecodeError` 訊息裡的一般文字）；
      (b) 原本靠「字串在型別名處結束」才遮得到的**前文**也跟著不遮，兩種例子：
          · 與型別名黏在一起、中間沒有分隔、合計超過長度上限的權杖串（`_CRED_AFTER_MASK_RE` 有 256 字上限）；
          · `no`／`not` 後面緊黏型別名的純字母（例 `password: no hunterUnicodeDecodeError: …` → 露出
            `hunter`：錯誤字串那支截在型別名處，`no hunterUnicodeDecodeError` 整段算否定片語、整段遮；
            散文版後面還接著冒號，否定片語那個分支不成立，只遮得到 `no`）。
      （本實作組自測：`tests/test_sec_r12_r11_prose_scrub.py` 以 AST、語料、蛻變關係三種方式驗證。
       批 Q 獨立 QA（2026-09-28，PASS-with-notes）驗的是分流之前的版本；分流與 (b) 第二例依其意見修，尚未經 QA 複驗。）
    ⚠️ 代價（據實揭露）：`TomlDecodeError` 的散文形照舊整段截 —— 引用 toml 錯誤訊息發問、AI 回答寫出
      「TomlDecodeError: …」時，冒號後面（含問題本身與解法）仍會被截掉，與 `scrub_secrets` 相同。
    ⚠️ Streamlit「Error parsing secrets file …」那一條（第 1 類的另一條）**照舊截斷**：它沒有散文形可放，
      放寬它 ＝ 多開一個少遮的口（其訊息本文會串入已解析的 TOML 內容）→ 本批不做；問答裡引用那句
      Streamlit 訊息時仍會被截（已知邊界）。
    """
    if text is None:
        return ""
    out = str(text)
    for _re, _rep in _RULES:
        out = (_CONTENT_BEARING_EXC_PROSE_RE if _re is _CONTENT_BEARING_EXC_RE else _re).sub(_rep, out)
    out = scrub_query_secrets(out)
    for _re, _rep in _RULES_AFTER_QUERY:
        out = _re.sub(_rep, out)
    for _re, _rep in _RULES_POST:
        _needles = _POST_NEEDLES.get(_re)
        if _needles is None or any(_n in out for _n in _needles):
            out = _re.sub(_rep, out)
    return out
