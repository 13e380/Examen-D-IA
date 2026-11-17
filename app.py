"""Point d'entrée Streamlit de CIVITAS."""
from datetime import datetime

import streamlit as st

from citizen_ui import citizen_space
from operator_ui import admin_gate, complaint_dashboard
from ui_shared import LANGUAGES, setup_page, tr


def main() -> None:
    """Construit la page : barre de marque, choix du profil et de la langue, puis l'espace choisi."""
    setup_page()
    brand, mode, language = st.columns([2.2, 3, 1.4], vertical_alignment="center")
    brand.markdown('<div class="cv-brand"><span class="cv-logo">◈</span><b>CIVITAS</b>'
                   '<small>Smart City · Lubumbashi</small></div>', unsafe_allow_html=True)
    with language:
        selected_language = st.selectbox(tr("🌐 Langue / Language"), list(LANGUAGES), key="language_name",
                                         label_visibility="collapsed")
    st.session_state["language"] = LANGUAGES[selected_language]
    with mode:
        choice = st.radio(
            "Profil",
            ["citizen", "admin"],
            format_func=lambda value: tr("👥 Espace Population" if value == "citizen" else "📥 Dépôt des plaintes"),
            horizontal=True,
            label_visibility="collapsed",
            key="role_mode",
        )
    if choice == "citizen":
        citizen_space()
    elif admin_gate():
        complaint_dashboard()
    st.markdown(
        f'<div class="cv-footer">◈ CIVITAS · {tr("Système expert Smart City")} · '
        f'{datetime.now():%d/%m/%Y %H:%M} · moteur hybride avant/arrière · dépôt persistant SQLite</div>',
        unsafe_allow_html=True,
    )


main()
