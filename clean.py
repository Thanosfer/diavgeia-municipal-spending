# clean.py
# Διαβάζει τα JSON από το data/raw/, κρατάει μόνο τα πεδία που μας χρειάζονται
# και τα σώζει σε μία βάση SQLite (data/spending.db) με δύο πίνακες:
# - decisions: μία γραμμή για κάθε απόφαση (Δήμος, ημερομηνία, θέμα)
# - expenses: μία γραμμή για κάθε δαπάνη της απόφασης (δικαιούχος, ποσό, ΚΑΕ, CPV)

# Τα ονόματα και τα ΑΦΜ των φυσικών προσώπων δεν μπαίνουν στη βάση.

import glob
import json
import re
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

RAW_DIR = "data/raw"
DB_PATH = "data/spending.db"

MUNICIPALITIES = {
    "6243": "Πειραιάς",
    "6026": "Μαρούσι",
}

def is_legal_entity(afm):
    """True αν το ΑΦΜ ανήκει σε νομικό πρόσωπο (εταιρεία, φορέα, σύλλογο)."""
    # Τα ΑΦΜ των νομικών προσώπων ξεκινούν από 08, 09, 8 ή 9
    # Αν δεν υπάρχει ΑΦΜ, δεν είμαστε σίγουροι, οπότε το θεωρούμε φυσικό πρόσωπο.
    return bool(afm) and afm.startswith(("08", "09", "8", "9"))


def load_decisions():
    """Διαβάζει όλα τα αρχεία JSON και επιστρέφει μία λίστα με όλες τις αποφάσεις."""
    decisions = []
    for path in sorted(glob.glob(f"{RAW_DIR}/*.json")):
        with open(path, encoding="utf-8") as f:
            decisions.extend(json.load(f)["decisions"])
    return decisions


def main():
    decisions_rows = []
    expense_rows = []

    for d in load_decisions():
        # Η ημερομηνία έρχεται σε milliseconds. Τη μετατρέπουμε σε ώρα Ελλάδος,
        # αλλιώς οι αποφάσεις της 1ης του μήνα θα έπεφταν στον προηγούμενο μήνα.
        issue_date = datetime.fromtimestamp(d["issueDate"] / 1000, ZoneInfo("Europe/Athens")).date()

        # Βγάζουμε το "Χρηματικό Ένταλμα Πληρωμής ΧΧΧ για:" από την αρχή του θέματος
        subject = re.sub(r"^Χρηματικό Ένταλμα Πληρωμής \S+ για:\s*", "", d["subject"]).strip()

        decisions_rows.append({
            "ada": d["ada"],
            "municipality": MUNICIPALITIES[d["organizationId"]],
            "issue_date": issue_date.isoformat(),
            "subject": subject,
            "url": d["documentUrl"],
        })

        # Κάθε απόφαση έχει μία ή περισσότερες δαπάνες (sponsor)
        for s in d["extraFieldValues"]["sponsor"]:
            payee = s["sponsorAFMName"]
            afm = payee.get("afm")
            legal = is_legal_entity(afm)

        expense_rows.append({
            "ada": d["ada"],
            "payee": payee.get("name", "").strip() if legal else "ΑΝΩΝΥΜΟΠΟΙΗΜΕΝΟ",
            "afm": afm if legal else None,
            "is_legal_entity": legal,
            "amount": s["expenseAmount"]["amount"],
            "kae": s.get("kae"),
            "cpv": s.get("cpv"),
        })

    decisions = pd.DataFrame(decisions_rows)
    expenses = pd.DataFrame(expense_rows)

    # Σώζουμε στη βάση. Το if_exists="replace" σβήνει τους παλιούς πίνακες,
    # οπότε μπορούμε να ξανατρέξουμε το script όσες φορές θέλουμε.
    conn = sqlite3.connect(DB_PATH)
    decisions.to_sql("decisions", conn, if_exists="replace", index=False)
    expenses.to_sql("expenses", conn, if_exists="replace", index=False)
    conn.close()

    print("Αποφάσεις:", len(decisions))
    print("Δαπάνες:", len(expenses))
    print("Ανωνυμοποιημένες δαπάνες:", (~expenses["is_legal_entity"]).sum())


if __name__ == "__main__":
    main()