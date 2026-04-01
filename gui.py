import streamlit as st

st.set_page_config(page_title="Search UI", page_icon="🔎")

items = [
    "Apple",
    "Banana",
    "Orange",
    "Grapes",
    "Mango",
    "Pineapple",
    "Strawberry",
    "Blueberry",
    "Watermelon",
    "Peach",
    "Pear",
    "Kiwi",
]

st.title("Personalized Search")
st.write("Type in the box to search.")

query = st.text_input("Search", placeholder="Try: apple")

if query:
    results = [item for item in items if query.lower() in item.lower()]
else:
    results = items

st.subheader("Results")

if results:
    for item in results:
        st.write(f"- {item}")
else:
    st.warning("No results found.")