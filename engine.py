"""
engine.py — Orchestration du moteur expert de CIVITAS (Moteur mixte de gestion de crise Smart City)

Contenu :
  1. Référentiel métier (17 règles R1..R17) + 10 règles d'inférence (I1..I10) dans engine_rules.py
  2. Indice de risque multicritère (0..100) et priorités P1..P4
  3. Affectation des unités : compétence (48 pts) + disponibilité (22 pts) + proximité (30 pts)
  4. Chaînage AVANT : faits captés -> règle métier -> cycles d'inférence jusqu'à saturation -> agenda
  5. Chaînage ARRIÈRE : but réglementaire -> sous-buts (récursifs) -> vérification dans la base de faits
  Résolution de conflits (3 mécanismes) :
     a) choix de la règle métier : poids lexical > nombre d'indices > gravité de la règle
     b) cycle d'inférence : spécificité (nb de conditions) > ordre d'appariement, avec réfraction
     c) agenda des incidents : criticité > spécificité > récence
  6. Acquisition multimodale (texte réel ; voix et image SIMULÉES, avec points d'extension)

Ce module est indépendant de Streamlit : il peut être testé seul ou réutilisé avec une autre interface.
Les valeurs par défaut (facteurs, populations, unités) sont des HYPOTHÈSES DE DÉMONSTRATION à calibrer.
"""
from __future__ import annotations

import hashlib
import math
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from engine_rules import (DERIVED_LABELS, INFERENCE_RULES, RULE_BY_ID, RULE_CATEGORY, RULES, InferenceRule,
                          Rule)

# --------------------------------------------------------------------------------------
# 1. CONSTANTES DU MODÈLE DE RISQUE
# --------------------------------------------------------------------------------------
# Score = 0,26 Gravité + 0,18 Exposition + 0,18 Vulnérabilité + 0,12 Tendance
#         + 0,18 Infrastructure + 0,08 Confiance
WEIGHTS: Dict[str, float] = {
    "gravite": 0.26,
    "exposition": 0.18,
    "vulnerabilite": 0.18,
    "tendance": 0.12,
    "infrastructure": 0.18,
    "confiance": 0.08,
}
FACTOR_LABELS: Dict[str, str] = {
    "gravite": "Gravité",
    "exposition": "Exposition",
    "vulnerabilite": "Vulnérabilité",
    "tendance": "Tendance",
    "infrastructure": "Infrastructure",
    "confiance": "Confiance",
}
FACTOR_ORDER = ["gravite", "exposition", "vulnerabilite", "tendance", "infrastructure", "confiance"]

POPULATION_DENSE_THRESHOLD = 270_000         # population au-delà de laquelle une zone est « dense »
THRESHOLDS = {"P1": 72, "P2": 52, "P3": 32}  # P4 : en dessous de 32
CRITICAL_GRAVITY = 90                          # « seuil critique » : gravité >= 90 => P1
PRIORITY_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
MAX_DESCRIPTION_CHARS = 2000
PRIORITY_LABEL = {"P1": "Critique", "P2": "Élevée", "P3": "Modérée", "P4": "Faible"}

STATUS_NEW = "Signalé"
STATUS_DEPLOYED = "Plan déployé"
STATUS_RESOLVED = "Résolu"

# Pondération de l'affectation des unités (total 100)
W_COMPETENCE, W_DISPONIBILITE, W_PROXIMITE = 48, 22, 30

DEFAULT_RELIABILITY = {"Texte": 75, "Voix": 65, "Image": 60}


# --------------------------------------------------------------------------------------
# 3. TERRITOIRE ET UNITÉS (données de démonstration — hypothèses)
# --------------------------------------------------------------------------------------
# district -> (x, y, population indicative). Grille arbitraire : 1 case = 2,5 km.
DISTRICTS: Dict[str, Tuple[int, int, int]] = {
    "Lubumbashi": (5, 5, 280_000),
    "Kamalondo": (4, 6, 260_000),
    "Kenya": (7, 6, 270_000),
    "Katuba": (3, 7, 350_000),
    "Kampemba": (6, 3, 300_000),
    "Ruashi": (8, 2, 230_000),
    "Annexe": (2, 4, 200_000),
}
KM_PER_CELL = 2.5
_MAX_POP = max(d[2] for d in DISTRICTS.values())


def distance_km(d1: str, d2: str) -> float:
    """Distance approximative en km entre deux quartiers de la grille (minimum 0,8 km)."""
    (x1, y1, _), (x2, y2, _) = DISTRICTS[d1], DISTRICTS[d2]
    return max(0.8, math.hypot(x1 - x2, y1 - y2) * KM_PER_CELL)


_DMAX = max(distance_km(a, b) for a in DISTRICTS for b in DISTRICTS)

