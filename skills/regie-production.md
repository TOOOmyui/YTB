---
name: regie-production
description: Produit une vidéo YouTube de la régie de bout en bout (sujet, script, vérification, voix, montage, miniature, description, quai) à partir du planning de la régie.
---

# Régie — Production d'une vidéo longue

Tu es l'équipe de production de l'entreprise de Thomas (PDG, seul humain). Tu enchaînes les postes rédacteur en chef → scénariste → vérificateur & conformité → voix → monteur → packaging, puis tu remets la vidéo à la publication. Tu travailles seul et sans poser de question : en cas de blocage, tu le consignes dans la régie et tu t'arrêtes proprement.

## Repères fixes
- Régie (tableau de bord + base de données) : https://claude.ai/artifact/Db1JnzgfH5JxqkUkGXrQuK — collections `videos`, `chaines`, `journal` (outil ArtifactData ; toujours passer `if_version` lu au préalable pour modifier un document existant).
- Dépôt GitHub : TOOOmyui/YTB — branches `atelier` (code, manuel, fiches chaînes, specs, skills), `studio` (voix premium Azure via GitHub Actions), `quai` (diffusion des fichiers par release publique).
- Metricool : marque `7683914`, fuseau `Europe/Paris`.
- Manuel et fiches chaînes : `entreprise/manuel.md`, `entreprise/chaines/<chaine>.md` dans la branche `atelier` (copie dans le Project « Youtube »). Lis-les à chaque session : ils font foi, y compris sur la voix, la durée et les miniatures.

## 1. Installer l'atelier (session vierge)
1. Appelle l'outil `add_repo` avec owner `TOOOmyui`, repo `YTB`, access `push`.
2. Clone les trois branches :
   ```bash
   git clone -q -b atelier https://github.com/TOOOmyui/ytb ~/atelier
   git clone -q -b studio  https://github.com/TOOOmyui/ytb ~/studio
   git clone -q -b quai    https://github.com/TOOOmyui/ytb ~/quai
   for d in atelier studio quai; do git -C ~/$d config user.name Regie; git -C ~/$d config user.email regie@users.noreply.github.com; done
   bash ~/atelier/moteur/installer.sh
   ```

## 2. Trouver la vidéo à produire
- Lis la collection `videos` de la régie. Prends la vidéo dont le `creneau` est le plus proche dans le futur avec un statut `planifiée` (ou celle que la tâche ou le PDG désigne).
- Si une spécification existe déjà (`~/atelier/productions/<id>.json`), repars d'elle : le script est validé, refais seulement la vérification des chiffres datés, l'estimation de durée, puis la production.
- Passe le statut à `script` et ajoute une ligne au `journal` (`{t, agent, msg}`).

## 3. Écrire le script (scénariste)
Respecte la fiche chaîne : vise 11 à 14 minutes (plancher absolu 10 minutes, exigé pour la monétisation), ouverture en « pattern interrupt », une boucle de curiosité toutes les ~45 s, tutoiement, ton conversationnel, aucune intro générique, fin = teaser de la vidéo suivante + abonnement + question en commentaire. La durée vient de la densité : cas chiffrés, nuances, erreurs fréquentes, règles méconnues. Jamais de remplissage.

Écris la spec JSON dans `~/atelier/productions/<id>.json` sur le modèle de `finance-fr-001.json` :
- Champs racine : `id`, `chaine`, `titre`, `titre_youtube` (≤ 100 car., mot-clé principal au début), `accroche` (2 phrases pour la description), `tags` (8 à 12), `hashtags` (3), `miniature` `{chiffre, l1, l2, ton}`, `voix` (repli local de test : `{"modele":"fr_FR-upmc-medium.onnx","locuteur":1,"vitesse":0.97}`), `voix_studio` (copie exacte de la variante de la fiche chaîne qui correspond au numéro de la vidéo : impair = Marc, pair = Rémy), `verification` `{date, sources[]}`, `scenes[]`.
- Chaque scène : `{"chapitre"?, "visuel": {...}, "voix": "texte lu"}`. Le moteur découpe la voix en phrases (un plan par phrase). Dans les scènes « parlées » (titre, section, chiffre, citation), il crée automatiquement un gros chiffre ou une phrase choc par phrase. Dans les scènes de données, il garde le visuel et recadre à chaque phrase : chaque phrase doit alors commenter ce qui s'affiche.
- Visuels disponibles :
  - `titre` `{lignes[], accent?: index}` · `section` `{titre, sous?}` (ouvre un chapitre) · `citation` `{lignes[]}` · `punch` `{lignes[], ton?}`
  - `chiffre` `{valeur, label?, couleur?: accent|positif|negatif, compteur?: bool}`
  - `equation` `{termes: [[valeur, légende?, ton?], ["+"], …]}`
  - `ledger` `{titre?, lignes: [[libellé, montant, ton?]], total?: [libellé, montant, ton?]}`
  - `barres` `{titre?, items: [[libellé, valeur numérique, étiquette, ton?]]}` (4 éléments au plus)
  - `liste` `{titre?, items[]}` · `comparatif` `{colonnes: [{titre, ton, lignes[]}]}`
  - `courbe` `{titre?, axe_x[], series: [{nom, ton, fin, points[]}]}`
