"""Catalogue des règles métier et index de recherche de CIVITAS."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

# 2. BASE DE CONNAISSANCES : 17 RÈGLES MÉTIER (R1..R17)
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Rule:
    """Règle métier : SI fait observé ALORS action prescrite, avec ses mots-clés, unités et facteurs de risque."""
    id: str
    fact: str                              # fait déclencheur (base de faits normalisée)
    icon: str
    keywords: Tuple[str, ...]              # lexique pour l'analyse lexicale (voie texte/voix)
    action: str                            # action prescrite (base de connaissances)
    steps: Tuple[str, ...]                 # étapes d'intervention
    needs: Tuple[Tuple[str, int], ...]     # compétences requises (type d'unité, nombre)
    factors: Tuple[int, int, int, int, int, int]  # gravité, exposition, vulnérabilité, tendance, infra, confiance
    consignes: Tuple[str, ...]             # consignes de sécurité pour la population
    all_of: Tuple[Tuple[str, ...], ...] = ()  # indices combinés : un mot de CHAQUE groupe doit être présent

    @property
    def premise(self) -> str:
        """Prémisse lisible de la règle, utilisée dans l'explication."""
        return f"SI fait = « {self.fact} »"


def _r(id_, fact, icon, kw, action, steps, needs, factors, consignes, all_of=()) -> Rule:
    """Fabrique une règle métier à partir de listes simples (raccourci d'écriture du catalogue)."""
    return Rule(id_, fact, icon, tuple(kw), action, tuple(steps), tuple(needs), tuple(factors), tuple(consignes),
                tuple(tuple(group) for group in all_of))


