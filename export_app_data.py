# export_app_data.py
# Βγάζει τα δεδομένα του dashboard σε CSV (φάκελος app_data/), ώστε το app.py
# να μη χρειάζεται τη βάση, που δεν ανεβαίνει στο GitHub.
# ΔΕΝ καλεί το LLM και ΔΕΝ αλλάζει τη βάση: μόνο διαβάζει (το view purchases το φτιάχνει το analysis.py).
# ΧΩΡΙΣ θέματα αποφάσεων (μπορεί να έχουν ονόματα υπαλλήλων).

#       python export_app_data.py

import os
import sqlite3

import pandas as pd

from analysis import DB_PATH, EQUIPMENT_WRONG, TOLERANCE, possible_duplicates, reliability

APP_DATA_DIR = "app_data"
PURCHASES_CSV = os.path.join(APP_DATA_DIR, "purchases.csv")
RELIABILITY_CSV = os.path.join(APP_DATA_DIR, "reliability.csv")

# Το σύνολο αγορών (results/analysis.md)
PURCHASES_TOTAL = 52651239.87


def export_purchases(conn):
    """Μία γραμμή για κάθε δαπάνη του view purchases, με source και url, χωρίς θέμα."""
    # 105 αποφάσεις ήρθαν από το API χωρίς documentUrl (κενό). Γι' αυτές δίνουμε
    # τη σελίδα της απόφασης στη Διαύγεια, που υπάρχει πάντα.
    purchases = pd.read_sql("""
        SELECT p.ada, p.municipality, p.month, p.sector, p.final_category, f.source, p.bucket,
               p.payee, p.afm, p.is_legal_entity, p.amount,
               COALESCE(NULLIF(d.url, ''), 'https://diavgeia.gov.gr/decision/view/' || p.ada) AS url
        FROM purchases p
        JOIN final_categories f ON f.ada = p.ada
        JOIN decisions d ON d.ada = p.ada
        ORDER BY p.ada, p.amount DESC
    """, conn, dtype={"sector": str, "afm": str}) # να μη χαθούν τα μηδενικά μπροστά (00, 090000045)

    # Οι δύο σημειώσεις, ως στήλες True/False
    purchases["possible_duplicate"] = purchases["ada"].isin(possible_duplicates(conn)["ada"])
    purchases["equipment_wrong"] = purchases["ada"].isin(EQUIPMENT_WRONG)
    return purchases


def check(purchases):
    """Έλεγχοι πριν γραφτούν τα αρχεία."""
    assert not any("subject" in column for column in purchases.columns), "Υπάρχει στήλη με θέμα"

    people = purchases[purchases["is_legal_entity"] == 0]
    assert (people["payee"] == "ΑΝΩΝΥΜΟΠΟΙΗΜΕΝΟ").all(), "Φυσικό πρόσωπο με όνομα"
    assert people["afm"].isna().all(), "Φυσικό πρόσωπο με ΑΦΜ"
    assert purchases["url"].str.startswith("https://diavgeia.gov.gr/").all(), "Λείπει σύνδεσμος"

    total = purchases.loc[purchases["bucket"] == "Αγορές", "amount"].sum()
    assert abs(total - PURCHASES_TOTAL) < TOLERANCE, f"Οι αγορές είναι {total:,.2f} €, όχι {PURCHASES_TOTAL:,.2f} €"

    print(f"Έλεγχοι OK: καμία στήλη subject, {len(people)} δαπάνες φυσικών προσώπων όλες ανωνυμοποιημένες, "
          f"αγορές {total:,.2f} €.")


def main():
    conn = sqlite3.connect(DB_PATH)
    purchases = export_purchases(conn)
    conn.close()

    scores = reliability().reset_index(names="final_category").rename(
        columns={"precision_%": "precision", "αξιοπιστία": "reliability"}
    )
    check(purchases)

    os.makedirs(APP_DATA_DIR, exist_ok=True)
    purchases.to_csv(PURCHASES_CSV, index=False, encoding="utf-8")
    scores.to_csv(RELIABILITY_CSV, index=False, encoding="utf-8")

    print(f"{PURCHASES_CSV}: {len(purchases)} γραμμές, {purchases['ada'].nunique()} αποφάσεις, "
          f"{os.path.getsize(PURCHASES_CSV) / 1e6:.1f} MB")
    print(f"{RELIABILITY_CSV}: {len(scores)} κατηγορίες, {os.path.getsize(RELIABILITY_CSV) / 1e3:.1f} KB")
    print(f"Πιθανές διπλές: {purchases.loc[purchases['possible_duplicate'], 'ada'].nunique()} αποφάσεις · "
          f"Εξοπλισμός λάθος: {purchases.loc[purchases['equipment_wrong'], 'ada'].nunique()} αποφάσεις")


if __name__ == "__main__":
    main()