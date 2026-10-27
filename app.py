# app.py
# Dashboard: πού πάνε τα χρήματα του Πειραιά και του Αμαρουσίου (2025, Διαύγεια Β.2.1).
# Διαβάζει ΜΟΝΟ τα app_data/*.csv (τα βγάζει το export_app_data.py): καμία βάση, κανένα LLM.
# Τα δεδομένα μένουν ελληνικά. Μεταφράζονται μόνο για εμφάνιση, με τα λεξικά πιο κάτω.

#       streamlit run app.py

import altair as alt
import pandas as pd
import streamlit as st

PURCHASES_CSV = "app_data/purchases.csv"
RELIABILITY_CSV = "app_data/reliability.csv"

# Οι κατηγορίες στα αγγλικά (μόνο για εμφάνιση)
LABELS = {
    "Μισθώματα": "Rentals",
    "Ενέργεια, νερό και τηλεφωνία": "Energy, water & telecoms",
    "Καύσιμα": "Fuel",
    "Οχήματα (ανταλλακτικά, ελαστικά, επισκευές)": "Vehicles (parts, tyres, repairs)",
    "Συντήρηση κτιρίων και εξοπλισμού": "Building & equipment maintenance",
    "Υλικά και αναλώσιμα": "Materials & consumables",
    "Τρόφιμα και παροχές εργαζομένων": "Food & staff benefits",
    "Υπηρεσίες τρίτων": "Third-party services",
    "Εκδηλώσεις και προβολή": "Events & promotion",
    "Εξοπλισμός": "Equipment",
    "Έργα": "Public works",
    "Μη αγορές (δάνεια, φόροι, αποδόσεις, προσωπικό)": "Non-purchases (loans, taxes, transfers, staff)",
    "Άλλο": "Other",
    "Χωρίς ΚΑΕ": "No KAE",
}
MUNICIPALITIES = {"Πειραιάς": "Piraeus", "Μαρούσι": "Marousi"}
BUCKETS = {"Αγορές": "Purchases", "Μη αγορές": "Non-purchases", "Χωρίς ΚΑΕ": "No KAE"}
RELIABILITY = {"υψηλή": "high", "μέτρια": "medium", "χαμηλή": "low"}

# Ένα σταθερό χρώμα για κάθε Δήμο, σε όλα τα γραφήματα (ελεγμένα και για αχρωματοψία)
COLORS = alt.Scale(domain=["Piraeus", "Marousi"], range=["#2a78d6", "#eb6834"])

# Τα ευρήματα, από το results/analysis.md (εγκεκριμένο κείμενο). Αφορούν όλα τα δεδομένα, όχι τα φίλτρα.
FINDINGS = """
Full year 2025, both municipalities (filters do not apply here).

1. **Purchases are about half of the money.** Of €102.8M, €52.7M are purchases. €41.1M are
   salaries, loans, taxes and transfers, and €9.1M have no KAE code.
2. **Transparency gap in Piraeus.** 12.6% of Piraeus' spending (€8.75M) is in decisions with
   no KAE code, so we cannot tell what was bought. In Marousi it is 1.2%.
3. **Athens could not be analysed.** It published only 33 expenditure approvals (B.2.1) in 2025,
   against about 4,000 in Piraeus and 4,100 in Marousi.
4. **Where purchases go.** Marousi: public works 21.4%, equipment 18.4%, energy 15.4%.
   Piraeus: equipment 23.0%, energy 13.0%, third-party services 10.8%. Equipment is unreliable:
   at least €5.5M of its €11.1M are services or transfers that were misclassified.
5. **Concentration.** The largest supplier receives 11.2% of Marousi's purchases and 9.6% of
   Piraeus' purchases. The Piraeus figure includes one possible duplicate of €1.13M.
6. **Year-end peak.** By decision date, December is the busiest month (€8.51M, 803 decisions)
   and January the quietest (€0.61M).
7. **Possible duplicate postings.** 51 purchase decisions (€1.75M, 3.3%) repeat the date,
   subject, amount and supplier of another decision.

**Recommendations**

- Every payment decision should carry a KAE code and a subject that says what was bought.
- Municipalities, or Diavgeia itself, could flag decisions that repeat the same date, subject,
  amount and supplier.
"""


@st.cache_data
def load_data():
    """Τα δύο CSV. Το dtype κρατάει τα μηδενικά μπροστά (τομέας 00, ΑΦΜ 090000045)."""
    purchases = pd.read_csv(PURCHASES_CSV, dtype={"sector": str, "afm": str})
    reliability = pd.read_csv(RELIABILITY_CSV)
    return purchases, reliability


def euros(amount):
    """Ποσό ως κείμενο, π.χ. €52,651,239.87"""
    return f"€{amount:,.2f}"


