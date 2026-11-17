"""Parcours citoyen : signalement, consignes et suivi public."""
from __future__ import annotations

import html
import mimetypes

import pandas as pd
import streamlit as st
from mutagen import MutagenError
from streamlit_geolocation import streamlit_geolocation

from ui_shared import (
    AUDIO_SIZE_WARNING_BYTES,
    AUDIO_WARNING_SECONDS,
    DESCRIPTION_WARNING_CHARS,
    IMAGE_WARNING_COUNT,
    MAX_AUDIO_DURATION_SECONDS,
    MAX_AUDIO_SIZE_BYTES,
    MAX_AUDIO_SIZE_MB,
    MAX_DESCRIPTION_CHARS,
    MAX_IMAGES_PER_REPORT,
    MAX_IMAGE_SIZE_MB,
    NO_SCENARIO,
    STATE,
    _k,
    audio_duration,
    badge,
    cb_audio_source_changed,
    cb_image_analyze,
    cb_image_source_changed,
    cb_voice_analyze,
    district_picker,
    eng,
    hero,
    render_incident_map,
    reset_draft,
    rule_label,
    show_flash,
    stat_cards,
    submit_incident,
    tr,
)


def report_section(p: str, is_admin: bool) -> None:
    """Affiche les trois voies de signalement (texte, voix, image) et envoie l'incident au moteur.

    Args:
        p: préfixe des clés de session (évite les collisions entre espaces).
        is_admin: True si le signalement vient d'un opérateur.
    """
    show_flash(is_admin)
    t_txt, t_voice, t_img = st.tabs([tr("✍️ Texte"), tr("🎙️ Voix"), tr("📷 Image")])
    rule_opts = [r.id for r in eng.RULES]

    # ---------------- Voie TEXTE ----------------
    with t_txt:
        text_revision = st.session_state.get(_k(p, "textn"), 0)
        cat = st.selectbox(
            tr("Type d'incident"), ["AUTO"] + rule_opts,
            format_func=lambda x: "🔎 Détection automatique (d'après la description)" if x == "AUTO" else rule_label(x),
        )
        district = district_picker(tr("Quartier / commune"), _k(p, "text_district"))
        desc = st.text_area(
            tr("Description"),
            height=120,
            placeholder=tr("Que se passe-t-il ? Où exactement ? Y a-t-il des blessés ?"),
            max_chars=MAX_DESCRIPTION_CHARS,
            key=f"{_k(p, 'text_description')}_{text_revision}",
        )
        text_near_limit = len(desc) >= DESCRIPTION_WARNING_CHARS
        text_confirmed = False
        if text_near_limit:
            st.warning(tr("Votre message approche de la longueur maximale. Vérifiez-le avant l'envoi."))
            text_confirmed = st.checkbox("Je confirme l'envoi de ce message.",
                                         key=f"{_k(p, 'text_confirm')}_{text_revision}")
        victims = st.checkbox(tr("🚑 Des personnes sont blessées ou en danger immédiat"))
        reliability, overrides = None, None
        if is_admin:
            c1, c2 = st.columns(2)
            reliability = c1.slider("Fiabilité de la source (%)", 0, 100, 85)
            force = c2.checkbox("Forcer la gravité")
            grav = c2.slider("Gravité forcée", 0, 100, 70)
            overrides = {"gravite": grav} if force else None
        sent = st.button(tr("🚨 Envoyer l'alerte"), type="primary", key=_k(p, "text_send"))
        if sent:
            matches = eng.classify_text(desc) if cat == "AUTO" else None
            if not district:
                st.error(tr("Indiquez une ville ou une zone pour ce signalement."))
            elif text_near_limit and not text_confirmed:
                st.warning(tr("Confirmez que vous souhaitez envoyer ce message."))
            elif cat == "AUTO" and not matches:
                st.error(tr("Aucune catégorie reconnue dans la description : choisissez le type d'incident manuellement."))
            elif len(desc.strip()) < 5:
                st.error(tr("Ajoutez une courte description (5 caractères minimum)."))
            else:
                rid = matches[0].rule_id if matches else cat
                submit_incident(is_admin, rule_id=rid, district=district, description=desc, channel="Texte",
                                victims=victims, reliability=reliability, overrides=overrides, candidates=matches,
                                acquisition_note="Analyse lexicale du texte." if matches else "Catégorie choisie manuellement.")
                st.session_state[_k(p, "textn")] = text_revision + 1
                st.rerun()

    # ---------------- Voie VOIX ----------------
    with t_voice:
        st.caption(tr("Transcription automatique **simulée** : le message est converti en texte puis injecté dans le moteur."))
        n = st.session_state.get(_k(p, "vn"), 0)
        st.selectbox(tr("Message vocal d'urgence simulé"), [NO_SCENARIO] + list(eng.VOICE_SCENARIOS), key=_k(p, "v_scn"))
        if hasattr(st, "audio_input"):
            st.audio_input(
                tr("…ou enregistrez votre message"),
                key=f"{p}_v_mic_{n}",
                on_change=cb_audio_source_changed,
                args=(p,),
            )
        st.file_uploader(tr("…ou importez un fichier audio"), type=["wav", "mp3", "m4a", "ogg"],
                         key=f"{p}_v_up_{n}", max_upload_size=MAX_AUDIO_SIZE_MB,
                         on_change=cb_audio_source_changed, args=(p,))
        audio_src = (st.session_state.get(f"{p}_v_mic_{n}")
                     or st.session_state.get(f"{p}_v_up_{n}"))
        audio_error = None
        duration = None
        if audio_src is not None:
            if audio_src.size > MAX_AUDIO_SIZE_BYTES:
                audio_error = "Cet enregistrement est trop volumineux. Réduisez-le ou choisissez-en un autre."
            else:
                try:
                    duration = audio_duration(audio_src.getvalue())
                except (MutagenError, OSError):
                    audio_error = "La durée de cet audio ne peut pas être vérifiée. Essayez un fichier valide."
                if duration is None and audio_error is None:
                    audio_error = "La durée de cet audio ne peut pas être vérifiée. Essayez un fichier valide."
                elif duration is not None and duration > MAX_AUDIO_DURATION_SECONDS:
                    audio_error = "Cet audio dépasse la durée autorisée. Enregistrez un message plus court."
        audio_near_limit = (
            (duration is not None and duration >= AUDIO_WARNING_SECONDS)
            or (audio_src is not None and audio_src.size >= AUDIO_SIZE_WARNING_BYTES)
        )
        audio_confirmed = True
        if audio_near_limit and not audio_error:
            st.warning(tr("Cet audio approche de la durée maximale. Confirmez avant de continuer."))
            audio_confirmed = st.checkbox(tr("Je confirme l'envoi de cet audio."), key=_k(p, "v_confirm_duration"))
        if audio_error:
            st.warning(tr(audio_error))
        st.button(
            tr("🎧 Transcrire et analyser"),
            key=_k(p, "v_go"),
            on_click=cb_voice_analyze,
            args=(p,),
            disabled=bool(audio_error) or not audio_confirmed,
        )
        if st.session_state.get(_k(p, "v_err")):
            error = st.session_state[_k(p, "v_err")]
            st.warning(tr(error) if isinstance(error, str) else "Choisissez un scénario, enregistrez ou importez un audio.")
        if st.session_state.get(_k(p, "v_ready")) and not audio_error:
            st.info(f"{st.session_state[_k(p, 'v_note')]} Fiabilité estimée : {st.session_state[_k(p, 'v_rel')]} %")
            transcript = st.text_area("Transcription (modifiable)", key=_k(p, "v_text"),
                                      height=110, max_chars=MAX_DESCRIPTION_CHARS)
            transcript_confirmed = True
            if len(transcript) >= DESCRIPTION_WARNING_CHARS:
                st.warning(tr("La transcription approche de la longueur maximale. Vérifiez-la avant l'envoi."))
                transcript_confirmed = st.checkbox(
                    tr("Je confirme l'envoi de ce message."),
                    key=_k(p, "v_confirm_transcript"),
                )
            c1, c2 = st.columns(2)
            c1.selectbox("Catégorie détectée", rule_opts, key=_k(p, "v_rule"), format_func=rule_label)
            with c2:
                voice_district = district_picker(tr("Quartier / commune"), _k(p, "v_district"))
            st.checkbox(tr("🚑 Des personnes sont blessées ou en danger immédiat"), key=_k(p, "v_vict"))
            if st.button("🚨 Envoyer l'alerte vocale", type="primary", key=_k(p, "v_send"),
                         disabled=not transcript_confirmed or bool(audio_error)):
                ss = st.session_state
                if not voice_district:
                    st.error(tr("Indiquez une ville ou une zone pour ce signalement."))
                else:
                    audio_src = (
                        ss.get(f"{p}_v_mic_{n}")
                        or ss.get(f"{p}_v_up_{n}")
                    )
                    attachments = ()
                    if audio_src is not None:
                        audio_name = getattr(audio_src, "name", None) or "message-vocal.wav"
                        attachments = ((
                            audio_name,
                            getattr(audio_src, "type", None)
                            or mimetypes.guess_type(audio_name)[0]
                            or "audio/wav",
                            audio_src.getvalue(),
                        ),)
                    submit_incident(is_admin, rule_id=ss[_k(p, "v_rule")], district=voice_district,
                                    description=ss[_k(p, "v_text")], channel="Voix", victims=ss[_k(p, "v_vict")],
                                    reliability=ss[_k(p, "v_rel")], transcript=ss[_k(p, "v_text")],
                                    acquisition_note="Transcription simulée.", attachments=attachments)
                    reset_draft(p, "v")
                    st.rerun()

    # ---------------- Voie IMAGE ----------------
    with t_img:
        st.caption(tr("Reconnaissance visuelle **simulée** : l'anomalie détectée est proposée, vous confirmez avant envoi."))
        n = st.session_state.get(_k(p, "in"), 0)
        uploaded_images = st.file_uploader(
            tr("Photo depuis la galerie"),
            type=["png", "jpg", "jpeg", "webp"],
            key=f"{p}_i_up_{n}",
            accept_multiple_files=True,
            max_upload_size=MAX_IMAGE_SIZE_MB,
            on_change=cb_image_source_changed,
            args=(p,),
        )
        with st.expander(tr("📸 Prendre une photo avec la caméra")):
            st.camera_input(
                tr("Caméra"), key=f"{p}_i_cam_{n}", label_visibility="collapsed",
                on_change=cb_image_source_changed, args=(p,), resolution="720p",
            )
        camera_image = st.session_state.get(f"{p}_i_cam_{n}")
        image_count = len(uploaded_images or []) or int(camera_image is not None)
        if uploaded_images and camera_image is not None:
            image_count += 1
        image_confirmed = True
        if image_count >= IMAGE_WARNING_COUNT:
            st.warning(tr("Vous approchez du nombre maximal de photos. Vérifiez votre sélection."))
            image_confirmed = st.checkbox(tr("Je confirme l'envoi de cette série de photos."),
                                          key=_k(p, "i_confirm_count"))
        if image_count > MAX_IMAGES_PER_REPORT:
            st.warning(tr("Le nombre de photos dépasse la limite autorisée. Retirez-en quelques-unes."))
        st.button(
            tr("🔍 Analyser l'image"),
            key=_k(p, "i_go"),
            on_click=cb_image_analyze,
            args=(p,),
            disabled=image_count > MAX_IMAGES_PER_REPORT or not image_confirmed,
        )
        if st.session_state.get(_k(p, "i_err")):
            error = st.session_state[_k(p, "i_err")]
            st.warning(tr(error) if isinstance(error, str) else "Ajoutez d'abord une photo.")
        if st.session_state.get(_k(p, "i_ready")):
            media = st.session_state.get(_k(p, "i_media"), [])
            if media:
                cols = st.columns(min(5, len(media)))
                for index, image in enumerate(media):
                    cols[index % len(cols)].image(image, caption=f"{index + 1}")
            st.info(f"{st.session_state[_k(p, 'i_note')]} Confiance : {st.session_state[_k(p, 'i_rel')]} %")
            c1, c2 = st.columns(2)
            c1.selectbox("Catégorie détectée", rule_opts, key=_k(p, "i_rule"), format_func=rule_label)
            with c2:
                image_district = district_picker(tr("Quartier / commune"), _k(p, "i_district"))
            image_description = st.text_area(
                "Commentaire (optionnel)", key=_k(p, "i_desc"), height=80, max_chars=MAX_DESCRIPTION_CHARS
            )
            desc_confirmed = True
            if len(image_description) >= DESCRIPTION_WARNING_CHARS:
                st.warning(tr("Votre message approche de la longueur maximale. Vérifiez-le avant l'envoi."))
                desc_confirmed = st.checkbox(tr("Je confirme l'envoi de ce commentaire."), key=_k(p, "i_confirm_desc"))
            st.checkbox(tr("🚑 Des personnes sont blessées ou en danger immédiat"), key=_k(p, "i_vict"))
            if st.button("🚨 Envoyer l'alerte image", type="primary", key=_k(p, "i_send")):
                ss = st.session_state
                desc = (ss.get(_k(p, "i_desc")) or "").strip() or ss[_k(p, "i_note")]
                if not image_district:
                    st.error(tr("Indiquez une ville ou une zone pour ce signalement."))
                elif not desc_confirmed:
                    st.warning(tr("Confirmez que vous souhaitez envoyer ce commentaire."))
                else:
                    inc = submit_incident(
                        is_admin,
                        rule_id=ss[_k(p, "i_rule")],
                        district=image_district,
                        description=desc,
                        channel="Image",
                        victims=ss[_k(p, "i_vict")],
                        reliability=ss[_k(p, "i_rel")],
                        image_name=", ".join(ss[_k(p, "i_names")]),
                        acquisition_note="Analyse visuelle simulée.",
                        attachments=tuple(
                            (filename, "image/webp", image_data)
                            for filename, image_data in zip(
                                ss[_k(p, "i_names")], ss[_k(p, "i_media")]
                            )
                        ),
                    )
                    reset_draft(p, "i")
                    st.rerun()

