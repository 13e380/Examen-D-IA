"""Tests unitaires du moteur expert CIVITAS (bibliothèque standard uniquement).

Exécution : ``python -m unittest -v test_engine`` depuis le dossier du projet.
"""
from __future__ import annotations

import os
import random
import tempfile
import unittest

import engine as eng
from repository import ComplaintRepository
from systeme_expert import SystemeExpertCrise

random.seed(42)  # consigne de reproductibilité (le moteur lui-même est déterministe)


def nouvel_etat() -> eng.CityState:
    """État de ville vide, toutes unités disponibles."""
    return eng.CityState()


class TestBaseDeConnaissances(unittest.TestCase):
    """Cohérence de la base de règles."""

    def test_au_moins_15_regles_metier(self) -> None:
        """Exigence du sujet : au moins 15 règles métier."""
        self.assertGreaterEqual(len(eng.RULES), 15)

    def test_identifiants_uniques(self) -> None:
        """Chaque règle a un identifiant unique."""
        ids = [r.id for r in eng.RULES] + [r.id for r in eng.INFERENCE_RULES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_facteurs_dans_les_bornes(self) -> None:
        """Les 6 facteurs de risque de chaque règle sont entre 0 et 100."""
        for r in eng.RULES:
            self.assertEqual(len(r.factors), 6, r.id)
            self.assertTrue(all(0 <= f <= 100 for f in r.factors), r.id)

    def test_chaque_regle_metier_a_une_categorie(self) -> None:
        """Toute règle métier alimente le chaînage avant via une catégorie."""
        self.assertEqual({r.id for r in eng.RULES}, set(eng.RULE_CATEGORY))

    def test_conditions_d_inference_atteignables(self) -> None:
        """Chaque condition est un fait de base possible ou la conclusion d'une autre règle."""
        conclusions = {r.conclusion for r in eng.INFERENCE_RULES}
        base = {"victimes", "gravite_extreme", "population_dense", "sante_saturee", "multi_incidents_zone"}
        base |= {f"categorie:{c}" for c in eng.RULE_CATEGORY.values()} | {f"priorite:P{i}" for i in range(1, 5)}
        for r in eng.INFERENCE_RULES:
            for c in r.conditions:
                self.assertIn(c, base | conclusions, f"{r.id} : condition {c} jamais produite")

    def test_sous_buts_connus(self) -> None:
        """Chaque sous-but du chaînage arrière est un but composé ou un fait vérifiable."""
        etat = nouvel_etat()
        for subs in eng.BACKWARD_RULES.values():
            for s in subs:
                if s not in eng.BACKWARD_RULES:
                    _, detail = eng.prove_subgoal(s, "Katuba", etat)
                    self.assertNotEqual(detail, "sous-but inconnu", s)


class TestAnalyseLexicale(unittest.TestCase):
    """Choix de la règle métier à partir du texte (1er mécanisme de résolution de conflits)."""

    def premiere(self, texte: str) -> str | None:
        """Identifiant de la règle retenue, ou None."""
        m = eng.classify_text(texte)
        return m[0].rule_id if m else None

    def test_detections_simples(self) -> None:
        """Phrases typiques → règle attendue, malgré accents et majuscules."""
        self.assertEqual(self.premiere("Un INCENDIE ravage la maison"), "R2")
        self.assertEqual(self.premiere("Forte secousse, un SÉISME"), "R8")
        self.assertEqual(self.premiere("coupure de courant dans tout le quartier"), "R13")
        self.assertEqual(self.premiere("cas de choléra, épidémie"), "R3")

    def test_faux_positifs_corriges(self) -> None:
        """« maire » seul ou « panne de voiture » ne déclenchent plus de règle."""
        self.assertIsNone(self.premiere("le maire a inauguré une route"))
        self.assertIsNone(self.premiere("une panne de voiture sur la route"))

    def test_indices_combines(self) -> None:
        """Dirigeant + attaque mortelle → R15."""
        self.assertEqual(self.premiere("le maire a été tué par balle"), "R15")

    def test_egalite_departagee_par_gravite(self) -> None:
        """R2 et R9 ont le même poids : la gravité (80 > 65) départage, et c'est expliqué."""
        m = eng.classify_text("accident avec incendie du camion")
        self.assertEqual([x.rule_id for x in m[:2]], ["R2", "R9"])
        self.assertEqual(m[0].weight, m[1].weight)
        self.assertIn("gravité", eng.tie_note(m))

    def test_texte_vide(self) -> None:
        """Cas limite : texte vide ou sans mot-clé."""
        self.assertEqual(eng.classify_text(""), [])
        self.assertEqual(eng.classify_text("bonjour tout le monde"), [])

    def test_detection_des_victimes(self) -> None:
        """Mots entiers : « tuées » compte, « statue » ne compte pas."""
        self.assertTrue(eng.detect_victims("deux personnes tuées"))
        self.assertTrue(eng.detect_victims("des Blessés graves"))
        self.assertFalse(eng.detect_victims("une statue est tombée"))

    def test_detection_du_quartier(self) -> None:
        """Le quartier cité est reconnu, sinon None."""
        self.assertEqual(eng.detect_district("incendie à Kamalondo"), "Kamalondo")
        self.assertIsNone(eng.detect_district("incendie à Paris"))


class TestScoreEtPriorite(unittest.TestCase):
    """Indice de risque multicritère et seuils de priorité."""

    def test_score_pondere(self) -> None:
        """Valeur de référence calculée à la main."""
        f = {"gravite": 90, "exposition": 90, "vulnerabilite": 80, "tendance": 65,
             "infrastructure": 85, "confiance": 65}
        self.assertAlmostEqual(eng.compute_score(f), 82.3)

    def test_poids_somme_un(self) -> None:
        """Les poids forment une moyenne pondérée."""
        self.assertAlmostEqual(sum(eng.WEIGHTS.values()), 1.0)

    def test_seuils(self) -> None:
        """Bornes exactes des priorités."""
        self.assertEqual(eng.compute_priority(72, False, 50)[0], "P1")
        self.assertEqual(eng.compute_priority(71.9, False, 50)[0], "P2")
        self.assertEqual(eng.compute_priority(52, False, 50)[0], "P2")
        self.assertEqual(eng.compute_priority(32, False, 50)[0], "P3")
        self.assertEqual(eng.compute_priority(31.9, False, 50)[0], "P4")

    def test_p1_force(self) -> None:
        """Victimes ou gravité ≥ 90 → P1 quel que soit le score."""
        self.assertEqual(eng.compute_priority(10, True, 10)[0], "P1")
        self.assertEqual(eng.compute_priority(10, False, 90)[0], "P1")


class TestChainageAvant(unittest.TestCase):
    """Cycles d'inférence jusqu'à saturation (2e mécanisme de résolution de conflits)."""

    def test_seisme_zone_dense(self) -> None:
        """Ordre attendu : I3 (plus spécifique) avant I1, puis I4 ; saturation en 3 cycles."""
        se = SystemeExpertCrise()
        inc = se.signaler("Forte secousse, des blessés", "Katuba")
        _, cycles = se.chainage_avant(inc.id)
        self.assertEqual([c.chosen.id for c in cycles], ["I3", "I1", "I4"])
        self.assertIn("spécifique", cycles[0].reason)
        self.assertEqual(len(se.actions_deduites(inc.id)), 3)

    def test_enchainement_sante_saturee(self) -> None:
        """I1 produit un fait qui déclenche I2 quand la santé est saturée."""
        memoire, cycles = eng.forward_infer(["victimes", "sante_saturee"])
        self.assertEqual([c.chosen.id for c in cycles], ["I1", "I2"])
        self.assertIn("renfort_hospitalier", memoire)

    def test_saturation_sans_doublon(self) -> None:
        """Réfraction : chaque règle au plus une fois, aucun fait dupliqué."""
        faits = ["victimes", "sante_saturee", "categorie:menace_securitaire", "gravite_extreme",
                 "population_dense", "categorie:sinistre_naturel", "multi_incidents_zone", "priorite:P1",
                 "categorie:atteinte_reseaux"]
        memoire, cycles = eng.forward_infer(faits)
        ids = [c.chosen.id for c in cycles]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(memoire), len(set(memoire)))
        self.assertLessEqual(len(cycles), len(eng.INFERENCE_RULES))

    def test_aucun_fait(self) -> None:
        """Cas limite : base vide → aucun cycle."""
        self.assertEqual(eng.forward_infer([]), ([], []))


