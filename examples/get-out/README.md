# Get Out (2017) — Film Domain Benchmark

## Overview
This directory contains benchmark results for the deeprepo film vertical
using the screenplay of *Get Out* (2017).

## Screenplay Acquisition
The actual screenplay PDF is **not included** in this repository (copyrighted material).
To reproduce the benchmark:

1. Search for "Get Out 2017 screenplay PDF" — multiple publicly hosted versions exist
2. Save the file as `get-out-2017.pdf` (or `.txt`) in this directory
3. The file is already in `.gitignore`

## Running the Benchmark

### RLM Analysis
deeprepo analyze examples/get-out/get-out-2017.pdf --domain film -o examples/get-out/

### Baseline Comparison
deeprepo baseline examples/get-out/get-out-2017.pdf --domain film -o examples/get-out/

### Scoring
python scripts/score_film_benchmark.py \
  --rlm examples/get-out/rlm_*.md \
  --baseline examples/get-out/baseline_*.md \
  --ground-truth GET_OUT_GROUND_TRUTH.md \
  --output examples/get-out/benchmark_results.md

## Ground Truth
See `GET_OUT_GROUND_TRUTH.md` in the project root — compiled from 23 publicly available sources (IMDb, production interviews, critical analysis).
