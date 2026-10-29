"""Build the canonical EuropeMedQA data files from the original workbook.

Reads EuropeMedQA.xlsx (one sheet per national exam, plus Legend and
Domainsubdomain metadata sheets), harmonises the per-sheet schemas into the
canonical column set, and writes:
- EuropeMedQA.csv — quoted CSV, one row per question (human-readable)
- data/train-00000-of-00001.parquet — typed file served on the Hugging Face Hub

Normalisations applied (see normalise_correct_option / consolidate_nullified):
- picture_provided casings (no/NO, yes/'YES '/SI) -> yes/no
- the three per-sheet nullified columns -> one column, 'ANULADA' -> 'yes'
- correct_option: quotes stripped from ECN multi-answer keys, lower-case
  letter keys upper-cased, 'ANULADA' withdrawn questions -> NA + nullified=yes
- 'domain 2 ' (some MIR rows) folded into 'domain'

Run from the repository root:

    python scripts/prepare_hf_dataset.py
"""

from pathlib import Path
import csv

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "EuropeMedQA.xlsx"
OUT_CSV = ROOT / "EuropeMedQA.csv"
OUT_PARQUET = ROOT / "data" / "train-00000-of-00001.parquet"
UPDATES_DIR = ROOT / "source" / "processed_csv"
IMAGES_DIR = ROOT / "images"

# Sheet name -> canonical exam identifier
SHEET_TO_EXAM = {
    "SSM_Q_ITA": "SSM_Italy",
    "ABILITAZIONE_ITA_clinica": "Abilitazione_Italy_clinical",
    "ABILITAZIONE_ITA_pre_clinica": "Abilitazione_Italy_preclinical",
    "MIR_Q_ESP": "MIR_Spain",
    "ECN_Q_FRA": "ECN_France",
    "PNA_Q_POR": "PNA_Portugal",
}

CANONICAL_COLUMNS = [
    "exam",
    "questionID",
    "testyear",
    "numberintest",
    "picture_provided",
    "question_text",
    "picture_link",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "option_e",
    "correct_option",
    "correct_fulltext",
    "domain",
    "subdomain",
    "nullified",
    "pain",
    "location",
]

EXPECTED_COUNTS = {
    "SSM_Italy": 1120,
    "Abilitazione_Italy_clinical": 3390,
    "Abilitazione_Italy_preclinical": 3306,
    "MIR_Spain": 2410,
    "ECN_France": 1214,
    "PNA_Portugal": 900,
}

# exam -> question count in the 2025/26 updates (source/processed_csv)
UPDATES_COUNTS = {
    "SSM_Italy": 280,               # 2025 + 2026, 140 each
    "MIR_Spain": 420,               # 2025 + 2026, 210 each
    "EDN_France": 962,              # 2023 + 2024 + 2025
    "PNA_Portugal": 150,            # 2025
    "PES_Poland_chirurgia_ogolna": 1200,
    "PES_Poland_choroby_wewnetrzne": 1200,
    "PES_Poland_medycyna_rodzinna": 1200,
    "PES_Poland_pediatria": 1200,
    "PES_Poland_psychiatria": 1200,
}

# Final row order: each exam's questions form one contiguous block, in this
# order; update rows append to their exam's block.
CANONICAL_EXAM_ORDER = [
    "SSM_Italy",
    "Abilitazione_Italy_clinical",
    "Abilitazione_Italy_preclinical",
    "MIR_Spain",
    "ECN_France",
    "PNA_Portugal",
    "EDN_France",
    "PES_Poland_chirurgia_ogolna",
    "PES_Poland_choroby_wewnetrzne",
    "PES_Poland_medycyna_rodzinna",
    "PES_Poland_pediatria",
    "PES_Poland_psychiatria",
]

# first free questionID numbers per exam in the canonical dataset
ID_CONTINUATION = {"MIR_Spain": ("ES", 2411, 4), "PNA_Portugal": ("PO", 901, 3)}

SEASON_ORDER = {"wiosna": 0, "jesien": 1}


