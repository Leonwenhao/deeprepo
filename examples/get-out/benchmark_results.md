# Film Benchmark: Get Out (2017)

**RLM output:** `examples/get-out/deeprepo_film_get-out-2017.pdf_20260221_221805.md`
**Baseline output:** `examples/get-out/baseline_film_get-out-2017.pdf_20260221_220215.md`

## Extraction Quality (vs Ground Truth)

| Category | GT Items | RLM Found | RLM P/R/F1 | Baseline Found | Baseline P/R/F1 | Winner |
|----------|----------|-----------|------------|----------------|-----------------|--------|
| Characters | 15 | 163 | 0.09/0.93/0.16 | 53 | 0.23/0.80/0.35 | Baseline |
| Props | 25 | 270 | 0.06/0.68/0.12 | 161 | 0.10/0.64/0.17 | Baseline |
| Vehicles | 4 | 98 | 0.02/0.50/0.04 | 54 | 0.04/0.50/0.07 | Baseline |
| Locations | 9 | 2 | 0.00/0.00/0.00 | 0 | 0.00/0.00/0.00 | Tie |
| Wardrobe | 14 | 53 | 0.00/0.00/0.00 | 63 | 0.05/0.21/0.08 | Baseline |
| Vfx | 7 | 78 | 0.03/0.29/0.05 | 22 | 0.09/0.29/0.14 | Baseline |
| Music | 5 | 140 | 0.01/0.20/0.01 | 31 | 0.03/0.20/0.06 | Baseline |
| Stunts | 25 | 85 | 0.01/0.04/0.02 | 35 | 0.06/0.08/0.07 | Baseline |

**Average F1:** RLM = 0.049, Baseline = 0.117

## Key
- P = Precision (correct / total extracted)
- R = Recall (correct / total ground truth)
- F1 = Harmonic mean of P and R
- Winner determined by F1 difference > 0.02