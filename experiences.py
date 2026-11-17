"""Expériences du rapport : précision de l'analyse lexicale, comportement du chaînage et temps de calcul.

Exécution : ``python experiences.py`` (graine 42, résultats écrits dans ``resultats_experiences.json``).
"""
from __future__ import annotations

import json
import random
import statistics
import time
from collections import Counter
from typing import Dict, List, Optional, Tuple

import engine as eng

SEED = 42

# Jeu de validation construit par l'équipe : (phrase, règle attendue ou None si aucune alerte ne doit partir).
# Il contient des formulations variées et des phrases pièges (homonymes, contexte non urgent).
JEU_VALIDATION: List[Tuple[str, Optional[str]]] = [
    ("La lave coule du volcan, les cendres tombent sur le quartier", "R1"),
    ("Éruption en cours, il faut partir", "R1"),
    ("Le feu a pris dans une maison, beaucoup de fumée", "R2"),
    ("Un véhicule brûle au rond-point", "R2"),
    ("Incendie au marché central", "R2"),
    ("Plusieurs cas de choléra dans l'avenue", "R3"),
    ("Des malades contagieux, il faut une quarantaine", "R3"),
    ("Braquage à la banque, des hommes armés", "R4"),
    ("Hold up en cours dans l'agence", "R4"),
    ("Le site de la mairie est piraté, un ransomware bloque tout", "R5"),
    ("Une fausse information circule sur les réseaux", "R5"),
    ("Des prisonniers se sont évadés de la prison", "R6"),
    ("Un animal échappé du zoo rôde", "R6"),
    ("Manifestation devant le gouvernorat", "R7"),
    ("Grève et émeute au centre-ville", "R7"),
    ("Forte secousse, les murs tremblent", "R8"),
    ("Tremblement de terre ce matin", "R8"),
    ("Collision entre un bus et un camion", "R9"),
    ("Accident grave sur la route de Kasumbalesa", "R9"),
    ("Une bombe a explosé près du stade", "R10"),
    ("Attentat au marché", "R10"),
    ("Un enfant a été enlevé à la sortie de l'école", "R11"),
    ("Kidnapping signalé, la victime a disparu", "R11"),
    ("Des rebelles armés ont fait une incursion", "R12"),
    ("Infiltration ennemie près de la frontière", "R12"),
    ("Blackout total dans la commune", "R13"),
    ("Délestage depuis deux jours, plus d'électricité", "R13"),
    ("Pénurie de farine dans tous les magasins", "R14"),
    ("Rupture de stock de carburant", "R14"),
    ("Le gouverneur a été abattu", "R15"),
    ("Assassinat du bourgmestre", "R15"),
    ("Flambée des prix du maïs", "R16"),
    ("Hausse anormale du taux de change", "R16"),
    ("Éboulement sur la route, des rochers bloquent le passage", "R17"),
    ("Glissement de terrain près du ravin", "R17"),
    # Phrases pièges : aucune règle ne doit se déclencher
    ("Le maire a inauguré une nouvelle école", None),
    ("Ma voiture est en panne devant chez moi", None),
    ("Le président du club a gagné le match", None),
    ("Bonjour, je voulais juste dire merci", None),
    ("La réunion de quartier est reportée", None),
]

# Jeu « difficile » : formulations hors lexique, négations et sens figurés.
# (phrase, règle attendue ou None, victimes attendues) — il mesure les limites de l'approche par mots-clés.
JEU_DIFFICILE: List[Tuple[str, Optional[str], bool]] = [
    ("Personne n'est blessé, juste un petit feu de poubelle", "R2", False),
    ("La maison est en flammes", "R2", False),
    ("Un camion s'est renversé sur la chaussée", "R9", False),
    ("Le courant est coupé partout depuis ce matin", "R13", False),
    ("Pas d'électricité à l'hôpital", "R13", False),
    ("Des tirs entendus près du camp militaire", "R12", False),
    ("On a volé l'argent de la banque", "R4", False),
    ("Un homme a été poignardé, il saigne beaucoup", None, True),
    ("Le feu rouge du carrefour ne marche plus", None, False),
    ("Le prix de la paix est élevé", None, False),
    ("Il est mort de rire en regardant le match", None, False),
    ("La rivière déborde, les maisons sont inondées", None, False),
    ("Une fuite de gaz, ça sent très fort", None, False),
    ("Les enfants sont coincés dans l'ascenseur", None, True),
    ("Fièvre et diarrhée chez beaucoup de voisins", "R3", False),
]


