# analysis.py
# Πού πάνε τα χρήματα των Δήμων; Ερωτήματα SQL πάνω στις τελικές κατηγορίες
# και τα αποτελέσματα στο results/analysis.md
# ΔΕΝ καλεί το LLM και ΔΕΝ αλλάζει τα final_categories / classifications:
# μόνο τα διαβάζει (και ξαναφτιάχνει το view purchases).

#       python analysis.py              ερωτήματα, έλεγχοι και analysis.md
#       python analysis.py equipment    οι 10 μεγαλύτερες αποφάσεις Εξοπλισμού (με θέματα, μόνο στην οθόνη)

import os
import sqlite3
import sys

import pandas as pd

from evaluate import SHORT, load_decisions

DB_PATH = "data/spending.db"
REPORT_PATH = "results/analysis.md"

# Ανοχή στις συγκρίσεις ποσών (τα float αθροίσματα δεν βγαίνουν πάντα ακριβώς ίδια)
TOLERANCE = 0.01

# Οι αποφάσεις από τις 10 μεγαλύτερες του Εξοπλισμού που κρίναμε με το χέρι ότι ΔΕΝ είναι
# Εξοπλισμός (κυρίως Υπηρεσίες). Δεν αλλάζουμε την κατηγορία τους, μόνο το γράφουμε στο report.
EQUIPMENT_WRONG = [
    "ΨΘΡΣΩΞΥ-8ΛΤ", "ΡΟΜΔΩΞΥ-Φ70", "ΨΔΥΘΩΞΥ-0Β9",
    "6ΘΣΦΩΞΥ-ΑΛ7", "93ΡΡΩΞΥ-ΑΝΖ", "9ΣΘΩΩΞΥ-ΦΟΝ",
]

# Μία γραμμή για κάθε δαπάνη, με όσα χρειάζονται τα ερωτήματα.
# Έξω μένουν οι γραμμές 82ΥΥ (κρατήσεις και επιστροφές).
# Ο κουβάς χωρίζει τις αγορές από τις μη αγορές και από τις αποφάσεις χωρίς κανέναν ΚΑΕ.
PURCHASES_VIEW = """
    CREATE VIEW purchases AS
    SELECT
        e.ada,
        d.municipality,
        substr(d.issue_date, 1, 7) AS month,
        substr(e.kae, 1, 2) AS sector,
        f.final_category,
        e.payee,
        e.afm,
        e.is_legal_entity,
        e.amount,
        CASE
            WHEN f.final_category = 'Χωρίς ΚΑΕ' THEN 'Χωρίς ΚΑΕ'
            WHEN f.final_category LIKE 'Μη αγορές%' THEN 'Μη αγορές'
            ELSE 'Αγορές'
        END AS bucket
    FROM expenses e
    JOIN decisions d ON d.ada = e.ada
    JOIN final_categories f ON f.ada = e.ada
    WHERE e.kae IS NULL OR substr(e.kae, 4, 2) != '82'
"""


def create_view(conn):
    """Ξαναφτιάχνει το view purchases (αν υπάρχει ήδη, το σβήνει πρώτα)."""
    conn.execute("DROP VIEW IF EXISTS purchases")
    conn.execute(PURCHASES_VIEW)
    conn.commit()


def check_view(conn):
    """Έλεγχοι του view: όλες οι αποφάσεις είναι μέσα, και οι κουβάδες κλείνουν στο σύνολο."""
    decisions, lines, total = conn.execute("""
        SELECT COUNT(DISTINCT ada), COUNT(*), SUM(amount) FROM purchases
    """).fetchone()
    buckets = pd.read_sql("""
        SELECT bucket AS κουβάς, COUNT(DISTINCT ada) AS αποφάσεις, COUNT(*) AS δαπάνες, SUM(amount) AS ευρώ
        FROM purchases
        GROUP BY bucket
        ORDER BY ευρώ DESC
    """, conn)

    assert decisions == 7812, f"Περίμενα 7812 αποφάσεις, βρήκα {decisions}"
    assert abs(buckets["ευρώ"].sum() - total) < TOLERANCE, "Οι κουβάδες δεν κλείνουν στο σύνολο"

    print(f"View purchases: {decisions} αποφάσεις, {lines} δαπάνες, {total:,.2f} €")
    print(buckets.round(2).to_string(index=False))


