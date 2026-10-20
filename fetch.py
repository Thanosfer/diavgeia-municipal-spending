# fetch.py
# Πρώτη δοκιμή: κατεβάζουμε τις αποφάσεις "Έγκρισης δαπάνης" (Β.2.1)
# του Δήμου Πειραιώς για τον Ιανουάριο 2025.

import json

import requests

URL = "https://diavgeia.gov.gr/luminapi/opendata/search.json"

params = {
    "org": "6243",                      # Δήμος Πειραιώς
    "type": "Β.2.1",                    # Έγκριση δαπάνης
    "from_issue_date": "2025-01-01",
    "to_issue_date": "2025-01-31",
    "size": 500,                        # το μέγιστο που επιτρέπει το API
    "page": 0,                          # η πρώτη σελίδα είναι η 0
}

response = requests.get(URL, params=params, headers={"Accept": "application/json"}, timeout=60)
response.raise_for_status()
data = response.json()

print("Σύνολο αποφάσεων:", data["info"] ["total"])
print("Πήραμε σε αυτή τη σελίδα:", len(data["decisions"]))

# Τυπώνουμε την πρώτη απόφαση για να δούμε τη δομή της
first = data["decisions"][0]
print(json.dumps(first, ensure_ascii=False, indent=2))