def precision_jeu_difficile() -> Dict[str, object]:
    """Précision de la catégorie et de la détection des victimes sur le jeu difficile."""
    cat_ok = vic_ok = 0
    details = []
    for phrase, attendu, victimes in JEU_DIFFICILE:
        m = eng.classify_text(phrase)
        obtenu = m[0].rule_id if m else None
        v = eng.detect_victims(phrase)
        cat_ok += obtenu == attendu
        vic_ok += v == victimes
        if obtenu != attendu or v != victimes:
            details.append({"phrase": phrase, "attendu": attendu, "obtenu": obtenu,
                            "victimes_attendues": victimes, "victimes_detectees": v})
    n = len(JEU_DIFFICILE)
    return {"phrases": n, "categorie_correcte": cat_ok, "precision_categorie": round(100 * cat_ok / n, 1),
            "victimes_correctes": vic_ok, "precision_victimes": round(100 * vic_ok / n, 1), "erreurs": details}


def precision_analyse_lexicale() -> Dict[str, object]:
    """Précision de classify_text sur le jeu de validation, avec la liste des erreurs."""
    erreurs = []
    for phrase, attendu in JEU_VALIDATION:
        m = eng.classify_text(phrase)
        obtenu = m[0].rule_id if m else None
        if obtenu != attendu:
            erreurs.append({"phrase": phrase, "attendu": attendu, "obtenu": obtenu})
    n = len(JEU_VALIDATION)
    pieges = [p for p in JEU_VALIDATION if p[1] is None]
    faux_pos = sum(1 for e in erreurs if e["attendu"] is None)
    return {"phrases": n, "correctes": n - len(erreurs), "precision": round(100 * (n - len(erreurs)) / n, 1),
            "pieges": len(pieges), "fausses_alertes": faux_pos, "erreurs": erreurs}


def statistiques_chainage() -> Dict[str, object]:
    """Cycles du chaînage avant pour chaque règle × zone × présence de victimes (ville vide)."""
    cycles, derives = [], Counter()
    for regle in eng.RULES:
        for zone in eng.DISTRICTS:
            for victimes in (False, True):
                etat = eng.CityState()
                inc = eng.create_incident(etat, regle.id, zone, "test", "Texte", "admin", victims=victimes)
                _, cyc = eng.forward_infer(eng.base_facts(etat, inc))
                cycles.append(len(cyc))
                derives.update(c.chosen.id for c in cyc)
    return {"cas": len(cycles), "cycles_moyen": round(statistics.mean(cycles), 2), "cycles_max": max(cycles),
            "cas_sans_deduction": cycles.count(0), "declenchements_par_regle": dict(sorted(derives.items()))}


def _ville_aleatoire(n: int, rng: random.Random) -> eng.CityState:
    """Ville contenant n incidents tirés au hasard (graine fixée)."""
    etat = eng.CityState()
    zones = list(eng.DISTRICTS)
    for _ in range(n):
        eng.create_incident(etat, rng.choice(eng.RULES).id, rng.choice(zones), "test", "Texte", "citizen",
                            victims=rng.random() < 0.3)
    return etat


def temps_de_calcul(tailles: Tuple[int, ...] = (10, 100, 500, 1000, 2000), repetitions: int = 50) -> List[Dict]:
    """Temps moyen (ms) d'un signalement, du chaînage arrière et de l'agenda selon le nombre d'incidents actifs."""
    rng = random.Random(SEED)
    lignes = []
    for n in tailles:
        etat = _ville_aleatoire(n, rng)
        t0 = time.perf_counter()
        for _ in range(repetitions):
            eng.create_incident(etat, "R2", "Katuba", "feu", "Texte", "citizen")
        t_signal = (time.perf_counter() - t0) / repetitions * 1000
        t0 = time.perf_counter()
        for _ in range(repetitions):
            eng.backward_chain("levee_evacuation", "Katuba", etat)
        t_arriere = (time.perf_counter() - t0) / repetitions * 1000
        t0 = time.perf_counter()
        for _ in range(repetitions):
            eng.agenda(etat)
        t_agenda = (time.perf_counter() - t0) / repetitions * 1000
        lignes.append({"incidents": n, "signalement_ms": round(t_signal, 3), "chainage_arriere_ms": round(t_arriere, 3),
                       "agenda_ms": round(t_agenda, 3)})
    return lignes


def temps_inference_seule(repetitions: int = 20000) -> float:
    """Temps moyen (µs) de forward_infer sur la base de faits la plus riche possible."""
    faits = ["victimes", "sante_saturee", "categorie:menace_securitaire", "gravite_extreme", "population_dense",
             "categorie:sinistre_naturel", "multi_incidents_zone", "priorite:P1", "categorie:atteinte_reseaux"]
    t0 = time.perf_counter()
    for _ in range(repetitions):
        eng.forward_infer(faits)
    return round((time.perf_counter() - t0) / repetitions * 1e6, 2)


def main() -> None:
    """Lance toutes les expériences et écrit les résultats."""
    random.seed(SEED)
    resultats = {"precision": precision_analyse_lexicale(), "difficile": precision_jeu_difficile(), "chainage": statistiques_chainage(),
                 "inference_us": temps_inference_seule(), "temps": temps_de_calcul()}
    with open("resultats_experiences.json", "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)
    print(json.dumps(resultats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
