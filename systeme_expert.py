"""Script principal : système expert hybride de gestion de crise Smart City (sujet 3.3).

La classe :class:`SystemeExpertCrise` regroupe le moteur dans une interface orientée objet :

* :meth:`SystemeExpertCrise.signaler` — injecte un fait (chaînage avant déclenché automatiquement) ;
* :meth:`SystemeExpertCrise.chainage_avant` — rejoue les cycles d'inférence d'un incident ;
* :meth:`SystemeExpertCrise.chainage_arriere` — démontre un but réglementaire ;
* :meth:`SystemeExpertCrise.expliquer` / :meth:`SystemeExpertCrise.expliquer_but` — module d'explication.

Le moteur n'utilise que la bibliothèque standard Python ; l'interface Streamlit (``app.py``) est une
couche de démonstration optionnelle. Exécution autonome : ``python systeme_expert.py``.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import engine as eng
from engine import CityState, Incident, InferenceCycle, Match, Recommendation

ProofTrace = List[Tuple[int, Optional[bool], str]]


class SystemeExpertCrise:
    """Système expert hybride : chaînage avant sur le flux d'incidents, chaînage arrière pour la
    validation réglementaire, trois mécanismes de résolution de conflits et module d'explication.

    Attributes:
        etat: base de faits (incidents) et unités d'intervention.
    """

    def __init__(self, etat: Optional[CityState] = None) -> None:
        """Crée le système avec un état fourni ou une ville vide (toutes les unités disponibles)."""
        self.etat: CityState = etat if etat is not None else CityState()

    # ------------------------------------------------------------------ base de connaissances
    @staticmethod
    def taille_base() -> Dict[str, int]:
        """Nombre de règles par famille (métier, inférence, chaînage arrière)."""
        return {"metier": len(eng.RULES), "inference": len(eng.INFERENCE_RULES),
                "arriere": len(eng.BACKWARD_RULES)}

    @staticmethod
    def analyser_texte(texte: str) -> List[Match]:
        """Analyse lexicale : règles candidates classées (poids lexical > nb d'indices > gravité > ordre)."""
        return eng.classify_text(texte)

    # ------------------------------------------------------------------ chaînage avant
    def signaler(self, description: str, zone: str, regle_id: Optional[str] = None, canal: str = "Texte",
                 role: str = "citizen", victimes: Optional[bool] = None,
                 fiabilite: Optional[int] = None) -> Incident:
        """Injecte un incident dans la base de faits ; le chaînage avant s'exécute aussitôt.

        Args:
            description: texte du signalement (2 000 caractères maximum).
            zone: quartier ou zone concernée.
            regle_id: règle métier imposée ; si None, elle est déduite du texte.
            canal: « Texte », « Voix » ou « Image ».
            role: « citizen » ou « admin ».
            victimes: si None, détectées dans le texte.
            fiabilite: fiabilité de la source en %, sinon valeur par défaut du canal.

        Raises:
            ValueError: aucune règle reconnue, ou données invalides (voir ``engine.create_incident``).
        """
        candidats = self.analyser_texte(description) if regle_id is None else None
        if regle_id is None:
            if not candidats:
                raise ValueError("Aucune règle métier ne correspond à cette description.")
            regle_id = candidats[0].rule_id
        if victimes is None:
            victimes = eng.detect_victims(description)
        return eng.create_incident(self.etat, regle_id, zone, description, canal, role, victims=victimes,
                                   reliability=fiabilite, candidates=candidats,
                                   acquisition_note="Analyse lexicale du texte." if candidats else "")

    def chainage_avant(self, incident_id: int) -> Tuple[List[str], List[InferenceCycle]]:
        """Rejoue le chaînage avant d'un incident sur l'état actuel : (base de faits saturée, cycles)."""
        inc = self._incident(incident_id)
        with self.etat.lock:
            return eng.forward_infer(eng.base_facts(self.etat, inc))

    def actions_deduites(self, incident_id: int) -> List[str]:
        """Faits dérivés (conclusions des règles d'inférence) au moment du signalement."""
        return eng.derived_actions(self._incident(incident_id).trace)

    def agenda(self) -> List[Incident]:
        """Incidents actifs triés par résolution de conflits : criticité > spécificité > récence."""
        return eng.agenda(self.etat)

    def recommander(self, incident_id: int) -> Recommendation:
        """Unités recommandées pour un incident (compétence 48 + disponibilité 22 + proximité 30)."""
        inc = self._incident(incident_id)
        return eng.recommend_units(self.etat, inc.rule, inc.district)

    def deployer(self, incident_id: int) -> Optional[Recommendation]:
        """Engage les unités recommandées (décision de l'opérateur)."""
        return eng.deploy_plan(self.etat, incident_id)

    def resoudre(self, incident_id: int) -> bool:
        """Clôt l'incident et libère ses unités."""
        return eng.resolve_incident(self.etat, incident_id)

    # ------------------------------------------------------------------ chaînage arrière
    def chainage_arriere(self, but: str, zone: str) -> Tuple[bool, ProofTrace]:
        """Démontre un but réglementaire dans une zone : (but atteint ?, arbre de preuve).

        Raises:
            KeyError: but inconnu (voir ``engine.GOAL_LABELS``).
        """
        return eng.backward_chain(but, zone, self.etat)

    # ------------------------------------------------------------------ module d'explication
    def expliquer(self, incident_id: int) -> str:
        """Chaîne de déduction d'un incident, étape par étape, en texte."""
        inc = self._incident(incident_id)
        return "\n".join(f"{n}. [{titre}] {texte}" for n, (titre, texte) in enumerate(inc.trace, 1))

    def expliquer_but(self, but: str, zone: str) -> str:
        """Arbre de preuve du chaînage arrière, indenté selon la profondeur."""
        _, trace = self.chainage_arriere(but, zone)
        signe = {True: "[OK]", False: "[KO]", None: "[BUT]"}
        return "\n".join("    " * profondeur + f"{signe[ok]} {texte}" for profondeur, ok, texte in trace)

    # ------------------------------------------------------------------ outils
    def _incident(self, incident_id: int) -> Incident:
        """Retourne l'incident ou lève KeyError s'il n'existe pas."""
        inc = eng.get_incident(self.etat, incident_id)
        if inc is None:
            raise KeyError(f"Incident #{incident_id} inconnu.")
        return inc


def demonstration() -> None:
    """Scénario autonome : signalement, chaînage avant, chaînage arrière avant/après résolution."""
    se = SystemeExpertCrise()
    print("Base de connaissances :", se.taille_base())
    inc = se.signaler("Forte secousse, des murs sont tombés, il y a des blessés", "Katuba")
    print(f"\nIncident #{inc.id} → {inc.rule_id} {inc.rule.fact}, priorité {inc.priority}, score {inc.score}")
    print("\n--- Explication (chaînage avant) ---")
    print(se.expliquer(inc.id))
    print("\n--- Chaînage arrière : levée d'évacuation à Katuba ---")
    print(se.expliquer_but("levee_evacuation", "Katuba"))
    se.deployer(inc.id)
    se.resoudre(inc.id)
    print("\n--- Après résolution du séisme ---")
    print(se.expliquer_but("levee_evacuation", "Katuba"))


if __name__ == "__main__":
    demonstration()
