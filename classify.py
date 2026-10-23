# classify.py
# Βάζει κατηγορία σε θέματα αποφάσεων με το τοπικό LLM (Ollama, Qwen 2.5 7B)
# - classify_subject(): ρωτάει το LLM για ένα θέμα (τη χρησιμοποιεί και το compare_sample.py)
# - main(): την τρέχει σε όλα τα θέματα και σώζει τις κατηγορίες στον πίνακα classifications

#  Θέλει περίπου 2 ώρες. Αν σταματήσει στη μέση, το ξανατρέχεις και συνεχίζει από εκεί που έμεινε.

import json
import sqlite3
import time

import requests

from categories import CATEGORIES, CATEGORY_DESCRIPTIONS

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:7b"
DB_PATH = "data/spending.db"

# Οι οδηγίες προς το LLM. Είναι οι ίδιοι κανόνες που ακολουθήσαμε στην κατηγορία με το χέρι.
PROMPT = """Είσαι βοηθός που κατηγοριοποιεί δαπάνες ελληνικών Δήμων.
Θα σου δώσω το θέμα μιας απόφασης πληρωμής από τη Διαύγεια.
Διάλεξε ΜΙΑ κατηγορία από τη λίστα, με βάση το ΤΙ αγοράστηκε ή πληρώθηκε.

Κατηγορίες:
{categories}

Κανόνες:
- Αγνόησε τον τρόπο πληρωμής (π.χ. πάγια προκαταβολή, εξόφληση λογαριασμού), τον παραλήπτη (π.χ. σχολείο, υπηρεσία) και τους αριθμούς αναφοράς (τιμολόγιο, ΑΔΑΜ).
- Αν ταιριάζει μια πιο συγκεκριμένη κατηγορία, προτίμησέ την από τις «Υπηρεσίες τρίτων».
- Φόροι, δάνεια, κρατήσεις και λογιστικές τακτοποιήσεις πάνε στις «Μη αγορές».
- Αν από το θέμα δεν φαίνεται τι πληρώθηκε, απάντησε «Άλλο».

Απάντησε μόνο με JSON της μορφής: {{"category": "<όνομα κατηγορίας ακριβώς όπως στη λίστα>"}}"""


def classify_subject(subject):
    """Στέλνει ένα θέμα στο LLM και επιστρέφει την κατηγορία του."""
    categories = "\n".join(f"- {category}: {CATEGORY_DESCRIPTIONS[category]}" for category in CATEGORIES)
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "messages": [
            {"role": "system", "content": PROMPT.format(categories=categories)},
            {"role": "user", "content": subject},
        ],
        # Το LLM πρέπει να απαντήσει με JSON που έχει ένα πεδίο "category",
        # και η τιμή του πρέπει να είναι ΑΚΡΙΒΩΣ ένα από τα ονόματα της λίστας
        "format": {
            "type": "object",
            "properties": {"category": {"type": "string", "enum": CATEGORIES}},
            "required": ["category"],
        },
        "options": {"temperature": 0}, # ίδια ερώτηση = ίδια απάντηση
        "stream": False, # θέλουμε όλη την απάντηση μαζί
    }, timeout=120)
    response.raise_for_status()

    answer = response.json()["message"]["content"]
    try:
        category = json.loads(answer).get("category")
    except json.JSONDecodeError:
        category = None
    # Αν το LLM έγραψε κάτι εκτός λίστας (ή χάλασε το JSON), το βάζουμε στο "Άλλο"
    return category if category in CATEGORIES else "Άλλο"


def main():
    conn = sqlite3.connect(DB_PATH)

    # Ο πίνακας με τα αποτελέσματα: μία γραμμή για κάθε θέμα.
    # Το IF NOT EXISTS τον φτιάχνει μόνο την πρώτη φορά, οπότε δεν σβήνει ό,τι έχουμε ήδη.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS classifications (
            subject TEXT PRIMARY KEY,
            category TEXT
        )
    """)

    # Τα θέματα που μένουν: όσα έχουν τουλάχιστον μία δαπάνη με ΚΑΕ που δεν είναι 82YY
    # (ίδιος κανόνας με το categories.py) και δεν έχουν πάρει ακόμα κατηγορία
    rows = conn.execute("""
        SELECT DISTINCT d.subject
        FROM decisions d
        JOIN expenses e ON e.ada = d.ada
        WHERE e.kae IS NOT NULL AND substr(e.kae, 4, 2) != '82'
         AND d.subject NOT IN (SELECT subject FROM classifications)
        ORDER BY d.subject
    """).fetchall()
    subjects = [row[0] for row in rows]
    print(f"Θέματα που μένουν: {len(subjects)}")

    start = time.time()
    for i, subject in enumerate(subjects, start=1):
        category = classify_subject(subject)
        conn.execute("INSERT INTO classifications (subject, category) VALUES (?, ?)", (subject, category))
        conn.commit() # σώζουμε αμέσως, για να μη χαθεί τίποτα αν σταματήσει

        # Κάθε 100 θέματα τυπώνουμε πού είμαστε 
        if i % 100 == 0:
            minutes = (time.time() - start) / 60
            print(f"{i} / {len(subjects)} ({minutes:.0f} λεπτά)")

    conn.close()
    print("Τελείωσε!")


if __name__ == "__main__":
    main()
