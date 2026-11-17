# Examen-D-IA

Hey bro, ici on retrouve la solution de notre examen d'IA basé sur : **Moteur mixte de gestion de crise Smart City** (sujet 3.3).

## CIVITAS — Moteur mixte de gestion de crise Smart City

Interface Streamlit (Population + Administration) au-dessus d'un moteur expert Python
(17 règles métier + 10 règles d'inférence, score multicritère, chaînage avant/arrière, module d'explication).

## Fichiers
- `systeme_expert.py` — **script principal** : classe `SystemeExpertCrise` (signaler, chaînage avant/arrière, explication). `python systeme_expert.py` lance une démonstration sans interface
- `test_engine.py` — 37 tests unitaires (`python -m unittest -v test_engine`)
- `experiences.py` — expériences du rapport (graine 42), résultats dans `resultats_experiences.json`
- `Rapport_CIVITAS.pdf` — rapport synthétique (3 pages)
- `app.py` — point d'entrée Streamlit et sélection du profil
- `ui_shared.py` — état partagé, traductions, limites d'envoi et composants communs
- `citizen_ui.py` — signalement, consignes et suivi public
- `operator_ui.py` — accès opérateur, recherche, suivi et traitement des plaintes
- `engine.py` — calcul du risque, affectation, chaînages et cycle de vie des incidents
- `engine_rules.py` — catalogue des 17 règles métier (R1..R17) et des 10 règles d'inférence (I1..I10)
- `repository.py` — persistance SQLite des plaintes, événements et pièces jointes
- `assets/style.css` — palette et styles adaptatifs avec prise en compte des préférences de mouvement réduit
- `assets/hero.html` — modèle HTML de l'en-tête
- `assets/live_clock.html` et `assets/live_clock.js` — horloge locale de l'appareil, actualisée dans le navigateur
- `requirements.txt` — dépendances

## Lancement local
```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
Ouvrir http://localhost:8501.

Code opérateur par défaut : `1234`. Pour le changer :
```bash
CIVITAS_ADMIN_PIN=monCodeSecret streamlit run app.py          # Linux / macOS
set CIVITAS_ADMIN_PIN=monCodeSecret && streamlit run app.py   # Windows (cmd)
```

## Test multi-appareils (smartphone + PC)
```bash
streamlit run app.py --server.address 0.0.0.0
```
Ouvrir `http://<IP-du-PC>:8501` depuis le téléphone (même réseau Wi-Fi). L'état est partagé :
un signalement citoyen apparaît sur le tableau de bord (actualisation automatique, barre latérale).
Note : la caméra et le micro du navigateur exigent HTTPS hors `localhost`.

## Limites connues (honnêteté technique)
- **Voix et image sont simulées** : `simulate_transcription()` et `analyze_image()` dans `engine.py` sont les
  points d'extension (Whisper/Vosk, CLIP/YOLO). L'interface fonctionne déjà avec une vraie implémentation.
- **Audio** : les fichiers importés sont plafonnés à 50 Mo et les enregistrements de plus d'une minute sont refusés.
  Une confirmation est demandée à l'approche de cette limite. Aucun réseau téléphonique NGN ni appel réel n'est intégré.
- **Photos** : chaque fichier est plafonné à 5 Mo, jusqu'à 10 images par signalement, filtrage des photos floues,
  compression WebP et plafonnement à 20 Mo par série. Les pièces jointes sont enregistrées dans le dépôt SQLite
  et restent disponibles après le redémarrage du serveur.
- **Texte** : les descriptions sont limitées à 2 000 caractères, avec une confirmation à partir de 1 600 caractères.
- **Langues** : français, anglais, swahili et lingala.
- **Localisation et carte** : le GPS est facultatif et arrondi avant stockage. La carte utilise les tuiles
  OpenStreetMap ; les quartiers de Lubumbashi sont indiqués par des centres approximatifs. Les autres zones sont
  cartographiées uniquement si le déclarant partage sa position. Aucune équipe n'est configurée hors Lubumbashi.
- **Accès depuis Internet** : `streamlit run app.py` ne publie pas l'application sur Internet. Pour un accès mondial,
  déployez-la sur un hébergeur avec HTTPS ; le navigateur exige un contexte sécurisé pour le GPS, et les tuiles
  OpenStreetMap nécessitent une connexion réseau.
- **Persistance** : plaintes, traces et pièces jointes sont enregistrées dans SQLite (`.data/civitas.sqlite3`). La disponibilité des unités est recalculée au démarrage à partir des plans déployés.
- **Données** : populations, facteurs par règle, unités et ETA sont des hypothèses de démonstration à calibrer.
- **Sécurité** : le code PIN est un contrôle minimal de démonstration, pas une authentification de production.

