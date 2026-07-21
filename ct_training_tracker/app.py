import streamlit as st

from ct_training_tracker.application import run

if __name__ == "__main__":
    st.set_page_config(
        page_title="CT Initial Training Tracker",
        page_icon="🫁",
        layout="wide",
    )
    run()
