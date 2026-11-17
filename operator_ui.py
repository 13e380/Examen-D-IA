"""Parcours opérateur : authentification et gestion des plaintes."""
from __future__ import annotations

import hmac
import html
import sqlite3

import pandas as pd
import streamlit as st

from ui_shared import (
    ADMIN_PIN,
    DISTRICTS,
    PRIO_ICON,
    REPOSITORY,
    STATE,
    backward_tree_html,
    badge,
    chips_html,
    eng,
    section_title,
    stat_cards,
    trace_timeline_html,
    unit_bars_html,
    fmt_incident,
    hero,
    render_incident_map,
    restore_state_from_repository,
    tr,
)


def admin_gate() -> bool:
    """Écran de connexion opérateur. Retourne True si le code saisi est correct."""
    if st.session_state.get("admin_ok"):
        return True
    hero("CIVITAS — Dépôt des plaintes", "Accès réservé aux opérateurs chargés du traitement des plaintes.")
    with st.form("login"):
        pin = st.text_input(tr("Code d'accès opérateur"), type="password")
        if st.form_submit_button(tr("🔐 Se connecter"), type="primary"):
            if hmac.compare_digest(pin.encode(), ADMIN_PIN.encode()):
                st.session_state["admin_ok"] = True
                st.rerun()
            else:
                st.error(tr("Code incorrect."))
    st.caption(tr("Démonstration : code par défaut « 1234 » (variable d'environnement CIVITAS_ADMIN_PIN)."))
    return False