def updates_exam_and_sort_key(stem: str) -> tuple[str, tuple]:
    """Map a processed_csv filename stem to its canonical exam identifier and
    a chronological sort key."""
    if stem.startswith("ssm_italy"):
        return "SSM_Italy", (int(stem.rsplit("_", 1)[1]),)
    if stem.startswith("mir_spain"):
        return "MIR_Spain", (int(stem.rsplit("_", 1)[1]),)
    if stem.startswith("pna_portugal"):
        return "PNA_Portugal", (int(stem.rsplit("_", 1)[1]),)
    if stem.startswith("edn_france"):
        return "EDN_France", (int(stem.rsplit("_", 1)[1]),)
    if stem.startswith("pes_poland_"):
        rest = stem.removeprefix("pes_poland_")
        specialty, year, season = rest.rsplit("_", 2)
        return f"PES_Poland_{specialty}", (int(year), SEASON_ORDER[season])
    raise ValueError(f"unknown updates exam: {stem}")


def load_updates() -> pd.DataFrame:
    """Ingest the 2025/26 exam CSVs (source/processed_csv) into the canonical
    schema, appending them after their exam's existing block (or at the end
    for EDN_France and the PES specialties)."""
    frames = []
    for csv_path in UPDATES_DIR.glob("*.csv"):
        exam, sort_key = updates_exam_and_sort_key(csv_path.stem)
        frames.append(((exam, sort_key), pd.read_csv(csv_path, dtype="string").assign(_exam=exam)))
    frames.sort(key=lambda item: item[0])
    raw = pd.concat([df for _, df in frames], ignore_index=True)

    # Build fix: three PES exams carry a duplicated question_number whose
    # second copy is the exam's missing number (verified against the raw JSON
    # collection). Reassign those rows before anything else.
    for exam_id, group in raw.groupby("exam_id"):
        nums = group["question_number"].astype(int)
        if not nums.duplicated().any():
            continue
        dup_idx = nums.index[nums.duplicated(keep="first")]
        missing = sorted(set(range(1, len(group) + 1)) - set(nums))
        assert len(dup_idx) == len(missing), f"{exam_id}: unexpected dup pattern"
        for i, m in zip(dup_idx, missing):
            raw.loc[i, "question_number"] = str(m)
            raw.loc[i, "question_id"] = f"{exam_id}_q{m:03d}"
        assert not raw.loc[group.index, "question_number"].duplicated().any()

    # Construct questionIDs where the source has none (MIR, PNA), continuing
    # each exam's existing numbering in chronological order. The updates
    # sittings differ by year, so (year, question_number) orders them.
    for exam, (prefix, start, width) in ID_CONTINUATION.items():
        mask = (raw["_exam"] == exam) & raw["question_id"].isna()
        ordered = raw[mask].assign(
            _n=raw.loc[mask, "year"].astype(int) * 1000
            + raw.loc[mask, "question_number"].astype(int)
        ).sort_values("_n")
        numbers = list(range(start, start + int(mask.sum())))
        raw.loc[ordered.index, "question_id"] = [
            f"{prefix}{n:0{width}d}" if n < 10**width else f"{prefix}{n}" for n in numbers
        ]

    out = pd.DataFrame(index=raw.index)
    out["exam"] = raw["_exam"]
    out["questionID"] = raw["question_id"]
    out["testyear"] = pd.to_numeric(raw["year"], errors="coerce").astype("Int64")
    out["numberintest"] = raw["question_number"]
    img = raw["image_file"].astype("string")
    out["picture_provided"] = img.notna().map({True: "yes", False: "no"})
    out["picture_link"] = raw.apply(
        lambda r: (
            ";".join(f"images/{r['exam_id']}/{p.strip()}" for p in str(r["image_file"]).split(";"))
            if pd.notna(r["image_file"]) else pd.NA
        ),
        axis=1,
    )
    out["question_text"] = raw["question_text"]
    for letter in "abcde":
        out[f"option_{letter}"] = raw[f"choice_{letter}"]

    ans = raw["correct_answer"].astype("string").str.strip().str.upper()
    annulled = ans.isin(["ANNULLED", "X"])
    out["correct_option"] = ans.mask(annulled).mask(ans.eq(""), pd.NA)
    out["nullified"] = pd.Series(pd.NA, index=raw.index, dtype="string")
    out.loc[annulled, "nullified"] = "yes"
    return out