def by_bucket(conn):
    """1. Ανά Δήμο και κουβά (όλοι οι κουβάδες)."""
    return pd.read_sql("""
        SELECT municipality AS Δήμος, bucket AS κουβάς,
               COUNT(DISTINCT ada) AS αποφάσεις, SUM(amount) AS ευρώ
        FROM purchases
        GROUP BY municipality, bucket
        ORDER BY municipality, ευρώ DESC
    """, conn)


def by_category(conn):
    """2. Κατηγορία × Δήμος, με ευρώ και % επί των αγορών του Δήμου."""
    # Το SUM(SUM(amount)) OVER (PARTITION BY municipality): πρώτα το GROUP BY δίνει το σύνολο
    # κάθε κατηγορίας, μετά το window τα αθροίζει ανά Δήμο, χωρίς να «μαζέψει» τις γραμμές.
    categories = pd.read_sql("""
        SELECT municipality AS Δήμος, final_category AS κατηγορία,
               COUNT(DISTINCT ada) AS αποφάσεις, SUM(amount) AS ευρώ,
               100 * SUM(amount) / SUM(SUM(amount)) OVER (PARTITION BY municipality) AS ποσοστό
        FROM purchases
        WHERE bucket = 'Αγορές'
        GROUP BY municipality, final_category
        ORDER BY municipality, ευρώ DESC
    """, conn)
    categories["κατηγορία"] = categories["κατηγορία"].map(SHORT)
    return categories


def by_month(conn):
    """3. Αγορές ανά μήνα."""
    return pd.read_sql("""
        SELECT month AS μήνας, COUNT(DISTINCT ada) AS αποφάσεις, SUM(amount) AS ευρώ
        FROM purchases
        WHERE bucket = 'Αγορές'
        GROUP BY month
        ORDER BY month
    """, conn)


def by_sector(conn):
    """4. Τομέας του ΚΑΕ (τα 2 πρώτα ψηφία) × κατηγορία, σε ευρώ."""
    sectors = pd.read_sql("""
        SELECT COALESCE(sector, 'Χωρίς ΚΑΕ') AS τομέας, final_category AS κατηγορία,
               SUM(amount) AS ευρώ
        FROM purchases
        WHERE bucket = 'Αγορές'
        GROUP BY τομέας, final_category
    """, conn)
    sectors["κατηγορία"] = sectors["κατηγορία"].map(SHORT)
    # Από «μακρύ» πίνακα (μία γραμμή για κάθε ζευγάρι) σε «πλατύ»: τομείς στις γραμμές, κατηγορίες στις στήλες
    return sectors.pivot_table(index="τομέας", columns="κατηγορία", values="ευρώ", aggfunc="sum", fill_value=0)


def top_suppliers(conn):
    """5. Οι 10 μεγαλύτεροι προμηθευτές-νομικά πρόσωπα ανά Δήμο, και το μερίδιό τους.
    Τα φυσικά πρόσωπα είναι ήδη ανωνυμοποιημένα: δεν τα δείχνουμε ένα-ένα, μόνο το σύνολό τους."""
    # Ομαδοποιούμε με το ΑΦΜ, γιατί η ίδια εταιρεία γράφεται με διαφορετικούς τρόπους.
    # Το MAX(payee) κρατάει απλώς ένα από τα ονόματα.
    suppliers = pd.read_sql("""
        WITH totals AS (
            SELECT municipality, SUM(amount) AS all_purchases
            FROM purchases
            WHERE bucket = 'Αγορές'
            GROUP BY municipality
        ),
        firms AS (
            SELECT municipality, afm, MAX(payee) AS payee,
                   COUNT(DISTINCT ada) AS decisions, SUM(amount) AS amount
            FROM purchases
            WHERE bucket = 'Αγορές' AND is_legal_entity = 1
            GROUP BY municipality, afm
        ),
        ranked AS (
            SELECT f.*,
                   ROW_NUMBER() OVER (PARTITION BY f.municipality ORDER BY f.amount DESC) AS rank,
                   100 * f.amount / t.all_purchases AS pct_all,
                   100 * f.amount / SUM(f.amount) OVER (PARTITION BY f.municipality) AS pct_legal
            FROM firms f
            JOIN totals t ON t.municipality = f.municipality
        )
        SELECT municipality AS Δήμος, rank AS θέση, payee AS δικαιούχος, afm AS ΑΦΜ,
               decisions AS αποφάσεις, amount AS ευρώ,
               pct_all AS "%_αγορών", pct_legal AS "%_νομικών"
        FROM ranked
        WHERE rank <= 10
        ORDER BY municipality, rank
    """, conn)

    # Τα φυσικά πρόσωπα (is_legal_entity = 0) ως ένα σύνολο ανά Δήμο
    anonymous = pd.read_sql("""
        SELECT municipality AS Δήμος,
               COUNT(DISTINCT CASE WHEN is_legal_entity = 0 THEN ada END) AS αποφάσεις,
               SUM(CASE WHEN is_legal_entity = 0 THEN amount ELSE 0 END) AS ευρώ,
               100 * SUM(CASE WHEN is_legal_entity = 0 THEN amount ELSE 0 END) / SUM(amount) AS "%_αγορών"
        FROM purchases
        WHERE bucket = 'Αγορές'
        GROUP BY municipality
    """, conn)
    return suppliers, anonymous


