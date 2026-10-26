# evaluate.py
# Πόσο αξιόπιστες είναι οι κατηγορίες του LLM?
# Τις συγκρίνει με τη κατηγρία του ΚΑΕ (και του CPV, όπου υπάρχει) και γράφει
# όλα τα αποτελέσματα στο results/evaluation.md
# ΔΕΝ καλεί το LLM: διαβάζει μόνο τον πίνακα classifications.

#       python evaluate.py          όλοι οι έλεγχοι και το evaluation.md
#       python evaluate.py judge    κρίνουμε με το χέρι τις 30 διαφωνίες (τυφλά)

import os
import random
import sqlite3
import sys

import pandas as pd

from categories import CATEGORIES, OLD_CATEGORY_KAE, kae_accepted, kae_category

DB_PATH = "data/spending.db"
REPORT_PATH = "results/evaluation.md"
DISAGREEMENTS_PATH = "data/disagreements30.csv"
SEED = 42

# Σύντομα ονόματα, για να χωράνε οι πίνακες στην οθόνη
SHORT = {
    "Μισθώματα": "Μισθώματα",
    "Ενέργεια, νερό και τηλεφωνία": "Ενέργεια",
    "Καύσιμα": "Καύσιμα",
    "Οχήματα (ανταλλακτικά, ελαστικά, επισκευές)": "Οχήματα",
    "Συντήρηση κτιρίων και εξοπλισμού": "Συντήρηση",
    "Υλικά και αναλώσιμα": "Υλικά",
    "Τρόφιμα και παροχές εργαζομένων": "Τρόφιμα",
    "Υπηρεσίες τρίτων": "Υπηρεσίες",
    "Εκδηλώσεις και προβολή": "Εκδηλώσεις",
    "Εξοπλισμός": "Εξοπλισμός",
    "Έργα": "Έργα",
    "Μη αγορές (δάνεια, φόροι, αποδόσεις, προσωπικό)": "Μη αγορές",
    "Άλλο": "Άλλο",
}

# Οι CPV που ελέγχουμε (οι αρχές του κωδικού) και η κατηγορία τους. Οι υπόλοιποι δεν ελέγχονται.
# Όπως στον ΚΑΕ, κερδίζει η μεγαλύτερη αρχή: το 501 (επισκευή οχημάτων, π.χ. 50118) είναι μέσα
# στο 50 (επισκευές και συντήρηση), αλλά για εμάς είναι Οχήματα, όπως και ο ΚΑΕ 6264.
CPV_CATEGORY = {
    "09": "Καύσιμα",
    "15": "Τρόφιμα και παροχές εργαζομένων",
    "34": "Οχήματα (ανταλλακτικά, ελαστικά, επισκευές)",
    "45": "Έργα",
    "50": "Συντήρηση κτιρίων και εξοπλισμού",
    "501": "Οχήματα (ανταλλακτικά, ελαστικά, επισκευές)",
}

# Οι κατηγορίες όπου ο ΚΑΕ είναι σαφής: εκεί η τελική κατηγορία είναι του ΚΑΕ, όχι του LLM.
KAE_WINS = [
    "Μισθώματα",
    "Καύσιμα",
    "Ενέργεια, νερό και τηλεφωνία",
    "Οχήματα (ανταλλακτικά, ελαστικά, επισκευές)",
]
# Εξαίρεση: ο 6643 (καύσιμα θέρμανσης) έχει και πετρέλαιο (Καύσιμα) και φυσικό αέριο (Ενέργεια).
# Εκεί αποφασίζει το LLM, που βλέπει στο θέμα τι αγοράστηκε.
KAE_UNCLEAR = ["6643"]


def cpv_prefix(cpv):
    """Η αρχή του CPV_CATEGORY που ταιριάζει σε ένα CPV (η μεγαλύτερη), ή None αν δεν ελέγχεται."""
    matches = [prefix for prefix in CPV_CATEGORY if cpv.startswith(prefix)]
    return max(matches, key=len) if matches else None


