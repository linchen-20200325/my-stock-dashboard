"""A2 scratch 證據提交前掃描（唯讀；任一違規 → exit 1；**A2 scratch 增補，非 #1268 內容**）。

用法（獨立腳本，不 import repo 其他模組）::

    python tests/ui2_viewport/a2_evidence_privacy_scan.py docs/vnext/onebrain_a2_scratch_evidence

掃什麼（對 json／md／txt／MANIFEST／SHA256SUMS 做文字規則；對 png 做結構規則）：
 1. 路徑／環境／憑證樣式：`/tmp/` `/home/` `/root/` `/opt/` `/Users/` `C:\\` `claude-0` `scratchpad` `a076536a` `session_` `ccr-`
    email 樣式、`ghp_` `github_pat_` `sk-`（需前接非英數＝獨立 token 起首，避免 `task-` 之類假陽性）`AIza` `AKIA` `Bearer `
    `token` `secret` `password` `api_key` `hostname` `user-agent`（後五者不分大小寫）、私網 IP（10.x／172.16-31.x／192.168.x）、
    `127.0.0.1:` `localhost:`。
 2. 內容守衛：JSON 內所有 `page_text`／`slot_text`／`page_text_ex_testinfo` 必含 FAKE
    （例外：`real_control.*`＝Real 對照槽，依設計不含示範文字，改要求 `no_demo_text` 為真且無槽外說明；其餘規則照掃），且不得有「非 FAKE-T」的台股四碼代碼樣式、
    金額樣式、帳號樣式（長數字／身分證樣式）；`network_sealed` 的 server_rejected／context_aborted 必為 0，外網 URL／host 陣列為空。
 3. PNG：只許 IHDR／PLTE／IDAT／IEND chunk（無 tEXt／iTXt／eXIf 等）、CRC 正確、尺寸合理（寬＝視窗寬；viewport 圖高＝視窗高）。
 4. SHA256SUMS 對每檔重算一致且無漏檔／多檔；MANIFEST.files 的 sha256／bytes 與實檔一致；base_head_sha＝711142ce 全 40 字元。
 5. 檔案白名單：副檔名只許 png／json／md／SHA256SUMS；單檔 ≤ 5 MB；不得含 `_DARK`／`supplementary_preview_css`；`_REALFEED` 只許 R1。
 6. 結果守衛：每版 runs＝5、failing＝0、15/15 viewport 通過、兩項新判定皆為真。
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path

BASE_HEAD_SHA = "711142ce38c5cdae07144ae164a72a3bb0f9df6a"
MAX_BYTES = 5 * 1024 * 1024
ALLOWED_EXT = {".png", ".json", ".md"}
PNG_ALLOWED_CHUNKS = {b"IHDR", b"PLTE", b"IDAT", b"IEND"}
VIEWPORTS = {"mobile_390": (390, 844), "desktop_1280": (1280, 900), "desktop_1440": (1440, 900)}
CASES = ("R1", "L1", "L2", "L3", "FAILCLOSED")
NEW_CHECKS = ("no_fake_t_above_slot", "caption_after_slot")

# (名稱, regex)。大小寫敏感者不加 IGNORECASE。
TEXT_RULES: list[tuple[str, re.Pattern]] = [
    ("/tmp/", re.compile(r"/tmp/")), ("/home/", re.compile(r"/home/")), ("/root/", re.compile(r"/root/")),
    ("/opt/", re.compile(r"/opt/")), ("/Users/", re.compile(r"/Users/")), ("C:\\", re.compile(r"C:\\")),
    ("claude-0", re.compile(r"claude-0")), ("scratchpad", re.compile(r"scratchpad")), ("a076536a", re.compile(r"a076536a")),
    ("session_", re.compile(r"session_")), ("ccr-", re.compile(r"ccr-")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("ghp_", re.compile(r"ghp_")), ("github_pat_", re.compile(r"github_pat_")),
    ("sk-", re.compile(r"(?<![A-Za-z0-9])sk-")), ("AIza", re.compile(r"AIza")), ("AKIA", re.compile(r"AKIA")),
    ("Bearer ", re.compile(r"Bearer ")),
    ("token", re.compile(r"token", re.I)), ("secret", re.compile(r"secret", re.I)), ("password", re.compile(r"password", re.I)),
    ("api_key", re.compile(r"api_key", re.I)), ("hostname", re.compile(r"hostname", re.I)),
    ("user-agent", re.compile(r"user-agent", re.I)),
    ("private-ip", re.compile(r"(?<![\d.])(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})(?![\d])")),
    ("127.0.0.1:", re.compile(r"127\.0\.0\.1:")), ("localhost:", re.compile(r"localhost:")),
]
# 內容守衛：台股四碼（獨立 4 位數字）、金額、帳號
RX_TW_CODE = re.compile(r"(?<![\dA-Za-z-])\d{4}(?![\d])")
RX_MONEY = re.compile(r"NT\$|\$\s?\d|\d[\d,]*(?:\.\d+)?\s?(?:元|萬元|百萬|億|TWD|USD)")
RX_ACCOUNT = re.compile(r"\d{8,}|[A-Z][12]\d{8}")
TEXT_FIELDS = ("page_text", "slot_text", "page_text_ex_testinfo")


def _walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _walk(v, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, o


def _scan_text(rel: str, text: str, errs: list[str]) -> None:
    for name, rx in TEXT_RULES:
        m = rx.search(text)
        if m:
            errs.append(f"{rel}: 命中規則 {name!r}（位置 {m.start()}）")


def _scan_json(rel: str, doc, errs: list[str]) -> None:
    for path, val in _walk(doc):
        key = path.rsplit("/", 1)[-1]
        if key in TEXT_FIELDS and isinstance(val, str):
            if "/real_control/" in path:
                # Real 對照：槽必須是預設槽，**不含**示範文字（故不要求 FAKE）；改查 no_demo_text 為真（見下）
                pass
            elif "FAKE" not in val:
                errs.append(f"{rel}{path}: 不含 FAKE")
            body = val.replace("FAKE-T", "")
            for nm, rx in (("台股四碼樣式", RX_TW_CODE), ("金額樣式", RX_MONEY), ("帳號樣式", RX_ACCOUNT)):
                m = rx.search(body)
                if m:
                    errs.append(f"{rel}{path}: 出現{nm} {m.group(0)!r}")
    if isinstance(doc, dict) and doc.get("real_control"):
        for vp, rc in doc["real_control"].items():
            if rc.get("no_demo_text") is not True or rc.get("testinfo_present"):
                errs.append(f"{rel}: real_control.{vp} 不是乾淨的 Real 預設槽")
    meta = doc.get("meta") if isinstance(doc, dict) else None
    if meta:
        ns = meta.get("network_sealed") or {}
        for k in ("server_rejected", "context_aborted"):
            if ns.get(k) != 0:
                errs.append(f"{rel}: network_sealed.{k}={ns.get(k)!r}（必為 0）")
        for k in ("server_rejected_hosts", "context_aborted_urls"):
            if ns.get(k) != []:
                errs.append(f"{rel}: network_sealed.{k} 不是空陣列")
    if isinstance(doc, dict) and isinstance(doc.get("runs"), list):          # summary.json
        for r in doc["runs"]:
            n = r.get("network") or {}
            if n.get("server_rejected") != 0 or n.get("context_aborted") != 0 or n.get("server_rejected_hosts") != [] \
                    or n.get("context_aborted_urls") != []:
                errs.append(f"{rel}: {r.get('case')} 的 network 不是全 0／空陣列")


def _scan_png(rel: str, data: bytes, errs: list[str]) -> tuple[int, int] | None:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        errs.append(f"{rel}: 不是 PNG 簽名")
        return None
    pos, wh, seen = 8, None, []
    while pos + 8 <= len(data):
        ln, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + ln]
        crc = struct.unpack(">I", data[pos + 8 + ln:pos + 12 + ln])[0]
        if zlib.crc32(typ + body) & 0xFFFFFFFF != crc:
            errs.append(f"{rel}: chunk {typ!r} CRC 錯誤")
        if typ not in PNG_ALLOWED_CHUNKS:
            errs.append(f"{rel}: 不允許的 chunk {typ!r}")
        seen.append(typ)
        if typ == b"IHDR":
            wh = struct.unpack(">II", body[:8])
        pos += 12 + ln
        if typ == b"IEND":
            break
    if not seen or seen[0] != b"IHDR" or seen[-1] != b"IEND":
        errs.append(f"{rel}: chunk 序列不是 IHDR…IEND")
    if pos != len(data):
        errs.append(f"{rel}: IEND 後有多餘位元組")
    if wh is None or not (1 <= wh[0] <= 2000 and 1 <= wh[1] <= 8000):
        errs.append(f"{rel}: PNG 尺寸異常 {wh}")
    return wh


def _check_png_dims(rel: str, wh, errs: list[str]) -> None:
    if wh is None:
        return
    name = Path(rel).name
    vp = next((k for k in VIEWPORTS if f"_{k}_" in name), None)
    if vp is None:
        errs.append(f"{rel}: 檔名無法辨識視窗")
        return
    vw, vh = VIEWPORTS[vp]
    if name.endswith("_viewport.png") and wh != (vw, vh):
        errs.append(f"{rel}: viewport 圖尺寸 {wh} ≠ {(vw, vh)}")
    elif "_clip" in name and wh[0] != vw:
        errs.append(f"{rel}: clip 圖寬 {wh[0]} ≠ {vw}")
    elif (name.endswith("_slot.png") or name.endswith("_testinfo.png")) and wh[0] > vw:
        errs.append(f"{rel}: 元素圖寬 {wh[0]} > 視窗寬 {vw}")


def scan(ev: Path) -> list[str]:
    errs: list[str] = []
    ev = ev.resolve()
    if not ev.is_dir():
        return [f"{ev.name}: 不是目錄"]
    files = sorted((p for p in ev.rglob("*") if p.is_file()), key=lambda p: p.relative_to(ev).as_posix())
    rels = {p.relative_to(ev).as_posix(): p for p in files}
    for rel, p in rels.items():
        name = p.name
        if name != "SHA256SUMS" and p.suffix not in ALLOWED_EXT:
            errs.append(f"{rel}: 副檔名不在白名單（png／json／md／SHA256SUMS）")
        if p.stat().st_size > MAX_BYTES:
            errs.append(f"{rel}: 超過 5 MB（{p.stat().st_size}）")
        if "_DARK" in name or "supplementary_preview_css" in rel:
            errs.append(f"{rel}: 不得包含 _DARK／supplementary_preview_css")
        if "_REALFEED" in name and not name.startswith("R1_"):
            errs.append(f"{rel}: _REALFEED 只許 R1")
        data = p.read_bytes()
        if p.suffix == ".png":
            _check_png_dims(rel, _scan_png(rel, data, errs), errs)
        else:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                errs.append(f"{rel}: 非 UTF-8 文字")
                continue
            _scan_text(rel, text, errs)
            if p.suffix == ".json":
                try:
                    _scan_json(rel, json.loads(text), errs)
                except json.JSONDecodeError as e:
                    errs.append(f"{rel}: JSON 解析失敗 {e}")
    # SHA256SUMS
    sums = ev / "SHA256SUMS"
    if not sums.exists():
        errs.append("SHA256SUMS: 缺")
    else:
        listed: dict[str, str] = {}
        for ln in sums.read_text(encoding="utf-8").splitlines():
            m = re.fullmatch(r"([0-9a-f]{64})  (\S.*)", ln)
            if not m:
                errs.append(f"SHA256SUMS: 格式錯誤 {ln[:60]!r}")
                continue
            if m.group(2) in listed:
                errs.append(f"SHA256SUMS: 重複 {m.group(2)}")
            listed[m.group(2)] = m.group(1)
        for rel, p in rels.items():
            if rel == "SHA256SUMS":
                continue
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            if rel not in listed:
                errs.append(f"SHA256SUMS: 漏列 {rel}")
            elif listed[rel] != h:
                errs.append(f"SHA256SUMS: {rel} 雜湊不符")
        for rel in listed:
            if rel not in rels:
                errs.append(f"SHA256SUMS: 列了不存在的檔 {rel}")
    # MANIFEST
    mp = ev / "MANIFEST.json"
    if not mp.exists():
        errs.append("MANIFEST.json: 缺")
        return errs
    man = json.loads(mp.read_text(encoding="utf-8"))
    if man.get("base_head_sha") != BASE_HEAD_SHA:
        errs.append("MANIFEST: base_head_sha 不是 711142ce 全 40 字元")
    if "非 DEC-137" not in str(man.get("label")):
        errs.append("MANIFEST: label 未標「非 DEC-137 正式存證」")
    mfiles = {e["path"]: e for e in man.get("files", [])}
    for rel, p in rels.items():
        if rel in ("MANIFEST.json", "SHA256SUMS"):
            continue
        e = mfiles.get(rel)
        if e is None:
            errs.append(f"MANIFEST.files: 漏列 {rel}")
        elif e["sha256"] != hashlib.sha256(p.read_bytes()).hexdigest() or e["bytes"] != p.stat().st_size:
            errs.append(f"MANIFEST.files: {rel} sha256／bytes 不符")
    for rel in mfiles:
        if rel not in rels:
            errs.append(f"MANIFEST.files: 列了不存在的檔 {rel}")
    if man.get("other_three_identical_to_1268_head") and not all(man["other_three_identical_to_1268_head"].values()):
        errs.append("MANIFEST: 其餘三檔未與 #1268 head 逐位元相同")
    rb = man.get("runner_blob_sha") or {}
    if not (rb.get("head_1268") and rb.get("a2_modified")):
        errs.append("MANIFEST: 缺 runner 的兩個 blob SHA")
    # 結果守衛
    for vdir, run in (man.get("runs") or {}).items():
        if run.get("runs") != 5 or run.get("failing") != 0:
            errs.append(f"{vdir}: runs={run.get('runs')} failing={run.get('failing')}（須 5／0）")
        if run.get("viewports_total") != 15 or run.get("viewports_passing") != 15:
            errs.append(f"{vdir}: viewport {run.get('viewports_passing')}/{run.get('viewports_total')}（須 15/15）")
        if sorted(run.get("cases", {})) != sorted(CASES):
            errs.append(f"{vdir}: 案例集合不是 {CASES}")
        for case, c in run.get("cases", {}).items():
            jp = ev / c["json"]
            if not jp.exists():
                errs.append(f"{vdir}: 缺 {c['json']}")
                continue
            doc = json.loads(jp.read_text(encoding="utf-8"))
            for vp, chk in ((doc.get("a2") or {}).get("new_checks") or {}).items():
                if not all(chk.get(k) is True for k in NEW_CHECKS):
                    errs.append(f"{c['json']}:{vp}: 新判定非真 {chk}")
            if sorted((doc.get("a2") or {}).get("new_checks") or {}) != sorted(VIEWPORTS):
                errs.append(f"{c['json']}: 缺視窗的新判定")
    if man.get("runs") and len(man["runs"]) != 2:
        errs.append(f"MANIFEST.runs 版本數 {len(man['runs'])} ≠ 2")
    return errs


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("用法：a2_evidence_privacy_scan.py <證據目錄>", file=sys.stderr)
        return 2
    errs = scan(Path(argv[0]))
    if errs:
        for e in errs:
            print("FAIL", e)
        print(f"scan FAILED：{len(errs)} 項")
        return 1
    print("scan OK：全部規則通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
