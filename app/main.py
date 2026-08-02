"""Agent Anatomy Explorer — router.

🏠 Home selects the agent; each agent gets its own workspace with the
same five pages (Anatomy · Live Run · Eval Lab · GraphRAG · Learning).
The page functions live in app/pages.py; navigation is defined in
app/nav.py; the design system in app/ui.py. This file only frames them:
common CSS + the navigation tree.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import home
from app.components import CSS
from app.nav import get_pages
from app.ui import CHROME_CSS

st.set_page_config(page_title="Agent Anatomy Explorer", page_icon="🧠",
                   layout="wide")
st.markdown(CSS + CHROME_CSS, unsafe_allow_html=True)

pages = get_pages()
nav = st.navigation({
    "Getting started": [
        st.Page(home.home_page, title="Home", icon="🏠", default=True),
    ],
    "🕵️ Fraud Investigator": [
        pages["fraud"]["anatomy"], pages["fraud"]["live"],
        pages["fraud"]["eval"], pages["fraud"]["graphrag"],
        pages["fraud"]["learning"],
    ],
    "📈 Cost Trend Analyst": [
        pages["cost"]["anatomy"], pages["cost"]["live"],
        pages["cost"]["eval"], pages["cost"]["graphrag"],
        pages["cost"]["learning"],
    ],
    "🎯 Portfolio Journey Analyst": [
        pages["portfolio"]["anatomy"], pages["portfolio"]["live"],
        pages["portfolio"]["eval"], pages["portfolio"]["graphrag"],
        pages["portfolio"]["learning"],
    ],
})
nav.run()
