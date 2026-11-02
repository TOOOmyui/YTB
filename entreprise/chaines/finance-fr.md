# Fiche chaîne — Finance (FR)

- **Identifiant** : finance-fr
- **Langue** : français
- **Statut** : active (lancement)
- **Plateformes** : YouTube (vidéos longues + Shorts), Instagram Reels — via Metricool, marque 7683914
- **Voix** : deux voix en alternance d'une vidéo à l'autre (décision du PDG, 02/11/2026) — Marc énergique (Azure fr-FR-Marc:MAI-Voice-2.1, style « excited ») pour les vidéos de numéro impair, Rémy HD (Azure fr-FR-Remy:DragonHDLatestNeural) pour les vidéos de numéro pair. Voix exclusives de la chaîne. La voix locale (Piper) sert uniquement aux tests : jamais de publication avec elle.
- **voix_studio** (à copier tel quel dans chaque spec selon le numéro de la vidéo) :
  - numéro impair (001, 003, 005…) : `{"fournisseur": "azure", "voix": "fr-FR-Marc:MAI-Voice-2.1", "style": "excited", "debit": "+6%"}`
  - numéro pair (002, 004, 006…) : `{"fournisseur": "azure", "voix": "fr-FR-Remy:DragonHDLatestNeural", "debit": "+0%"}`
- **Vitesses mesurées** (même phrase, casting du 02/11) : Marc ≈ 17 % plus lent que la voix de test, Rémy (débit naturel) ≈ 2 % plus lent. `moteur/estimer_duree.py` applique ces coefficients.

## Ligne éditoriale
- Finance personnelle pour les particuliers français : épargne, placements, fiscalité, frais bancaires, immobilier, retraite.
- Fondée sur des statistiques et des sources officielles ; angle « ce que ta banque ne te dit pas », sans complotisme ni promesse de gain.
- Avantage distinctif : précision juridique et fiscale française.

## Format des scripts
- Vidéos longues : 11 à 14 minutes visées, **plancher absolu de 10 minutes** (le pipeline refuse en dessous) ; avant toute commande au studio, `estimer_duree.py` doit donner au moins 10 min 30 (décision du PDG ; au-delà du seuil de 8 minutes des publicités en milieu de vidéo). Environ 1 700 à 2 300 mots de voix selon la voix. La durée vient de la densité (cas chiffrés, nuances, erreurs fréquentes), jamais du remplissage : la rétention prime.
- Réels : 30 à 60 secondes.
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
- Miniatures personnalisées YouTube : **en attente de la vérification de la chaîne par le PDG** (youtube.com/verify). Tant que ce n'est pas fait, ne pas envoyer `videoThumbnailUrl` à Metricool (requête refusée). Une fois vérifiée, ce paragraphe est mis à jour et la publication envoie la miniature.

## Conformité propre
- Mention « ce n'est pas un conseil en investissement » dans chaque vidéo et chaque description.
- Aucune recommandation de produit nominatif à acheter ; comparaisons de catégories uniquement.

## Créneaux
- Longues : lun., mer., ven., dim. 18:00 Europe/Paris
- Réels : mar., jeu., sam. 12:30 Europe/Paris

## Voix réservées aux futures chaînes
- Tom (fr_FR-tom-medium), Jessica (fr_FR-upmc-medium, locuteur 0), Siwis (fr_FR-siwis-medium).
