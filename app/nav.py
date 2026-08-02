"""Page registry — one st.Page set per agent (built once, shared).

Both the router (app/main.py) and the Home page (app/home.py) use the
same StreamlitPage objects, so st.switch_page always targets a page that
is registered in the active navigation.
"""
from __future__ import annotations

from functools import partial

import streamlit as st

from app import pages

_PAGES: dict | None = None


def _build() -> dict:
    out = {}
    for agent in ("fraud", "cost", "portfolio"):
        out[agent] = {
            "anatomy": st.Page(partial(pages.anatomy_page, agent),
                               title="Anatomy", icon="🧠",
                               url_path=f"{agent}-anatomy"),
            "live": st.Page(partial(pages.live_page, agent),
                            title="Live Run", icon="▶️",
                            url_path=f"{agent}-live"),
            "eval": st.Page(partial(pages.eval_page, agent),
                            title="Eval Lab", icon="📊",
                            url_path=f"{agent}-eval"),
            "graphrag": st.Page(partial(pages.graphrag_page, agent),
                                title="GraphRAG", icon="🧬",
                                url_path=f"{agent}-graphrag"),
            "learning": st.Page(partial(pages.learning_page, agent),
                                title="Learning", icon="🎓",
                                url_path=f"{agent}-learning"),
        }
    return out


def get_pages() -> dict:
    global _PAGES
    if _PAGES is None:
        _PAGES = _build()
    return _PAGES