UNIT_SPECS: Dict[str, List[str]] = {
    "Pompiers": ["Lubumbashi", "Kamalondo", "Kenya", "Ruashi"],
    "Police": ["Lubumbashi", "Kamalondo", "Katuba", "Kenya", "Kampemba", "Annexe"],
    "Santé": ["Lubumbashi", "Katuba", "Kampemba", "Kenya", "Ruashi"],
    "Réseaux": ["Lubumbashi", "Kenya", "Katuba"],
    "Armée": ["Annexe", "Ruashi"],
    "Voirie": ["Lubumbashi", "Kampemba", "Katuba"],
}
UNIT_PREFIX = {"Pompiers": "POM", "Police": "POL", "Santé": "SAN", "Réseaux": "RES", "Armée": "ARM", "Voirie": "VOI"}
UNIT_ICON = {"Pompiers": "🚒", "Police": "🚓", "Santé": "🚑", "Réseaux": "🔧", "Armée": "🪖", "Voirie": "🚧"}
UNIT_SPEED_KMH = {"Pompiers": 45, "Police": 55, "Santé": 50, "Réseaux": 40, "Armée": 35, "Voirie": 30}
MAIN_UNIT_TYPES = ["Pompiers", "Police", "Santé", "Réseaux"]


@dataclass
class Unit:
    """Unité d'intervention (pompiers, police, santé, réseaux, armée, voirie)."""
    id: str
    type: str
    district: str
    skill: float                     # niveau de compétence 0..1
    available: bool = True
    incident_id: Optional[int] = None


def build_units() -> List[Unit]:
    """Crée la flotte d'unités de démonstration, toutes disponibles."""
    skills = [1.0, 0.9, 0.95, 0.85, 1.0]
    units: List[Unit] = []
    for utype, districts in UNIT_SPECS.items():
        for n, d in enumerate(districts, start=1):
            units.append(Unit(f"{UNIT_PREFIX[utype]}-{n:02d}", utype, d, skills[(n - 1) % len(skills)]))
    return units


# --------------------------------------------------------------------------------------
# 4. ÉTAT DE LA VILLE (base de faits dynamique)
# --------------------------------------------------------------------------------------
@dataclass
class Incident:
    """Fait de la base de faits : un incident signalé, avec son score, sa priorité et sa trace."""
    id: int
    rule_id: str
    district: str
    description: str
    channel: str                       # Texte | Voix | Image
    role: str                          # citizen | admin
    victims: bool
    factors: Dict[str, int]
    score: float
    priority: str
    reason: str
    created_at: datetime
    seq: int                           # ordre d'injection (récence)
    status: str = STATUS_NEW
    trace: List[Tuple[str, str]] = field(default_factory=list)
    assignments: List[dict] = field(default_factory=list)
    eta: Optional[int] = None
    transcript: Optional[str] = None
    image_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    resolved_at: Optional[datetime] = None

    @property
    def rule(self) -> Rule:
        """Règle métier associée à l'incident."""
        return RULE_BY_ID[self.rule_id]

    @property
    def active(self) -> bool:
        """Vrai tant que l'incident n'est pas résolu."""
        return self.status != STATUS_RESOLVED


class CityState:
    """Mémoire de travail partagée (faits + unités). Thread-safe via un verrou réentrant."""

    def __init__(self) -> None:
        """Crée un état vide protégé par un verrou réentrant."""
        self.lock = threading.RLock()
        self.reset()

    def reset(self) -> None:
        """Vide la base de faits et remet toutes les unités disponibles."""
        with self.lock:
            self.incidents: List[Incident] = []
            self.units: List[Unit] = build_units()
            self.log: List[str] = []
            self._seq = 0

    def add_log(self, msg: str) -> None:
        """Ajoute une ligne horodatée au journal (200 dernières conservées)."""
        self.log.append(f"{datetime.now():%H:%M:%S} — {msg}")
        self.log = self.log[-200:]


# --------------------------------------------------------------------------------------
# 5. SCORE, PRIORITÉ, AFFECTATION
# --------------------------------------------------------------------------------------
def compute_score(factors: Dict[str, int]) -> float:
    """Score de risque pondéré (0..100) : 0,26 G + 0,18 E + 0,18 V + 0,12 T + 0,18 I + 0,08 C."""
    return round(sum(WEIGHTS[k] * factors[k] for k in WEIGHTS), 1)


def compute_priority(score: float, victims: bool, gravity: int) -> Tuple[str, str]:
    """P1 si victime signalée, seuil critique ou score >= 72 ; P2 >= 52 ; P3 >= 32 ; P4 sinon."""
    if victims:
        return "P1", "victime signalée"
    if gravity >= CRITICAL_GRAVITY:
        return "P1", f"seuil critique de gravité (≥ {CRITICAL_GRAVITY})"
    if score >= THRESHOLDS["P1"]:
        return "P1", f"score ≥ {THRESHOLDS['P1']}"
    if score >= THRESHOLDS["P2"]:
        return "P2", f"score ≥ {THRESHOLDS['P2']}"
    if score >= THRESHOLDS["P3"]:
        return "P3", f"score ≥ {THRESHOLDS['P3']}"
    return "P4", f"score < {THRESHOLDS['P3']}"


def _clamp(v: float, lo: int = 0, hi: int = 100) -> int:
    """Arrondit puis borne une valeur dans l'intervalle [lo, hi]."""
    return int(max(lo, min(hi, round(v))))