def complaint_dashboard() -> None:
    """Centre de commandement : plaintes, moteur et agenda, validation réglementaire, base de connaissances."""
    hero("CIVITAS — Centre de commandement", "Plaintes, raisonnement du moteur expert et validation réglementaire.")
    with st.sidebar:
        st.markdown("### 📥 Gestion des plaintes")
        auto = st.toggle("Actualisation automatique", True)
        every = st.slider("Intervalle (s)", 3, 30, 5) if auto else 5
        if st.button("🔒 Se déconnecter"):
            st.session_state["admin_ok"] = False
            st.rerun()

    def render_dashboard() -> None:
        """Liste, filtre et détail des plaintes, avec les actions de déploiement et de résolution."""
        complaints = REPOSITORY.list_complaints()
        active = [item for item in complaints if item.active]
        urgent = [item for item in active if item.priority == "P1"]
        resolved = len(complaints) - len(active)
        stat_cards([
            ("📥", str(len(complaints)), "Plaintes reçues", "cyan"),
            ("⏳", str(len(active)), "À traiter", "amber"),
            ("🚨", str(len(urgent)), "Urgentes P1", "red"),
            ("✅", str(resolved), "Résolues", "green"),
        ])

        with st.expander("🔎 Rechercher et filtrer", expanded=True):
            f1, f2, f3 = st.columns([2, 1, 1])
            search = f1.text_input("Recherche (zone, texte ou numéro)", key="complaint_search").strip().casefold()
            status_options = [eng.STATUS_NEW, eng.STATUS_DEPLOYED, eng.STATUS_RESOLVED]
            selected_statuses = f2.multiselect("Statut", status_options, default=status_options, key="complaint_status_filter")
            selected_priorities = f3.multiselect(
                "Priorité", ["P1", "P2", "P3", "P4"], default=["P1", "P2", "P3", "P4"],
                key="complaint_priority_filter",
            )
        filtered = [
            item for item in complaints
            if item.status in selected_statuses
            and item.priority in selected_priorities
            and (
                not search
                or search in str(item.id)
                or search in item.district.casefold()
                or search in item.description.casefold()
                or search in item.rule.fact.casefold()
            )
        ]
        if filtered:
            st.dataframe(
                pd.DataFrame([
                    {
                        "N°": item.id,
                        "Priorité": f"{PRIO_ICON[item.priority]} {item.priority}",
                        "Type": item.rule.fact,
                        "Zone": item.district,
                        "Reçue le": item.created_at.strftime("%d/%m/%Y %H:%M"),
                        "Canal": item.channel,
                        "Statut": item.status,
                    }
                    for item in filtered
                ]),
                hide_index=True,
                use_container_width=True,
            )
            chosen_id = st.selectbox(
                "Ouvrir une plainte",
                [item.id for item in filtered],
                format_func=lambda complaint_id: fmt_incident(
                    next(item for item in filtered if item.id == complaint_id)
                ),
                key="complaint_selected_id",
            )
            incident = REPOSITORY.get_complaint(chosen_id)
            if incident is None:
                st.error("Cette plainte n'est plus disponible dans le dépôt. Actualisez le tableau.")
                return

            st.divider()
            st.subheader(f"Plainte #{incident.id} · {incident.rule.icon} {incident.rule.fact}")
            st.markdown(
                f"{badge(incident.priority)} **{incident.status}** · {html.escape(incident.district)} · "
                f"{incident.created_at:%d/%m/%Y à %H:%M}",
                unsafe_allow_html=True,
            )
            st.write(incident.description)
            if incident.transcript:
                st.caption(f"Transcription : {incident.transcript}")
            if incident.image_name:
                st.caption(f"Photos : {incident.image_name}")
            attachments = REPOSITORY.get_attachments(incident.id)
            image_attachments = [
                (filename, data) for filename, content_type, data in attachments
                if content_type.startswith("image/")
            ]
            audio_attachments = [
                (filename, content_type, data)
                for filename, content_type, data in attachments
                if content_type.startswith("audio/")
            ]
            if image_attachments:
                st.markdown("**Photos compressées**")
                image_columns = st.columns(min(5, len(image_attachments)))
                for index, (filename, image_data) in enumerate(image_attachments):
                    image_columns[index % len(image_columns)].image(image_data, caption=filename)
            for filename, content_type, audio_data in audio_attachments:
                st.markdown(f"**Message vocal — {html.escape(filename)}**")
                st.audio(audio_data, format=content_type)
            if incident.latitude is not None and incident.longitude is not None:
                st.caption(f"Position partagée : {incident.latitude:.3f}, {incident.longitude:.3f}")

            action_col, status_col = st.columns([1, 2])
            if action_col.button(
                "🚀 Déployer le plan",
                type="primary",
                disabled=incident.status != eng.STATUS_NEW or incident.district not in DISTRICTS,
                key=f"deploy_complaint_{incident.id}",
            ):
                recommendation = eng.deploy_plan(STATE, incident.id)
                if recommendation is not None:
                    try:
                        REPOSITORY.save_complaint(
                            eng.get_incident(STATE, incident.id),
                            "Plan d'intervention déployé",
                            f"{len(recommendation.rows)} unité(s) engagée(s)",
                        )
                    except (OSError, sqlite3.Error, TypeError, ValueError) as error:
                        restore_state_from_repository()
                        st.error(f"Le plan n'a pas pu être enregistré : {error}")
                    else:
                        st.rerun()
            if status_col.button(
                "✅ Marquer comme résolue",
                disabled=not incident.active,
                key=f"resolve_complaint_{incident.id}",
            ):
                if eng.resolve_incident(STATE, incident.id):
                    try:
                        REPOSITORY.save_complaint(
                            eng.get_incident(STATE, incident.id),
                            "Plainte résolue",
                            "Statut modifié par un opérateur",
                        )
                    except (OSError, sqlite3.Error, TypeError, ValueError) as error:
                        restore_state_from_repository()
                        st.error(f"Le statut n'a pas pu être enregistré : {error}")
                    else:
                        st.rerun()

            st.markdown(f'<div class="cv-card"><b>🎯 Consigne recommandée</b><br>{html.escape(incident.rule.action)}</div>',
                        unsafe_allow_html=True)
            deduced = eng.derived_actions(incident.trace)
            if deduced:
                st.markdown("**Actions déduites par le chaînage avant**")
                st.markdown(chips_html(deduced, "derived"), unsafe_allow_html=True)
            with st.expander("🧠 Raisonnement du moteur (module d'explication)", expanded=False):
                st.markdown(trace_timeline_html(incident.trace), unsafe_allow_html=True)
            with st.expander("🕒 Historique de traitement"):
                for event in REPOSITORY.get_events(incident.id):
                    detail = f" — {html.escape(event['details'])}" if event["details"] else ""
                    st.markdown(
                        f"- **{html.escape(event['created_at'][:16])}** · "
                        f"{html.escape(event['action'])}{detail}"
                    )
            if incident.assignments:
                st.markdown("**Équipes engagées**")
                st.dataframe(pd.DataFrame([
                    {"Unité": row["unit"], "Type": row["type"], "Base": row["district"],
                     "ETA (min)": row["eta_min"]}
                    for row in incident.assignments
                ]), hide_index=True, use_container_width=True)
        else:
            st.info("Aucune plainte ne correspond aux filtres sélectionnés.")

        st.divider()
        st.subheader("📍 Carte des plaintes")
        if filtered:
            render_incident_map(filtered, "complaint_depot_map")
        else:
            st.caption("La carte apparaîtra dès qu'une plainte correspondra aux filtres.")

    tab_complaints, tab_engine, tab_backward, tab_kb = st.tabs(
        ["📥 Plaintes", "🧠 Moteur & agenda", "⚖️ Validation réglementaire", "📚 Base de connaissances"]
    )
    with tab_complaints:
        if auto:
            st.fragment(run_every=f"{every}s")(render_dashboard)()
        else:
            render_dashboard()
    with tab_engine:
        if auto:
            st.fragment(run_every=f"{every}s")(engine_view)()
        else:
            engine_view()
    with tab_backward:
        backward_view()
    with tab_kb:
        knowledge_view()