RULES: List[Rule] = [
    _r("R1", "Éruption volcanique", "🌋", ["eruption", "volcan", "lave", "cendres volcaniques"],
       "Enclencher le processus d'évacuation de la population vers un lieu sûr et sécuriser la zone éruptive.",
       ["Déclencher l'alerte et l'évacuation vers les sites sûrs", "Sécuriser le périmètre de la zone éruptive",
        "Ouvrir les centres d'accueil et assurer la prise en charge médicale"],
       [("Police", 2), ("Santé", 1), ("Armée", 1)], (95, 85, 80, 70, 75, 70),
       ["Quittez la zone sans attendre, par les itinéraires indiqués.", "Protégez-vous le nez et la bouche des cendres.",
        "Rejoignez le centre d'accueil le plus proche."]),
    _r("R2", "Incendie (maison ou véhicule)", "🔥", ["incendie", "feu", "brule", "flamme", "fumee"],
       "Faire appel aux autorités compétentes (sapeurs-pompiers) pour maîtriser le feu et protéger les riverains.",
       ["Alerter et dépêcher les sapeurs-pompiers", "Évacuer et protéger les riverains",
        "Prendre en charge les blessés ou intoxiqués"],
       [("Pompiers", 2), ("Santé", 1)], (80, 60, 65, 75, 50, 70),
       ["Sortez immédiatement et éloignez-vous du bâtiment ou du véhicule.", "Ne retournez jamais à l'intérieur.",
        "Dégagez l'accès pour les pompiers."]),
    _r("R3", "Épidémie", "🦠", ["epidemie", "cholera", "ebola", "contagion", "contagieux", "malades", "quarantaine"],
       "Effectuer une mise en quarantaine de la zone touchée et dépêcher les autorités ainsi que les structures sanitaires affiliées.",
       ["Mettre la zone touchée en quarantaine", "Dépêcher les autorités et les structures sanitaires affiliées",
        "Diffuser les consignes d'hygiène à la population"],
       [("Santé", 2), ("Police", 1)], (85, 80, 85, 75, 55, 65),
       ["Restez chez vous si vous présentez des symptômes.", "Lavez-vous les mains au savon, buvez de l'eau traitée.",
        "Signalez les cas suspects au centre de santé."]),
    _r("R4", "Cambriolage d'une banque", "🏦", ["cambriolage", "cambrioleurs", "braquage", "hold up", "banque", "vol a main armee"],
       "Faire intervenir la police pour stabiliser le périmètre et appréhender les suspects.",
       ["Boucler le périmètre de l'agence", "Appréhender les suspects", "Recueillir les témoignages et sécuriser les preuves"],
       [("Police", 2)], (60, 40, 40, 45, 40, 70),
       ["Éloignez-vous de la zone.", "Ne vous approchez pas des suspects.", "Gardez vos témoignages pour la police."]),
    _r("R5", "Cyberattaque", "💻", ["cyberattaque", "piratage", "pirate", "hacker", "ransomware", "rancongiciel", "virus informatique", "fausse information"],
       "Déclencher le protocole d'isolement de l'information, supprimer les sources problématiques et sensibiliser la population sur le vrai du faux.",
       ["Isoler les systèmes d'information touchés", "Supprimer les sources problématiques",
        "Sensibiliser la population sur le vrai du faux"],
       [("Réseaux", 2), ("Police", 1)], (65, 70, 50, 65, 85, 60),
       ["Ne partagez pas les informations non vérifiées.", "Ne cliquez pas sur les liens suspects.",
        "Suivez uniquement les canaux officiels."]),
    _r("R6", "Évasion (animaux ou personnes)", "🏃", ["evasion", "evade", "fuyard", "prisonnier", "animal echappe", "echappe"],
       "Faire intervenir la police ou les services spécialisés pour capturer les fuyards et rassurer la population.",
       ["Quadriller le secteur de fuite", "Capturer les fuyards (police ou services spécialisés)",
        "Rassurer la population par un communiqué"],
       [("Police", 2)], (60, 50, 45, 50, 30, 65),
       ["Verrouillez portes et fenêtres.", "N'approchez pas les fuyards.", "Signalez toute observation à la police."]),
    _r("R7", "Manifestation / Contestation", "📢", ["manifestation", "manifestants", "contestation", "protestation", "emeute", "greve"],
       "Dépêcher les forces de l'ordre pour maintenir la situation sous contrôle et préserver un climat de paix.",
       ["Déployer les forces de l'ordre", "Maintenir la situation sous contrôle",
        "Ouvrir un canal de dialogue pour préserver la paix"],
       [("Police", 2)], (55, 55, 45, 60, 35, 70),
       ["Évitez le secteur concerné.", "Restez calme et ne participez pas aux affrontements.", "Suivez les consignes des forces de l'ordre."]),
    _r("R8", "Séisme", "🌍", ["seisme", "tremblement", "secousse"],
       "Activer les protocoles d'urgence sismique, évaluer les dégâts structurels et déployer les équipes de secours.",
       ["Activer les protocoles d'urgence sismique", "Évaluer les dégâts structurels",
        "Déployer les équipes de secours et d'hébergement"],
       [("Pompiers", 2), ("Santé", 2), ("Voirie", 1)], (90, 85, 80, 65, 85, 70),
       ["Abritez-vous sous un meuble solide, loin des vitres.", "Après la secousse, sortez avec prudence.",
        "N'entrez pas dans un bâtiment endommagé."]),
    _r("R9", "Accident de la circulation", "🚗", ["accident", "collision", "carambolage", "percute"],
       "Faire intervenir la police de la circulation routière et dépêcher les secours médicaux d'urgence.",
       ["Sécuriser la zone et réguler la circulation", "Dépêcher les secours médicaux d'urgence",
        "Dégager la chaussée et établir le constat"],
       [("Police", 1), ("Santé", 1)], (65, 35, 40, 40, 35, 75),
       ["Signalez votre position précise.", "Ne déplacez pas les blessés sans nécessité.", "Dégagez la voie pour les secours."]),
    _r("R10", "Attentat (politique ou civil)", "💥", ["attentat", "explosion", "bombe", "kamikaze", "attaque terroriste"],
       "Ouvrir une enquête pour identifier les suspects, sécuriser la zone et prendre en charge les blessés.",
       ["Sécuriser la zone et établir un périmètre", "Prendre en charge les blessés",
        "Ouvrir une enquête pour identifier les suspects"],
       [("Police", 2), ("Santé", 2), ("Armée", 1)], (95, 80, 75, 70, 65, 60),
       ["Éloignez-vous immédiatement de la zone.", "N'approchez pas d'objets suspects.", "Libérez les accès pour les secours."]),
    _r("R11", "Kidnapping", "🚨", ["kidnapping", "enlevement", "enleve", "rapt", "otage", "disparu"],
       "Mobiliser les autorités compétentes dès le signalement pour enquêter et retrouver la personne disparue.",
       ["Enregistrer le signalement et mobiliser les autorités", "Lancer les recherches",
        "Mener l'enquête pour retrouver la personne"],
       [("Police", 2)], (75, 35, 70, 60, 20, 60),
       ["Signalez sans délai : description, lieu, heure.", "Ne négociez pas seul avec les ravisseurs.", "Conservez tout indice."]),
    _r("R12", "Infiltration de forces ennemies", "🪖", ["infiltration", "ennemi", "ennemis", "rebelles", "incursion", "guerre"],
       "Enclencher l'évacuation de la population civile et dépêcher les forces armées pour défendre le territoire.",
       ["Évacuer la population civile", "Dépêcher les forces armées", "Défendre le territoire et verrouiller les accès"],
       [("Armée", 2), ("Police", 1)], (95, 85, 80, 75, 70, 55),
       ["Évacuez par les axes désignés.", "Restez à l'abri et éloignez-vous des zones de combat.", "Écoutez les messages officiels."]),
    _r("R13", "Panne généralisée d'électricité", "💡", ["blackout", "delestage", "electricite", "panne de courant", "coupure de courant", "panne generale",
                                                    "coupure generale", "pas de courant"],
       "Activer le processus de rétablissement d'urgence sur l'ensemble de la ville pour sauvegarder les infrastructures vitales.",
       ["Activer le rétablissement d'urgence sur toute la ville", "Alimenter en priorité les infrastructures vitales",
        "Informer la population du calendrier de reprise"],
       [("Réseaux", 2)], (60, 90, 60, 60, 95, 75),
       ["Débranchez les appareils sensibles.", "Évitez les bougies près de matières inflammables.", "Limitez les appels aux urgences."]),
    _r("R14", "Manque d'approvisionnement", "📦", ["penurie", "approvisionnement", "rupture de stock", "famine", "vivres"],
       "Mobiliser les stocks stratégiques de la ville et réguler la distribution des provisions essentielles.",
       ["Mobiliser les stocks stratégiques de la ville", "Réguler la distribution des provisions essentielles",
        "Surveiller les points de distribution"],
       [("Voirie", 1), ("Police", 1)], (55, 85, 65, 60, 60, 60),
       ["N'achetez que le nécessaire.", "Rendez-vous aux points de distribution officiels.", "Signalez les cas de spéculation."]),
    _r("R15", "Assassinat du responsable / dirigeant", "⚖️", ["assassinat", "assassine", "assassin"],
       "Mener une enquête judiciaire, installer immédiatement l'adjoint en intérim et organiser les élections de remplacement.",
       ["Mener l'enquête judiciaire", "Installer immédiatement l'adjoint en intérim", "Organiser les élections de remplacement"],
       [("Police", 2), ("Armée", 1)], (80, 60, 50, 60, 30, 60),
       ["Restez calme et évitez les rassemblements.", "Ne relayez pas de rumeurs.", "Attendez le communiqué officiel."],
       # « maire » seul ne suffit plus : il faut un dirigeant ET un indice d'attaque mortelle
       all_of=[("maire", "president", "gouverneur", "bourgmestre", "dirigeant", "ministre", "responsable de la ville"),
               ("tue", "tuee", "abattu", "meurtre", "assassine", "execute", "poignarde", "fusille")]),
    _r("R16", "Hausse anormale des taux ou prix", "📈", ["hausse", "prix", "taux", "inflation", "flambee"],
       "Dépêcher une commission de contrôle économique pour encadrer et réguler le marché.",
       ["Dépêcher la commission de contrôle économique", "Encadrer les prix et contrôler les marchés",
        "Publier les mesures de régulation"],
       [], (40, 80, 60, 55, 30, 55),
       ["Comparez les prix avant d'acheter.", "Signalez les prix abusifs à la commission.", "Évitez les achats de panique."]),
    _r("R17", "Éboulement", "⛰️", ["eboulement", "glissement", "effondrement", "ravin"],
       "Faire intervenir les autorités et les services de voirie pour sécuriser le périmètre et entreprendre les réparations.",
       ["Sécuriser le périmètre", "Engager les services de voirie", "Entreprendre les réparations"],
       [("Voirie", 2), ("Pompiers", 1), ("Santé", 1)], (70, 50, 55, 55, 65, 70),
       ["Éloignez-vous de la zone instable.", "Ne tentez pas de franchir les débris.", "Signalez les personnes ensevelies aux secours."]),
]
RULE_BY_ID: Dict[str, Rule] = {r.id: r for r in RULES}