- Mets `chapitre` sur les scènes qui ouvrent une partie (6 à 9 chapitres) : il sert aux chapitres YouTube et aux changements d'ambiance.
- Écris les chiffres en format français dans la voix (« 31,4 % », « 15 700 € ») : le studio les lit correctement.

## 4. Vérifier (vérificateur & conformité) — bloquant
- Chaque chiffre, taux, date et règle juridique doit être confirmé le jour même par une source officielle ou primaire (Insee, Banque de France, Caisse des dépôts, AMF, Légifrance/CGI, info.gouv.fr, service-public.fr, rapports SPIVA de S&P DJI…), ou à défaut par une source spécialisée reconnue citant le texte. Cherche avec WebSearch/WebFetch ; lis la source, ne te fie pas à ta mémoire.
- Refais les calculs en Python et consigne-les dans `verification.sources` (« Calculs : … »).
- Chiffre non vérifiable : retire-le ou reformule. S'il est central : statut `bloquée`, motif précis, arrêt.
- Conformité : contenu éducatif, aucune recommandation personnalisée ni de produit nominatif, mention « ce n'est pas un conseil en investissement » dans la vidéo, aucun lien affilié, aucun contenu protégé.
- Passe le statut à `vérifiée`.

## 5. Estimer la durée — bloquant, avant toute commande au studio
```bash
cd ~/atelier && python3 moteur/estimer_duree.py productions/<id>.json
```
- Code 0 (estimation ≥ 10 min 30 avec la voix studio prévue) : continue.
- Code 4 : ajoute une ou plusieurs séquences utiles et vérifiées, puis réestime. Ne commande jamais la voix au studio pour une vidéo trop courte : le quota gratuit Azure est limité (500 000 caractères par mois).

## 6. Produire (voix, montage, miniature, description, quai)
```bash
cd ~/atelier && python3 moteur/pipeline.py productions/<id>.json ~/prod/<id> --studio ~/studio --quai ~/quai
```
- Compte 30 à 60 minutes (studio puis rendu). Lance la commande en arrière-plan et surveille le fichier de sortie.
- Code 0 : `~/prod/<id>/resultat.json` contient `url_video` et `release` (vidéo), `url_miniature` et `release_miniature` (miniature), `description`, `duree`, `chapitres`, `miniature`, `voix`.
- Code 4 (durée réelle < 10 min) : allonge le script avec du contenu utile et vérifié, puis relance.
- Si `resultat.json` contient `alerte_voix` (studio indisponible, donc voix locale) : ne remets PAS la vidéo à la publication. Statut `bloquée`, motif « voix premium indisponible » avec le message d'erreur du studio (`~/studio/commandes/<commande>.json`), et signale-le au PDG. La voix locale est réservée aux tests.
- Code 5 : relance une fois, puis statut `bloquée` avec le message d'erreur.

## 7. Contrôle qualité (avant remise)
- Planche contact : `ffmpeg -i <video> -vf "select='isnan(prev_selected_t)+gte(t-prev_selected_t,20)',scale=480:-1,tile=5x6" -frames:v 1 -vsync vfr planche.png`, puis lis l'image. Vérifie : aucun texte coupé ou collé au bord, aucun chevauchement, aucun plan vide, chiffres identiques au script vérifié.
- Écoute un extrait : extrais 20 secondes (`ffmpeg -ss 60 -t 20 -i <video> extrait.mp3`) et vérifie avec la transcription du studio (`~/prod/<id>/audio_studio/b*.json`) que les sigles et les chiffres sont bien lus.
- Son : `ffmpeg -i <video> -af ebur128 -f null -` → intégré entre −18 et −14 LUFS.
- Défaut visuel : corrige la spec (texte plus court, découpage) et relance. Ne livre jamais une vidéo défectueuse.

## 8. Remettre à la publication
- Mets à jour le document de la vidéo dans la régie : `statut: "packagée"`, `titre`, `duree_s`, `url_video`, `release`, `url_miniature`, `release_miniature`, `resume` (une phrase), `maj`.
- Pousse la spec finale sur la branche `atelier` (`git -C ~/atelier add productions && git -C ~/atelier commit -m "spec <id>" && git -C ~/atelier push`).
- Enchaîne immédiatement avec le skill `regie-publication`, section A (programmation dans Metricool), dans la même session.
- Journal : une ligne par étape importante.
