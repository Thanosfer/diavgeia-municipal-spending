# make_sample.py
# Φτιάχνει ένα δείγμα 20 αποφάσεων, για να δοκιμάσουμε το LLM πριν από τη μαζική εκτέλεση.
# Το data/sample20.csv έχει μια κενή στήλη manual_category, που τη συμπληρώνουμε
# ΜΕ ΤΟ ΧΕΡΙ πριν τρέξει το LLM.

import sqlite3

import pandas as pd

from categories import kae_category

DB_PATH = "data/spending.db"
SAMPLE_PATH = "data/sample20.csv"
SAMPLE_SIZE = 20
SEED = 42 # ίδιο seed = ίδιο δείγμα κάθε φορά


def main():
    conn = sqlite3.connect(DB_PATH)
    # Ίδιος κανόνας με το categories.py: ΚΑΕ της μεγαλύτερης δαπάνης που δεν είναι 82YY
    decisions = pd.read_sql("""
        WITH decision_kae AS (
            SELECT ada, kae, MAX(amount) AS max_amount
            FROM expenses
            WHERE kae IS NOT NULL AND substr(kae, 4, 2) != '82'
            GROUP BY ada
        )
        SELECT d.ada, d.municipality, d.subject, k.kae
        FROM decision_kae k
        JOIN decisions d ON d.ada = k.ada
        ORDER BY d.ada
    """, conn)
    conn.close()

    # Το LLM θα ρωτηθεί μία φορά ανά θέμα, οπότε κρατάμε κάθε θέμα μία φορά
    decisions = decisions.drop_duplicates("subject")
    decisions["kae_category"] = decisions["kae"].map(kae_category).fillna("(χωρίς αντιστοίχιση)")

    # 1η επιλογή: μία απόφαση για κάθε συνδυασμό Δήμου και κατηγορίας ΚΑΕ
    per_category = decisions.drop_duplicates("subject")
    # 2η επιλογή: από αυτές, 10 ανά Δήμο. Έτσι κάθε Δήμος έχει 10 διαφορετικά είδη.
    sample = per_category.groupby("municipality").sample(n=SAMPLE_SIZE // 2, random_state=SEED)

    # Ανακατεύουμε, αλλιώς πρώτα θα ήταν όλος ο ένας Δήμος και μετά ο άλλος
    sample = sample.sample(frac=1, random_state=SEED)

    # Στο CSV ΔΕΝ βάζουμε τον ΚΑΕ: την κατηγορία τη βάζουμε μόνο από το θέμα, όπως το LLM
    sample["manual_category"] = ""
    sample[["ada", "municipality", "subject", "manual_category"]].to_csv(
        SAMPLE_PATH, index=False, encoding="utf-8-sig"
    )

    print(f"Σώθηκαν {len(sample)} αποφάσεις στο {SAMPLE_PATH}")
    print(sample["municipality"].value_counts().to_string())


if __name__ == "__main__":
    main()
