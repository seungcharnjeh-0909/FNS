# FNS Business Planning Closing Automation System (Phase 1 Prototype)

⚠️ **DO NOT COMMIT COMPANY FINANCIAL DATA.** The `.gitignore` in this
repo excludes `*.xlsx`, `uploads/`, `outputs/`, and `data/company_data/`
by default. Double-check `git status` before every commit.

## What this is

A local-only prototype that proves the source Management Performance
Excel workbook can be read, structurally inspected, and data-quality
checked in Python — as the first step toward eventually replacing the
Excel-based monthly closing process.

**This version does NOT calculate P/L, expense, or variance yet.**
It only imports and validates the three raw data sources:
`RAW_SYSTEM(PL)`, `RAW_SYSTEM(EXP)`, and `Code Mapping`.

No login, no cloud storage, no multi-user support — everything runs
on your machine for a single local session.

## Setup (Visual Studio Code)

1. Open the `business_planning_system` folder in VS Code.
2. Open a terminal in VS Code (`` Ctrl+` `` / `` Cmd+` ``).
3. Create and activate a virtual environment:

   ```bash
   python -m venv .venv

   # Windows
   .venv\Scripts\activate

   # macOS / Linux
   source .venv/bin/activate
   ```

4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Run the app:

   ```bash
   streamlit run app.py
   ```

6. Your browser should open automatically at `http://localhost:8501`.
   If not, open that URL manually.

## Using it

1. Go to the **Data Import** page (left sidebar) and upload the
   Management Performance `.xlsx` workbook.
2. Review the sheet inventory and confirm the 3 required sheets were
   found.
3. Go to the **Data Quality** page to review automated checks:
   nulls, duplicate keys, unexpected months, unmapped CCTR codes,
   duplicate mapping keys, and blank organizational hierarchy.

## Project structure

```
business_planning_system/
├── app.py                     # Streamlit entry point
├── pages/
│   ├── 1_Data_Import.py       # Upload + inspect + load raw data
│   └── 2_Data_Quality.py      # Automated data-quality checks
├── core/
│   ├── workbook_loader.py     # Opens the .xlsx workbook
│   ├── workbook_inspector.py  # Sheet inventory / visibility
│   ├── raw_pl_parser.py       # RAW_SYSTEM(PL) -> clean DataFrame
│   ├── raw_expense_parser.py  # RAW_SYSTEM(EXP) -> clean DataFrame
│   ├── mapping_engine.py      # Code Mapping master data + checks
│   └── validation_engine.py   # Null / duplicate / bad-value checks
├── models/
│   └── validation.py          # CheckResult data shape
├── config/
│   ├── settings.json          # App-level settings
│   └── sheet_config.json      # Sheet names / header rows (no hardcoding)
├── data/sample/                # (empty - put synthetic sample files here)
├── tests/
├── requirements.txt
└── .gitignore
```

## Roadmap

This is Phase 1 of a multi-phase plan:

- **Phase 1 (current):** import + validate raw data, reproduce Excel
  results in Python for the 검증 (reconciliation) sheet.
- **Phase 2:** calculation engines (P/L, Expense, Variance,
  Reconciliation, Management Performance) run natively in Python;
  Excel becomes an output format, not the calculation engine.
- **Phase 3:** persistent history in SQLite.
- **Phase 4:** PostgreSQL + centralized master data, multiple
  business areas.
- **Phase 5:** direct MNG system integration (API/DB), removing
  manual Excel upload.
- **Phase 6:** AI assistant for variance explanation and reporting
  (never performs calculations itself — always reads from the
  validated Python engines).

Public deployment / multi-user access is **not** part of this phase.
Because this handles company financial data, publishing it for other
people to use should go through your organization's normal review for
data handling, access control, and hosting — that's a separate
conversation once the calculation logic itself is proven correct.