class TestChainageArriere(unittest.TestCase):
    """Validation réglementaire récursive."""

    def test_evacuation_refusee_puis_autorisee(self) -> None:
        """Le but dépend de l'état : refusé pendant le séisme, autorisé après résolution."""
        se = SystemeExpertCrise()
        inc = se.signaler("séisme", "Katuba")
        ok, trace = se.chainage_arriere("levee_evacuation", "Katuba")
        self.assertFalse(ok)
        self.assertTrue(trace[0][2].startswith("BUT"))
        self.assertTrue(trace[-1][2].startswith("CONCLUSION"))
        self.assertTrue(se.resoudre(inc.id))
        self.assertTrue(se.chainage_arriere("levee_evacuation", "Katuba")[0])

    def test_autre_zone_non_affectee(self) -> None:
        """Un incident à Katuba n'empêche pas la levée d'évacuation à Kenya."""
        se = SystemeExpertCrise()
        se.signaler("séisme", "Katuba")
        self.assertTrue(se.chainage_arriere("levee_evacuation", "Kenya")[0])

    def test_quarantaine_et_unites_de_sante(self) -> None:
        """Moins de 50 % d'unités de santé → quarantaine non levable."""
        se = SystemeExpertCrise()
        for u in se.etat.units:
            if u.type == "Santé":
                u.available = False
        self.assertFalse(se.chainage_arriere("levee_quarantaine", "Annexe")[0])

    def test_ordre_public_et_plan_deploye(self) -> None:
        """Une manifestation active bloque le retour à l'ordre public, même avec un plan déployé."""
        se = SystemeExpertCrise()
        inc = se.signaler("manifestation devant la mairie", "Lubumbashi")
        se.deployer(inc.id)
        self.assertFalse(se.chainage_arriere("retour_ordre_public", "Lubumbashi")[0])

    def test_but_inconnu(self) -> None:
        """Cas limite : but inexistant → KeyError."""
        with self.assertRaises(KeyError):
            SystemeExpertCrise().chainage_arriere("but_inexistant", "Katuba")