def transparency(conn):
    """6. Διαφάνεια: πόσα ευρώ κάθε Δήμου είναι σε αποφάσεις χωρίς κανέναν ΚΑΕ (όλοι οι κουβάδες)."""
    return pd.read_sql("""
        SELECT municipality AS Δήμος,
               COUNT(DISTINCT CASE WHEN bucket = 'Χωρίς ΚΑΕ' THEN ada END) AS αποφάσεις_χωρίς_ΚΑΕ,
               SUM(CASE WHEN bucket = 'Χωρίς ΚΑΕ' THEN amount ELSE 0 END) AS ευρώ_χωρίς_ΚΑΕ,
               100 * SUM(CASE WHEN bucket = 'Χωρίς ΚΑΕ' THEN amount ELSE 0 END) / SUM(amount) AS "%_ευρώ"
        FROM purchases
        GROUP BY municipality
    """, conn)


def check_totals(buckets, categories, months, sectors):
    """Οι αγορές πρέπει να κλείνουν στο ίδιο σύνολο από όποια μεριά κι αν τις αθροίσουμε."""
    total = buckets.loc[buckets["κουβάς"] == "Αγορές", "ευρώ"].sum() # Δήμοι: το άθροισμα των 2 Δήμων
    for name, other in [
        ("κατηγορίες", categories["ευρώ"].sum()),
        ("μήνες", months["ευρώ"].sum()),
        ("τομείς", sectors.to_numpy().sum()),
    ]:
        assert abs(other - total) < TOLERANCE, f"Οι {name} δίνουν {other:,.2f} €, όχι {total:,.2f} €"

    # Τα % των κατηγοριών κάθε Δήμου αθροίζουν σε 100
    for municipality, pct in categories.groupby("Δήμος")["ποσοστό"].sum().items():
        assert abs(pct - 100) < TOLERANCE, f"Τα % του Δήμου {municipality} αθροίζουν σε {pct:.4f}"

    print(f"Έλεγχοι OK: Δήμοι, κατηγορίες, μήνες και τομείς κλείνουν στα {total:,.2f} €, και τα % κάθε Δήμου στο 100.")


def top_equipment(conn):
    """Οι 10 μεγαλύτερες αποφάσεις Εξοπλισμού, για να τις ελέγξουμε με το μάτι.
    Έχει θέματα αποφάσεων, οπότε ΔΕΝ μπαίνει στο analysis.md."""
    # Ο ΚΑΕ της απόφασης: της μεγαλύτερης δαπάνης που δεν είναι 82ΥΥ (όπως στο evaluate.py)
    return pd.read_sql("""
        WITH totals AS (
            SELECT ada, SUM(amount) AS amount
            FROM purchases
            WHERE final_category = 'Εξοπλισμός'
            GROUP BY ada
        ),
        decision_kae AS (
            SELECT ada, kae, MAX(amount) AS max_amount
            FROM expenses
            WHERE kae IS NOT NULL AND substr(kae, 4, 2) != '82'
            GROUP BY ada
        )
        SELECT t.ada, d.subject, k.kae, t.amount, f.source
        FROM totals t
        JOIN decisions d ON d.ada = t.ada
        JOIN decision_kae k ON k.ada = t.ada
        JOIN final_categories f ON f.ada = t.ada
        ORDER BY t.amount DESC
        LIMIT 10
    """, conn)