def load_decisions():
    """Μία γραμμή για κάθε απόφαση που είδε το LLM (7.668): ΚΑΕ απόφασης, CPV, ποσό, κατηγορίες."""
    conn = sqlite3.connect(DB_PATH)
    # Ο ΚΑΕ απόφασης είναι ο ΚΑΕ της μεγαλύτερης δαπάνης που δεν είναι 82YY (όπως στο categories.py).
    # Το CPV απόφασης είναι το CPV της μεγαλύτερης δαπάνης που έχει CPV (οι περισσότερες δεν έχουν).
    decisions = pd.read_sql("""
        WITH decision_kae AS (
            SELECT ada, kae, MAX(amount) AS max_amount, SUM(amount) AS total
            FROM expenses
            WHERE kae IS NOT NULL AND substr(kae, 4, 2) != '82'
            GROUP BY ada
        ),
        decision_cpv AS (
            SELECT ada, cpv, MAX(amount) AS max_amount
            FROM expenses
            WHERE cpv IS NOT NULL AND cpv != ''
            GROUP BY ada
        )
        SELECT k.ada, d.subject, k.kae, p.cpv, k.total, c.category AS llm_category
        FROM decision_kae k
        JOIN decisions d ON d.ada = k.ada
        JOIN classifications c ON c.subject = d.subject
        LEFT JOIN decision_cpv p ON p.ada = k.ada
    """, conn)
    conn.close()

    decisions["kae_old"] = decisions["kae"].map(lambda kae: kae_category(kae, OLD_CATEGORY_KAE))
    decisions["kae_new"] = decisions["kae"].map(kae_category)
    # Ελέγχεται όποια απόφαση έχει ΚΑΕ με κατηγορία. Η παλιά και η νέα αντιστοίχιση
    # έχουν τους ίδιους κωδικούς (απλώς μετακινούν κάποιους), άρα ελέγχουν τις ίδιες αποφάσεις.
    decisions["checked"] = decisions["kae_new"].notna()

    decisions["agree_old"] = decisions["llm_category"] == decisions["kae_old"]
    decisions["agree_strict"] = [llm in kae_accepted(kae) for llm, kae in zip(decisions["llm_category"], decisions["kae"])]
    decisions["agree_lenient"] = [llm in kae_accepted(kae, lenient=True) for llm, kae in zip(decisions["llm_category"], decisions["kae"])]
    return decisions


def as_table(df):
    """Ένας πίνακας pandas ως κείμενο markdown (μέσα σε ``` για να κρατήσει τη στοίχιση)."""
    return "```\n" + df.to_string() + "\n```"


def agreement_section(decisions):
    """Συμφωνία LLM–ΚΑΕ πριν/μετά, σε αποφάσεις και σε ευρώ."""
    checked = decisions[decisions["checked"]]
    rows = {}
    for label, column in [
        ("Πριν (παλιά αντιστοίχιση)", "agree_old"),
        ("Μετά, αυστηρή", "agree_strict"),
        ("Μετά, χαλαρή (666x: και Συντήρηση)", "agree_lenient"),
    ]:
        agree = checked[column]
        rows[label] = {
            "αποφάσεις_%": 100 * agree.mean(),
            "ευρώ_%": 100 * checked.loc[agree, "total"].sum() / checked["total"].sum(),
        }
    table = pd.DataFrame(rows).T.round(1)

    unchecked = decisions[~decisions["checked"]]
    return "\n\n".join([
        "## Συμφωνία LLM–ΚΑΕ",
        f"Παρονομαστής: μόνο οι αποφάσεις που ελέγχονται, {len(checked)} αποφάσεις "
        f"({checked['total'].sum() / 1e6:.2f} εκ. €).",
        as_table(table),
        f"Δεν ελέγχονται {len(unchecked)} αποφάσεις ({unchecked['total'].sum() / 1e6:.2f} εκ. €), "
        "γιατί ο ΚΑΕ τους δεν αντιστοιχεί σε κατηγορία (κυρίως 6495 λοιπές δαπάνες και 81ΥΥ).",
    ])