def normalise_picture_provided(series: pd.Series) -> pd.Series:
    """Harmonise NO/no, YES/'YES '/SI casings into yes/no, preserving NaN."""
    return series.astype("string").str.strip().str.lower().map(
        {"no": "no", "yes": "yes", "si": "yes"}
    )


def consolidate_nullified(df: pd.DataFrame) -> pd.Series:
    """Merge the per-sheet nullified columns ('nullified', 'Nullified',
    'nullified ') into one. 'ANULADA' (PNA) means the question was withdrawn
    -> 'yes'. NaN stays NaN where an exam does not track nullification."""
    cols = [c for c in ["nullified", "Nullified", "nullified "] if c in df.columns]
    if not cols:
        return pd.Series(pd.NA, index=df.index, dtype="string")
    merged = (
        df[cols]
        .astype("string")
        .bfill(axis=1)
        .iloc[:, 0]
        .str.strip()
        .str.lower()
        .replace({"anulada": "yes"})
    )
    return merged


def normalise_correct_option(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Clean correct_option/correct_fulltext.

    - Strip the quote/bracket styles ECN uses on multi-answer keys
      ('"A", "B", "E"', "['A','B','E']" -> 'A,B,E') and upper-case letter keys
      recorded in lower case (MIR, Abilitazione). Roman-numeral ECN options
      (I–IV) are left untouched.
    - 'ANULADA' marks withdrawn questions: the key/fulltext become NA and the
      question is flagged nullified. This also covers the MIR rows whose only
      nullification marker is an ANULADA fulltext.

    Returns (correct_option, correct_fulltext, extra_nullified_mask).
    """
    option = df["correct_option"].astype("string").str.strip()
    fulltext = df["correct_fulltext"].astype("string").str.strip()

    # .fillna(False): eq() on NA fulltext yields NA, and mask() treats NA
    # conditions as "replace", which would wipe valid keys (pandas Kleene
    # logic: False | NA -> NA).
    anulada = option.str.upper().eq("ANULADA").fillna(False) | fulltext.str.upper().eq(
        "ANULADA"
    ).fillna(False)
    option = option.mask(anulada)
    fulltext = fulltext.mask(fulltext.str.upper().eq("ANULADA"))

    option = option.str.replace(r"[\"\'\[\]\s]", "", regex=True)
    plain = option.str.fullmatch(r"[a-exX]+(,[a-exX]+)*", case=False).fillna(False)
    option = option.mask(plain, option.str.upper())
    return option, fulltext, anulada


def load_sheet(sheet: str) -> pd.DataFrame:
    df = pd.read_excel(XLSX, sheet_name=sheet)
    df.columns = [c.strip() for c in df.columns]

    # Everything except testyear is text; keep columns homogeneous so pyarrow
    # does not infer int64 on numeric-looking values ('15 - QCM' would then
    # fail). Integral floats from Excel (2.0) become plain integers ('2').
    for col in df.columns:
        if col == "testyear":
            continue
        s = df[col]
        if s.dtype.kind == "f" and (s.dropna() % 1 == 0).all():
            df[col] = s.astype("Int64").astype("string")
        else:
            df[col] = s.astype("string")

    df.insert(0, "exam", SHEET_TO_EXAM[sheet])

    # 'domain 2' holds a secondary domain on some MIR rows where 'domain' is
    # empty; fold it into 'domain' and normalise whitespace.
    if "domain 2" in df.columns:
        secondary = df["domain 2"].astype("string").str.strip()
        df["domain"] = df["domain"].astype("string").fillna(secondary)
        df = df.drop(columns=["domain 2"])

    if "picture_provided" in df.columns:
        df["picture_provided"] = normalise_picture_provided(df["picture_provided"])
    else:
        df["picture_provided"] = pd.NA

    df["nullified"] = consolidate_nullified(df)
    df["correct_option"], df["correct_fulltext"], extra = normalise_correct_option(df)
    df.loc[extra, "nullified"] = "yes"
    df["testyear"] = pd.to_numeric(df["testyear"], errors="coerce").astype("Int64")

    for col in ("domain", "subdomain"):
        if col in df.columns:
            # '' (e.g. PNA's all-empty domain column) must become NA so the
            # CSV and parquet agree on missingness.
            df[col] = df[col].astype("string").str.strip().replace("", pd.NA)

    return df[[c for c in CANONICAL_COLUMNS if c in df.columns]]


def main() -> None:
    frames = [load_sheet(sheet) for sheet in SHEET_TO_EXAM]
    base = pd.concat(frames, ignore_index=True)

    # Align on the canonical column order, adding any missing ones as NA.
    base = base.reindex(columns=CANONICAL_COLUMNS)

    # Source typo: one preclinical ID lost its leading 'I' (sequence runs
    # IT1252, T1253, IT1254); IT1253 is unused within that exam.
    mask = (base["exam"] == "Abilitazione_Italy_preclinical") & (base["questionID"] == "T1253")
    base.loc[mask, "questionID"] = "IT1253"

    # Weave the 2025/26 updates in: rows append to the end of their exam's
    # existing block (IDs continue the existing numbering); EDN_France and the
    # PES specialties are new exams and go last.
    updates = load_updates().reindex(columns=CANONICAL_COLUMNS)
    blocks = []
    for exam in CANONICAL_EXAM_ORDER:
        blocks.append(base[base["exam"] == exam])
        blocks.append(updates[updates["exam"] == exam])
    df = pd.concat(blocks, ignore_index=True)

    # Validation
    expected = {
        e: EXPECTED_COUNTS.get(e, 0) + UPDATES_COUNTS.get(e, 0) for e in CANONICAL_EXAM_ORDER
    }
    assert len(df) == sum(expected.values()), f"unexpected row count: {len(df)}"
    counts = df["exam"].value_counts().to_dict()
    assert counts == expected, f"per-exam counts changed: {counts}"
    assert not df.duplicated(["exam", "questionID"]).any(), "duplicate (exam, questionID)"
    assert df["question_text"].notna().all(), "missing question_text"
    keys = df["correct_option"].dropna()
    assert keys.str.fullmatch(r"[A-E](,[A-E])*|X|[IVX]+").all(), (
        f"unexpected correct_option values: {sorted(set(keys))[:10]}"
    )
    edn = df[df["exam"] == "EDN_France"]
    assert edn["correct_option"].isna().all(), "EDN rows must have no answer key"
    mir_new = df[(df["exam"] == "MIR_Spain") & (df["testyear"].fillna(0) >= 2025)]
    assert mir_new["questionID"].tolist() == [f"ES{n}" for n in range(2411, 2411 + len(mir_new))], (
        "MIR continuation IDs wrong"
    )
    linked = df.loc[df["picture_link"].notna(), "picture_link"]
    for links in linked:
        # Legacy rows reference bare source filenames that are not shipped;
        # update rows use repo-relative images/ paths that must resolve.
        if links.startswith("images/"):
            for p in links.split(";"):
                assert (ROOT / p).is_file(), f"missing image: {p}"

    # The CSV quotes every text field so typed readers (pyarrow/datasets) do
    # not infer int64 on numeric-looking columns and then fail on values like
    # '15 - QCM'. The parquet file is the canonical typed artefact on the Hub.
    df.to_csv(OUT_CSV, index=False, quoting=csv.QUOTE_NONNUMERIC)
    OUT_PARQUET.parent.mkdir(exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)
    print(f"wrote {OUT_CSV} and {OUT_PARQUET} with {len(df)} rows")
    print(df["exam"].value_counts().to_string())
    print()
    print("nullified:", df["nullified"].value_counts(dropna=False).to_dict())
    print("correct_option missing:", int(df["correct_option"].isna().sum()))
    print("multi-answer keys:", int(df["correct_option"].str.contains(",").sum()))
    print("questions with image:", int((df["picture_provided"] == "yes").sum()))


if __name__ == "__main__":
    main()
