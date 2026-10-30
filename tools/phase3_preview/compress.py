"""PNG 壓縮：> LIMIT 的 PNG 以調色盤量化（PIL）；仍超過就縮小寬度。用法：python tools/phase3_preview/compress.py"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

D = Path(__file__).resolve().parents[2] / "docs" / "vnext" / "phase3_preview"
LIMIT = 280 * 1024      # 目標 <300KB，留餘裕

for p in sorted(D.glob("*.png")):
    if p.stat().st_size <= LIMIT:
        continue
    im = Image.open(p).convert("RGB")
    q = im.quantize(colors=64, method=Image.Quantize.MEDIANCUT)
    q.save(p, optimize=True)
    scale = 1.0
    while p.stat().st_size > LIMIT and scale > 0.5:
        scale -= 0.1
        w, h = int(im.width * scale), int(im.height * scale)
        im.resize((w, h), Image.LANCZOS).quantize(colors=64).save(p, optimize=True)
    print(p.name, p.stat().st_size // 1024, "KB", f"scale={scale:.1f}")