def confusion_section(decisions):
    """Πίνακας σύγχυσης (γραμμές: LLM, στήλες: ΚΑΕ) και precision/recall ανά κατηγορία."""
    checked = decisions[decisions["checked"]]
    llm = checked["llm_category"].map(SHORT)
    kae = checked["kae_new"].map(SHORT)

    order = [SHORT[category] for category in CATEGORIES]
    matrix = pd.crosstab(llm, kae).reindex(index=order, columns=order[:-1], fill_value=0)
    matrix.index.name = "LLM ↓ / ΚΑΕ →"
    matrix.columns.name = None

    # Precision: από όσες το LLM είπε Χ, πόσες έχουν και ΚΑΕ Χ.
    # Recall: από όσες έχουν ΚΑΕ Χ, πόσες τις βρήκε Χ και το LLM.
    both = pd.Series([matrix.loc[c, c] for c in order[:-1]], index=order[:-1])
    scores = pd.DataFrame({
        "LLM": matrix.sum(axis=1)[order[:-1]],
        "ΚΑΕ": matrix.sum(axis=0),
        "και_τα_δύο": both,
    })
    scores["precision_%"] = (100 * scores["και_τα_δύο"] / scores["LLM"]).round(1)
    scores["recall_%"] = (100 * scores["και_τα_δύο"] / scores["ΚΑΕ"]).round(1)

    return "\n\n".join([
        "## Πίνακας σύγχυσης (νέα αντιστοίχιση, αυστηρή)",
        "Κάθε κελί: πόσες αποφάσεις έχουν αυτή την κατηγορία από το LLM (γραμμή) και αυτή από τον ΚΑΕ (στήλη). "
        "Η διαγώνιος είναι οι συμφωνίες.",
        as_table(matrix),
        as_table(scores),
    ])


def cpv_section(decisions):
    """Συμφωνία με το CPV, μόνο για τις αρχές του CPV_CATEGORY."""
    with_cpv = decisions[decisions["cpv"].notna()].copy()
    with_cpv["prefix"] = with_cpv["cpv"].map(cpv_prefix)
    checked = with_cpv[with_cpv["prefix"].notna()].copy()
    checked["cpv_category"] = checked["prefix"].map(CPV_CATEGORY)
    checked["llm_agrees"] = checked["llm_category"] == checked["cpv_category"]
    checked["kae_agrees"] = checked["kae_new"] == checked["cpv_category"]

    # Μία γραμμή για κάθε αρχή, και για όσες δεν έχουν καμία απόφαση (με 0)
    per_prefix = checked.groupby("prefix")[["llm_agrees", "kae_agrees"]].agg(["count", "sum"])
    per_prefix = pd.DataFrame({
        "κατηγορία": [SHORT[CPV_CATEGORY[prefix]] for prefix in CPV_CATEGORY],
        "αποφάσεις": per_prefix[("llm_agrees", "count")],
        "LLM_συμφωνεί": per_prefix[("llm_agrees", "sum")],
        "ΚΑΕ_συμφωνεί": per_prefix[("kae_agrees", "sum")],
    }, index=list(CPV_CATEGORY)).fillna(0).astype({"αποφάσεις": int, "LLM_συμφωνεί": int, "ΚΑΕ_συμφωνεί": int})

    return "\n\n".join([
        "## Συμφωνία με το CPV",
        f"Από τις {len(decisions)} αποφάσεις, {len(with_cpv)} έχουν CPV. Ελέγχονται οι {len(checked)} "
        f"με αρχή {', '.join(CPV_CATEGORY)}. Οι άλλες {len(with_cpv) - len(checked)} δεν ελέγχονται.",
        as_table(per_prefix),
        f"Συμφωνία LLM–CPV: {100 * checked['llm_agrees'].mean():.1f}%. "
        f"Για σύγκριση, ΚΑΕ–CPV: {100 * checked['kae_agrees'].mean():.1f}%.",
    ])