class TestAgenda(unittest.TestCase):
    """Agenda des incidents (3e mécanisme : criticité > spécificité > récence)."""

    def test_criticite_puis_specificite_puis_recence(self) -> None:
        """Ordre attendu sur un petit jeu d'incidents."""
        etat = nouvel_etat()
        p2 = eng.create_incident(etat, "R16", "Kenya", "hausse des prix", "Texte", "admin", overrides={"gravite": 100})
        a = eng.create_incident(etat, "R2", "Katuba", "incendie", "Texte", "citizen", victims=True)
        b = eng.create_incident(etat, "R4", "Ruashi", "braquage", "Texte", "citizen", victims=True)
        c = eng.create_incident(etat, "R2", "Annexe", "incendie", "Texte", "citizen", victims=True)
        ordre = [i.id for i in eng.agenda(etat)]
        # P1 d'abord ; parmi les P1, R2 (2 types d'unités + victimes = 3) avant R4 (1 + 1 = 2) ;
        # entre les deux R2, le plus récent (c) d'abord.
        self.assertEqual(ordre[:3], [c.id, a.id, b.id])
        self.assertIn(p2.id, ordre)


class TestCasLimites(unittest.TestCase):
    """Robustesse : entrées invalides et états particuliers."""

    def setUp(self) -> None:
        """Ville vide pour chaque test."""
        self.etat = nouvel_etat()

    def test_entrees_invalides(self) -> None:
        """Zone vide, texte trop long, GPS incomplet ou hors limites → ValueError."""
        cas = [dict(district=" "), dict(description="x" * 2001), dict(latitude=1.0),
               dict(latitude=100.0, longitude=0.0), dict(district="z" * 81)]
        for extra in cas:
            args = dict(state=self.etat, rule_id="R2", district="Katuba", description="feu",
                        channel="Texte", role="citizen")
            args.update(extra)
            with self.assertRaises(ValueError, msg=str(extra)):
                eng.create_incident(**args)
        self.assertEqual(self.etat.incidents, [])

    def test_regle_inconnue(self) -> None:
        """Identifiant de règle inexistant → KeyError."""
        with self.assertRaises(KeyError):
            eng.create_incident(self.etat, "R99", "Katuba", "feu", "Texte", "citizen")

    def test_aucune_regle_reconnue(self) -> None:
        """La classe refuse un texte sans catégorie."""
        with self.assertRaises(ValueError):
            SystemeExpertCrise().signaler("bonjour", "Katuba")

    def test_zone_hors_couverture(self) -> None:
        """Hors des quartiers connus : aucune unité, déficit signalé, pas d'exception."""
        inc = eng.create_incident(self.etat, "R2", "Paris", "feu", "Texte", "citizen")
        rec = eng.recommend_units(self.etat, inc.rule, "Paris")
        self.assertEqual(rec.rows, [])
        self.assertEqual(rec.shortfalls, dict(inc.rule.needs))

    def test_deficit_d_unites(self) -> None:
        """Plus d'unités disponibles → déficit au lieu d'un échec."""
        for u in self.etat.units:
            u.available = False
        rec = eng.recommend_units(self.etat, eng.RULE_BY_ID["R8"], "Katuba")
        self.assertEqual(rec.rows, [])
        self.assertEqual(sum(rec.shortfalls.values()), 5)

    def test_cycle_de_vie(self) -> None:
        """Déployer deux fois est refusé ; résoudre libère les unités."""
        inc = eng.create_incident(self.etat, "R2", "Katuba", "feu", "Texte", "citizen")
        self.assertIsNotNone(eng.deploy_plan(self.etat, inc.id))
        self.assertIsNone(eng.deploy_plan(self.etat, inc.id))
        engagees = [u for u in self.etat.units if u.incident_id == inc.id]
        self.assertEqual(len(engagees), 3)
        self.assertFalse(eng.toggle_unit(self.etat, engagees[0].id))
        self.assertTrue(eng.resolve_incident(self.etat, inc.id))
        self.assertFalse(eng.resolve_incident(self.etat, inc.id))
        self.assertTrue(all(u.available for u in engagees))

    def test_incident_inconnu(self) -> None:
        """Explication d'un incident inexistant → KeyError."""
        with self.assertRaises(KeyError):
            SystemeExpertCrise().expliquer(404)