def filter_data(purchases):
    """Τα φίλτρα του sidebar. Γυρίζει όλους τους κουβάδες (Δήμος και μήνες) και μόνο τις
    αγορές (επιπλέον κατηγορία), γιατί η κατηγορία υπάρχει μόνο στις αγορές."""
    st.sidebar.header("Filters")
    municipalities = st.sidebar.multiselect(
        "Municipality", list(MUNICIPALITIES), default=list(MUNICIPALITIES), format_func=MUNICIPALITIES.get
    )
    categories = sorted(purchases.loc[purchases["bucket"] == "Αγορές", "final_category"].unique(), key=LABELS.get)
    chosen = st.sidebar.multiselect("Category", categories, default=categories, format_func=LABELS.get)
    months = sorted(purchases["month"].unique())
    first, last = st.sidebar.select_slider("Months", options=months, value=(months[0], months[-1]))

    selected = purchases[
        purchases["municipality"].isin(municipalities) & purchases["month"].between(first, last)
    ]
    bought = selected[(selected["bucket"] == "Αγορές") & selected["final_category"].isin(chosen)]
    return selected, bought


def overview(selected, bought):
    st.subheader("Overview")
    col1, col2 = st.columns(2)
    col1.metric("Total purchases", euros(bought["amount"].sum()))
    col2.metric("Purchase decisions", f"{bought['ada'].nunique():,}")

    # Διαφάνεια: % των ευρώ κάθε Δήμου σε αποφάσεις χωρίς ΚΑΕ (όλοι οι κουβάδες)
    st.markdown("**Transparency: share of all payments with no KAE code**")
    cols = st.columns(max(selected["municipality"].nunique(), 1))
    for col, (municipality, rows) in zip(cols, selected.groupby("municipality")):
        no_kae = rows.loc[rows["bucket"] == "Χωρίς ΚΑΕ", "amount"].sum()
        col.metric(MUNICIPALITIES[municipality], f"{100 * no_kae / rows['amount'].sum():.1f}%",
                   help=f"{euros(no_kae)} of {euros(rows['amount'].sum())}")


def categories_tab(bought, reliability):
    st.subheader("Purchases by category")
    table = bought.groupby(["municipality", "final_category"], as_index=False)["amount"].sum()
    table["share"] = 100 * table["amount"] / table.groupby("municipality")["amount"].transform("sum")
    table = table.merge(reliability, on="final_category", how="left")

    # Ετικέτα: η κατηγορία στα αγγλικά και η αξιοπιστία της
    table["Category"] = table["final_category"].map(LABELS) + " (" + table["reliability"].map(RELIABILITY) + ")"
    table["Municipality"] = table["municipality"].map(MUNICIPALITIES)

    chart = alt.Chart(table).mark_bar(cornerRadiusEnd=4).encode(
        x=alt.X("amount:Q", title="Euros"),
        y=alt.Y("Category:N", sort="-x", title=None),
        yOffset="Municipality:N",
        color=alt.Color("Municipality:N", scale=COLORS),
        tooltip=["Municipality", "Category", alt.Tooltip("amount:Q", format=",.0f", title="Euros"),
                 alt.Tooltip("share:Q", format=".1f", title="% of purchases")],
    )
    st.altair_chart(chart)
    st.caption("Reliability = how often the category agreed with the KAE code when checked "
               "(high ≥ 80%, medium ≥ 50%, low < 50%).")

    st.dataframe(
        table[["Municipality", "Category", "amount", "share", "precision"]]
        .sort_values(["Municipality", "amount"], ascending=[True, False]),
        hide_index=True,
        column_config={
            "amount": st.column_config.NumberColumn("Euros", format="%.2f"),
            "share": st.column_config.NumberColumn("% of purchases", format="%.1f"),
            "precision": st.column_config.NumberColumn("Precision %", format="%.1f"),
        },
    )


def monthly_tab(bought):
    st.subheader("Purchases by month")
    table = bought.groupby(["month", "municipality"], as_index=False)["amount"].sum()
    table["Municipality"] = table["municipality"].map(MUNICIPALITIES)
    chart = alt.Chart(table).mark_line(point=True, strokeWidth=2).encode(
        x=alt.X("month:O", sort="ascending", title="Month (decision date)"),
        y=alt.Y("amount:Q", title="Euros"),
        color=alt.Color("Municipality:N", scale=COLORS),
        tooltip=["Municipality", "month", alt.Tooltip("amount:Q", format=",.0f", title="Euros")],
    )
    st.altair_chart(chart)


