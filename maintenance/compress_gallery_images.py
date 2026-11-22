import csv
import os
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(".")
MANIFEST = ROOT / "maintenance" / "gallery_images_manifest.csv"
BATCH = os.environ.get("BATCH_FILTER", "Batch 10")
MAX_DIM = int(os.environ.get("MAX_DIM", "1800"))
QUALITY = int(os.environ.get("JPEG_QUALITY", "80"))
MIN_BYTES = int(os.environ.get("MIN_BYTES", str(400 * 1024)))

seen = set()
targets = []
with MANIFEST.open(newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row.get("Batch") != BATCH or row.get("Exists") != "Yes":
            continue
        path = row.get("Image Path", "")
        if path in seen:
            continue
        seen.add(path)
        p = ROOT / path
        if p.suffix.lower() not in {".jpg", ".jpeg"} or not p.exists():
            continue
        targets.append(p)

report = []
for p in targets:
    before = p.stat().st_size
    if before <= MIN_BYTES:
        report.append([str(p), before, before, 0.0, "skipped-small"])
        continue
    try:
        with Image.open(p) as src:
            img = ImageOps.exif_transpose(src).convert("RGB")
            if max(img.size) > MAX_DIM:
                img.thumbnail((MAX_DIM, MAX_DIM), Image.Resampling.LANCZOS)
            tmp = p.with_suffix(p.suffix + ".tmp")
            img.save(tmp, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        after = tmp.stat().st_size
        if after < before:
            tmp.replace(p)
            pct = round((1 - after / before) * 100, 1)
            report.append([str(p), before, after, pct, "compressed"])
        else:
            tmp.unlink(missing_ok=True)
            report.append([str(p), before, before, 0.0, "kept-original"])
    except Exception as e:
        report.append([str(p), before, before, 0.0, f"error: {e}"])

out = ROOT / "maintenance" / "compression_last_run.csv"
with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Image Path", "Before Bytes", "After Bytes", "Reduction Percent", "Status"])
    w.writerows(report)

before_total = sum(r[1] for r in report)
after_total = sum(r[2] for r in report)
print(f"Batch: {BATCH}")
print(f"Files considered: {len(report)}")
print(f"Before MB: {before_total/1048576:.2f}")
print(f"After MB: {after_total/1048576:.2f}")
print(f"Saved MB: {(before_total-after_total)/1048576:.2f}")