def engine_view() -> None:
    """Onglet moteur : indicateurs, agenda expliqué, disponibilité des unités et raisonnement pas à pas."""
    kpis = eng.compute_kpis(STATE)
    stat_cards([
        ("📡", str(kpis["active"]), "Incidents actifs", "cyan"),
        ("🚨", f"{kpis['p1_share']:.0f} %", "Part critique (P1)", "red"),
        ("🚓", f"{kpis['availability']:.0f} %", "Unités disponibles", "green"),
        ("👥", f"{kpis['exposed_pop']:,}".replace(",", " "), "Population exposée", "violet"),
    ])
    left, right = st.columns([3, 2])
    with left:
        section_title("⟳", "Agenda du chaînage avant",
                      "Résolution de conflits : 1. criticité → 2. spécificité → 3. récence")
        rows = eng.agenda_rows(STATE)
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.info("Aucun incident actif : l'agenda est vide.")
    with right:
        section_title("🚓", "Disponibilité des unités", "Mise à jour à chaque déploiement")
        st.markdown(unit_bars_html(kpis["by_type"]), unsafe_allow_html=True)
    active = eng.agenda(STATE)
    if active:
        section_title("🧠", "Raisonnement pas à pas", "Choisissez un incident pour voir sa chaîne de déduction")
        chosen = st.selectbox("Incident", [i.id for i in active],
                              format_func=lambda i: fmt_incident(eng.get_incident(STATE, i)),
                              key="engine_trace_incident")
        incident = eng.get_incident(STATE, chosen)
        if incident:
            deduced = eng.derived_actions(incident.trace)
            if deduced:
                st.markdown(chips_html(deduced, "derived"), unsafe_allow_html=True)
            st.markdown(trace_timeline_html(incident.trace), unsafe_allow_html=True)


def backward_view() -> None:
    """Onglet chaînage arrière : choix d'un but et d'une zone, verdict et arbre de preuve."""
    section_title("⟲", "Chaînage arrière — validation réglementaire",
                  "Le moteur part du but et remonte vers les faits qui doivent le justifier")
    c1, c2 = st.columns([3, 2])
    goal = c1.selectbox("But à démontrer", list(eng.BACKWARD_GOALS),
                        format_func=lambda key: eng.BACKWARD_GOALS[key]["label"], key="backward_goal")
    zone = c2.selectbox("Zone", DISTRICTS, key="backward_zone")
    ok, lines = eng.backward_chain(goal, zone, STATE)
    verdict = "AUTORISÉE" if ok else "NON AUTORISÉE"
    st.markdown(
        f'<div class="cv-verdict {"ok" if ok else "ko"}"><b>{"✔" if ok else "✖"} Action {verdict}</b>'
        f'<span>{html.escape(eng.BACKWARD_GOALS[goal]["label"])} · {html.escape(zone)}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(backward_tree_html(lines), unsafe_allow_html=True)
    st.caption("La démonstration est recalculée sur l'état actuel de la ville : déployez ou résolvez des "
               "plaintes puis revenez ici pour voir la conclusion changer.")


def knowledge_view() -> None:
    """Onglet base de connaissances : toutes les règles et les mécanismes de résolution de conflits."""
    section_title("📚", f"Règles métier ({len(eng.RULES)})", "SI fait observé ALORS action prescrite")
    st.dataframe(pd.DataFrame([
        {"ID": r.id, "Fait": f"{r.icon} {r.fact}", "Mots-clés": ", ".join(r.keywords)
         + (" | combinaisons : " + " + ".join("/".join(g) for g in r.all_of) if r.all_of else ""),
         "Action": r.action, "Unités": ", ".join(f"{t} ×{n}" for t, n in r.needs) or "Commission"}
        for r in eng.RULES
    ]), hide_index=True, use_container_width=True)
    section_title("⟳", f"Règles d'inférence ({len(eng.INFERENCE_RULES)})",
                  "Chaînage avant : la conclusion d'une règle peut déclencher une autre règle")
    st.dataframe(pd.DataFrame([
        {"ID": r.id, "SI": " ET ".join(r.conditions), "ALORS": r.conclusion, "Explication": r.explanation}
        for r in eng.INFERENCE_RULES
    ]), hide_index=True, use_container_width=True)
    section_title("⟲", f"Règles du chaînage arrière ({len(eng.BACKWARD_RULES)})", "BUT ⇐ sous-but ET sous-but")
    st.dataframe(pd.DataFrame([
        {"But": eng.GOAL_LABELS.get(goal) or eng.SUBGOAL_LABELS.get(goal, goal),
         "Sous-buts": " ET ".join(eng.GOAL_LABELS.get(s) or eng.SUBGOAL_LABELS.get(s, s) for s in subs)}
        for goal, subs in eng.BACKWARD_RULES.items()
    ]), hide_index=True, use_container_width=True)
    section_title("⚖️", "Mécanismes de résolution de conflits")
    st.markdown(
        '<div class="cv-grid3">'
        '<div class="cv-card"><h4>1 · Choix de la règle métier</h4>Poids lexical → nombre d\'indices → '
        'gravité de la règle → ordre de la base.</div>'
        '<div class="cv-card"><h4>2 · Cycles d\'inférence</h4>Spécificité (nombre de conditions) → ordre '
        'd\'appariement, avec réfraction : une règle ne se déclenche qu\'une fois.</div>'
        '<div class="cv-card"><h4>3 · Agenda des incidents</h4>Criticité (P1→P4) → spécificité '
        '(unités requises + victimes) → récence.</div></div>',
        unsafe_allow_html=True,
    )
