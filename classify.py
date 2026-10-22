# classify.py
# Βάζει κατηγορία σε θέματα αποφάσεων με το τοπικό LLM (Ollama, Qwen 2.5 7B)
# Σε αυτή τη φάση έχει μόνο τη συνάρτηση classify_subject(), που τη δοκιμάζουμε
# στο δείγμα των 20.

import json

import requests

from categories import CATEGORIES

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:7b"

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
    categories = "\n".join(f"- {category}" for category in CATEGORIES)
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