def build_factors(state: CityState, rule: Rule, district: str, role: str,
                  channel: str, reliability: Optional[int], overrides: Optional[Dict[str, int]]) -> Dict[str, int]:
    """Calcule les 6 facteurs de risque d'un incident selon la règle, la zone, la source et le contexte.

    L'exposition tient compte de la population, la tendance des incidents similaires actifs,
    la confiance du canal et du rôle (opérateur +10, citoyen -10). Les `overrides` forcent une valeur.
    """
    grav, expo, vuln, tend, infra, _ = rule.factors
    pop = DISTRICTS.get(district, (0, 0, 0))[2]
    same = sum(1 for i in state.incidents if i.active and i.rule_id == rule.id and i.district == district)
    conf = reliability if reliability is not None else DEFAULT_RELIABILITY.get(channel, 65)
    conf += 10 if role == "admin" else -10          # source opérateur plus fiable que signalement anonyme
    f = {
        "gravite": grav,
        "exposition": _clamp(0.7 * expo + 30 * pop / _MAX_POP),
        "vulnerabilite": vuln,
        "tendance": _clamp(tend + 10 * same),        # incidents similaires actifs => dynamique aggravante
        "infrastructure": infra,
        "confiance": _clamp(conf),
    }
    if overrides:
        for k, v in overrides.items():
            if k in f:
                f[k] = _clamp(v)
    return f


@dataclass
class Recommendation:
    """Résultat de l'affectation : unités retenues, déficits par type et temps d'arrivée maximal."""
    rows: List[dict]
    shortfalls: Dict[str, int]
    eta: Optional[int]


def recommend_units(state: CityState, rule: Rule, district: str) -> Recommendation:
    """Affectation : compétence (48) + disponibilité (22) + proximité (30), parmi les unités libres."""
    rows: List[dict] = []
    shortfalls: Dict[str, int] = {}
    if district not in DISTRICTS:
        return Recommendation([], dict(rule.needs), None)
    for utype, count in rule.needs:
        cands = []
        for u in state.units:
            if u.type != utype or not u.available:
                continue
            dist = distance_km(u.district, district)
            comp = W_COMPETENCE * u.skill
            disp = W_DISPONIBILITE
            prox = W_PROXIMITE * (1 - dist / _DMAX)
            eta = round(3 + dist / UNIT_SPEED_KMH[utype] * 60)
            cands.append({"unit": u.id, "type": utype, "district": u.district,
                          "competence": round(comp, 1), "disponibilite": disp, "proximite": round(prox, 1),
                          "total": round(comp + disp + prox, 1), "distance_km": round(dist, 1), "eta_min": eta})
        cands.sort(key=lambda r: -r["total"])
        taken = cands[:count]
        rows.extend(taken)
        if len(taken) < count:
            shortfalls[utype] = count - len(taken)
    eta = max((r["eta_min"] for r in rows), default=None)
    return Recommendation(rows, shortfalls, eta)


# --------------------------------------------------------------------------------------
# 6. CHAÎNAGE AVANT : création de faits, agenda, résolution de conflits
# --------------------------------------------------------------------------------------
def specificity(inc: Incident) -> int:
    """Nombre de conditions spécifiques : compétences requises par la règle (+1 si victime signalée)."""
    return len(inc.rule.needs) + (1 if inc.victims else 0)


def agenda(state: CityState) -> List[Incident]:
    """Résolution de conflits : (1) criticité, (2) spécificité, (3) récence (le plus récent d'abord)."""
    act = [i for i in state.incidents if i.active]
    return sorted(act, key=lambda i: (PRIORITY_RANK[i.priority], -specificity(i), -i.seq))


def sorted_incidents(state: CityState, include_resolved: bool = False) -> List[Incident]:
    """Tri pour le tableau : priorité puis score de risque décroissant."""
    items = [i for i in state.incidents if include_resolved or i.active]
    return sorted(items, key=lambda i: (PRIORITY_RANK[i.priority], -i.score, -i.seq))


def get_incident(state: CityState, incident_id: int) -> Optional[Incident]:
    """Retourne l'incident portant cet identifiant, ou None."""
    return next((i for i in state.incidents if i.id == incident_id), None)


def create_incident(state: CityState, rule_id: str, district: str, description: str, channel: str, role: str,
                    victims: bool = False, reliability: Optional[int] = None, transcript: Optional[str] = None,
                    image_name: Optional[str] = None, overrides: Optional[Dict[str, int]] = None,
                    candidates: Optional[List["Match"]] = None, acquisition_note: str = "",
                    latitude: Optional[float] = None, longitude: Optional[float] = None) -> Incident:
    """Injecte un fait (incident) dans la base de faits et lance le chaînage avant.

    Raises:
        ValueError: zone vide ou trop longue, description trop longue, coordonnées GPS incomplètes ou hors limites.
        KeyError: identifiant de règle inconnu.
    """
    if not district.strip() or len(district) > 80:
        raise ValueError("La zone doit contenir entre 1 et 80 caractères.")
    if len(description) > MAX_DESCRIPTION_CHARS:
        raise ValueError(f"La description ne peut pas dépasser {MAX_DESCRIPTION_CHARS} caractères.")
    if (latitude is None) != (longitude is None):
        raise ValueError("La latitude et la longitude doivent être fournies ensemble.")
    if latitude is not None and longitude is not None:
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("Coordonnées GPS hors limites.")
    rule = RULE_BY_ID[rule_id]
    with state.lock:
        state._seq += 1
        factors = build_factors(state, rule, district, role, channel, reliability, overrides)
        score = compute_score(factors)
        prio, reason = compute_priority(score, victims, factors["gravite"])
        inc = Incident(id=state._seq, rule_id=rule_id, district=district, description=description.strip(),
                       channel=channel, role=role, victims=victims, factors=factors, score=score,
                       priority=prio, reason=reason, created_at=datetime.now(), seq=state._seq,
                       transcript=transcript, image_name=image_name,
                       latitude=latitude, longitude=longitude)
        state.incidents.append(inc)
        rec = recommend_units(state, rule, district)
        inc.trace = _forward_trace(state, inc, rec, candidates, acquisition_note)
        state.add_log(f"#{inc.id} {rule.id} « {rule.fact} » ({district}) → {prio}, score {score}")
    return inc


