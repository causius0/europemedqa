# Medical Exam CSVs — Build Summary

Built from `data/updates_raw/` → `data/processed_csv/`. Nothing under `updates_raw/` was modified; nothing was committed.

**Totals: 58 CSVs, 7,812 questions, 179 extracted images, 168 image references — all resolve to real files.**

CSV columns (all files): `exam_id, question_number, question_id, question_text, choice_a, choice_b, choice_c, choice_d, choice_e, correct_answer, image_file, language, country, year`

## Per-exam

| Exam | CSV | Questions | Answer-key source | Images |
|---|---|---|---|---|
| SSM Italy 2025 | `ssm_italy_2025.csv` | 140 ✓ | PDF header: correct answer is always **A** | 13 |
| SSM Italy 2026 | `ssm_italy_2026.csv` | 140 ✓ | PDF header: correct answer is always **A** | 9 |
| MIR Spain 2025 | `mir_spain_2025.csv` | 210 ✓ | Official FSE JSON key (`plantilla_definitiva_OFICIAL_v0.json`) | 25 |
| MIR Spain 2026 | `mir_spain_2026.csv` | 210 ✓ | Official `plantilla_definitiva.pdf` (v0 booklet canonical) | 25 |
| EDN France 2023 | `edn_france_2023.csv` | 305 (279 transversal + 26 LCA) ✓ | **None exists** — see below | 29 |
| EDN France 2024 | `edn_france_2024.csv` | 339 (310 + 29 LCA) ✓ | **None exists** — see below | 40 |
| EDN France 2025 | `edn_france_2025.csv` | 318 (289 + 29 LCA) ✓ | **None exists** — see below | 34 |
| PNA Portugal 2025 | `pna_portugal_2025.csv` | 150 ✓ | Official `chave.pdf` ("Prova A" column), 150/150 | 3 |
| PES Poland (50 exams) | `pes_poland_<specialty>_<year>_<wiosna\|jesien>.csv` | 120 each = 6,000 ✓ | Each exam's `(klucz)` key PDF, 6,000/6,000 | 1 |

Per-paper EDN counts match the source manifests exactly (93/93/93, 105/107/98, 93/98/98). The 878 "expected" EDN questions are the transversal papers; the extra 84 rows are the LCA sections.

## Answer keys

- **SSM**: `correct_answer = A` for all 280 rows, per the header printed in both PDFs and consistent with the ☒/X marks on option A in 140/140 questions per year.
- **MIR**: annulled questions **13, 50, 64, 139, 142, 161, 208** are marked `ANNULLED` in both years — verified identical in the 2025 official JSON (nulls) and the 2026 official key PDF (blank cells). MIR exams have 4 options, so `choice_e` is empty. All 420 answers cross-checked against the keys.
- **EDN**: `correct_answer` is **empty for all 962 rows**. The CNG publishes questions-only PDFs with no official corrigé; community corrections exist only inside interactive prep platforms (edn.chat, oreille-externe.fr, refoua.fr) that require a live browser session. No downloadable key exists.
- **PNA**: 150/150 answers from `chave.pdf`.
- **PES**: 6,000/6,000 answers. 11 questions whose klucz marks them annulled keep `correct_answer = X` (list under Issues).

## Images

Extracted with PyMuPDF, saved as PNGs under `images/<exam_id>/`, linked by bare filename in `image_file` (two files for one question are `;`-separated).

- **SSM**: 22 figures, mapped geometrically (image position vs. question header on the page); spot-verified visually (2025 Q33 chest X-ray, Q43 lichen planus skin photo).
- **MIR**: 25 per year from `imagenes.pdf`, matched 1:1 to the image-linked questions (Q*n* → `imagen_NN.png`). Note the source defect fixed below.
- **EDN**: 103 figures; 92 questions linked, including all 24 QZP click-on-image questions.
- **PNA**: Q73 12-lead ECG; Q80 CTG + tocography traces (2 files).
- **PES**: essentially text-only — exactly 1 genuine figure (sleeve-gastrectomy diagram, chirurgia ogólna 2019 wiosna Q100).

## Issues & uncertainties

1. **PES 2021–2022 are scans, not text PDFs** (contrary to the original staging notes). All 40 PDFs in `fallback_nil_2021_2022/` are NAPS2 scans with zero text characters. Those 20 exams were OCR'd with tesseract (`pol`); their question/choice text carries OCR noise and is lower-fidelity than the 2018–2020 text-layer rows. Their **keys were transcribed by hand** from the key-page images (automated key OCR proved unreliable — systematic misreads), stored in `~/workspace/pes_parse/manual_keys/*.json`, each validated to 120 entries.
2. **PES scanned exams — empty choices**: ~47 questions across 17 scanned exams have at least one empty `choice_*` cell where OCR couldn't split a choice cleanly. Correct answers are present for all. Worst: choroby_wewnetrzne 2021 jesień, choroby_wewnetrzne 2022 jesień, medycyna_rodzinna 2021 jesień, psychiatria 2022 jesień (4 each).
3. **PES annulled (`X` in klucz)**: chirurgia 2021 jesień q114; chirurgia 2021 wiosna q15, q78; chirurgia 2022 wiosna q116; choroby wewnętrzne 2021 wiosna q93; medycyna rodzinna 2021 jesień q110; medycyna rodzinna 2022 jesień q105; medycyna rodzinna 2022 wiosna q51; pediatria 2021 wiosna q50; pediatria 2022 jesień q73, q79.
4. **MIR 2026 image defect (fixed)**: the embedded ECG pixmap is mislabeled "Imagen 12" inside the image, but the booklet overlays the correct caption "Imagen 11". `imagen_11.png` is a 150-dpi render of the booklet page as candidates actually saw it; the other 24 are raw embedded images.
5. **EDN question types**: 81 QRP questions have 6–16 proposals — only A–E kept (extras dropped, listed in `edn_france_build_issues.log`). 119 QROC (open short-answer) and 24 QZP questions have no text choices by design. 26 TCS questions use the fixed 5-point Likert scale as choices A–E. 39 questions mention imaging/ECG only descriptively and have no figure — correctly left unlinked.
6. **Minor source defects preserved as-is**: MIR 2026 Q24 "variantepatogénicaenJAK2" (missing spaces in the PDF itself); PNA Q80 stem contains figure-axis text pulled from inside the CTG image; one dropped apostrophe in an EDN stem.
7. **Question IDs**: SSM uses the printed `codice domanda` (ssm2025861–ssm20261220); EDN uses constructed IDs (`edn2023_P1_KFP1_q2`); PES uses `<exam_id>_qNNN`; MIR and PNA have no stable codes in the PDFs, so `question_id` is empty there.
8. **Coordinator note**: the SSM (22) and PNA (3) image files were re-extracted during final assembly after the workers' copies were lost to a VM replacement; filenames match the CSV references exactly and content was spot-verified against the workers' descriptions.

## Build artifacts (for re-runs/audits)

- EDN: `build_edn_csvs.py`, `edn_france_build_issues.log` (this folder)
- PES: `~/workspace/pes_parse/` (parsers, OCR caches, `manual_keys/*.json`)
- MIR: `/tmp/mirbuild/` (ephemeral — may be gone)
