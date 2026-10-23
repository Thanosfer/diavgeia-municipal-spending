# label_sample.py
# Βάζουμε με το χέρι κατηγορία στις 20 αποφάσεις του δείγματος, ΠΡΙΝ τρέξει το LLM.
# Δείχνει ένα θέμα τη φορά και ζητάει τον αριθμό της κατηγορίας.
# Σώζει μετά από κάθε απάντηση, οπότε μπορείς να σταματήσεις (Ctrl+C) και να συνεχίσεις.

import sys

import pandas as pd

from categories import CATEGORIES

SAMPLE_PATH = "data/sample20.csv"

def ask_category(subject):
    """Δείχνει το θέμα και τις κατηγορίες και επιστρέφει αυτή που διαλέξαμε."""
    print(subject)
    print()
    for number, category in enumerate(CATEGORIES, start=1):
        print(f"    {number:2d}. {category}")
    while True:
        answer = input("Κατηγορία (αριθμός): ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(CATEGORIES):
            return CATEGORIES[int(answer) - 1]
        print("Δώσε έναν αριθμό από το 1 έως", len(CATEGORIES))


def main():
    # Ποιο δείγμα: αυτό που δίνουμε στην εντολή, αλλιώς το 1ο
    sample_path = sys.argv[1] if len(sys.argv) > 1 else SAMPLE_PATH
    sample = pd.read_csv(sample_path, encoding="utf-8-sig", dtype={"manual_category": str})

    for i, row in sample.iterrows():
        if pd.notna(row["manual_category"]):
            continue # έχει ήδη κατηγορία από προηγούμενη φορά

        print(f"\n--- {i + 1} / {len(sample)} · {row['municipality']} ---")
        sample.loc[i, "manual_category"] = ask_category(row["subject"])
        sample.to_csv(sample_path, index=False, encoding="utf-8-sig") # σώζουμε αμέσως

    print("\nΤελείωσες! Κατανομή:")
    print(sample["manual_category"].value_counts().to_string())


if __name__ == "__main__":
    main()