def base_facts(state: CityState, inc: Incident) -> List[str]:
    """Faits de base de la mémoire de travail pour un incident (ordre stable pour l'explication)."""
    facts = [f"incident:{inc.rule_id}", f"categorie:{RULE_CATEGORY.get(inc.rule_id, 'autre')}",
             f"priorite:{inc.priority}", f"zone:{inc.district}"]
    if inc.victims:
        facts.append("victimes")
    if inc.factors.get("gravite", 0) >= CRITICAL_GRAVITY:
        facts.append("gravite_extreme")
    if DISTRICTS.get(inc.district, (0, 0, 0))[2] >= POPULATION_DENSE_THRESHOLD:
        facts.append("population_dense")
    sante = [u for u in state.units if u.type == "Santé"]
    if sante and sum(u.available for u in sante) / len(sante) < 0.5:
        facts.append("sante_saturee")
    if any(i.active and i.id != inc.id and i.district == inc.district for i in state.incidents):
        facts.append("multi_incidents_zone")
    return facts


@dataclass
class InferenceCycle:
    """Un cycle du chaînage avant : règles déclenchables, règle retenue et raison du choix."""
    number: int
    candidates: List[str]
    chosen: InferenceRule
    reason: str


def forward_infer(facts: List[str]) -> Tuple[List[str], List[InferenceCycle]]:
    """Chaînage avant jusqu'à saturation.

    À chaque cycle : (1) filtrage des règles dont toutes les conditions sont dans la base de faits,
    (2) résolution de conflit — spécificité (plus de conditions d'abord) puis ordre d'appariement,
    (3) déclenchement : la conclusion est ajoutée comme nouveau fait (réfraction : une règle ne se
    redéclenche pas et une règle qui n'apporte aucun fait nouveau est ignorée).
    """
    memory = list(facts)
    known = set(memory)
    fired: set = set()
    cycles: List[InferenceCycle] = []
    while True:
        applicable = [r for r in INFERENCE_RULES
                      if r.id not in fired and r.conclusion not in known and all(c in known for c in r.conditions)]
        if not applicable:
            break
        order = {r.id: n for n, r in enumerate(INFERENCE_RULES)}
        applicable.sort(key=lambda r: (-len(r.conditions), order[r.id]))
        chosen = applicable[0]
        if len(applicable) == 1:
            reason = "seule règle déclenchable"
        elif len(applicable[1].conditions) < len(chosen.conditions):
            reason = f"plus spécifique ({len(chosen.conditions)} conditions)"
        else:
            reason = "même spécificité : ordre d'appariement"
        fired.add(chosen.id)
        known.add(chosen.conclusion)
        memory.append(chosen.conclusion)
        cycles.append(InferenceCycle(len(cycles) + 1, [r.id for r in applicable], chosen, reason))
    return memory, cycles


def derived_actions(trace: List[Tuple[str, str]]) -> List[str]:
    """Actions déduites par le chaînage avant, relues depuis la trace (persistée en base)."""
    for title, text in trace:
        if title == "Actions déduites" and not text.startswith("Aucune"):
            return [part.strip() for part in text.split(" · ") if part.strip()]
    return []


def _forward_trace(state: CityState, inc: Incident, rec: Recommendation,
                   candidates: Optional[List["Match"]], note: str) -> List[Tuple[str, str]]:
    """Construit la trace explicative (module d'explication) du traitement d'un incident."""
    rule = inc.rule
    who = "opérateur" if inc.role == "admin" else "citoyen"
    acq = {"Texte": "Rapport textuel reçu", "Voix": "Appel vocal transcrit (Speech-to-Text)",
           "Image": "Image analysée (reconnaissance visuelle)"}[inc.channel]
    steps = [("Acquisition", f"{acq} — source : {who}, quartier {inc.district}. {note}".strip())]
    facts = base_facts(state, inc)
    steps.append(("Instanciation du fait",
                  f"Ajout du fait normalisé « {rule.fact} » dans la base de faits (confiance {inc.factors['confiance']}/100"
                  f"{', victime signalée' if inc.victims else ''}). Faits de base : {', '.join(facts)}."))
    match_txt = f"Sélection de la règle {rule.id} : {rule.premise} ALORS « {rule.action} »"
    if candidates and len(candidates) > 1:
        others = ", ".join(f"{m.rule_id} (poids {m.weight})" for m in candidates[1:4])
        match_txt += f". Règles concurrentes écartées : {others}."
        tie = tie_note(candidates)
        if tie:
            match_txt += f" {tie}"
    steps.append(("Filtrage et appariement", match_txt))
    _, cycles = forward_infer(facts)
    for c in cycles:
        steps.append((f"Chaînage avant — cycle {c.number}",
                      f"Règles déclenchables : {', '.join(c.candidates)} → {c.chosen.id} retenue ({c.reason}). "
                      f"SI {' ET '.join(c.chosen.conditions)} ALORS {c.chosen.conclusion}. {c.chosen.explanation}"))
    if not cycles:
        steps.append(("Chaînage avant — saturation", "Aucune règle d'inférence déclenchable : pas de fait dérivé."))
    else:
        steps.append(("Chaînage avant — saturation",
                      f"Base de faits saturée après {len(cycles)} cycle(s) : plus aucune règle ne produit de fait nouveau."))
    steps.append(("Actions déduites", " · ".join(DERIVED_LABELS.get(c.chosen.conclusion, c.chosen.conclusion)
                                                for c in cycles) or "Aucune action complémentaire déduite."))
    ag = agenda(state)
    rank = next((n for n, i in enumerate(ag, 1) if i.id == inc.id), len(ag))
    formula = " + ".join(f"{WEIGHTS[k]:.2f}×{inc.factors[k]}" for k in FACTOR_ORDER)
    steps.append(("Résolution de conflit",
                  f"Score = {formula} = {inc.score}. Priorité {inc.priority} ({inc.reason}). "
                  f"Rang {rank}/{len(ag)} dans l'agenda (criticité > spécificité > récence)."))
    if rec.rows:
        units = ", ".join(f"{r['unit']} ({r['district']}, {r['eta_min']} min)" for r in rec.rows)
        short = f" Déficit : {', '.join(f'{k} ×{v}' for k, v in rec.shortfalls.items())}." if rec.shortfalls else ""
        out = f"Unités recommandées : {units}. ETA max : {rec.eta} min.{short}"
    else:
        out = "Aucune unité terrain requise : cellule administrative / commission à mobiliser."
    steps.append(("Sortie tableau de bord", out + " Journalisation complète pour validation par l'opérateur."))
    return steps


