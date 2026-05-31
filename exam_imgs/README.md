# Test dataset (Phase 1)

Place 10–15 comic page images here for benchmark and QA:

- Western comics (LTR)
- Manga (RTL) — set `reading_direction: rtl` in config.yaml
- Webtoon / splash / overlapping panels

Current samples:

- `01_Asterix_the_Gaul_page-0002.jpg`
- `01_Asterix_the_Gaul_page-0004.jpg`

Run benchmark:

```powershell
python benchmark.py --dataset exam_imgs
```

Phase 1 target: **fast mode** (YOLO only) **&lt; 600 ms/page** on Ryzen 5600H-class CPU.
