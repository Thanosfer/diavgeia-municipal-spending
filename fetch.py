# fetch.py
# Κατεβάζει από τη Διαύγεια τις αποφάσεις "Έγκρισης δαπάνης" (Β.2.1) του 2025
# και σώζει κάθε σελίδα αποτελεσμάτων ως JSON στο data/raw/.

# Σημειώσεις για το API:
# - Δεν δέχεται εύρος ημερομηνιών πάνω από 6 μήνες, για αυτό ζητάμε έναν μήνα τη φορά.
# - Δίνει το πολύ 500 αποφάσεις ανά σελίδα, οπότε ζητάμε σελίδες μέχρι να τις πάρουμε όλες.

import calendar
import json
import os
import time

import requests

URL = "https://diavgeia.gov.gr/luminapi/opendata/search.json"
DECISION_TYPE = "Β.2.1" # Έγκριση δαπάνης
YEAR = 2025
PAGE_SIZE = 500
RAW_DIR = "data/raw"

MUNICIPALITIES = {
    "6243": "ΔΗΜΟΣ ΠΕΙΡΑΙΩΣ",
    "6025": "ΔΗΜΟΣ ΑΜΑΡΟΥΣΙΟΥ",
}

def get_page(org_id, month, page):
    """Ζητάει μια σελίδα αποφάσεων για έναν Δήμο και έναν μήνα."""
    last_day = calendar.monthrange(YEAR, month)[1]
    params = {
        "org": org_id,
        "type": DECISION_TYPE,
        "from_issue_date": f"{YEAR}-{month:02d}-01",
        "to_issue_date": f"{YEAR}-{month:02d}-{last_day}",
        "size": PAGE_SIZE,
        "page": page,
    }
    response = requests.get(URL, params=params, headers={"Accept": "application/json"}, timeout=60)
    response.raise_for_status() # αν το API γυρίσει σφάλμα, σταματάμε εδώ
    return response.json()

def main():
    os.makedirs(RAW_DIR, exist_ok=True)

    for org_id, name in MUNICIPALITIES.items():
        for month in range(1, 13):
            page = 0
            while True:
                filename = f"{RAW_DIR}/{org_id}_{YEAR}-{month:02d}_p{page}.json"

                # Αν το αρχείο υπάρχει ήδη, δεν το ξανακατεβάζουμε
                if os.path.exists(filename):
                    with open(filename, encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    data = get_page(org_id, month, page)
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False)
                    time.sleep(1) # μικρή παύση για να μη φορτώνουμε το API

                total = data["info"]["total"]
                print(f"{name} | μήνας {month:02d} | σελίδα {page} | σύνολο μήνα: {total}")

                # Αν πήραμε όλες τις αποφάσεις του μήνα, πάμε στο επόμενο
                if (page + 1) * PAGE_SIZE >= total:
                    break
                page += 1


if __name__ == "__main__":
    main()