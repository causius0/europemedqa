# EuropeMedQA

**Multilingual European medical question-answering dataset for LLM benchmarking.**

EuropeMedQA is a curated collection of **12,340 real medical exam questions** drawn from national licensing and specialty-training examinations across four European countries and four languages. It is the data foundation that powers the [medical-ai-leaderboard](https://github.com/causius0/medical-ai-leaderboard) benchmark.

## Contents

The dataset ships in two formats:

| File | Description |
|------|-------------|
| `EuropeMedQA.csv` | Canonical UTF-8 CSV, one row per question, with an `exam` column identifying the source exam. |
| `EuropeMedQA.xlsx` | Original multi-sheet workbook (one sheet per exam). |

## Data description

The CSV contains **12,340 questions** across **6 exam sheets** covering **4 countries / languages**:

| Exam | Country | Language | Questions | Years |
|------|---------|----------|-----------|-------|
| SSM (Scuole di Specializzazione in Medicina) | Italy | Italian | 1,120 | 2017–2024 |
| Abilitazione — clinical | Italy | Italian | 3,390 | 2019 |
| Abilitazione — pre-clinical | Italy | Italian | 3,306 | 2019, 2022–2024 |
| MIR (Médico Interno Residente) | Spain | Spanish | 2,410 | 2013–2023 |
| ECN (Épreuves Classantes Nationales) | France | French | 1,214 | 2019–2022 |
| PNA (Prova Nacional de Acesso) | Portugal | Portuguese | 900 | 2019–2024 |

### Column schema

The canonical CSV uses the union of columns across all exam sheets, prefixed by an `exam` column:

- `exam` — source exam identifier (e.g. `SSM_Italy`, `MIR_Spain`)
- `questionID` — unique question identifier
- `testyear` — exam year
- `numberintest` — question number within the exam
- `picture_provided` — whether an image accompanies the question (where applicable)
- `question_text` — the question stem
- `picture_link` — link to the accompanying image (where applicable)
- `option_a` … `option_e` — answer options
- `correct_option` — letter of the correct option
- `correct_fulltext` — full text of the correct answer
- `domain` / `subdomain` — medical domain and subdomain classification (where present)
- `nullified` — whether the question was nullified/withdrawn (where present)
- `pain`, `location` — additional annotations present in the Italian SSM sheet

Not every column is populated for every exam; columns are filled where the source sheet provides them.

## Provenance

The dataset is a **superset** of the Italian SSM questions used in the [medical-ai-leaderboard](https://github.com/causius0/medical-ai-leaderboard) benchmark. It aggregates real, previously administered national medical examinations — the Italian SSM and Abilitazione, the Spanish MIR, the French ECN, and the Portuguese PNA — into a single multilingual evaluation resource for medical LLMs.

## Usage

Load the CSV with any standard tooling, e.g.:

```python
import pandas as pd
df = pd.read_csv("EuropeMedQA.csv")
print(df["exam"].value_counts())
```

For benchmarking, filter by `exam` to evaluate on a specific national exam, or use the full multilingual set for cross-lingual medical QA evaluation.

## References

- **Paper:** [EuropeMedQA: A Multilingual European Medical Question-Answering Benchmark](https://arxiv.org/abs/2604.14306)
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

## License

The dataset is provided for research and benchmarking purposes. Please respect the terms of the original national examination materials.