# --------------------------------------------------------------------------------------
# 3. RÈGLES D'INFÉRENCE (chaînage avant de faits dérivés : I1..I10)
# --------------------------------------------------------------------------------------
# Chaque règle : SI toutes les conditions sont dans la base de faits ALORS on ajoute la conclusion.
# Une conclusion peut devenir la condition d'une autre règle (enchaînement I1 -> I2, I1 -> I6, I3 -> I4...).
@dataclass(frozen=True)
class InferenceRule:
    """Règle d'inférence du chaînage avant : SI toutes les conditions ALORS ajouter la conclusion."""
    id: str
    conditions: Tuple[str, ...]
    conclusion: str
    explanation: str


INFERENCE_RULES: List[InferenceRule] = [
    InferenceRule("I1", ("victimes",), "besoin_secours_medical",
                  "Des victimes sont signalées : il faut des secours médicaux."),
    InferenceRule("I2", ("besoin_secours_medical", "sante_saturee"), "renfort_hospitalier",
                  "Unités de santé disponibles < 50 % : demander un renfort aux hôpitaux voisins."),
    InferenceRule("I3", ("categorie:sinistre_naturel", "population_dense"), "evacuation_preventive",
                  "Sinistre naturel dans une zone densément peuplée : évacuation préventive."),
    InferenceRule("I4", ("evacuation_preventive",), "ouverture_centres_accueil",
                  "Une évacuation est décidée : ouvrir les centres d'accueil."),
    InferenceRule("I5", ("categorie:menace_securitaire", "gravite_extreme"), "bouclage_zone",
                  "Menace sécuritaire de gravité extrême : boucler la zone."),
    InferenceRule("I6", ("bouclage_zone", "besoin_secours_medical"), "couloir_secours_securise",
                  "Zone bouclée avec des blessés : ouvrir un couloir sécurisé pour les secours."),
    InferenceRule("I7", ("categorie:atteinte_reseaux",), "infrastructures_vitales_menacees",
                  "Atteinte aux réseaux : hôpitaux, eau et télécoms sont menacés."),
    InferenceRule("I8", ("infrastructures_vitales_menacees", "population_dense"), "cellule_crise_municipale",
                  "Infrastructures vitales menacées pour une forte population : activer la cellule de crise."),
    InferenceRule("I9", ("multi_incidents_zone",), "zone_sous_tension",
                  "Plusieurs incidents actifs dans la même zone : zone sous tension."),
    InferenceRule("I10", ("zone_sous_tension", "priorite:P1"), "cellule_crise_municipale",
                  "Zone sous tension avec un incident critique : activer la cellule de crise."),
]