def possible_duplicates(conn):
    """Πιθανές διπλές αναρτήσεις στις αγορές: αποφάσεις με ίδια ημερομηνία, θέμα, ποσό και δικαιούχους
    (μόνο εταιρείες, γιατί τα ανωνυμοποιημένα ίδια ποσά είναι συνήθως διαφορετικά πρόσωπα).
    Δεν τις αφαιρούμε, γιατί δεν είναι σίγουρο ότι είναι λάθη. Γυρίζει τα «επιπλέον αντίγραφα» (ada, ποσό)."""
    return pd.read_sql("""
        WITH per_decision AS (
            SELECT p.ada, d.issue_date, d.subject, SUM(p.amount) AS amount,
                   GROUP_CONCAT(DISTINCT p.afm) AS afms
            FROM purchases p
            JOIN decisions d ON d.ada = p.ada
            WHERE p.bucket = 'Αγορές'
            GROUP BY p.ada
        ),
        numbered AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY issue_date, subject, amount, afms ORDER BY ada) AS copy
            FROM per_decision
            WHERE afms IS NOT NULL
        )
        SELECT ada, amount
        FROM numbered
        WHERE copy > 1
    """, conn)


def reliability():
    """Αξιοπιστία κάθε κατηγορίας από την precision του LLM (όπως στο evaluate.py):
    από τις ελεγμένες αποφάσεις όπου το LLM είπε Χ, πόσες έχουν και ΚΑΕ Χ."""
    decisions = load_decisions()
    checked = decisions[decisions["checked"]]
    agrees = checked["llm_category"] == checked["kae_new"]
    precision = 100 * agrees.groupby(checked["llm_category"]).mean()

    def label(p):
        if p >= 80:
            return "υψηλή"
        if p >= 50:
            return "μέτρια"
        return "χαμηλή"

    return pd.DataFrame({
        "precision_%": precision.round(1),
        "αξιοπιστία": precision.map(label),
    })


def md_table(df, index=False):
    """Ένας πίνακας pandas ως κείμενο markdown (μέσα σε ``` για να κρατήσει τη στοίχιση)."""
    return "```\n" + df.round(1).to_string(index=index) + "\n```"