## Journal des ajouts — 14/11/2026

Les éléments ci-dessous ont été ajoutés lors de la mise à niveau de CIVITAS :

- **Interface** : palette bleue, rouge et blanche, cartes et boutons animés, mise en page mobile améliorée,
  et marge supérieure augmentée pour éviter que la barre Streamlit recouvre le contenu.
- **Limites d’envoi** : plafond global d’import à 50 Mo ; les fichiers audio sont limités à 50 Mo et à une minute.
  Une confirmation est demandée quand l’audio approche de la limite. Aucun quota d’appels supplémentaire ni
  connexion à un réseau téléphonique NGN n’a été ajouté ; les appels réels ne sont pas pris en charge.
- **Photos** : jusqu'à 10 images par signalement, 5 Mo par image, contrôle de netteté avant analyse et
  compression en WebP (redimensionnement maximal de 1 600 × 1 600 pixels). Une confirmation est demandée
  à partir de 8 images ; une série compressée est limitée à 20 Mo. Les images sont conservées comme pièces
  jointes dans SQLite.
- **Descriptions et suivi** : limite de 2 000 caractères pour les descriptions et transcriptions ; confirmation
  demandée à partir de 1 600 caractères. Les signalements sont associés à leur identifiant, heure, zone,
  priorité et canal dans la trace du moteur.
- **Carte et localisation** : ajout d’une carte OpenStreetMap des alertes publiques et du tableau de bord.
  Le partage de position GPS est facultatif et la position est arrondie avant stockage. Les quartiers connus
  de Lubumbashi sont affichés à partir de points centraux indicatifs ; ailleurs, un signalement n’est placé sur
  la carte que si le GPS est partagé. Aucune équipe n’est configurée hors de la zone de démonstration de
  Lubumbashi et le déploiement d’un plan y est désactivé.
- **Langues** : ajout du sélecteur français, anglais, swahili et lingala, avec traduction des principaux éléments
  de navigation et de signalement.
- **Dépendances et configuration** : ajout de Folium, Streamlit-Folium, Streamlit-Geolocation et Mutagen ;
  configuration Streamlit du plafond global d’import dans `.streamlit/config.toml`.
- **Vérifications effectuées** : compilation Python, rendu des parcours citoyen et opérateur, changement de
  langue, traitement de durées audio de part et d’autre d’une minute, rejet des descriptions trop longues,
  validation des coordonnées, détection d’images floues et conversion WebP.

## Dépôt persistant des plaintes

- L'ancien espace Administration est remplacé par un tableau de bord réservé aux opérateurs, exclusivement
  consacré aux plaintes : recherche, filtres par statut et priorité, détail du signalement, pièces jointes,
  carte des zones et historique horodaté des actions.
- Les plaintes, leurs statuts, la trace du moteur et les photos compressées sont enregistrés dans SQLite,
  ainsi que les fichiers audio transmis, dans `.data/civitas.sqlite3`. La base et ses fichiers de journalisation
  sont ignorés par Git.
- Pour choisir un autre emplacement, définir `CIVITAS_DB_PATH` avant de lancer Streamlit. Par exemple :
  `CIVITAS_DB_PATH=/chemin/securise/civitas.sqlite3 streamlit run app.py`.
- Les déploiements et résolutions sont inscrits dans l'historique de chaque plainte. Les plaintes ouvertes et
  les équipes affectées sont rechargées au démarrage ; les données de démonstration ne sont plus ajoutées
  automatiquement.
- Cette persistance locale n'est pas une sauvegarde. En production, sauvegarder régulièrement le fichier SQLite
  avec une méthode compatible avec SQLite et protéger son accès. Le code opérateur par défaut reste une valeur
  de démonstration ; configurer `CIVITAS_ADMIN_PIN` avant tout usage réel.
- Cette section met à jour les anciennes notes de ce README indiquant que les plaintes restaient en mémoire
  et que les photos étaient temporaires.

## Améliorations de structure et d'interface — 16/11/2026

Les éléments utiles du parcours existant sont conservés : signalements texte/voix/photo, consignes, GPS facultatif,
carte, suivi public, tableau opérateur, filtres, historique et stockage SQLite. Les fonctions simulées restent
explicitement signalées comme telles ; elles ne sont pas présentées comme une reconnaissance réelle.

- **Interface séparée par rôle** : `app.py` reste le point d'entrée ; `citizen_ui.py` et `operator_ui.py`
  regroupent chacun un parcours. `ui_shared.py` contient l'état et les éléments communs. Aucun de ces modules
  ne dépasse 1 000 lignes.
- **Moteur clarifié** : `engine_rules.py` porte le catalogue métier ; `engine.py` conserve l'orchestration et
  les fonctions publiques utilisées par l'application. Les comportements du moteur restent accessibles via
  `import engine`.