DERIVED_LABELS: Dict[str, str] = {
    "besoin_secours_medical": "🚑 Secours médicaux requis",
    "renfort_hospitalier": "🏥 Renfort hospitalier",
    "evacuation_preventive": "🚌 Évacuation préventive",
    "ouverture_centres_accueil": "🏫 Ouverture des centres d'accueil",
    "bouclage_zone": "🚧 Bouclage de la zone",
    "couloir_secours_securise": "🛣️ Couloir de secours sécurisé",
    "infrastructures_vitales_menacees": "⚡ Infrastructures vitales menacées",
    "cellule_crise_municipale": "🏛️ Cellule de crise municipale activée",
    "zone_sous_tension": "📶 Zone sous tension",
}

# Catégories utilisées comme faits de base par les règles d'inférence
RULE_CATEGORY: Dict[str, str] = {
    "R1": "sinistre_naturel", "R8": "sinistre_naturel", "R17": "sinistre_naturel",
    "R2": "sinistre_feu", "R9": "accident_route", "R3": "crise_sanitaire",
    "R4": "menace_securitaire", "R6": "menace_securitaire", "R7": "menace_securitaire",
    "R10": "menace_securitaire", "R11": "menace_securitaire", "R12": "menace_securitaire",
    "R15": "menace_securitaire", "R5": "atteinte_reseaux", "R13": "atteinte_reseaux",
    "R14": "crise_economique", "R16": "crise_economique",
}
