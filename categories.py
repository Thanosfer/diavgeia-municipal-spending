# categories.py
# Οι κατηγορίες δαπανών και η αντιστοίχισή τους σε κωδικούς ΚΑΕ.
# Η κατηγορία λέει ΤΙ αγοράστηκε (είδος), οπότε την αντιστοιχίζουμε στα ψηφία
# ΜΕΤΑ την τελεία του ΚΑΕ (π.χ. στο 20.6641.01 κοιτάμε το 6641).

# Θα το χρησιμοποιήσουν:
# - το classify.py (η λίστα CATEGORIES μπαίνει στο prompt)
# - ο έλεγχος του Βήματος 4 (η kae_category() δίνει την κατηγορία του ΚΑΕ)

import sqlite3

import pandas as pd

DB_PATH = "data/spending.db"

# Για κάθε κατηγορία, οι αρχές των κωδικών που της αντιστοιχούν.
# Π.χ. το "664" πιάνει το 6641, 6643 κ.λπ.
CATEGORY_KAE = {
    "Μισθώματα": ["623"],
    "Ενέργεια, νερό και τηλεφωνία": ["621", "622", "6271", "6273"],
    "Καύσιμα": ["664"],
    "Οχήματα (ανταλλακτικά, ελαστικά, επισκευές)": ["6671", "6672", "6263"],
    "Συντήρηση κτιρίων και εξοπλισμού": ["626", "666"],
    "Υλικά και αναλώσιμα": ["661", "663", "669", "6673"],
    "Τρόφιμα και παροχές εργαζομένων": ["606", "648"],
    "Υπηρεσίες τρίτων": ["61", "6279", "74", "6463", "6414"],
    "Εκδηλώσεις και προβολή": ["643", "647"],
    "Εξοπλισμός": ["71"],
    "Έργα": ["73"],
    "Μη αγορές (δάνεια, φόροι, αποδόσεις, προσωπικό)": ["60", "63", "65", "67", "68", "642", "6492"],
}

# Οι κατηγορίες που επιτρέπουμε στο LLM. Το "Άλλο" δεν αντιστοιχεί σε ΚΑΕ.
CATEGORIES = list(CATEGORY_KAE) + ["Άλλο"]


def kae_category(kae):
    """Επιστρέφει την κατηγορία ενός ΚΑΕ, ή None αν δεν ταιριάζει σε καμία."""
    code = kae[3:] # ό,τι υπάρχει μετά το "XX."
    # Αν ταιριάζουν δύο αρχές (π.χ. το "626" και το "6263"), κερδίζει η μεγαλύτερη,
    # γιατί είναι πιο συγκεκριμένη.
    best_category = None
    best_length = 0
    for category, prefixes in CATEGORY_KAE.items():
        for prefix in prefixes:
            if code.startswith(prefix) and len(prefix) > best_length:
                best_category = category
                best_length = len(prefix)
    return best_category


def main():
    """Δείχνει πόσες αποφάσεις πέφτουν σε κάθε κατηγορία με βάση τον ΚΑΕ τους."""
    conn = sqlite3.connect(DB_PATH)
    # ΚΑΕ απόφασης: ο ΚΑΕ της μεγαλύτερης δαπάνης που δεν είναι 82ΥΥ.
    # Οι γραμμές χωρίς ΚΑΕ (NULL) εξαιρούνται ρητά.
    decision_kae = pd.read_sql("""
        SELECT ada, kae, MAX(amount) AS max_amount, SUM(amount) AS total
        FROM expenses
        WHERE kae IS NOT NULL AND substr(kae, 4, 2) != '82'
        GROUP BY ada
    """, conn)
    conn.close()

    decision_kae["category"] = decision_kae["kae"].map(kae_category).fillna("(χωρίς αντιστοίχιση)")
    summary = decision_kae.groupby("category").agg(
        decisions=("ada", "count"),
        million_eur=("total", "sum"),
    )
    summary["million_eur"] = (summary["million_eur"] / 1_000_000).round(2)
    print(summary.sort_values("decisions", ascending=False).to_string())
    print()
    print("Σύνολο αποφάσεων:", len(decision_kae))


if __name__ == "__main__":
    main()
