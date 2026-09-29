# Korean semiconductor study guide

One integrated 32-page PDF for learning the actual Process Studio ALD/Etch models
and designing a small AMK PSE portfolio project. Includes a 14-day core plan,
optional 7-day extension, semiconductor fundamentals, implemented equations and
units, worked examples, troubleshooting, metrology, and ASML/KLA context.

Final artifact: `output/pdf/Process_Studio_Semiconductor_Study_KR.pdf`.

## Rebuild

From the repository root, with Python 3.10 or newer:

```powershell
python -m pip install -r sim_app/requirements.txt -r docs/study/requirements.txt
python docs/study/build_study_pdf.py
```

The builder imports the actual Python models through `sim_app.service`, reruns
the eight reference cases, and draws three vector charts from those outputs.
Numerical guards reject a rebuild when key model results have changed; update
the study text and static table values only after reviewing the new behavior.
The guide's fixed date and model versions describe this edition, not future
versions. Timestamps in PDF metadata can differ between builds.

Fonts default to Windows `C:/Windows/Fonts`: `malgun.ttf`, `malgunbd.ttf`, and
`arial.ttf`. Fonts are embedded as subsets, so readers need not install them.
No font binaries are redistributed in the repository. On another platform,
provide a directory containing legally available copies with those names:

```powershell
python docs/study/build_study_pdf.py --font-dir /path/to/fonts
```

Superscripts/subscripts are typeset through ReportLab markup to avoid missing
Unicode glyphs in Malgun Gothic. The approximately-equal sign uses Arial.
The builder does not require a network connection or a running web server.

## Verification of the 2026-09-30 edition

- Generated 32 pages with 32 navigation bookmarks and 9 clickable links.
- Reran 8 reference cases and confirmed the baseline, RF fault, time
  compensation, high-bias and ALD purge examples against current model outputs.
- Rendered all 32 pages with Poppler at 100 dpi and visually inspected the
  complete contact sheets; inspected equations, unit exponents, plots, tables
  and bibliography at full page resolution.
- Corrected missing mathematical glyphs discovered during visual review.
- Checked extracted text, exact page footer sequence, horizontal text margins,
  page bounds, and replacement characters. Layout guards stop on overflow.
- This verifies the document and its consistency with the code. It is not an
  independent physical validation of the models or measured equipment results.

QA intermediates are in ignored `local/pdf_qa/`, not in the public deliverable.
Use Poppler to review a rebuild, e.g.:

```powershell
pdftoppm -r 100 -png output/pdf/Process_Studio_Semiconductor_Study_KR.pdf local/pdf_qa/page
```

## Evidence and source boundaries

The equations in the guide describe repository implementations, not newly
verified claims about commercial equipment. `ALD_MODEL.md` and `ETCH_MODEL.md`
distinguish literature coefficients from project assumptions. The guide does
not claim a TCAD replacement, actual equipment troubleshooting, measured film
quality, or a validated SF6/CF4/Cl2 reaction network.

Primary external sources checked on 2026-09-30:

- ASML: *How microchips are made*; *The Rayleigh criterion for resolution*.
- Aalto research portal: Ylilammi, Ylivaara & Puurunen (2018), DOI
  10.1063/1.5028178. The institutional abstract and bibliographic record were
  read. Full-paper URLs were blocked/timed out in this run; the guide relies on
  the repository's documented implementation for the detailed equations and
  does not claim a fresh full-paper replication.
- UC Berkeley: Kim (2006), UCB/EECS-2006-56, primary technical report.
- Applied Materials: PSE Etch job R2619048, Hillsboro. This experienced-hire
  role is used only to connect hypothesis experiments, DOE and root-cause
  analysis; its qualifications are not AMK entry-level hiring requirements.
- NIST/SEMATECH: *What is Process Capability?*.
- KLA: *Chip Manufacturing* product/technology overview.

Clickable citations are in the PDF. ASML TSE/KLA FAE connections are learning
suggestions, not claims that this guide covers a particular vacancy completely.
AI assisted code and document creation. Learners must distinguish their own
experiment design, verification and interpretation when using this portfolio.
