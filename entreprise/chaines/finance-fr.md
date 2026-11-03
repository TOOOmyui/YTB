# Fiche chaîne — Clear Assets (finance-fr)

- **Nom public** : Clear Assets (décision du PDG, 02/11/2026) — devise : « La finance personnelle, textes et chiffres à l'appui »
- **Identifiant interne** : finance-fr
- **Langue** : français
- **Statut** : active (lancement)
- **Plateformes** : YouTube (vidéos longues ; Shorts et Reels en pause) — via Metricool, marque 7683914
- **Chaîne YouTube** : vérifiée par téléphone le 03/11/2026 (miniatures personnalisées et vidéos de plus de 15 min autorisées)
- **Voix** : deux voix en alternance d'une vidéo à l'autre (décision du PDG, 02/11/2026) — Marc énergique (Azure fr-FR-Marc:MAI-Voice-2.1, style « excited ») pour les vidéos de numéro impair, Rémy HD (Azure fr-FR-Remy:DragonHDLatestNeural) pour les vidéos de numéro pair. Voix exclusives de la chaîne. La voix locale (Piper) sert uniquement aux tests : jamais de publication avec elle.
- **voix_studio** (à copier tel quel dans chaque spec selon le numéro de la vidéo) :
  - numéro impair (001, 003, 005…) : `{"fournisseur": "azure", "voix": "fr-FR-Marc:MAI-Voice-2.1", "style": "excited", "debit": "+0%"}`
  - numéro pair (002, 004, 006…) : `{"fournisseur": "azure", "voix": "fr-FR-Remy:DragonHDLatestNeural", "debit": "+0%"}`
- **Vitesses étalonnées sur vidéos complètes (02/11)** : Marc ≈ 3 % plus rapide que la voix de test au débit naturel, Rémy ≈ 2 % plus rapide. `moteur/estimer_duree.py` applique ces coefficients.

## Identité visuelle
- Monogramme « CA » dans un médaillon à double filet, typographie Libre Baskerville ; couleurs : beige papier #FAF7F0 / #F0E8D8, encre bleu nuit #1B2433, or #B0843C.
- Fichiers : `marque/finance-fr/` (logo 800 px, bannière 2560×1440, pastille 160 px pour le filigrane YouTube et les miniatures).
- Miniatures : fond beige, gros chiffre en couleur (rouge = coût, vert = gain, ambre = neutre), bandeau bleu nuit, signature « CLEAR ASSETS » en bas à droite.

## Ligne éditoriale
- Finance personnelle pour les particuliers français : épargne, placements, fiscalité, frais bancaires, immobilier, retraite.
- Fondée sur des statistiques et des sources officielles ; angle « ce que ta banque ne te dit pas », sans complotisme ni promesse de gain.
- Avantage distinctif : précision juridique et fiscale française.

## Format des scripts
- Vidéos longues : 11 à 14 minutes visées, **plancher absolu de 10 minutes** (le pipeline refuse en dessous) ; avant toute commande au studio, `estimer_duree.py` doit donner au moins 10 min 30 (décision du PDG ; au-delà du seuil de 8 minutes des publicités en milieu de vidéo). Environ 1 700 à 2 300 mots de voix selon la voix. La durée vient de la densité (cas chiffrés, nuances, erreurs fréquentes), jamais du remplissage : la rétention prime.
- Réels / Shorts : **en pause** (décision du PDG du 02/11/2026). Ne pas en produire ni en programmer jusqu'à nouvel ordre.
- Pas d'intro générique ; ouverture par un pattern interrupt.
- Une nouvelle boucle de curiosité environ toutes les 45 secondes.
- Ton conversationnel, tutoiement, non corporate ; chaque section enchaîne sur la suivante.
- Montage légèrement plus dynamique que la vidéo n°1.
- Fin : teaser de la vidéo suivante + appel à l'abonnement + question ouverte.

## Charte visuelle (moteur v2 — validée par le PDG le 27/10/2026)
- Montage dynamique et rapide, jamais monotone : un plan par phrase (changement toutes les 2 à 4 secondes), caméra toujours en mouvement (poussée lente, recadrages à chaque phrase, coups de zoom sur les chiffres), transitions rapides avec effets sonores.
- Sous-titres mot à mot, mot prononcé surligné dans la couleur d'accent.
- Ambiances : dominante claire et épurée — blanc, beige papier, gris perle — plus une ambiance sombre « nuit ». Elles alternent à chaque chapitre au sein d'une vidéo, et l'ordre de rotation change d'une vidéo à l'autre.
- Typographie Inter (gras/noir pour les titres et chiffres) ; accent ambre, vert pour les gains, rouge pour les coûts.
- Types de plans : chiffre clé animé, phrase choc, titre, équation, tableau comptable, barres, courbe, liste, comparatif, carte de chapitre.
- Musique électro sobre générée par la régie (libre de droits), atténuée sous la voix.
- Le scénariste découpe chaque scène en phrases courtes ; dans les scènes de données, chaque phrase doit commenter ce qui apparaît à l'écran.

## Miniatures
- 1280×720, générées par `moteur/miniature.py` depuis le champ `miniature` de la spec ; publiées sur le quai (`url_miniature`).
- Miniatures personnalisées YouTube : **actives** — chaîne vérifiée par le PDG le 03/11/2026. Chaque post Metricool envoie `videoThumbnailUrl: url_miniature` ; la release de la miniature n'est nettoyée qu'après confirmation de l'import (l'URL renvoyée par Metricool commence par static.metricool.com).
- Toute miniature porte la signature Clear Assets (pastille + nom) : `pipeline.py` l'ajoute automatiquement pour la chaîne finance-fr.

## Conformité propre
- Mention « ce n'est pas un conseil en investissement » dans chaque vidéo et chaque description.
- Aucune recommandation de produit nominatif à acheter ; comparaisons de catégories uniquement.

## Créneaux
- Longues : lun., mer., ven., dim. 18:00 Europe/Paris
- Réels : en pause (décision du PDG du 02/11/2026)

## Voix réservées aux futures chaînes
- Tom (fr_FR-tom-medium), Jessica (fr_FR-upmc-medium, locuteur 0), Siwis (fr_FR-siwis-medium).