- **Design externalisé** : la palette bleu, rouge et blanc, les cartes, les transitions, la mise en page mobile
  et le mode de mouvement réduit sont dans `assets/style.css`. Le bandeau est défini dans `assets/hero.html`.
- **Dynamisme** : une horloge locale de l'appareil se met à jour dans le navigateur à l'aide de
  `assets/live_clock.js`. JavaScript est limité à cette horloge ; les effets visuels utilisent CSS et aucune
  dépendance supplémentaire n'est requise.
- **Nettoyage documentaire** : la documentation précédente indiquait à la fois que les photos étaient
  temporaires et persistées. Elle décrit maintenant le comportement réel : les pièces jointes sont stockées
  dans SQLite.
- **Points non supprimés** : les parcours d'urgence, les contrôles de taille et de netteté, l'authentification
  opérateur de démonstration et la traçabilité restent en place, car ils protègent ou complètent les parcours
  existants. Le code PIN par défaut `1234` demeure réservé aux démonstrations ; configurez
  `CIVITAS_ADMIN_PIN` avant tout usage réel.

## Moteur expert et design « Smart City » — 16/11/2026 (soir)

### Exigences du sujet 3.3 et où les trouver dans l'application
| Exigence | Implémentation | Où le montrer |
|---|---|---|
| ≥ 15 règles métier | 17 règles R1..R17 (`engine_rules.py`) + 10 règles d'inférence I1..I10 + 7 règles de chaînage arrière | Opérateur → **📚 Base de connaissances** |
| Chaînage avant | Faits de base → règle métier → cycles d'inférence jusqu'à saturation (`forward_infer`) | Opérateur → **🧠 Moteur & agenda** |
| Chaînage arrière | Démonstration récursive d'un but réglementaire (`backward_chain`) | Opérateur → **⚖️ Validation réglementaire** |
| ≥ 2 mécanismes de résolution de conflits | 3 mécanismes : choix de la règle (poids lexical → nb d'indices → gravité), cycles d'inférence (spécificité → ordre, réfraction), agenda (criticité → spécificité → récence) | Base de connaissances + traces |
| Module d'explication | Frise étape par étape de chaque déduction et arbre de preuve du chaînage arrière | Détail d'une plainte, onglets moteur et validation |

### Changements
- **Chaînage avant réel** : les conclusions d'une règle deviennent des faits qui en déclenchent d'autres
  (ex. victimes → I1 secours médicaux → I6 couloir sécurisé si zone bouclée). Chaque cycle est tracé avec
  les règles déclenchables, la règle retenue et la raison du choix.
- **Chaînage arrière récursif** : les buts (levée d'évacuation, levée de quarantaine, retour à l'ordre public,
  réouverture de la circulation) se décomposent en sous-buts, eux-mêmes démontrés par des faits. Il est
  maintenant accessible dans l'interface et recalculé en direct sur l'état de la ville.
- **Corrections de l'analyse lexicale** : « maire » ou « président » seuls ne déclenchent plus R15 (il faut aussi
  un indice d'attaque mortelle) ; « panne » seul (ex. panne de voiture) ne déclenche plus R13 ; les égalités de
  poids sont départagées et expliquées ; « tué », « décédé », « noyé », « coincé »… sont reconnus comme victimes.
- **Design Smart City** : thème sombre (`.streamlit/config.toml`), grille de plan urbain, bandeau avec silhouette
  de ville animée (fenêtres, antennes, liens réseau), tuiles d'indicateurs néon, frise de raisonnement, arbre de
  preuve, jauges de disponibilité des unités, carte sombre (CartoDB Dark Matter). Les animations respectent
  le réglage « mouvement réduit » du système.
- Une copie de l'état précédent a été conservée dans `Smart City (sauvegarde)`.

## Livrables d'examen — 16/11/2026

- **Script principal orienté objet** : `systeme_expert.py` (classe `SystemeExpertCrise`). Le moteur n'utilise que la
  bibliothèque standard ; Streamlit, folium, etc. ne servent qu'à l'interface de démonstration.
- **Tests** : `python -m unittest -v test_engine` → 37 tests (base de règles, analyse lexicale, score, chaînage avant et
  arrière, agenda, cas limites, persistance SQLite).
- **Documentation** : toutes les fonctions et classes ont une docstring ; typage via `typing`.
- **Reproductibilité** : graine fixée à 42 (`experiences.py`, tests, dessin du bandeau).
- **Résultats** : 100 % sur le jeu de validation (40 phrases), 60 % sur le jeu difficile (15 phrases : synonymes,
  négations, sens figurés) ; signalement complet en ≈ 1 ms avec 2 000 incidents actifs.