def deploy_plan(state: CityState, incident_id: int) -> Optional[Recommendation]:
    """Engage les unités recommandées pour un incident signalé.

    Returns:
        La recommandation appliquée, ou None si l'incident n'existe pas ou n'est plus au statut « Signalé ».
    """
    with state.lock:
        inc = get_incident(state, incident_id)
        if not inc or inc.status != STATUS_NEW:
            return None
        rec = recommend_units(state, inc.rule, inc.district)
        for row in rec.rows:
            unit = next(u for u in state.units if u.id == row["unit"])
            unit.available = False
            unit.incident_id = inc.id
        inc.assignments = rec.rows
        inc.eta = rec.eta
        inc.status = STATUS_DEPLOYED
        inc.trace.append(("Déploiement du plan",
                          f"Plan validé par l'opérateur à {datetime.now():%H:%M:%S} : {len(rec.rows)} unité(s) engagée(s)."))
        state.add_log(f"#{inc.id} plan déployé ({len(rec.rows)} unités, ETA {rec.eta} min)")
        return rec


def resolve_incident(state: CityState, incident_id: int) -> bool:
    """Marque un incident comme résolu et libère ses unités. Retourne False s'il n'est pas actif."""
    with state.lock:
        inc = get_incident(state, incident_id)
        if not inc or not inc.active:
            return False
        for u in state.units:
            if u.incident_id == inc.id:
                u.available, u.incident_id = True, None
        inc.status = STATUS_RESOLVED
        inc.resolved_at = datetime.now()
        inc.trace.append(("Résolution", f"Incident marqué résolu à {inc.resolved_at:%H:%M:%S} ; unités libérées."))
        state.add_log(f"#{inc.id} résolu")
        return True


def toggle_unit(state: CityState, unit_id: str) -> bool:
    """Bascule disponibilité (maintenance / retour). Refusé si l'unité est engagée sur un incident."""
    with state.lock:
        u = next((x for x in state.units if x.id == unit_id), None)
        if not u or u.incident_id is not None:
            return False
        u.available = not u.available
        state.add_log(f"Unité {u.id} {'disponible' if u.available else 'indisponible'}")
        return True


def compute_kpis(state: CityState) -> dict:
    """Indicateurs du tableau de bord : incidents actifs, part P1, disponibilité des unités, population exposée."""
    with state.lock:
        active = [i for i in state.incidents if i.active]
        p1 = [i for i in active if i.priority == "P1"]
        by_type = {}
        for t in UNIT_SPECS:
            us = [u for u in state.units if u.type == t]
            by_type[t] = (sum(u.available for u in us), len(us))
        tot_av = sum(u.available for u in state.units)
        exposed: Dict[str, int] = {}
        for i in active:
            exposed[i.district] = max(exposed.get(i.district, 0), i.factors["exposition"])
        exposed_pop = sum(DISTRICTS.get(d, (0, 0, 0))[2] * e / 100 for d, e in exposed.items())
        return {
            "active": len(active), "p1": len(p1),
            "p1_share": (100 * len(p1) / len(active)) if active else 0.0,
            "availability": 100 * tot_av / len(state.units), "units_available": tot_av, "units_total": len(state.units),
            "by_type": by_type, "exposed_pop": int(exposed_pop), "resolved": len(state.incidents) - len(active),
        }


# --------------------------------------------------------------------------------------
# 7. CHAÎNAGE ARRIÈRE : validation réglementaire d'un but
# --------------------------------------------------------------------------------------
SINISTRE_NATUREL_RULES = {"R1", "R8", "R17"}
RESEAUX_RULES = {"R5", "R13"}
SECURITE_RULES = {"R4", "R6", "R7", "R10", "R11", "R12", "R15"}