class TestModuleExplication(unittest.TestCase):
    """La trace retrace la chaîne de déduction."""

    def test_etapes_presentes(self) -> None:
        """Les étapes clés figurent dans l'ordre."""
        se = SystemeExpertCrise()
        inc = se.signaler("accident avec incendie du camion, blessés", "Kenya")
        titres = [t for t, _ in inc.trace]
        attendus = ["Acquisition", "Instanciation du fait", "Filtrage et appariement",
                    "Actions déduites", "Résolution de conflit", "Sortie Dashboard"]
        positions = [titres.index(t) for t in attendus]
        self.assertEqual(positions, sorted(positions))
        texte = se.expliquer(inc.id)
        self.assertIn("Égalité de poids lexical", texte)
        self.assertIn("Chaînage avant — cycle 1", texte)

    def test_explication_du_but(self) -> None:
        """L'arbre de preuve est indenté et conclut."""
        texte = SystemeExpertCrise().expliquer_but("reouverture_circulation", "Kampemba")
        self.assertIn("    [OK]", texte)
        self.assertIn("AUTORISÉE", texte)


class TestPersistance(unittest.TestCase):
    """Aller-retour SQLite : un incident relu est identique."""

    def test_aller_retour(self) -> None:
        """Enregistrer puis relire conserve la trace et les pièces jointes."""
        with tempfile.TemporaryDirectory() as dossier:
            depot = ComplaintRepository(os.path.join(dossier, "test.sqlite3"))
            etat = nouvel_etat()
            inc = eng.create_incident(etat, "R2", "Katuba", "feu", "Texte", "citizen", victims=True)
            depot.save_complaint(inc, "Plainte déposée", attachments=(("p.webp", "image/webp", b"abc"),))
            relu = depot.get_complaint(inc.id)
            self.assertIsNotNone(relu)
            self.assertEqual(relu.trace, inc.trace)
            self.assertEqual(relu.priority, "P1")
            self.assertEqual(depot.get_attachments(inc.id)[0][2], b"abc")
            self.assertIsNone(depot.get_complaint(999))


if __name__ == "__main__":
    unittest.main(verbosity=2)
