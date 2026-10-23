# make_sample.py
# Φτιάχνει ένα δείγμα 20 αποφάσεων, για να δοκιμάσουμε το LLM πριν από τη μαζική εκτέλεση.
# Το data/sample20.csv έχει μια κενή στήλη manual_category, που τη συμπληρώνουμε
# ΜΕ ΤΟ ΧΕΡΙ πριν τρέξει το LLM.

# Χωρίς ορίσματα φτιάχνει το 1ο δείγμα. Για το 2ο:
#   python make_sample.py data/sample20_2.csv 7
# (το αρχείο και το seed). To 2ο δείγμα δεν έχει κανένα θέμα του 1ου.

import os
import sqlite3
import sys

import pandas as pd

from categories import kae_category

DB_PATH = "data/spending.db"
FIRST_SAMPLE_PATH = "data/sample20.csv"
SAMPLE_SIZE = 20
SEED = 42 # ίδιο seed = ίδιο δείγμα κάθε φορά


def main():
    sample_path = sys.argv[1] if len(sys.argv) > 1 else FIRST_SAMPLE_PATH
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else SEED

    # Δεν σβήνουμε ποτέ δείγμα που υπάρχει: μπορεί να έχει ήδη κατηγορίες από το χέρι
    if os.path.exists(sample_path):
        print(f"Το {sample_path} υπάρχει ήδη. Αν θέλεις σίγουρα καινούργιο, σβήσε το πρώτα.")
        return  

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
    # Σε κάθε δείγμα εκτός από το 1ο, βγάζουμε τα θέματα του 1ου
    if sample_path != FIRST_SAMPLE_PATH:
        first_sample = pd.read_csv(FIRST_SAMPLE_PATH, encoding="utf-8-sig")
        decisions = decisions[~decisions["subject"].isin(first_sample["subject"])]
    decisions["kae_category"] = decisions["kae"].map(kae_category).fillna("(χωρίς αντιστοίχιση)")

    # 1η επιλογή: μία απόφαση για κάθε συνδυασμό Δήμου και κατηγορίας ΚΑΕ
    per_category = decisions.groupby(["municipality", "kae_category"]).sample(n=1, random_state=seed)
    # 2η επιλογή: από αυτές, 10 ανά Δήμο. Έτσι κάθε Δήμος έχει 10 διαφορετικά είδη.
    sample = per_category.groupby("municipality").sample(n=SAMPLE_SIZE // 2, random_state=seed)

    # Ανακατεύουμε, αλλιώς πρώτα θα ήταν όλος ο ένας Δήμος και μετά ο άλλος
    sample = sample.sample(frac=1, random_state=seed)

    # Στο CSV ΔΕΝ βάζουμε τον ΚΑΕ: την κατηγορία τη βάζουμε μόνο από το θέμα, όπως το LLM
    sample["manual_category"] = ""
    sample[["ada", "municipality", "subject", "manual_category"]].to_csv(
        sample_path, index=False, encoding="utf-8-sig"
    )

    print(f"Σώθηκαν {len(sample)} αποφάσεις στο {sample_path}")
    print(sample["municipality"].value_counts().to_string())


if __name__ == "__main__":
    main()