# Base de règles du chaînage arrière : BUT <- SOUS-BUT 1 ET SOUS-BUT 2 ...
# Un sous-but présent dans ce dictionnaire est lui-même démontré par d'autres sous-buts (récursivité) ;
# sinon c'est un fait terminal vérifié directement dans la base de faits (incidents + unités).
BACKWARD_RULES: Dict[str, Tuple[str, ...]] = {
    "levee_evacuation": ("sinistre_maitrise", "reseaux_retablis", "perimetre_securise"),
    "levee_quarantaine": ("epidemie_resolue", "structures_sanitaires_ok"),
    "retour_ordre_public": ("aucune_manifestation_active", "perimetre_securise"),
    "reouverture_circulation": ("chaussee_degagee", "perimetre_securise"),
    "sinistre_maitrise": ("aucun_sinistre_naturel_actif", "aucun_incendie_actif"),
    "perimetre_securise": ("incidents_securitaires_pris_en_charge", "forces_ordre_disponibles"),
    "chaussee_degagee": ("aucun_accident_ni_eboulement_actif", "voirie_disponible"),
}
GOAL_LABELS: Dict[str, str] = {
    "levee_evacuation": "Autoriser la levée d'évacuation et le retour des habitants",
    "levee_quarantaine": "Autoriser la levée de la quarantaine",
    "retour_ordre_public": "Déclarer le retour à l'ordre public",
    "reouverture_circulation": "Rouvrir la circulation dans la zone",
}
SUBGOAL_LABELS: Dict[str, str] = {
    "sinistre_maitrise": "sinistre maîtrisé",
    "perimetre_securise": "périmètre sécurisé",
    "chaussee_degagee": "chaussée dégagée",
    "aucun_sinistre_naturel_actif": "aucun sinistre naturel actif",
    "aucun_incendie_actif": "aucun incendie actif",
    "reseaux_retablis": "réseaux rétablis",
    "incidents_securitaires_pris_en_charge": "incidents sécuritaires pris en charge",
    "forces_ordre_disponibles": "forces de l'ordre disponibles",
    "epidemie_resolue": "épidémie résolue dans la zone",
    "structures_sanitaires_ok": "structures sanitaires disponibles (≥ 50 %)",
    "aucune_manifestation_active": "aucune manifestation active",
    "aucun_accident_ni_eboulement_actif": "aucun accident ni éboulement actif",
    "voirie_disponible": "services de voirie disponibles",
}
BACKWARD_GOALS: Dict[str, dict] = {
    key: {"label": label, "subgoals": list(BACKWARD_RULES[key])} for key, label in GOAL_LABELS.items()
}


def _open(state: CityState, district: str, rule_ids: set, only_new: bool = False) -> List[Incident]:
    """Incidents actifs d'une zone appartenant aux règles données (option : seulement ceux sans plan)."""
    return [i for i in state.incidents
            if i.district == district and i.rule_id in rule_ids and i.active
            and (i.status == STATUS_NEW or not only_new)]


def _unit_rate(state: CityState, utype: str) -> Tuple[int, int]:
    """Nombre d'unités disponibles et nombre total pour un type d'unité."""
    us = [u for u in state.units if u.type == utype]
    return sum(u.available for u in us), len(us)


def prove_subgoal(name: str, district: str, state: CityState) -> Tuple[bool, str]:
    """Vérifie un fait terminal dans la base de faits."""
    def fmt(items: List[Incident]) -> str:
        """Liste courte « #id règle » des incidents."""
        return ", ".join(f"#{i.id} {i.rule_id}" for i in items)

    def none_open(rule_ids: set, ok_txt: str, ko_txt: str, only_new: bool = False) -> Tuple[bool, str]:
        """Vrai si aucun incident des règles données n'est ouvert dans la zone, avec l'explication."""
        o = _open(state, district, rule_ids, only_new)
        return (not o, ok_txt if not o else f"{ko_txt} : {fmt(o)}")

    if name == "aucun_sinistre_naturel_actif":
        return none_open(SINISTRE_NATUREL_RULES, "aucun séisme, éruption ou éboulement actif", "sinistre(s) actif(s)")
    if name == "aucun_incendie_actif":
        return none_open({"R2"}, "aucun incendie actif", "incendie(s) actif(s)")
    if name == "reseaux_retablis":
        return none_open(RESEAUX_RULES, "aucune panne/cyberattaque active", "réseau(x) non rétabli(s)")
    if name == "incidents_securitaires_pris_en_charge":
        return none_open(SECURITE_RULES, "chaque incident sécuritaire a un plan déployé ou est résolu",
                         "incident(s) sécuritaire(s) sans plan déployé", only_new=True)
    if name == "epidemie_resolue":
        return none_open({"R3"}, "aucune épidémie active", "épidémie active")
    if name == "aucune_manifestation_active":
        return none_open({"R7"}, "aucune manifestation active", "manifestation active")
    if name == "aucun_accident_ni_eboulement_actif":
        return none_open({"R9", "R17"}, "chaussée libre de tout accident ou éboulement", "obstacle(s) actif(s)")
    if name == "structures_sanitaires_ok":
        av, tot = _unit_rate(state, "Santé")
        rate = 100 * av / tot if tot else 0
        return (rate >= 50, f"disponibilité des unités de santé : {rate:.0f} % ({av}/{tot})")
    if name == "forces_ordre_disponibles":
        av, tot = _unit_rate(state, "Police")
        return (av >= 1, f"{av}/{tot} unité(s) de police disponible(s)")
    if name == "voirie_disponible":
        av, tot = _unit_rate(state, "Voirie")
        return (av >= 1, f"{av}/{tot} unité(s) de voirie disponible(s)")
    return False, "sous-but inconnu"


