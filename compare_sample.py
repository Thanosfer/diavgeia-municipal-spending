# compare_sample.py
# Τρέχει το LLM στις 20 αποφάσεις του δείγματος και το συγκρίνει με τη δική μας κατηγορία.

import sys

import pandas as pd

from classify import classify_subject

SAMPLE_PATH = "data/sample20.csv"


def main():
    # Ποιο δείγμα: αυτό που δίνουμε στην εντολή, αλλιώς το 1ο
    sample_path = sys.argv[1] if len(sys.argv) > 1 else SAMPLE_PATH
    sample = pd.read_csv(sample_path, encoding="utf-8-sig")

    llm_categories = []
    for i, row in sample.iterrows():
        category = classify_subject(row["subject"])
        llm_categories.append(category)
        mark = "✓" if category == row["manual_category"] else "✗"
        print(f"{i + 1:2d} {mark} {category}")
    sample["llm_category"] = llm_categories

    agree = (sample["llm_category"] == sample["manual_category"]).sum()
    print(f"\nΣυμφωνία: {agree} / {len(sample)}")

    print("\nΔιαφωνίες:")
    for i, row in sample[sample["llm_category"] != sample["manual_category"]].iterrows():
        print(f"\n#{i + 1} {row['subject'][:100]}")
        print(f"   εμείς: {row['manual_category']}")
        print(f"   LLM:   {row['llm_category']}")


if __name__ == "__main__":
    main()