def suppliers_tab(bought):
    st.subheader("Top 10 suppliers (legal entities)")
    st.caption("Grouped by tax number (AFM), because one company is often written in several ways. "
               "Payments to natural persons are anonymised by Diavgeia and shown only as a total.")
    for municipality, rows in bought.groupby("municipality"):
        firms = rows[rows["is_legal_entity"] == 1].groupby("afm", as_index=False).agg(
            Supplier=("payee", "max"), Decisions=("ada", "nunique"), Euros=("amount", "sum")
        )
        firms["% of all purchases"] = 100 * firms["Euros"] / rows["amount"].sum()
        firms["% of legal entities"] = 100 * firms["Euros"] / firms["Euros"].sum()
        top = firms.sort_values("Euros", ascending=False).head(10)

        st.markdown(f"**{MUNICIPALITIES[municipality]}**")
        st.dataframe(top.rename(columns={"afm": "AFM"}), hide_index=True,
                     column_config={c: st.column_config.NumberColumn(format="%.1f")
                                    for c in ["% of all purchases", "% of legal entities"]})

        people = rows[rows["is_legal_entity"] == 0]
        st.caption(f"Anonymised natural persons: {euros(people['amount'].sum())} "
                   f"({100 * people['amount'].sum() / rows['amount'].sum():.1f}% of purchases, "
                   f"{people['ada'].nunique():,} decisions)")


def other_buckets_tab(selected):
    st.subheader("Non-purchases and decisions with no KAE")
    st.caption("Kept apart from the categories: non-purchases are salaries, loans, taxes and transfers; "
               "'No KAE' decisions have no budget code, so we cannot tell what was paid.")
    others = selected[selected["bucket"] != "Αγορές"]
    table = others.groupby(["municipality", "bucket"], as_index=False).agg(
        Decisions=("ada", "nunique"), Euros=("amount", "sum")
    )
    table["Municipality"] = table["municipality"].map(MUNICIPALITIES)
    table["Type"] = table["bucket"].map(BUCKETS)
    st.dataframe(table[["Municipality", "Type", "Decisions", "Euros"]], hide_index=True,
                 column_config={"Euros": st.column_config.NumberColumn(format="%.2f")})


def notes_tab(purchases):
    """Οι σημειώσεις αφορούν όλα τα δεδομένα, γι' αυτό δεν ακολουθούν τα φίλτρα."""
    st.subheader("Notes on the data")
    bought = purchases[purchases["bucket"] == "Αγορές"]
    equipment = bought[bought["final_category"] == "Εξοπλισμός"]
    wrong = equipment[equipment["equipment_wrong"]]
    duplicates = bought[bought["possible_duplicate"]]

    st.markdown(f"""
- **Equipment is overstated.** Of the 10 largest equipment decisions, {wrong['ada'].nunique()} were checked by
  hand and belong to other categories, mostly services ({euros(wrong['amount'].sum())},
  {100 * wrong['amount'].sum() / equipment['amount'].sum():.0f}% of all equipment). Their category was not changed.
- **Possible duplicate postings.** {duplicates['ada'].nunique()} purchase decisions
  ({euros(duplicates['amount'].sum())}) repeat the date, subject, amount and supplier of another decision.
  They were not removed, because they may be legitimate.
- **Month** is the issue date of the payment decision, not the date of the purchase.
- **Categories** come from the KAE code where it is clear (rentals, energy, fuel, vehicles) and from a
  local LLM that read the decision subject everywhere else.
- **Source:** [Diavgeia](https://diavgeia.gov.gr), expenditure approvals (B.2.1), mostly payment orders, 2025. Withholdings and refunds
  (KAE 82xx) are excluded.
""")
    st.markdown("**Equipment decisions that belong to other categories**")
    flagged = wrong.groupby(["ada", "url"], as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    st.dataframe(flagged, hide_index=True, column_config={
        "url": st.column_config.LinkColumn("Diavgeia", display_text="open"),
        "amount": st.column_config.NumberColumn("Euros", format="%.2f"),
    })


def main():
    st.set_page_config(page_title="Municipal spending – Diavgeia", layout="wide")
    st.title("Where does the money go?")
    st.caption("Spending of the Municipalities of Piraeus and Marousi in 2025, from Diavgeia.")

    purchases, reliability = load_data()
    selected, bought = filter_data(purchases)

    overview(selected, bought)
    tabs = st.tabs(["Categories", "Monthly", "Suppliers", "Non-purchases & no KAE", "Notes", "Findings"])
    with tabs[0]:
        categories_tab(bought, reliability)
    with tabs[1]:
        monthly_tab(bought)
    with tabs[2]:
        suppliers_tab(bought)
    with tabs[3]:
        other_buckets_tab(selected)
    with tabs[4]:
        notes_tab(purchases)
    with tabs[5]:
        st.markdown(FINDINGS)


main()