def _label(goal: str) -> str:
    """Libellé lisible d'un but ou d'un sous-but du chaînage arrière."""
    return GOAL_LABELS.get(goal) or SUBGOAL_LABELS.get(goal, goal)


def _prove(goal: str, district: str, state: CityState, depth: int,
           trace: List[Tuple[int, Optional[bool], str]]) -> bool:
    """Démontre récursivement un but : un but composé exige tous ses sous-buts, un fait terminal est vérifié dans la base."""
    if goal in BACKWARD_RULES:
        idx = len(trace)
        trace.append((depth, None, ""))
        subs = BACKWARD_RULES[goal]
        results = [_prove(sub, district, state, depth + 1, trace) for sub in subs]
        ok = all(results)
        trace[idx] = (depth, ok, f"But « {_label(goal)} » ⇐ SI " + " ET ".join(_label(x) for x in subs)
                      + (" — démontré" if ok else " — non démontré"))
        return ok
    ok, detail = prove_subgoal(goal, district, state)
    trace.append((depth, ok, f"Fait « {_label(goal)} » : {detail}"))
    return ok


def backward_chain(goal_key: str, district: str, state: CityState) -> Tuple[bool, List[Tuple[int, Optional[bool], str]]]:
    """Chaînage arrière récursif : on part du but et on remonte vers les faits qui le justifient."""
    trace: List[Tuple[int, Optional[bool], str]] = [(0, None, f"BUT : {GOAL_LABELS[goal_key]} — zone « {district} »")]
    with state.lock:
        ok = _prove(goal_key, district, state, 1, trace)
    trace.append((0, ok, "CONCLUSION : " + ("tous les sous-buts sont démontrés — action AUTORISÉE."
                                             if ok else "au moins un sous-but n'est pas démontré — action NON autorisée.")))
    return ok, trace


def agenda_rows(state: CityState) -> List[dict]:
    """Agenda expliqué : rang et valeur de chaque critère de résolution de conflit."""
    with state.lock:
        return [{"Rang": n, "N°": i.id, "Règle": f"{i.rule.icon} {i.rule_id} · {i.rule.fact}", "Zone": i.district,
                 "1. Criticité": i.priority, "2. Spécificité": specificity(i), "3. Récence": i.seq,
                 "Score": i.score, "Statut": i.status}
                for n, i in enumerate(agenda(state), 1)]