def main():
    conn = sqlite3.connect(DB_PATH)
    create_view(conn)
    check_view(conn)

    buckets = by_bucket(conn)
    categories = by_category(conn)
    months = by_month(conn)
    sectors = by_sector(conn)
    suppliers, anonymous = top_suppliers(conn)
    check_totals(buckets, categories, months, sectors)

    # Η αξιοπιστία μπαίνει δίπλα σε κάθε κατηγορία
    scores = reliability()
    categories = categories.join(scores.rename(index=SHORT), on="κατηγορία") # στον πίνακα τα ονόματα είναι σύντομα

    # Οι σημειώσεις: Εξοπλισμός και πιθανές διπλές αναρτήσεις
    top10 = top_equipment(conn)
    wrong = top10[top10["ada"].isin(EQUIPMENT_WRONG)]
    equipment_total = categories.loc[categories["κατηγορία"] == "Εξοπλισμός", "ευρώ"].sum()
    duplicates = possible_duplicates(conn)
    duplicates_eur = duplicates["amount"].sum()
    purchases_total = buckets.loc[buckets["κουβάς"] == "Αγορές", "ευρώ"].sum()
    no_kae = transparency(conn)
    conn.close()

    sections = [
        "# Πού πάνε τα χρήματα των Δήμων (Πειραιάς και Μαρούσι, 2025)",
        "Αποφάσεις Β.2.1 (έγκριση δαπάνης, κυρίως χρηματικά εντάλματα πληρωμής) από τη Διαύγεια. "
        "Η κατηγορία είναι η τελική "
        "(ΚΑΕ όπου είναι σαφής, αλλιώς LLM). Οι γραμμές 82ΥΥ (κρατήσεις και επιστροφές) δεν μετράνε. "
        "Ποσά σε ευρώ.",

        "## 1. Αγορές, μη αγορές και αποφάσεις χωρίς ΚΑΕ",
        "Οι «Μη αγορές» είναι μισθοδοσία, δάνεια, φόροι και αποδόσεις. Οι πίνακες 2–5 κοιτάνε μόνο τις αγορές.",
        md_table(buckets),

        "## 2. Κατηγορίες ανά Δήμο",
        "Το ποσοστό είναι επί των αγορών του Δήμου. Η αξιοπιστία βγαίνει από την precision του LLM: "
        "υψηλή ≥ 80%, μέτρια ≥ 50%, αλλιώς χαμηλή. Για Μισθώματα, Ενέργεια, Καύσιμα και Οχήματα "
        "αποφασίζει κυρίως ο ΚΑΕ, οπότε εκεί η αξιοπιστία είναι μάλλον μεγαλύτερη από όση δείχνει η στήλη. "
        "Το «Άλλο» βγαίνει 0%, γιατί κανένας ΚΑΕ δεν αντιστοιχεί σε «Άλλο».",
        md_table(categories),
        f"**Προσοχή στον Εξοπλισμό** (precision {scores.loc['Εξοπλισμός', 'precision_%']}%): από τις 10 μεγαλύτερες "
        f"αποφάσεις του, οι {len(wrong)} ({wrong['amount'].sum() / 1e6:.2f} εκ. €, το "
        f"{100 * wrong['amount'].sum() / equipment_total:.0f}% όλου του Εξοπλισμού) κρίθηκαν με το χέρι ότι ανήκουν "
        "σε άλλη κατηγορία, κυρίως Υπηρεσίες. Το ποσό του Εξοπλισμού είναι άρα πολύ μεγαλύτερο από το πραγματικό.",

        "## 3. Αγορές ανά μήνα",
        md_table(months),

        "## 4. Τομέας του ΚΑΕ × κατηγορία",
        "Ο τομέας είναι τα 2 πρώτα ψηφία του ΚΑΕ (η υπηρεσία του Δήμου που πλήρωσε).",
        md_table(sectors, index=True),

        "## 5. Μεγαλύτεροι προμηθευτές (νομικά πρόσωπα)",
        "Μερίδιο επί όλων των αγορών του Δήμου και επί όσων πήγαν σε νομικά πρόσωπα. "
        "Τα φυσικά πρόσωπα είναι ανωνυμοποιημένα από τη Διαύγεια και φαίνονται μόνο ως σύνολο.",
        md_table(suppliers),
        md_table(anonymous),

        "## 6. Διαφάνεια",
        "Αποφάσεις χωρίς κανέναν ΚΑΕ: δεν ξέρουμε τι πληρώθηκε. Το ποσοστό είναι επί όλων των ευρώ του Δήμου.",
        md_table(no_kae),
        f"Πιθανές διπλές αναρτήσεις: {len(duplicates)} αποφάσεις αγορών ({duplicates_eur / 1e6:.2f} εκ. €, το "
        f"{100 * duplicates_eur / purchases_total:.1f}% των αγορών) έχουν ίδια ημερομηνία, θέμα, ποσό και "
        "δικαιούχο με μια άλλη απόφαση. Δεν τις αφαιρέσαμε, γιατί μπορεί να είναι και κανονικές επαναλήψεις.",
    ]

    report = "\n\n".join(sections) + "\n"
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)


def equipment():
    conn = sqlite3.connect(DB_PATH)
    create_view(conn)
    # Δύο γραμμές για κάθε απόφαση, γιατί τα θέματα είναι πολύ μακριά για πίνακα
    for i, row in enumerate(top_equipment(conn).itertuples(), start=1):
        print(f"\n{i}. {row.ada}   ΚΑΕ {row.kae}   {row.amount:,.2f} €   (από: {row.source})")
        print(f"   {row.subject}")
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "equipment":
        equipment()
    else:
        main()