def citizen_space() -> None:
    """Espace Population : avertissement, indicateurs, signalement, consignes et suivi des alertes."""
    hero("CIVITAS — Espace Population", "Signalez un incident et suivez les consignes de sécurité.")
    safety_notice = tr(
        "⚠️ Danger immédiat ? Contactez d'abord les services d'urgence locaux. "
        "Cette application complète l'appel d'urgence, elle ne le remplace pas."
    )
    st.markdown(f'<div class="cv-alert">{html.escape(safety_notice)}</div>', unsafe_allow_html=True)
    live = eng.sorted_incidents(STATE)
    stat_cards([
        ("📡", str(len(live)), tr("Alertes actives"), "cyan"),
        ("🚨", str(sum(i.priority == "P1" for i in live)), tr("Alertes critiques"), "red"),
        ("📍", str(len({i.district for i in live})), tr("Zones touchées"), "amber"),
        ("🚑", str(sum(len(i.assignments) for i in live)), tr("Équipes mobilisées"), "green"),
    ])
    share_location = st.checkbox(tr("📍 Partager ma position GPS (facultatif)"), key="share_gps")
    if share_location:
        location = streamlit_geolocation()
        latitude = location.get("latitude") if isinstance(location, dict) else None
        longitude = location.get("longitude") if isinstance(location, dict) else None
        if latitude is not None and longitude is not None:
            st.session_state["citizen_location"] = (float(latitude), float(longitude))
            st.success("Position reçue. Elle sera arrondie avant d’être ajoutée au signalement.")
        else:
            st.info("Autorisez la localisation dans votre navigateur pour joindre votre position.")
    else:
        st.session_state.pop("citizen_location", None)
    t1, t2, t3 = st.tabs([tr("🚨 Signaler"), tr("📋 Consignes"), tr("📍 Alertes & suivi")])

    with t1:
        report_section("cit", is_admin=False)

    with t2:
        rid = st.selectbox(tr("Quelle est la situation ?"), [r.id for r in eng.RULES], format_func=rule_label)
        r = eng.RULE_BY_ID[rid]
        steps = "".join(f'<li><span>{n}</span>{html.escape(c)}</li>' for n, c in enumerate(r.consignes, 1))
        st.markdown(
            f'<div class="cv-card"><h4>{r.icon} {html.escape(r.fact)}</h4>'
            f'<p class="cv-muted">{html.escape(tr("Que faire ?"))}</p><ol class="cv-steps">{steps}</ol>'
            f'<p class="cv-muted">🏛️ Les autorités interviendront : {html.escape(r.action)}</p></div>',
            unsafe_allow_html=True,
        )

    with t3:
        st.subheader(tr("Mes signalements"))
        mine = [eng.get_incident(STATE, i) for i in st.session_state.get("my_ids", [])]
        mine = [i for i in mine if i]
        if mine:
            st.dataframe(pd.DataFrame([{"N°": i.id, "Type": i.rule.fact, "Quartier": i.district,
                                        "Heure": i.created_at.strftime("%H:%M"), "Statut": i.status} for i in mine]),
                         hide_index=True)
        else:
            st.caption(tr("Vous n'avez encore envoyé aucun signalement."))
        st.subheader(tr("Bulletin d'alerte public"))
        pub = [i for i in eng.sorted_incidents(STATE) if i.priority in ("P1", "P2")]
        if not pub:
            st.success(tr("Aucune alerte majeure en cours."))
        for i in pub:
            st.markdown(f'<div class="cv-card">{badge(i.priority)}<b>{i.rule.icon} {html.escape(i.rule.fact)}</b> — '
                        f'{html.escape(i.district)} <span class="cv-muted">({i.status})</span><br>'
                        f'<span class="cv-muted">Consigne : {html.escape(i.rule.consignes[0])}</span></div>',
                        unsafe_allow_html=True)
        if pub:
            render_incident_map(pub, "citizen_alert_map")