def make_disagreements(decisions):
    """Φτιάχνει το data/disagreements30.csv: 30 τυχαίες διαφωνίες, τυφλά (A/B σε τυχαία σειρά)."""
    if os.path.exists(DISAGREEMENTS_PATH):
        return # υπάρχει ήδη: ΔΕΝ το ξαναφτιάχνουμε, για να μη σβηστούν οι κρίσεις μας

    disagreements = decisions[decisions["checked"] & ~decisions["agree_strict"]]
    sample = disagreements.sample(n=30, random_state=SEED)

    # Σε ποιες το LLM είναι το A και σε ποιες το B: 15 και 15, σε τυχαία σειρά
    llm_positions = ["A"] * 15 + ["B"] * 15
    random.Random(SEED).shuffle(llm_positions)

    rows = []
    for llm_is, (_, row) in zip(llm_positions, sample.iterrows()):
        llm, kae = row["llm_category"], row["kae_new"]
        rows.append({
            "ada": row["ada"],
            "subject": row["subject"],
            "A": llm if llm_is == "A" else kae,
            "B": kae if llm_is == "A" else llm,
            "judge": "",
            "llm_is": llm_is, # η «κρυφή» στήλη: δεν την κοιτάμε πριν τελειώσουμε
        })
    pd.DataFrame(rows).to_csv(DISAGREEMENTS_PATH, index=False, encoding="utf-8-sig")
    print(f"Έφτιαξα το {DISAGREEMENTS_PATH} (30 διαφωνίες). Κρίνε τες με: python evaluate.py judge")


def judge():
    """Δείχνει μία διαφωνία τη φορά (θέμα, A, B) και σώζει την κρίση μας. Το llm_is δεν φαίνεται."""
    sample = pd.read_csv(DISAGREEMENTS_PATH, encoding="utf-8-sig", dtype={"judge": str})
    answers = {"a": "A", "b": "B", "d": "διφορούμενο"}

    for i, row in sample.iterrows():
        if pd.notna(row["judge"]):
            continue # έχει ήδη κρίση από προηγούμενη φορά

        print(f"\n--- {i + 1} / {len(sample)} ---")
        print(row["subject"])
        print(f"\n    A. {row['A']}\n    B. {row['B']}")
        while True:
            answer = input("Ποια είναι σωστή; (a / b / d = διφορούμενο): ").strip().lower()
            if answer in answers:
                break
        sample.loc[i, "judge"] = answers[answer]
        sample.to_csv(DISAGREEMENTS_PATH, index=False, encoding="utf-8-sig") # σώζουμε αμέσως

    print("\nΤελείωσες! Τρέξε τώρα: python evaluate.py")


def accuracy_section(decisions):
    """Εκτίμηση ακρίβειας του LLM από τις 30 τυφλές κρίσεις, ως εύρος."""
    judged = pd.read_csv(DISAGREEMENTS_PATH, encoding="utf-8-sig", dtype={"judge": str})
    if judged["judge"].isna().any():
        return "## Εκτίμηση ακρίβειας\n\nΟι κρίσεις δεν έχουν τελειώσει (python evaluate.py judge)."

    llm_right = (judged["judge"] == judged["llm_is"]).sum()
    ambiguous = (judged["judge"] == "διφορούμενο").sum()
    kae_right = len(judged) - llm_right - ambiguous

    # Όπου LLM και ΚΑΕ συμφωνούν, θεωρούμε ότι το LLM έχει δίκιο. Στις διαφωνίες, έχει δίκιο
    # όσο συχνά είχε στις 30: χωρίς τα διφορούμενα (κάτω όριο) ή μαζί τους (πάνω όριο).
    agree = decisions.loc[decisions["checked"], "agree_strict"].mean()
    low = agree + (1 - agree) * llm_right / len(judged)
    high = agree + (1 - agree) * (llm_right + ambiguous) / len(judged)

    return "\n\n".join([
        "## Εκτίμηση ακρίβειας",
        f"Στις {len(judged)} τυχαίες διαφωνίες (κρίση με το χέρι, τυφλά): είχε δίκιο ο ΚΑΕ σε {kae_right}, "
        f"το LLM σε {llm_right}, διφορούμενες: {ambiguous}.",
        f"Το LLM συμφωνεί με τον ΚΑΕ στο {100 * agree:.1f}% των ελεγμένων αποφάσεων. Αν εκεί έχει δίκιο, "
        f"και στις διαφωνίες έχει δίκιο όσο συχνά είχε στο δείγμα, η ακρίβειά του είναι "
        f"**{100 * low:.1f}% έως {100 * high:.1f}%** (χωρίς / με τα διφορούμενα).",
        f"Προσοχή: είναι δείγμα {len(judged)} αποφάσεων, οπότε το εύρος είναι κατά προσέγγιση.",
    ])


