"""État, ressources et composants d'interface partagés de CIVITAS."""
from __future__ import annotations

from pathlib import Path
import streamlit.components.v1 as components

from io import BytesIO
import html
import math
import os
import sqlite3
from typing import Optional

import folium
from mutagen import File as MutagenFile, MutagenError
import numpy as np
import streamlit as st
from streamlit_folium import st_folium
from PIL import Image, ImageOps

import engine as eng
from repository import ComplaintRepository

# --------------------------------------------------------------------------------------
# CONFIGURATION GÉNÉRALE
# --------------------------------------------------------------------------------------

ADMIN_PIN = os.getenv("CIVITAS_ADMIN_PIN", "1234")   # À CHANGER hors démonstration
DISTRICTS = list(eng.DISTRICTS)
PRIO_ICON = {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🟢"}
NO_SCENARIO = "— Aucun —"
MAX_AUDIO_SIZE_MB = 50
MAX_AUDIO_SIZE_BYTES = MAX_AUDIO_SIZE_MB * 1024 * 1024
AUDIO_SIZE_WARNING_BYTES = int(MAX_AUDIO_SIZE_BYTES * 0.8)
MAX_AUDIO_DURATION_SECONDS = 60
AUDIO_WARNING_SECONDS = 50
MIN_IMAGE_SHARPNESS = 100.0
MAX_IMAGES_PER_REPORT = 10
IMAGE_WARNING_COUNT = 8
MAX_IMAGE_SIZE_MB = 5
MAX_COMPRESSED_REPORT_MB = 20
MAX_DESCRIPTION_CHARS = eng.MAX_DESCRIPTION_CHARS
DESCRIPTION_WARNING_CHARS = 1600
LANGUAGES = {
    "Français": "fr",
    "English": "en",
    "Kiswahili": "sw",
    "Lingála": "ln",
}
TRANSLATIONS = {
    "en": {
        "Alertes actives": "Active alerts",
        "Alertes critiques": "Critical alerts",
        "Équipes mobilisées": "Teams deployed",
        "👥 Espace Population": "👥 Community",
        "📥 Dépôt des plaintes": "📥 Complaint repository",
        "CIVITAS — Espace Population": "CIVITAS — Community",
        "CIVITAS — Dépôt des plaintes": "CIVITAS — Complaint repository",
        "Classez, consultez et suivez les signalements reçus.": "Review, manage, and track incoming reports.",
        "Accès réservé aux opérateurs chargés du traitement des plaintes.": "Access reserved for staff handling complaints.",
        "Signalez un incident et suivez les consignes de sécurité.": "Report an incident and follow safety guidance.",
        "⚠️ Danger immédiat ? Contactez d'abord les services d'urgence locaux. Cette application complète l'appel d'urgence, elle ne le remplace pas.":
            "⚠️ Immediate danger? Contact your local emergency services first. This app complements, but does not replace, an emergency call.",
        "🚨 Signaler": "🚨 Report",
        "📋 Consignes": "📋 Guidance",
        "📍 Alertes & suivi": "📍 Alerts & tracking",
        "✍️ Texte": "✍️ Text",
        "🎙️ Voix": "🎙️ Voice",
        "📷 Image": "📷 Photo",
        "Type d'incident": "Incident type",
        "Quartier / commune": "District / area",
        "Autre zone": "Other area",
        "Ville ou zone": "City or area",
        "Description": "Description",
        "Que se passe-t-il ? Où exactement ? Y a-t-il des blessés ?": "What happened? Where exactly? Is anyone injured?",
        "🚑 Des personnes sont blessées ou en danger immédiat": "🚑 Someone is injured or in immediate danger",
        "🚨 Envoyer l'alerte": "🚨 Send report",
        "Quelle est la situation ?": "What is happening?",
        "Que faire ?": "What to do",
        "Mes signalements": "My reports",
        "Vous n'avez encore envoyé aucun signalement.": "You have not submitted any reports yet.",
        "Bulletin d'alerte public": "Public alert bulletin",
        "Aucune alerte majeure en cours.": "No major alerts at this time.",
        "Photo depuis la galerie": "Choose photos",
        "📸 Prendre une photo avec la caméra": "📸 Take a photo",
        "🔍 Analyser l'image": "🔍 Analyze photos",
        "🎧 Transcrire et analyser": "🎧 Transcribe and analyze",
        "📍 Partager ma position GPS (facultatif)": "📍 Share my GPS location (optional)",
        "🌐 Langue / Language": "🌐 Language",
        "CIVITAS — Espace Administration": "CIVITAS — Administration",
        "Accès réservé aux opérateurs et à la Mairie.": "Access reserved for operators and city officials.",
        "Tableau de bord de crise · Opérateurs & Mairie": "Crisis dashboard · Operators & City Hall",
        "Message vocal d'urgence simulé": "Simulated emergency voice message",
        "…ou enregistrez votre message": "…or record your message",
        "…ou importez un fichier audio": "…or upload an audio file",
        "Caméra": "Camera",
        "Reconnaissance visuelle **simulée** : l'anomalie détectée est proposée, vous confirmez avant envoi.":
            "Visual recognition is **simulated**: a suggested finding is shown for confirmation before sending.",
        "Transcription automatique **simulée** : le message est converti en texte puis injecté dans le moteur.":
            "Automatic transcription is **simulated**: the message is converted to text and passed to the engine.",
        "Je confirme l'envoi de ce message.": "I confirm sending this message.",
        "Je confirme l'envoi de cet audio.": "I confirm sending this audio.",
        "Je confirme l'envoi de cette série de photos.": "I confirm sending this photo set.",
        "Je confirme l'envoi de ce commentaire.": "I confirm sending this comment.",
        "Zones touchées": "Affected areas",
        "Code d'accès opérateur": "Operator access code",
        "🔐 Se connecter": "🔐 Sign in",
        "Code incorrect.": "Incorrect code.",
        "Démonstration : code par défaut « 1234 » (variable d'environnement CIVITAS_ADMIN_PIN).":
            "Demo access code: “1234” (CIVITAS_ADMIN_PIN environment variable).",
        "Votre message approche de la longueur maximale. Vérifiez-le avant l'envoi.":
            "Your message is approaching its maximum length. Review it before sending.",
        "Confirmez que vous souhaitez envoyer ce message.": "Confirm that you want to send this message.",
        "Ajoutez une courte description (5 caractères minimum).":
            "Add a short description (at least 5 characters).",
        "Aucune catégorie reconnue dans la description : choisissez le type d'incident manuellement.":
            "No incident category was detected. Select the incident type manually.",
        "Cette photo semble trop floue. Reprenez-la en tenant le téléphone immobile.":
            "This photo appears blurry. Retake it while holding the phone steady.",
        "Vous approchez du nombre maximal de photos. Vérifiez votre sélection.":
            "You are approaching the photo limit. Review your selection.",
        "Le nombre de photos dépasse la limite autorisée. Retirez-en quelques-unes.":
            "The photo limit has been exceeded. Remove some photos.",
        "Cette zone est hors couverture des équipes de démonstration de Lubumbashi. Contactez directement les services d’urgence locaux.":
            "This area is outside the Lubumbashi demo teams’ coverage. Contact your local emergency services directly.",
        "Données de démonstration": "Demo data",
        "Système expert Smart City": "Smart City expert system",
        "Cette photo ne peut pas être lue. Essayez un autre fichier.":
            "This photo cannot be read. Try another file.",
        "Une photo ne peut pas être lue ou traitée. Essayez un autre fichier.":
            "A photo could not be read or processed. Try another file.",
        "Une photo est trop volumineuse. Choisissez des images plus légères.":
            "A photo is too large. Choose smaller images.",
        "La série de photos est trop volumineuse après compression. Choisissez moins de photos.":
            "The compressed photo set is too large. Choose fewer photos.",
        "Une photo semble trop floue. Reprenez-la en tenant le téléphone immobile.":
            "A photo appears blurry. Retake it while holding the phone steady.",
        "Cet audio dépasse la durée autorisée. Enregistrez un message plus court.":
            "This audio is too long. Record a shorter message.",
        "La durée de cet audio ne peut pas être vérifiée. Essayez un fichier WAV, MP3, M4A ou OGG valide.":
            "The audio duration could not be verified. Try a valid WAV, MP3, M4A, or OGG file.",
        "Cet enregistrement est trop volumineux. Réduisez-le ou choisissez-en un autre.":
            "This recording is too large. Reduce its size or choose another.",
        "Cet audio approche de la durée maximale. Confirmez avant de continuer.":
            "This audio is approaching the maximum duration. Confirm to continue.",
        "Le message approche de la longueur maximale. Vérifiez-le avant l'envoi.":
            "Your message is approaching its maximum length. Review it before sending.",
        "La transcription approche de la longueur maximale. Vérifiez-la avant l'envoi.":
            "The transcript is approaching its maximum length. Review it before sending.",
    },
    "sw": {
        "Alertes actives": "Tahadhari zinazoendelea",
        "Alertes critiques": "Tahadhari za dharura",
        "Équipes mobilisées": "Timu zilizotumwa",
        "👥 Espace Population": "👥 Wananchi",
        "📥 Dépôt des plaintes": "📥 Hifadhi ya malalamiko",
        "CIVITAS — Espace Population": "CIVITAS — Wananchi",
        "CIVITAS — Dépôt des plaintes": "CIVITAS — Hifadhi ya malalamiko",
        "Classez, consultez et suivez les signalements reçus.": "Panga, kagua na ufuatilie taarifa zilizopokelewa.",
        "Accès réservé aux opérateurs chargés du traitement des plaintes.": "Ufikiaji umewekewa waendeshaji wanaoshughulikia malalamiko.",
        "Signalez un incident et suivez les consignes de sécurité.": "Ripoti tukio na ufuate maagizo ya usalama.",
        "⚠️ Danger immédiat ? Contactez d'abord les services d'urgence locaux. Cette application complète l'appel d'urgence, elle ne le remplace pas.":
            "⚠️ Hatari ya haraka? Wasiliana kwanza na huduma za dharura za eneo lako. Programu hii haichukui nafasi ya simu ya dharura.",
        "🚨 Signaler": "🚨 Ripoti",
        "📋 Consignes": "📋 Maelekezo",
        "📍 Alertes & suivi": "📍 Tahadhari na ufuatiliaji",
        "✍️ Texte": "✍️ Maandishi",
        "🎙️ Voix": "🎙️ Sauti",
        "📷 Image": "📷 Picha",
        "Type d'incident": "Aina ya tukio",
        "Quartier / commune": "Mtaa / eneo",
        "Autre zone": "Eneo lingine",
        "Ville ou zone": "Mji au eneo",
        "Description": "Maelezo",
        "Que se passe-t-il ? Où exactement ? Y a-t-il des blessés ?": "Nini kimetokea? Wapi hasa? Kuna waliojeruhiwa?",
        "🚑 Des personnes sont blessées ou en danger immédiat": "🚑 Kuna mtu aliyejeruhiwa au aliye hatarini",
        "🚨 Envoyer l'alerte": "🚨 Tuma ripoti",
        "Quelle est la situation ?": "Hali ikoje?",
        "Que faire ?": "Cha kufanya",
        "Mes signalements": "Ripoti zangu",
        "Vous n'avez encore envoyé aucun signalement.": "Bado hujatuma ripoti yoyote.",
        "Bulletin d'alerte public": "Taarifa za tahadhari",
        "Aucune alerte majeure en cours.": "Hakuna tahadhari kubwa kwa sasa.",
        "Photo depuis la galerie": "Chagua picha",
        "📸 Prendre une photo avec la caméra": "📸 Piga picha",
        "🔍 Analyser l'image": "🔍 Changanua picha",
        "🎧 Transcrire et analyser": "🎧 Andika sauti na uchanganue",
        "📍 Partager ma position GPS (facultatif)": "📍 Shiriki eneo langu la GPS (hiari)",
        "🌐 Langue / Language": "🌐 Lugha / Language",
        "CIVITAS — Espace Administration": "CIVITAS — Utawala",
        "Accès réservé aux opérateurs et à la Mairie.": "Ufikiaji ni wa waendeshaji na viongozi wa jiji pekee.",
        "Tableau de bord de crise · Opérateurs & Mairie": "Dashibodi ya dharura · Waendeshaji na viongozi wa jiji",
        "Message vocal d'urgence simulé": "Ujumbe wa sauti wa dharura wa mfano",
        "…ou enregistrez votre message": "…au rekodi ujumbe wako",
        "…ou importez un fichier audio": "…au pakia faili la sauti",
        "Caméra": "Kamera",
        "Zones touchées": "Maeneo yaliyoathirika",
        "Code d'accès opérateur": "Nambari ya kuingia ya mhudumu",
        "🔐 Se connecter": "🔐 Ingia",
        "Code incorrect.": "Msimbo si sahihi.",
        "Démonstration : code par défaut « 1234 » (variable d'environnement CIVITAS_ADMIN_PIN).":
            "Msimbo wa mfano: “1234” (kigezo cha mazingira CIVITAS_ADMIN_PIN).",
        "Votre message approche de la longueur maximale. Vérifiez-le avant l'envoi.":
            "Ujumbe wako unakaribia urefu wa juu. Ukague kabla ya kutuma.",
        "Je confirme l'envoi de ce message.": "Nathibitisha kutuma ujumbe huu.",
        "Je confirme l'envoi de cet audio.": "Nathibitisha kutuma sauti hii.",
        "Je confirme l'envoi de cette série de photos.": "Nathibitisha kutuma picha hizi.",
        "Je confirme l'envoi de ce commentaire.": "Nathibitisha kutuma maoni haya.",
        "Données de démonstration": "Data ya mfano",
        "Système expert Smart City": "Mfumo wa kitaalamu wa Smart City",
        "Cette photo semble trop floue. Reprenez-la en tenant le téléphone immobile.":
            "Picha hii inaonekana kuwa na ukungu. Piga picha nyingine huku simu ikiwa imetulia.",
        "Une photo semble trop floue. Reprenez-la en tenant le téléphone immobile.":
            "Picha inaonekana kuwa na ukungu. Piga picha nyingine huku simu ikiwa imetulia.",
        "Cet audio dépasse la durée autorisée. Enregistrez un message plus court.":
            "Sauti hii ni ndefu sana. Rekodi ujumbe mfupi zaidi.",
        "Cet audio approche de la durée maximale. Confirmez avant de continuer.":
            "Sauti hii inakaribia muda wa juu. Thibitisha ili kuendelea.",
        "La transcription approche de la longueur maximale. Vérifiez-la avant l'envoi.":
            "Nakala inakaribia urefu wa juu. Ikague kabla ya kutuma.",
    },
    "ln": {
        "Alertes actives": "Bakebisi oyo ezali",
        "Alertes critiques": "Bakebisi ya likama",
        "Équipes mobilisées": "Bituluku oyo etindami",
        "👥 Espace Population": "👥 Bato",
        "📥 Dépôt des plaintes": "📥 Ebombelo ya mabóndeli",
        "CIVITAS — Espace Population": "CIVITAS — Bato",
        "CIVITAS — Dépôt des plaintes": "CIVITAS — Ebombelo ya mabóndeli",
        "Classez, consultez et suivez les signalements reçus.": "Tángola, tala mpe landela bansango oyo ezwami.",
        "Accès réservé aux opérateurs chargés du traitement des plaintes.": "Bokɔti ezali kaka mpo na basali oyo batalelaka mabóndeli.",
        "Signalez un incident et suivez les consignes de sécurité.": "Bóyebisa likambo mpe bólanda malako ya bokengi.",
        "⚠️ Danger immédiat ? Contactez d'abord les services d'urgence locaux. Cette application complète l'appel d'urgence, elle ne le remplace pas.":
            "⚠️ Likama ya mbala moko? Bóbenga liboso lisungi ya mbalakaka ya esika bozali. Application oyo ezwi esika ya telefone ya mbalakaka te.",
        "🚨 Signaler": "🚨 Yebisa likambo",
        "📋 Consignes": "📋 Malako",
        "📍 Alertes & suivi": "📍 Makebisi mpe bolandi",
        "✍️ Texte": "✍️ Makomi",
        "🎙️ Voix": "🎙️ Mongongo",
        "📷 Image": "📷 Foto",
        "Type d'incident": "Lolenge ya likambo",
        "Quartier / commune": "Quartier / etuka",
        "Autre zone": "Etuka mosusu",
        "Ville ou zone": "Engumba to etuka",
        "Description": "Ndimbola",
        "Que se passe-t-il ? Où exactement ? Y a-t-il des blessés ?": "Nini esalemi? Wapi mpenza? Bato bazoki?",
        "🚑 Des personnes sont blessées ou en danger immédiat": "🚑 Moto azoki to azali na likama",
        "🚨 Envoyer l'alerte": "🚨 Tinda likebisi",
        "Quelle est la situation ?": "Likambo nini esalemi?",
        "Que faire ?": "Nini ya kosala",
        "Mes signalements": "Makambo nayebisi",
        "Vous n'avez encore envoyé aucun signalement.": "Naino oyebisi likambo moko te.",
        "Bulletin d'alerte public": "Makebisi mpo na bato nyonso",
        "Aucune alerte majeure en cours.": "Likebisi monene ezali te sikoyo.",
        "Photo depuis la galerie": "Pona bafoto",
        "📸 Prendre une photo avec la caméra": "📸 Bakisa foto",
        "🔍 Analyser l'image": "🔍 Tala bafoto",
        "🎧 Transcrire et analyser": "🎧 Kobongola mongongo mpe kotalela",
        "📍 Partager ma position GPS (facultatif)": "📍 Kokabola esika na ngai ya GPS (na bolingi)",
        "🌐 Langue / Language": "🌐 Monɔkɔ / Language",
        "CIVITAS — Espace Administration": "CIVITAS — Boyangeli",
        "Accès réservé aux opérateurs et à la Mairie.": "Bato oyo basalaka mosala mpe bakonzi ya engumba kaka nde bakoki kokɔta.",
        "Tableau de bord de crise · Opérateurs & Mairie": "Etanda ya mikakatano · Basali mpe bakonzi ya engumba",
        "Message vocal d'urgence simulé": "Nsango ya mongongo ya mbalakaka ya komeka",
        "…ou enregistrez votre message": "…to kokoma mongongo na yo",
        "…ou importez un fichier audio": "…to kotya fisye ya mongongo",
        "Caméra": "Kamɛra",
        "Zones touchées": "Bisika oyo likama ekómeli",
        "Code d'accès opérateur": "Mot ya kokɔta ya mosali",
        "🔐 Se connecter": "🔐 Kokɔta",
        "Code incorrect.": "Mot ezali malamu te.",
        "Démonstration : code par défaut « 1234 » (variable d'environnement CIVITAS_ADMIN_PIN).":
            "Mot ya komeka: “1234” (CIVITAS_ADMIN_PIN environment variable).",
        "Votre message approche de la longueur maximale. Vérifiez-le avant l'envoi.":
            "Nsango na yo ekómi pene na molai oyo epesami. Tala yango liboso ya kotinda.",
        "Je confirme l'envoi de ce message.": "Nandimi kotinda nsango oyo.",
        "Je confirme l'envoi de cet audio.": "Nandimi kotinda mongongo oyo.",
        "Je confirme l'envoi de cette série de photos.": "Nandimi kotinda bafoto oyo.",
        "Je confirme l'envoi de ce commentaire.": "Nandimi kotinda makanisi oyo.",
        "Données de démonstration": "Ba données ya komeka",
        "Système expert Smart City": "Système ya mayele ya Smart City",
        "Cette photo semble trop floue. Reprenez-la en tenant le téléphone immobile.":
            "Foto oyo ezali polele te. Zwa foto mosusu mpe simbá telefone malamu.",
        "Une photo semble trop floue. Reprenez-la en tenant le téléphone immobile.":
            "Foto ezali polele te. Zwa mosusu mpe simbá telefone malamu.",
        "Cet audio dépasse la durée autorisée. Enregistrez un message plus court.":
            "Mongongo oyo eleki ntango. Koma mokuse.",
        "Cet audio approche de la durée maximale. Confirmez avant de continuer.":
            "Mongongo oyo ekómi pene na ntango oyo epesami. Ndimá mpo okoba.",
        "La transcription approche de la longueur maximale. Vérifiez-la avant l'envoi.":
            "Makomi ekómi pene na molai oyo epesami. Tala yango liboso ya kotinda.",
    },
}

DISTRICT_COORDINATES = {
    # Approximate district anchors; exact boundaries are not available in the demo data.
    "Lubumbashi": (-11.6609, 27.4794),
    "Kamalondo": (-11.6790, 27.4850),
    "Kenya": (-11.6720, 27.4650),
    "Katuba": (-11.6920, 27.4590),
    "Kampemba": (-11.6650, 27.5110),
    "Ruashi": (-11.6400, 27.5260),
    "Annexe": (-11.6930, 27.5150),
}


@st.cache_resource
def get_repository() -> ComplaintRepository:
    """Dépôt SQLite partagé par toutes les sessions (mis en cache par Streamlit)."""
    return ComplaintRepository()


REPOSITORY = get_repository()


@st.cache_resource
def get_state() -> eng.CityState:
    """Charge les plaintes persistées dans l'état partagé du moteur."""
    state = eng.CityState()
    _load_persisted_state(state)
    return state


def _load_persisted_state(state: eng.CityState) -> None:
    """Recharge les plaintes en base et réengage les unités des plans déployés."""
    state.incidents = REPOSITORY.list_complaints()
    state._seq = max((incident.seq for incident in state.incidents), default=0)
    state.units = eng.build_units()
    for incident in state.incidents:
        if incident.status == eng.STATUS_DEPLOYED:
            for assignment in incident.assignments:
                unit = next((unit for unit in state.units if unit.id == assignment["unit"]), None)
                if unit:
                    unit.available = False
                    unit.incident_id = incident.id


def restore_state_from_repository() -> None:
    """Resynchronise l'état en mémoire avec la base (après une erreur d'écriture)."""
    with STATE.lock:
        _load_persisted_state(STATE)


STATE = get_state()


def tr(text: str) -> str:
    """Traduit un libellé dans la langue choisie ; le texte français est renvoyé s'il n'y a pas de traduction."""
    language = st.session_state.get("language", "fr")
    return TRANSLATIONS.get(language, {}).get(text, text)


def compress_image(data: bytes) -> bytes:
    """Redresse, réduit à 1600 px maximum et compresse une image en WebP."""
    with Image.open(BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source)
        if image.width * image.height > 30_000_000:
            raise ValueError("Cette image est trop grande pour être traitée.")
        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        elif image.mode == "L":
            image = image.convert("RGB")
        output = BytesIO()
        image.save(output, format="WEBP", quality=78, method=4)
        return output.getvalue()


def audio_duration(data: bytes) -> Optional[float]:
    """Durée d'un fichier audio en secondes, ou None si elle ne peut pas être lue."""
    audio = MutagenFile(BytesIO(data))
    duration = getattr(getattr(audio, "info", None), "length", None)
    return float(duration) if duration is not None else None


def browser_location() -> Optional[tuple[float, float]]:
    """Position GPS partagée par le navigateur, arrondie à 3 décimales, ou None."""
    location = st.session_state.get("citizen_location")
    if not location:
        return None
    latitude, longitude = location
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return round(latitude, 3), round(longitude, 3)


def render_incident_map(incidents: list[eng.Incident], key: str) -> None:
    """Carte des incidents (GPS si partagé, sinon centre indicatif du quartier)."""
    coordinates = []
    for incident in incidents:
        latitude = getattr(incident, "latitude", None)
        longitude = getattr(incident, "longitude", None)
        if latitude is not None and longitude is not None:
            point = (latitude, longitude)
            exact = True
        else:
            point = DISTRICT_COORDINATES.get(incident.district)
            exact = False
        if point is not None:
            coordinates.append((incident, point, exact))

    center = coordinates[-1][1] if coordinates else (-11.6609, 27.4794)
    map_view = folium.Map(location=center, zoom_start=12, tiles="CartoDB dark_matter")
    colors = {"P1": "#ff3b5c", "P2": "#ff8a3d", "P3": "#ffd23f", "P4": "#2ee6a6"}
    for incident, point, exact in coordinates:
        label = f"#{incident.id} · {incident.rule.fact} · {incident.district} · {incident.priority}"
        folium.CircleMarker(
            location=point,
            radius=9 if incident.priority in ("P1", "P2") else 6,
            color=colors[incident.priority],
            fill=True,
            fill_opacity=0.82,
            weight=3,
            tooltip=label,
            popup=f"{html.escape(label)} · {'GPS' if exact else 'centre indicatif'}",
        ).add_to(map_view)
    if len(coordinates) > 1:
        map_view.fit_bounds([point for _, point, _ in coordinates], padding=(24, 24))
    st_folium(map_view, height=420, use_container_width=True, returned_objects=[], key=key)
    unmapped = [incident for incident in incidents
                if getattr(incident, "latitude", None) is None
                and incident.district not in DISTRICT_COORDINATES]
    if unmapped:
        st.caption("Certains signalements hors zone connue n’ont pas de GPS et ne peuvent pas être placés sur la carte.")
    if any(not exact for _, _, exact in coordinates):
        st.caption("Les points sans GPS précis représentent le centre indicatif du quartier.")


ASSET_DIR = Path(__file__).resolve().parent / "assets"


def setup_page() -> None:
    """À appeler au début de CHAQUE exécution du script.

    Streamlit relance app.py à chaque clic, mais Python n'importe ce module qu'une seule fois :
    une injection faite au niveau du module disparaîtrait donc dès le premier clic.
    """
    st.set_page_config(page_title="CIVITAS — Gestion de crise", page_icon="🛡️",
                       layout="wide", initial_sidebar_state="collapsed")
    st.markdown(f"<style>{(ASSET_DIR / 'style.css').read_text(encoding='utf-8')}</style>",
                unsafe_allow_html=True)


# AFFICHAGE ET COMPOSANTS COMMUNS
def rule_label(rid: str) -> str:
    """Libellé « icône + fait » d'une règle."""
    r = eng.RULE_BY_ID[rid]
    return f"{r.icon} {r.fact}"


def badge(prio: str) -> str:
    """Pastille HTML de priorité."""
    return f'<span class="cv-badge {prio.lower()}">{prio} · {eng.PRIORITY_LABEL[prio]}</span>'


def _skyline_svg() -> str:
    """Silhouette de ville générée (déterministe) : immeubles, fenêtres allumées, antennes et liens réseau."""
    import random
    rnd = random.Random(42)  # graine fixée à 42 (consigne de reproductibilité)
    parts = ['<svg class="cv-skyline" viewBox="0 0 1200 150" preserveAspectRatio="none" aria-hidden="true">']
    x, nodes = 0, []
    while x < 1200:
        w = rnd.randint(34, 78)
        h = rnd.randint(40, 135)
        y = 150 - h
        parts.append(f'<rect class="b" x="{x}" y="{y}" width="{w - 4}" height="{h}" rx="2"/>')
        for wy in range(y + 8, 146, 12):
            for wx in range(x + 6, x + w - 10, 10):
                if rnd.random() < 0.28:
                    delay = rnd.uniform(0, 6)
                    parts.append(f'<rect class="w" x="{wx}" y="{wy}" width="4" height="5" '
                                 f'style="animation-delay:{delay:.1f}s"/>')
        if h > 105 and rnd.random() < 0.6:
            cx = x + (w - 4) // 2
            parts.append(f'<line class="ant" x1="{cx}" y1="{y}" x2="{cx}" y2="{y - 16}"/>')
            parts.append(f'<circle class="beacon" cx="{cx}" cy="{y - 17}" r="2.6" '
                         f'style="animation-delay:{rnd.uniform(0, 2):.1f}s"/>')
            nodes.append((cx, y - 17))
        x += w
    for (x1, y1), (x2, y2) in zip(nodes, nodes[1:]):
        parts.append(f'<path class="link" d="M{x1} {y1} Q{(x1 + x2) / 2} {min(y1, y2) - 30} {x2} {y2}"/>')
    parts.append("</svg>")
    return "".join(parts)


SKYLINE_SVG = _skyline_svg()


def hero(title: str, subtitle: str) -> None:
    """Bandeau d'en-tête avec la silhouette de ville et l'horloge."""
    template = (ASSET_DIR / "hero.html").read_text(encoding="utf-8")
    markup = template.replace("{{title}}", html.escape(tr(title)))
    markup = markup.replace("{{subtitle}}", html.escape(tr(subtitle)))
    markup = markup.replace("{{skyline}}", SKYLINE_SVG)
    # Une seule ligne : évite que Markdown interprète l'indentation HTML comme un bloc de code.
    st.markdown(" ".join(line.strip() for line in markup.splitlines()), unsafe_allow_html=True)
    render_live_clock()


def stat_cards(items: list[tuple[str, str, str, str]]) -> None:
    """Tuiles d'indicateurs : (icône, valeur, libellé, accent parmi cyan|red|amber|green|violet)."""
    cells = "".join(
        f'<div class="cv-stat {accent}"><div class="cv-stat-icon">{icon}</div>'
        f'<div><div class="cv-stat-value">{html.escape(str(value))}</div>'
        f'<div class="cv-stat-label">{html.escape(label)}</div></div></div>'
        for icon, value, label, accent in items
    )
    st.markdown(f'<div class="cv-stats">{cells}</div>', unsafe_allow_html=True)


def section_title(icon: str, title: str, subtitle: str = "") -> None:
    """Titre de section avec icône et sous-titre."""
    sub = f'<span>{html.escape(subtitle)}</span>' if subtitle else ""
    st.markdown(f'<div class="cv-section"><b>{icon}</b><div><h3>{html.escape(title)}</h3>{sub}</div></div>',
                unsafe_allow_html=True)


def chips_html(labels: list[str], kind: str = "") -> str:
    """Rangée de puces HTML (actions déduites, étiquettes)."""
    return '<div class="cv-chips-row">' + "".join(
        f'<span class="cv-chip {kind}">{html.escape(label)}</span>' for label in labels) + "</div>"


_TRACE_KIND = {
    "Acquisition": "acq", "Instanciation du fait": "fact", "Filtrage et appariement": "match",
    "Actions déduites": "out", "Résolution de conflit": "conflict", "Sortie tableau de bord": "out", "Sortie Dashboard": "out",
    "Déploiement du plan": "ok", "Résolution": "ok",
}


def trace_timeline_html(trace) -> str:
    """Module d'explication : la chaîne de déduction affichée comme une frise étape par étape."""
    items = []
    for n, (title, text) in enumerate(trace, 1):
        kind = _TRACE_KIND.get(title, "infer" if title.startswith("Chaînage avant") else "fact")
        items.append(f'<li class="{kind}"><span class="cv-step">{n}</span><div><b>{html.escape(title)}</b>'
                     f'<p>{html.escape(text)}</p></div></li>')
    return f'<ol class="cv-timeline">{"".join(items)}</ol>'


def backward_tree_html(lines) -> str:
    """Arbre de preuve du chaînage arrière en HTML."""
    rows = []
    for depth, ok, text in lines:
        state = "ok" if ok is True else "ko" if ok is False else "goal"
        icon = "✔" if ok is True else "✖" if ok is False else "◎"
        rows.append(f'<div class="cv-node {state}" style="--d:{depth}"><i>{icon}</i>'
                    f'<span>{html.escape(text)}</span></div>')
    return f'<div class="cv-tree">{"".join(rows)}</div>'


def unit_bars_html(by_type: dict) -> str:
    """Jauges de disponibilité par type d'unité en HTML."""
    rows = []
    for utype, (available, total) in by_type.items():
        rate = 100 * available / total if total else 0
        level = "ok" if rate >= 60 else "warn" if rate >= 30 else "ko"
        rows.append(f'<div class="cv-bar {level}"><div class="cv-bar-head"><span>{eng.UNIT_ICON[utype]} '
                    f'{html.escape(utype)}</span><b>{available}/{total}</b></div>'
                    f'<div class="cv-bar-track"><div style="width:{rate:.0f}%"></div></div></div>')
    return f'<div class="cv-bars">{"".join(rows)}</div>'


def render_live_clock() -> None:
    """Horloge locale de l'appareil, mise à jour dans le navigateur."""
    template = (ASSET_DIR / "live_clock.html").read_text(encoding="utf-8")
    script = (ASSET_DIR / "live_clock.js").read_text(encoding="utf-8")
    components.html(template.replace("<!-- CIVITAS_CLOCK_SCRIPT -->", f"<script>{script}</script>"),
                    height=34, scrolling=False)

def trace_markdown(lines) -> str:
    """Trace du chaînage arrière en liste Markdown (version texte)."""
    out = []
    for depth, ok, text in lines:
        icon = "✅" if ok is True else "❌" if ok is False else "▪️"
        out.append("  " * depth + f"- {icon} {text}")
    return "\n".join(out)


def fmt_incident(inc: eng.Incident) -> str:
    """Résumé d'un incident sur une ligne."""
    return f"#{inc.id} {PRIO_ICON[inc.priority]} {inc.priority} · {inc.rule.fact} · {inc.district} (score {inc.score})"


# --------------------------------------------------------------------------------------
# VOIES D'ENTRÉE MULTIMODALES (partagées par les deux profils)
# --------------------------------------------------------------------------------------
def _k(p: str, name: str) -> str:
    """Clé de session préfixée."""
    return f"{p}_{name}"


def submit_incident(is_admin: bool, **kw) -> eng.Incident:
    """Crée l'incident dans le moteur puis l'enregistre ; annule la création si l'écriture échoue."""
    attachments = tuple(kw.pop("attachments", ()))
    if not is_admin:
        location = browser_location()
        if location:
            kw["latitude"], kw["longitude"] = location
            kw["acquisition_note"] = (
                f"{kw.get('acquisition_note', '')} Position GPS facultative, arrondie pour protéger la vie privée."
            ).strip()
    inc = eng.create_incident(STATE, role="admin" if is_admin else "citizen", **kw)
    try:
        REPOSITORY.save_complaint(
            inc,
            "Plainte déposée" if not is_admin else "Plainte créée par un opérateur",
            attachments=attachments,
        )
    except (OSError, sqlite3.Error, TypeError, ValueError):
        with STATE.lock:
            STATE.incidents.remove(inc)
            if STATE._seq == inc.seq:
                STATE._seq -= 1
        raise
    st.session_state.setdefault("my_ids", []).append(inc.id)
    st.session_state["flash"] = inc.id
    return inc


def district_picker(label: str, key: str) -> str:
    """Sélecteur de quartier, avec saisie libre pour une autre zone."""
    district = st.selectbox(
        label,
        list(DISTRICTS) + ["Autre zone"],
        key=key,
        format_func=lambda value: tr(value),
    )
    if district == "Autre zone":
        return st.text_input(tr("Ville ou zone"), key=f"{key}_other", max_chars=80).strip()
    return district


def reset_draft(p: str, kind: str) -> None:
    """Réinitialise un brouillon (voix 'v' ou image 'i') et vide les uploaders en changeant leur clé."""
    for name in ("text", "rule", "district", "vict", "rel", "note", "ready", "err", "desc",
                 "name", "names", "media", "scn", "confirm_duration", "confirm_count", "confirm_desc"):
        st.session_state.pop(_k(p, f"{kind}_{name}"), None)
    st.session_state[_k(p, f"{kind}n")] = st.session_state.get(_k(p, f"{kind}n"), 0) + 1


def cb_audio_source_changed(p: str) -> None:
    """Réinitialise l'analyse vocale quand la source audio change."""
    for name in ("ready", "err", "confirm_duration", "confirm_transcript"):
        st.session_state.pop(_k(p, f"v_{name}"), None)


def cb_image_source_changed(p: str) -> None:
    """Réinitialise l'analyse d'image quand les photos changent."""
    for name in ("ready", "err", "names", "media", "confirm_count", "confirm_desc"):
        st.session_state.pop(_k(p, f"i_{name}"), None)


def image_sharpness(data: bytes) -> float:
    """Netteté d'une image : variance du laplacien (faible = floue)."""
    with Image.open(BytesIO(data)) as image:
        if image.width * image.height > 30_000_000:
            raise ValueError("Cette image est trop grande pour être traitée.")
        gray = ImageOps.exif_transpose(image).convert("L")
        gray.thumbnail((512, 512), Image.Resampling.LANCZOS)
        pixels = np.asarray(gray, dtype=np.float32)
    if min(pixels.shape) < 3:
        return 0.0
    laplacian = (
        pixels[:-2, 1:-1] + pixels[2:, 1:-1]
        + pixels[1:-1, :-2] + pixels[1:-1, 2:]
        - 4 * pixels[1:-1, 1:-1]
    )
    return float(np.var(laplacian))


def cb_voice_analyze(p: str) -> None:
    """Vérifie l'audio (taille, durée), le transcrit (simulation) et pré-remplit le formulaire."""
    n = st.session_state.get(_k(p, "vn"), 0)
    src = st.session_state.get(f"{p}_v_mic_{n}") or st.session_state.get(f"{p}_v_up_{n}")
    scn = st.session_state.get(_k(p, "v_scn"))
    scn = None if scn in (None, NO_SCENARIO) else scn
    if src is None and scn is None:
        st.session_state[_k(p, "v_err")] = True
        st.session_state[_k(p, "v_ready")] = False
        return
    if src is not None and src.size > MAX_AUDIO_SIZE_BYTES:
        st.session_state[_k(p, "v_err")] = "Cet enregistrement est trop volumineux. Réduisez-le ou choisissez-en un autre."
        st.session_state[_k(p, "v_ready")] = False
        return
    duration = None
    if src is not None:
        try:
            duration = audio_duration(src.getvalue())
        except (MutagenError, OSError):
            duration = None
        if duration is None:
            st.session_state[_k(p, "v_err")] = "La durée de cet audio ne peut pas être vérifiée. Essayez un fichier WAV, MP3, M4A ou OGG valide."
            st.session_state[_k(p, "v_ready")] = False
            return
        if duration > MAX_AUDIO_DURATION_SECONDS:
            st.session_state[_k(p, "v_err")] = "Cet audio dépasse la durée autorisée. Enregistrez un message plus court."
            st.session_state[_k(p, "v_ready")] = False
            return
        near_audio_limit = duration >= AUDIO_WARNING_SECONDS or src.size >= AUDIO_SIZE_WARNING_BYTES
        if near_audio_limit and not st.session_state.get(_k(p, "v_confirm_duration")):
            st.session_state[_k(p, "v_err")] = "Cochez la confirmation avant d'analyser cet audio."
            st.session_state[_k(p, "v_ready")] = False
            return
    data = src.getvalue() if src is not None else None
    name = getattr(src, "name", "enregistrement.wav") if src is not None else ""
    # --- Point d'extension : remplacer par une vraie transcription (Whisper, Vosk, API STT) ---
    text, rel, note = eng.simulate_transcription(data, name, scn if src is None else None)
    matches = eng.classify_text(text)
    ss = st.session_state
    ss[_k(p, "v_text")] = text
    ss[_k(p, "v_rule")] = matches[0].rule_id if matches else eng.RULES[0].id
    ss[_k(p, "v_district")] = eng.detect_district(text) or DISTRICTS[0]
    ss[_k(p, "v_vict")] = eng.detect_victims(text)
    ss[_k(p, "v_rel")] = rel
    ss[_k(p, "v_note")] = note + ("" if matches else " Aucune catégorie reconnue : choisissez-la manuellement.")
    if duration is not None:
        ss[_k(p, "v_note")] += f" Durée : {math.ceil(duration)} s."
    ss[_k(p, "v_err")] = False
    ss[_k(p, "v_ready")] = True


def cb_image_analyze(p: str) -> None:
    """Vérifie les photos (nombre, taille, netteté), les compresse et propose une catégorie (simulation)."""
    n = st.session_state.get(_k(p, "in"), 0)
    sources = st.session_state.get(f"{p}_i_up_{n}") or []
    camera_source = st.session_state.get(f"{p}_i_cam_{n}")
    if camera_source is not None:
        sources = [camera_source]
        sources.extend(st.session_state.get(f"{p}_i_up_{n}") or [])
    if not sources:
        st.session_state[_k(p, "i_err")] = "Ajoutez d'abord une photo."
        st.session_state[_k(p, "i_ready")] = False
        return
    if len(sources) > MAX_IMAGES_PER_REPORT:
        st.session_state[_k(p, "i_err")] = "Le nombre de photos dépasse la limite autorisée. Retirez-en quelques-unes."
        st.session_state[_k(p, "i_ready")] = False
        return
    if len(sources) >= IMAGE_WARNING_COUNT and not st.session_state.get(_k(p, "i_confirm_count")):
        st.session_state[_k(p, "i_err")] = "Cochez la confirmation avant d'analyser cette série de photos."
        st.session_state[_k(p, "i_ready")] = False
        return
    compressed_images = []
    names = []
    for src in sources:
        data = src.getvalue()
        if src.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            st.session_state[_k(p, "i_err")] = "Une photo est trop volumineuse. Choisissez des images plus légères."
            st.session_state[_k(p, "i_ready")] = False
            return
        name = getattr(src, "name", "photo.jpg") or "photo.jpg"
        try:
            sharpness = image_sharpness(data)
            compressed = compress_image(data)
        except (OSError, ValueError, Image.DecompressionBombError):
            st.session_state[_k(p, "i_err")] = "Une photo ne peut pas être lue ou traitée. Essayez un autre fichier."
            st.session_state[_k(p, "i_ready")] = False
            return
        compressed_images.append(compressed)
        if sum(len(image) for image in compressed_images) > MAX_COMPRESSED_REPORT_MB * 1024 * 1024:
            st.session_state[_k(p, "i_err")] = (
                "La série de photos est trop volumineuse après compression. Choisissez moins de photos."
            )
            st.session_state[_k(p, "i_ready")] = False
            return
        if sharpness < MIN_IMAGE_SHARPNESS:
            st.session_state[_k(p, "i_err")] = (
                "Une photo semble trop floue. Reprenez-la en tenant le téléphone immobile."
            )
            st.session_state[_k(p, "i_ready")] = False
            return
        names.append(name)
    # --- Point d'extension : remplacer par un modèle de vision (CLIP, YOLO, API vision) ---
    rid, conf, expl = eng.analyze_image(names[0], sources[0].getvalue())
    ss = st.session_state
    ss[_k(p, "i_rule")] = rid
    ss[_k(p, "i_rel")] = conf
    ss[_k(p, "i_note")] = f"{expl} {len(names)} photo(s) compressée(s) et conservée(s) temporairement."
    ss[_k(p, "i_names")] = names
    ss[_k(p, "i_media")] = compressed_images
    ss[_k(p, "i_vict")] = False
    ss[_k(p, "i_err")] = False
    ss[_k(p, "i_ready")] = True


def show_flash(is_admin: bool) -> None:
    """Affiche la confirmation du dernier signalement et les consignes de sécurité."""
    iid = st.session_state.pop("flash", None)
    inc = eng.get_incident(STATE, iid) if iid else None
    if not inc:
        return
    if is_admin:
        st.success(f"Incident #{inc.id} enregistré — {inc.rule.fact} ({inc.district}) · {inc.priority} · score {inc.score}")
    else:
        st.success(f"✅ Alerte #{inc.id} transmise aux opérateurs. Merci.")
        st.markdown("**En attendant les secours :**\n" + "\n".join(f"- {c}" for c in inc.rule.consignes))
    if inc.district not in DISTRICTS:
        st.warning(
            "Cette zone est hors couverture des équipes de démonstration de Lubumbashi. "
            "Contactez directement les services d’urgence locaux."
        )




# --------------------------------------------------------------------------------------
# ESPACE POPULATION
# --------------------------------------------------------------------------------------


# --------------------------------------------------------------------------------------
# DÉPÔT DES PLAINTES
# --------------------------------------------------------------------------------------




# --------------------------------------------------------------------------------------
# POINT D'ENTRÉE : bascule de profil
# --------------------------------------------------------------------------------------