# --------------------------------------------------------------------------------------
# 8. ACQUISITION MULTIMODALE
# --------------------------------------------------------------------------------------
def normalize(text: str) -> str:
    """Met un texte en minuscules, sans accents ni ponctuation, pour l'analyse lexicale."""
    t = unicodedata.normalize("NFKD", text.lower().replace("’", "'"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9' ]+", " ", t)


@dataclass
class Match:
    """Règle candidate trouvée par l'analyse lexicale, avec son poids et les indices trouvés."""
    rule_id: str
    weight: int
    hits: List[str]


def _kw_pattern(kw: str) -> "re.Pattern[str]":
    """Expression régulière d'un mot-clé : mot entier si court (≤ 4 lettres), préfixe sinon."""
    k = re.escape(normalize(kw).strip())
    return re.compile(r"\b" + k + (r"\b" if len(kw) <= 4 else ""))


_PATTERNS = {r.id: [(kw, _kw_pattern(kw)) for kw in r.keywords] for r in RULES}
_COMBOS = {r.id: [[(kw, _kw_pattern(kw)) for kw in group] for group in r.all_of] for r in RULES}
_RULE_ORDER = {r.id: n for n, r in enumerate(RULES)}


def classify_text(text: str) -> List[Match]:
    """Analyse lexicale : mots-clés -> règles candidates.

    Résolution de conflit entre règles candidates : (1) poids lexical (longueur cumulée des termes),
    (2) nombre d'indices trouvés, (3) gravité de la règle, (4) ordre de la base.
    """
    t = normalize(text)
    out: List[Match] = []
    for rid, pats in _PATTERNS.items():
        hits = [kw for kw, p in pats if p.search(t)]
        groups = _COMBOS[rid]
        if groups:
            found = [next((kw for kw, p in group if p.search(t)), None) for group in groups]
            if all(found):
                hits.append("+".join(found))
        if hits:
            out.append(Match(rid, sum(len(h.replace("+", "")) for h in hits), hits))
    return sorted(out, key=lambda m: (-m.weight, -len(m.hits), -RULE_BY_ID[m.rule_id].factors[0], _RULE_ORDER[m.rule_id]))


def tie_note(candidates: List[Match]) -> str:
    """Explique un départage quand les deux meilleures règles ont le même poids lexical."""
    if len(candidates) < 2 or candidates[0].weight != candidates[1].weight:
        return ""
    a, b = candidates[0], candidates[1]
    if len(a.hits) != len(b.hits):
        why = f"plus d'indices ({len(a.hits)} contre {len(b.hits)})"
    else:
        ga, gb = RULE_BY_ID[a.rule_id].factors[0], RULE_BY_ID[b.rule_id].factors[0]
        why = f"gravité plus élevée ({ga} contre {gb})" if ga != gb else "ordre de la base de règles"
    return f"Égalité de poids lexical entre {a.rule_id} et {b.rule_id} : départagée par {why}."


def detect_district(text: str) -> Optional[str]:
    """Retourne le premier quartier connu cité dans le texte, ou None."""
    t = normalize(text)
    for d in DISTRICTS:
        if normalize(d) in t:
            return d
    return None


_VICTIM_RE = re.compile(
    r"\b(blesse\w*|morts?|victimes?|piege\w*|en danger|a l'interieur|au secours|tuee?s?|decede\w*|deces"
    r"|noye\w*|inconscient\w*|saigne\w*|coince\w*|enseveli\w*)\b")


def detect_victims(text: str) -> bool:
    """Vrai si le texte mentionne des blessés, morts ou personnes en danger (mots entiers)."""
    return bool(_VICTIM_RE.search(normalize(text)))


# --- Voix : transcription SIMULÉE (point d'extension : remplacer par Whisper / Vosk / API STT) ---
VOICE_SCENARIOS: Dict[str, str] = {
    "🔥 Appel — maison en feu": "Allô, au secours ! Il y a un incendie dans une maison à Kamalondo, beaucoup de fumée et des enfants sont à l'intérieur.",
    "🌍 Appel — forte secousse": "Il y a eu une forte secousse à Katuba, un tremblement de terre, des murs sont tombés et il y a des blessés.",
    "💡 Appel — coupure générale": "Depuis ce matin c'est la coupure d'électricité dans tout Kenya, les hôpitaux sont touchés.",
    "🚗 Appel — accident": "Un grave accident de la circulation à Kampemba, une collision entre un camion et un minibus, il y a des blessés.",
    "🦠 Appel — épidémie": "Beaucoup de malades à Annexe avec des symptômes de choléra, l'épidémie se propage vite.",
}


def simulate_transcription(data: Optional[bytes], name: str, scenario: Optional[str]) -> Tuple[str, int, str]:
    """Retourne (transcription, fiabilité %, note). SIMULATION : aucun audio n'est réellement décodé."""
    if scenario and scenario in VOICE_SCENARIOS:
        return VOICE_SCENARIOS[scenario], 80, "Transcription simulée (scénario de démonstration)."
    digest = int(hashlib.sha256((data or b"") + name.encode()).hexdigest(), 16)
    key = list(VOICE_SCENARIOS)[digest % len(VOICE_SCENARIOS)]
    return (VOICE_SCENARIOS[key], 55 + digest % 20,
            "Transcription SIMULÉE (fichier non décodé) — vérifiez et corrigez le texte avant envoi.")


# --- Image : analyse SIMULÉE (point d'extension : remplacer par un modèle de vision CLIP/YOLO) ---
VISUAL_RULES = {
    "R2": "fumées denses et flammes", "R17": "masses de terre/roches sur la voirie",
    "R7": "rassemblement dense de personnes", "R9": "véhicules endommagés sur la chaussée",
    "R12": "présence de silhouettes armées", "R13": "quartier plongé dans le noir",
}


def analyze_image(name: str, data: Optional[bytes]) -> Tuple[str, int, str]:
    """Retourne (rule_id, confiance %, explication). Heuristique sur le nom du fichier, sinon hachage déterministe."""
    m = classify_text(name.rsplit(".", 1)[0].replace("_", " ").replace("-", " "))
    if m and m[0].rule_id in VISUAL_RULES:
        rid = m[0].rule_id
        return rid, 78, f"Anomalie visuelle simulée : {VISUAL_RULES[rid]} (déduite du nom de fichier)."
    digest = int(hashlib.sha256((data or b"") + name.encode()).hexdigest(), 16)
    rid = list(VISUAL_RULES)[digest % len(VISUAL_RULES)]
    return (rid, 45 + digest % 15,
            f"Analyse SIMULÉE : {VISUAL_RULES[rid]} (confiance faible) — confirmez ou corrigez la catégorie.")


# --------------------------------------------------------------------------------------
# 9. JEU DE DONNÉES DE DÉMONSTRATION
# --------------------------------------------------------------------------------------
def seed_demo(state: CityState) -> None:
    """Charge un jeu d'incidents de démonstration dans l'état de la ville."""
    create_incident(state, "R2", "Kamalondo", "Fumées denses et flammes sur une maison, voisins en danger.",
                    "Image", "admin", victims=True, reliability=85, image_name="incendie_maison.jpg")
    create_incident(state, "R13", "Kenya", "Coupure d'électricité généralisée signalée par plusieurs habitants.",
                    "Texte", "citizen", reliability=70)
    create_incident(state, "R7", "Lubumbashi", "Rassemblement de contestation devant l'hôtel de ville.",
                    "Texte", "admin", reliability=80)
    create_incident(state, "R9", "Katuba", "Collision entre un camion et un minibus, blessés légers.",
                    "Voix", "citizen", reliability=65, transcript=VOICE_SCENARIOS["🚗 Appel — accident"])
    create_incident(state, "R16", "Kampemba", "Flambée des prix du maïs sur le marché central.",
                    "Texte", "admin", reliability=75)