def final_categories_section(decisions):
    """Φτιάχνει τον πίνακα final_categories: ο ΚΑΕ όπου είναι σαφής, αλλιώς το LLM."""
    code = decisions["kae"].str[3:] # ό,τι υπάρχει μετά το "XX."
    kae_wins = decisions["kae_new"].isin(KAE_WINS) & ~code.str.startswith(tuple(KAE_UNCLEAR))

    final = pd.DataFrame({
        "ada": decisions["ada"],
        "llm_category": decisions["llm_category"],
        "final_category": decisions["kae_new"].where(kae_wins, decisions["llm_category"]),
        "source": kae_wins.map({True: "ΚΑΕ", False: "LLM"}),
        "total": decisions["total"],
    })

    # Οι 144 αποφάσεις χωρίς κανέναν ΚΑΕ (το COUNT(kae) μετράει μόνο όσους δεν είναι NULL).
    # Κάποιες έχουν θέμα ίδιο με θέμα που είδε το LLM, οπότε κρατάμε και την κατηγορία του.
    conn = sqlite3.connect(DB_PATH)
    no_kae = pd.read_sql("""
        SELECT d.ada, c.category AS llm_category, SUM(e.amount) AS total
        FROM decisions d
        JOIN expenses e ON e.ada = d.ada
        LEFT JOIN classifications c ON c.subject = d.subject
        GROUP BY d.ada
        HAVING COUNT(e.kae) = 0
    """, conn)
    no_kae["final_category"] = "Χωρίς ΚΑΕ"
    no_kae["source"] = None # δεν αποφάσισε ούτε ο ΚΑΕ ούτε το LLM
    final = pd.concat([final, no_kae], ignore_index=True)

    # Το ποσό χρειάζεται μόνο για τον πίνακα του report, όχι στη βάση
    final.drop(columns="total").to_sql("final_categories", conn, if_exists="replace", index=False)
    all_decisions = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    conn.close()

    summary = final.groupby("final_category").agg(
        αποφάσεις=("ada", "count"),
        εκ_ευρώ=("total", "sum"),
    ).sort_values("αποφάσεις", ascending=False)
    summary["εκ_ευρώ"] = (summary["εκ_ευρώ"] / 1e6).round(2)
    changed = ((final["source"] == "ΚΑΕ") & (final["final_category"] != final["llm_category"])).sum()

    return "\n\n".join([
        "## Τελική κατηγορία (πίνακας final_categories)",
        f"Ο ΚΑΕ κερδίζει στις κατηγορίες όπου είναι σαφής ({', '.join(SHORT[c] for c in KAE_WINS)}), "
        f"εκτός από τον {', '.join(KAE_UNCLEAR)} (καύσιμα θέρμανσης: πετρέλαιο ή φυσικό αέριο). "
        "Σε όλες τις άλλες αποφάσεις μένει η κατηγορία του LLM.",
        f"Ο ΚΑΕ αποφάσισε σε {(final['source'] == 'ΚΑΕ').sum()} αποφάσεις και άλλαξε την κατηγορία του LLM σε {changed}. "
        f"Οι {len(no_kae)} αποφάσεις χωρίς ΚΑΕ είναι «Χωρίς ΚΑΕ». Έξω μένουν οι {all_decisions - len(final)} "
        "αποφάσεις με μόνο κρατήσεις και επιστροφές (82ΥΥ), που δεν είναι αγορές.",
        as_table(summary),
    ])


def main():
    decisions = load_decisions()
    make_disagreements(decisions) # πρώτα αυτό, γιατί το χρειάζεται η accuracy_section()
    sections = [
        "# Έλεγχος αξιοπιστίας της κατηγοριοποίησης",
        agreement_section(decisions),
        confusion_section(decisions),
        cpv_section(decisions),
        accuracy_section(decisions),
        final_categories_section(decisions),
    ]

    report = "\n\n".join(sections) + "\n"
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "judge":
        judge()
    else:
        main()
