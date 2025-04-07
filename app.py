import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# --- Load environment and connect to DB ---
load_dotenv()
db_url = os.getenv("SUPABASE_DB_URL")
engine = create_engine(db_url)

st.set_page_config(page_title="Shared Budget Tracker", layout="wide")
st.title("💸 Shared Budget Tracker")

# --- Sidebar Navigation ---
page = st.sidebar.radio("Select Page", ["Add Expense", "View Expenses"])

# --- Add Expense Page ---
if page == "Add Expense":
    with engine.connect() as conn:
        # Fetch dropdown data
        categories = conn.execute(text("SELECT id, name FROM categories")).fetchall()
        subcategories = conn.execute(text("SELECT id, name FROM subcategories")).fetchall()
        people = conn.execute(text("SELECT id, name FROM people")).fetchall()

    # Create dictionaries for dropdowns
    category_dict = {name: id for id, name in categories}
    subcategory_dict = {name: id for id, name in subcategories}
    people_dict = {name: id for id, name in people}

    # --- Form Inputs ---
    st.subheader("➕ Record a New Expense")
    with st.form("expense_form"):
        category = st.selectbox("Category", list(category_dict.keys()))
        subcategory = st.selectbox("Subcategory", list(subcategory_dict.keys()))
        note = st.text_input("Note")
        amount = st.number_input("Total Amount", min_value=0.0, step=0.01)

        selected_people = st.multiselect("Who was involved?", list(people_dict.keys()))
        # if one person is selected, then their share is equal to the total amount
        if selected_people == 1:
            shares = {selected_people[0]: amount}
        else:
            shares = {}
            for name in selected_people:
                shares[name] = st.number_input(f"{name}'s Share", min_value=0.0, step=0.01, key=name)

        submitted = st.form_submit_button("Submit Expense")

    # --- Handle Form Submission ---
    if submitted:
        total_share = sum(shares.values())
        if round(total_share, 2) != round(amount, 2):
            st.error(f"⚠️ Total share ({total_share}) must equal total amount ({amount})")
        elif not selected_people:
            st.error("⚠️ Select at least one person")
        else:
            with engine.begin() as conn:
                result = conn.execute(
                    text("""
                        INSERT INTO expenses (category_id, subcategory_id, note, amount)
                        VALUES (:cat, :subcat, :note, :amt) RETURNING id
                    """),
                    {"cat": category_dict[category], "subcat": subcategory_dict[subcategory],
                     "note": note, "amt": amount}
                )
                expense_id = result.fetchone()[0]

                for person, share in shares.items():
                    conn.execute(
                        text("""
                            INSERT INTO expense_participants (expense_id, person_id, share)
                            VALUES (:eid, :pid, :sh)
                        """),
                        {"eid": expense_id, "pid": people_dict[person], "sh": share}
                    )
            st.success("✅ Expense recorded successfully!")

# --- View Expenses Page ---
if page == "View Expenses":
    st.subheader("📊 Expense Breakdown")
    with engine.connect() as conn:
        df = pd.read_sql("""
            SELECT 
                e.id AS expense_id,
                e.note,
                e.amount,
                e.created_at,
                p.name AS person,
                ep.share,
                c.name AS category,
                s.name AS subcategory
            FROM expenses e
            JOIN expense_participants ep ON e.id = ep.expense_id
            JOIN people p ON p.id = ep.person_id
            JOIN categories c ON e.category_id = c.id
            JOIN subcategories s ON e.subcategory_id = s.id
            ORDER BY e.created_at DESC
        """, conn)

    st.dataframe(df)

