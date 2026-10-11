# Process study portfolio figures

[그림 3장, 데이터, 한국어 설명 보기](ready-to-use/README_KR.md)

Three 3200 × 1800 PNG figures, three vector SVGs, four CSV tables, and five original solver result JSONs. Re-exported from previously solved cases at source commit `cac40a64f910e42f061992b92cc054d05251d0f0`. No synthetic results, display smoothing, or physical-validation claims were added.

1. ALD exposure duration, thickness and bottom/top coverage.
2. Etch depth and CD under two combined recipe changes; causal attribution is explicitly limited.
3. Coupled RF–Ar power accounting, density and matching losses.

Run `python portfolio/2026-10-process-study/export_portfolio.py` from the repository root to reproduce the figures. Requires NumPy, Matplotlib, and Windows Malgun Gothic. The exporter checks source geometry metrics, coverage ratios, and RF power conservation. The exact renderer versions and input hashes are saved in `ready-to-use/manifest.json`.
