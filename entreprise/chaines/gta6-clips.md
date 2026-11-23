# Fiche chaîne — Clips GTA 6 (gta6-clips)

- **Statut** : en préparation (16/11/2026). Moteur prêt et testé ; ouverture suspendue aux 4 décisions du PDG listées en bas de fiche.
- **Décision de cap** (PDG, 13/11/2026) : à la sortie de GTA 6 (annoncée le 19/11/2026), la chaîne YouTube de Clear Assets est réutilisée pour des clips Twitch de GTA 6 ; même contenu en Reels sur le compte Instagram « ÇA ».
- **Identifiant interne** : gta6-clips · **Langue** : français · **Nom public** : à choisir par le PDG.
- **Plateformes** : YouTube Shorts ; Instagram Reels dès que le compte est relié à Upload-Post. Publication par Metricool, offre gratuite, comme les vidéos longues (décision du PDG du 23/11/2026, « publie comme tu publies les vidéos YouTube ») : une session Claude programmée programme les shorts de la file. Plafond de l'offre gratuite : 20 publications par mois, vidéos longues comprises — 1 short par jour au plus. Voie API YouTube directe préparée en réserve (audit nécessaire). Mise en place et dossier d'audit : `entreprise/youtube-api-audit.md`. Tant que l'audit n'est pas accordé, publication à la main depuis le centre de contrôle.
- **Pilotage** : centre de contrôle `docs/index.html` (branche `main`) — file des clips, validation, rejet, publication immédiate, pause, mode de publication, réglages, journal.
- **Réglages machine** : `entreprise/chaines/gta6-clips.json` (jeu, filtres, liste blanche, hashtags). Cette fiche explique, le JSON commande.

## Ligne éditoriale
- Les moments de stream GTA 6 qui provoquent une réaction : chute, poursuite qui dégénère, bug, fou rire, exploit, découverte.
- Un short = un moment, compréhensible sans contexte, 12 à 59 secondes.
- Toujours le streamer à l'honneur : son nom à l'écran, son lien en description.
- Refusé : contenu humiliant pour une personne, propos haineux, nudité, « drama » entre streamers, fuites. Les titres de clips contenant un mot de `mots_interdits` sont écartés d'office.

## Crédit — règle bloquante (décision du PDG du 16/11/2026, remplace la liste blanche)
- Mode « ouvert » : la régie clippe tous les streamers francophones du jeu, sans accord préalable, **toujours crédités** : `twitch.tv/<login>` à l'écran pendant tout le short, lien du clip original et de la chaîne Twitch en description.
- Un clip dont le login de la chaîne ne peut pas être établi est écarté : pas de crédit, pas de short.
- Retrait : sur demande d'un streamer (commentaire, message, réclamation), le short est supprimé le jour même et son login entre dans `streamers_exclus`. La description de chaque short l'indique.
- Risque assumé par le PDG : réclamations pour atteinte aux droits d'auteur (avertissements YouTube) et politique « contenu réutilisé » pour la monétisation.

## Format et charte
- 1080×1920, 12 à 59 s, son normalisé à −14 LUFS.
- Fond : le clip agrandi et flouté. Image complète du stream au centre (facecam et incrustations du streamer visibles, décision du 23/11/2026 après contrôle des premiers shorts) ; si la zone de facecam du streamer est renseignée (`facecam: [x, y, largeur, hauteur]` en fractions de l'image), facecam en haut et jeu dessous.
- Accroche en capitales en haut (8 mots au plus, lisible en 1 seconde, sans piège à clics : elle décrit ce qui se passe vraiment).
- Crédit `twitch.tv/<login>` à l'écran pendant tout le short.
- Sous-titres « pop » par groupes de 1 à 3 mots, générés par transcription ; si la transcription est douteuse, pas de sous-titres plutôt que des sous-titres faux.
- Rien d'important sous 1 560 px ni dans la colonne de boutons à droite (interface Shorts/Reels).

## Titres et descriptions
- Titre : 60 caractères au plus, ce qui se passe + nom du streamer ; « GTA 6 » dans le titre ou les hashtags. Le titre du clip Twitch sert de brouillon ; l'agent de programmation le réécrit.
- Description : une phrase, lien du clip original, lien de la chaîne Twitch, ligne de crédit, ligne « retrait sur demande », hashtags `#GTA6 #Twitch #Shorts`.
- YouTube : type `short`, catégorie `GAMING`, `madeForKids: false`, `isAiGeneratedContent: false`.

## Chaîne de fabrication
1. **Tournée** (workflow `Clips` sur `main`, toutes les 3 h) : `moteur/clips/tournee.py` repère → télécharge → monte → dépose les fichiers en release `clips-AAAAMMJJ` et un manifeste par short dans `file/` (branche `clips`, statut « montée »).
2. **Contrôle** (centre de contrôle, facultatif) : titre retouché, short validé ou rejeté.
3. **Publication** (workflow `Publier` sur `main`, toutes les heures, ou bouton « Publier maintenant ») : `moteur/clips/publier.py` envoie par l'API YouTube (ou Upload-Post selon `publication.fournisseur`) au créneau ouvert, seulement une fois l'audit accordé (`youtube_verifie`) ; avant, publication à la main (⬇ Télécharger, ✓ Marquer publié) ; mode « auto » = meilleur short de la file, mode « manuel » = shorts validés seulement. Manifeste déplacé dans `publies/`, journal `publications.json`. Deux échecs → statut « bloquée ». Un short non publié sous 96 h passe dans `rejetes/` (fichier expiré).
4. **Analyse** : avec le rapport hebdomadaire de l'analyste.

## Créneaux (hypothèse de départ, à ajuster par l'analyste après 2 semaines)
- 4 shorts par jour : 12:30, 15:30, 18:00, 21:00 (Europe/Paris) — réglables dans le centre de contrôle (`publication.creneaux`, `max_par_jour`).
- Jamais deux shorts du même streamer à la suite.

## Conformité propre
- Jeu classé PEGI 18 : pas de scène de violence gratuite montée pour choquer, pas de nudité ; en cas de doute, le short n'est pas programmé.
- Musique : les radios du jeu diffusent des titres sous licence, que YouTube et Instagram peuvent détecter. Un short dont la musique de radio couvre l'action est écarté au contrôle.
- Conditions d'utilisation de Rockstar Games sur les vidéos de jeu : à relire par le Vérificateur le jour de la sortie, avant le premier short.

## Décisions attendues du PDG
1. **Application Twitch** : créer l'application sur dev.twitch.tv et déposer `TWITCH_CLIENT_ID` et `TWITCH_CLIENT_SECRET` dans les secrets du dépôt GitHub (les agents ne manipulent pas ces identifiants).
2. **Publication** : Metricool écarté par le PDG (16/11/2026) ; canal de publication à choisir.
3. **API YouTube** : projet Google Cloud, secrets `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`, demande d'audit (voir `entreprise/youtube-api-audit.md`).
4. **Clear Assets** : sort des vidéos finance 008 (18/11) et 009 (20/11), nouveau nom et habillage de la chaîne.
