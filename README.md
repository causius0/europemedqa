---
license: cc-by-4.0
pretty_name: EuropeMedQA
task_categories:
- question-answering
language:
- it
- es
- fr
- pt
- pl
multilinguality: multilingual
size_categories:
- 10K<n<100K
source_datasets:
- original
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train-00000-of-00001.parquet
tags:
- medical
- exams
- multiple-choice
- benchmark
---

# EuropeMedQA

**Multilingual European medical question-answering dataset for LLM benchmarking.**

EuropeMedQA is a curated collection of **20,152 real medical exam questions** drawn from national licensing and specialty-training examinations across five European countries and five languages. It is the data foundation that powers the [medical-ai-leaderboard](https://github.com/causius0/medical-ai-leaderboard) benchmark.

## Dataset Description

- **Languages:** Italian, Spanish, French, Portuguese, Polish
- **Task:** multiple-choice medical question answering (1–5 correct options per question)
- **Size:** 20,152 questions, 734 linked images
- **License:** CC BY 4.0 (curation); see [License](#license) for exam-material provenance

## Composition

| Exam | Country | Language | Questions | Years |
|------|---------|----------|-----------|-------|
| SSM (Scuole di Specializzazione in Medicina) | Italy | Italian | 1,400 | 2017–2026 |
| Abilitazione — clinical | Italy | Italian | 3,390 | 2019 |
| Abilitazione — pre-clinical | Italy | Italian | 3,306 | 2019, 2022–2024 |
| MIR (Médico Interno Residente) | Spain | Spanish | 2,830 | 2013–2026 |
| ECN (Épreuves Classantes Nationales) | France | French | 1,214 | 2019–2022 |
| EDN (Épreuves Dématérialisées Nationales, ECN successor) | France | French | 962 | 2023–2025 |
| PNA (Prova Nacional de Acesso) | Portugal | Portuguese | 1,050 | 2019–2025 |
| PES (Państwowy Egzamin Specjalizacyjny) — surgery | Poland | Polish | 1,200 | 2018–2022 |
| PES — internal medicine | Poland | Polish | 1,200 | 2018–2022 |
| PES — family medicine | Poland | Polish | 1,200 | 2018–2022 |
| PES — paediatrics | Poland | Polish | 1,200 | 2018–2022 |
| PES — psychiatry | Poland | Polish | 1,200 | 2018–2022 |

The 2025/26 sittings (SSM 2025–2026, MIR 2025–2026, EDN 2023–2025, PNA 2025) and the Polish PES exams were collected in October 2026 and integrated from the audited build in [`source/processed_csv/`](source/processed_csv/SUMMARY.md) (see its `SUMMARY.md` for per-exam provenance and answer-key sources).

The dataset ships in the following files:

| File | Description |
|------|-------------|
| `data/train-00000-of-00001.parquet` | Typed parquet served by `load_dataset` and the dataset viewer. |
| `EuropeMedQA.csv` | Same content as a quoted UTF-8 CSV, one row per question, with an `exam` column identifying the source exam. |
| `EuropeMedQA.xlsx` | Original multi-sheet workbook for the 2013–2024 exams (one sheet per exam, plus `Legend` and `Domainsubdomain` metadata sheets). |
| `images/` | 179 figures from the 2025/26 exams, referenced by `picture_link` (`images/<exam>/<file>`; `;`-separated when a question has two figures). |
| `source/processed_csv/` | The ingested update CSVs, build script, and build log. |

## Data Fields

| Column | Type | Description |
|--------|------|-------------|
| `exam` | string | Source exam: `SSM_Italy`, `Abilitazione_Italy_clinical`, `Abilitazione_Italy_preclinical`, `MIR_Spain`, `ECN_France`, `EDN_France`, `PNA_Portugal`, `PES_Poland_<specialty>` (5 specialties). |
| `questionID` | string | Question identifier, unique within an exam (e.g. `FR0001`, `ES2411`, `IT0001`, `edn2023_P1_KFP1_q2`, `pes_poland_pediatria_2020_jesien_q073`). |
| `testyear` | int | Exam year; missing for 2,186 Abilitazione pre-clinical rows and 3 legacy MIR rows. |
| `numberintest` | string | Question number within its exam sitting. |
| `picture_provided` | string | `yes`/`no`; untracked (blank) for the two Abilitazione exams. |
| `question_text` | string | The question stem. |
| `picture_link` | string | Image reference. Update-row values are repo-relative paths into `images/` (1,413 legacy rows keep bare source filenames whose files are **not** distributed). `;`-separated when a question has two figures. |
| `option_a` … `option_e` | string | Answer options. 187 questions have no options by design or defect (see Limitations); 2,654 rows have no `option_e`. |
| `correct_option` | string | Correct key(s), upper-case. Multi-answer questions list comma-separated keys (e.g. `A,B,E`, 809 ECN rows). ECN items whose options are Roman numerals keep Roman keys. Blank on 1,053 rows: 962 EDN (no official key exists), 40 withdrawn, 51 otherwise missing. |
| `correct_fulltext` | string | Full text of the correct answer, when provided by the source (legacy rows only). It is a manual transcription: on ~458 SSM rows it differs slightly from the keyed option text (truncations, letter prefixes). Prefer `correct_option` + `option_*` for scoring. |
| `domain` / `subdomain` | string | Medical domain classification, where the source provides it. |
| `nullified` | string | `yes`/`no`; `yes` marks questions withdrawn by the issuing body (91 rows: 63 MIR, 26 PES, 2 PNA). Blank where the exam does not track nullification. |
| `pain` / `location` | string | Additional annotations present only on the SSM sheet. |

Columns are populated where the source exam provides them; not every column applies to every exam.

## Usage

```python
from datasets import load_dataset

ds = load_dataset("causius0/europemedqa")
print(ds["train"][0])
```

With pandas, or when working from a clone of this repository:

```python
import pandas as pd

df = pd.read_csv("EuropeMedQA.csv")
print(df["exam"].value_counts())
```

For benchmarking, filter by `exam` to evaluate on a specific national exam, or use the full multilingual set for cross-lingual medical QA evaluation. For automatic scoring, keep only rows that have an answer key, are not withdrawn, and show at least one option:

```python
def scorable(r):
    return (
        (r["correct_option"] or "") != ""
        and r["nullified"] != "yes"
        and any(r[f"option_{letter}"] for letter in "abcde")
    )

scored = ds.filter(scorable)
```

## Data Cleaning

`EuropeMedQA.csv` and the parquet file are generated by [`scripts/prepare_hf_dataset.py`](scripts/prepare_hf_dataset.py), which applies:

- harmonised `picture_provided` casings (`NO`, `YES `, `SI` → `no`/`yes`);
- the three per-sheet nullification columns merged into one `nullified` column (`ANULADA` → `yes`);
- withdrawn questions (`ANULADA`/`ANNULLED`/`X`) given a blank `correct_option`/`correct_fulltext` and `nullified=yes`;
- ECN multi-answer keys stripped of quotes/brackets (`"A", "B", "E"`, `['A','B','E']` → `A,B,E`);
- lower-case answer keys upper-cased; `testyear` stored as an integer (not `2019.0`);
- one source ID typo fixed (`T1253` → `IT1253` in the Abilitazione pre-clinical exam).

For the 2025/26 updates:

- question numbers repaired in three PES 2022 exams where the build duplicated a number and skipped another (86→88, 56→58, 66→68; verified against the raw JSON collection);
- MIR and PNA update rows have no printed codes, so IDs continue the existing numbering (`ES2411…ES2830`, `PO901…PO1050`) in chronological order;
- update rows carry `picture_link` paths into the repo's `images/` folder.

## Known Limitations

- **EDN France has no answer keys.** The CNG publishes questions-only papers; `correct_option` is blank for all 962 EDN rows. Community keys exist only in interactive prep platforms and were not incorporated.
- **SSM 2025–2026 answer key is `A` for every question** — a property of how the source papers are printed (the marked option is always A), not a data error. Balance the options before using these sittings for evaluation.
- **PES 2021–2022 are OCR'd scans** (20 of 50 exams): text carries OCR noise, 44 questions have empty option cells where OCR could not split choices (their keys are present), and keys for those sittings were transcribed by hand from key-page images.
- **187 questions have no answer options**: 119 EDN QROC (open short-answer) and 24 EDN QZP (click-on-image) by design, plus the 44 PES OCR cases above. 81 EDN QRP questions list 6–16 proposals in the source; only A–E were kept.
- **Legacy images are not distributed**: 1,413 pre-2025 questions reference images by bare source filename only. The 179 figures of the 2025/26 exams ship in `images/`.
- Answer-key formats differ by exam (single letter vs. comma-separated multi-answer vs. Roman numerals), reflecting the real exam formats.
- The questions are real, previously administered national examinations and may contain source errata.

## Provenance

The dataset is a **superset** of the Italian SSM questions used in the [medical-ai-leaderboard](https://github.com/causius0/medical-ai-leaderboard) benchmark. It aggregates real, previously administered national medical examinations — the Italian SSM and Abilitazione, the Spanish MIR, the French ECN and EDN, the Portuguese PNA, and the Polish PES — into a single multilingual evaluation resource for medical LLMs.

## License

The *curation and annotation* of this dataset is released under **CC BY 4.0**, matching the license of the companion paper. The underlying questions originate from national examination bodies; users are responsible for ensuring their use complies with the terms of those institutions. The dataset is intended for research and benchmarking purposes.

## References

- **Paper:** [EuropeMedQA Study Protocol](https://arxiv.org/abs/2604.14306)
- **Leaderboard:** [causius0/medical-ai-leaderboard](https://github.com/causius0/medical-ai-leaderboard)

## Citation

If you use EuropeMedQA in your work, please cite:

```bibtex
@misc{europemedqa2026,
  title  = {EuropeMedQA: A Multilingual European Medical Question-Answering Benchmark},
  author = {Causio, Andrea and others},
  year   = {2026},
  url    = {https://arxiv.org/abs/2604.14306}
}
```
