# Where does the money go? Municipal spending in Piraeus and Marousi (2025)

A student project that analyses the spending of two Greek municipalities using open data from [Diavgeia](https://diavgeia.gov.gr), the Greek government's transparency portal. A local LLM sorts each spending decision into a category, and the result is checked against the official budget codes.

**Live dashboard:** https://diavgeia-municipal-spending.streamlit.app

[Dashboard overview](docs/overview.png)

---

## What I did

1. **Downloaded** every *expenditure approval* (decision type B.2.1) of 2025 for Piraeus and Marousi through the Diavgeia API: **8,171 decisions** with **58,810 expense lines**.
2. **Cleaned** the data and stored it in a SQLite database. People who are not companies were **anonymised** (name and tax ID removed).
3. **Classified** each decision into one of 12 categories (Rentals, Fuel, Energy, Vehicles, Public works, …) with a local LLM (**Qwen 2.5 7B via Ollama**, free and offline), based on the decision's subject.
4. **Checked how reliable the LLM is**, by comparing it with the official budget code (KAE) of each payment.
5. **Analysed** the spending with SQL and built an interactive **Streamlit** dashboard.

## Key findings

- **€52.7M** was spent on purchases in 2025 across both municipalities (5,773 decisions). Loans, tax withholdings and transfers to other bodies are shown separately, because they are not purchases.
- **Transparency:** in Piraeus, **12.6%** of all payments (€8.75M, withholdings excluded) is in decisions with **no budget code**, and most of them have no real description either. In Marousi this is 1.2%.
- **December** is the biggest month (€8.5M), and January the smallest (€0.6M). The month is the date of the decision, not of the actual purchase.
- The largest supplier receives about **11%** of all purchases in Marousi and **10%** in Piraeus.
- **51 decisions** (€1.75M, 3.3% of purchases) look like possible duplicate postings: same date, subject, amount and company. They are flagged, not removed.
- I started with **Athens** too, but it published only **33** decisions of this type in 2025, so it could not be compared.

## How reliable is the LLM?

The budget code (KAE) is a good, independent check: it says what was paid, but it is a number that a reader cannot understand, and in many cases it is only "other services" or "other materials". The LLM reads the subject and gives a readable category.

| Check | Result |
|---|---|
| Agreement with the budget code | **77.8%** of decisions (69.1% of euros) |
| Blind manual review of 30 disagreements | the LLM was right in 6, the budget code in 23 |
| Estimated real accuracy | **about 82–83%** |
| Agreement with the EU product code (CPV), where it exists | 91% (221 decisions, mostly vehicles) |

Because of this, the dashboard uses a **final category**: the budget code where it is clear (rentals, fuel, energy, vehicles) and the LLM everywhere else. Each category shows a reliability label (high / medium / low).

Full details: [`results/evaluation.md`](results/evaluation.md) and [`results/analysis.md`](results/analysis.md).

## Limitations

- **Equipment is not reliable:** I checked its 10 largest decisions by hand and 6 of them belong to other categories (at least €5.5M of its €11.1M).
- The LLM puts **school meals** under Materials instead of Food, so Food is probably underestimated.
- Only two municipalities and one year. The categories are my own and other choices are possible.
- These are the data **as published** on Diavgeia. A finding here is about the published data, not a judgement about the municipalities.

## Run it yourself

Only the dashboard (uses the anonymised data in `app_data/`):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The full pipeline also needs [Ollama](https://ollama.com) with `ollama pull qwen2.5:7b`:

| Script | What it does |
|---|---|
| `fetch.py` | downloads the decisions from the Diavgeia API (one month at a time, with paging and cache) |
| `clean.py` | cleans the data, anonymises people, loads SQLite |
| `categories.py` | the categories and their mapping to budget codes |
| `make_sample.py`, `label_sample.py` | test samples of 20 decisions, labelled by hand |
| `classify.py` | classifies each unique subject with the LLM (can resume if stopped) |
| `evaluate.py` | compares the LLM with the budget code and CPV, builds the final category |
| `analysis.py` | SQL analysis and the report in `results/` |
| `export_app_data.py` | exports the anonymised data for the dashboard |
| `app.py` | the Streamlit dashboard |

## Privacy

- People who are not companies appear only as `ANONYMISED` (rule: Greek company tax IDs start with 8 or 9).
- The decision subjects are **not** published here, because some of them contain employees' names. Each decision links to its official page on Diavgeia.

## Tools

Python · requests · pandas · SQLite · Ollama (Qwen 2.5 7B) · Streamlit

*Independent student project. Not affiliated with Diavgeia or the municipalities. The categories may contain errors.*