# Fiche chaîne — Clips GTA 6 (gta6-clips)

- **Statut** : en préparation (16/11/2026). Moteur prêt et testé ; ouverture suspendue aux 4 décisions du PDG listées en bas de fiche.
- **Décision de cap** (PDG, 13/11/2026) : à la sortie de GTA 6 (annoncée le 19/11/2026), la chaîne YouTube de Clear Assets est réutilisée pour des clips Twitch de GTA 6 ; même contenu en Reels sur le compte Instagram « ÇA ».
- **Identifiant interne** : gta6-clips · **Langue** : français · **Nom public** : à choisir par le PDG.
- **Plateformes** : YouTube Shorts (marque Metricool 7683914) ; Instagram Reels dès que le compte est relié à Metricool.
- **Réglages machine** : `entreprise/chaines/gta6-clips.json` (jeu, filtres, liste blanche, hashtags). Cette fiche explique, le JSON commande.

## Ligne éditoriale
- Les moments de stream GTA 6 qui provoquent une réaction : chute, poursuite qui dégénère, bug, fou rire, exploit, découverte.
- Un short = un moment, compréhensible sans contexte, 12 à 59 secondes.
- Toujours le streamer à l'honneur : son nom à l'écran, son lien en description.
- Refusé : contenu humiliant pour une personne, propos haineux, nudité, « drama » entre streamers, fuites. Les titres de clips contenant un mot de `mots_interdits` sont écartés d'office.

## Accords — règle bloquante
- **Aucun clip n'est téléchargé ni monté sans accord du streamer.** Le repéreur ne retient que les streamers de `streamers_autorises`, et seulement si le champ `accord` est rempli (date + preuve : mail, message privé, page publique de son programme de clippers).
- Raisons : le clip appartient au streamer (manuel, poste Vérificateur : « aucun extrait protégé ») ; YouTube démonétise le « contenu réutilisé » sans apport ; un retrait pour atteinte aux droits d'auteur vaut avertissement sur la chaîne, trois avertissements la ferment.
- **Prospection** : à chaque tournée, `rapports/prospects.json` (branche `clips`) liste les streamers francophones non autorisés dont les clips GTA 6 marchent le mieux. Le DG les présente au PDG dans le rapport hebdomadaire ; le PDG envoie lui-même la demande (les agents n'écrivent pas aux streamers).
- Modèle de demande : « Bonjour, je lance une chaîne de shorts GTA 6 (YouTube Shorts + Reels). J'aimerais reprendre certains de tes clips Twitch, avec ton nom à l'écran et le lien de ta chaîne en description de chaque vidéo. Si tu préfères un autre format de crédit, ou retirer une vidéo à tout moment, il suffit de me le dire. Est-ce que tu es d'accord ? »
- Retrait : sur demande d'un streamer, le short est supprimé le jour même et le streamer passe dans `streamers_exclus`.

## Format et charte
- 1080×1920, 12 à 59 s, son normalisé à −14 LUFS.
- Fond : le clip agrandi et flouté. Jeu zoomé ×1,33 au centre ; si la zone de facecam du streamer est renseignée (`facecam: [x, y, largeur, hauteur]` en fractions de l'image), facecam en haut et jeu dessous.
- Accroche en capitales en haut (8 mots au plus, lisible en 1 seconde, sans piège à clics : elle décrit ce qui se passe vraiment).
- Crédit `twitch.tv/<login>` à l'écran pendant tout le short.
- Sous-titres « pop » par groupes de 1 à 3 mots, générés par transcription ; si la transcription est douteuse, pas de sous-titres plutôt que des sous-titres faux.
- Rien d'important sous 1 560 px ni dans la colonne de boutons à droite (interface Shorts/Reels).

## Titres et descriptions
- Titre : 60 caractères au plus, ce qui se passe + nom du streamer ; « GTA 6 » dans le titre ou les hashtags. Le titre du clip Twitch sert de brouillon ; l'agent de programmation le réécrit.
- Description : une phrase, lien du clip original, lien de la chaîne Twitch, mention « Diffusé avec l'accord de … », hashtags `#GTA6 #Twitch #Shorts`.
- YouTube : type `short`, catégorie `GAMING`, `madeForKids: false`, `isAiGeneratedContent: false`.

## Chaîne de fabrication
1. **Tournée** (GitHub Actions, workflow `Clips` sur `main`, toutes les 3 h de 6 h 17 à 21 h 17 UTC) : `moteur/clips/tournee.py` repère → télécharge → monte → dépose les fichiers en release `clips-AAAAMMJJ` et un manifeste par short dans `file/` sur la branche `clips`. Jamais plus de 8 shorts en file.
2. **Programmation** (session Claude, skill `regie-clips`) : contrôle visuel de chaque short, réécriture du titre et de l'accroche, programmation Metricool, passage du manifeste de `file/` à `programmes/`.
3. **Analyse** : avec le rapport hebdomadaire de l'analyste (vues à 48 h par streamer, par durée, par créneau).

## Créneaux (hypothèse de départ, à ajuster par l'analyste après 2 semaines)
- 3 shorts par jour : 12:30, 18:00, 21:00 (Europe/Paris). Semaine de sortie : jusqu'à 4 par jour si la file le permet.
- Jamais deux shorts du même streamer à la suite.

## Conformité propre
- Jeu classé PEGI 18 : pas de scène de violence gratuite montée pour choquer, pas de nudité ; en cas de doute, le short n'est pas programmé.
- Musique : les radios du jeu diffusent des titres sous licence, que YouTube et Instagram peuvent détecter. Un short dont la musique de radio couvre l'action est écarté au contrôle.
- Conditions d'utilisation de Rockstar Games sur les vidéos de jeu : à relire par le Vérificateur le jour de la sortie, avant le premier short.

## Décisions attendues du PDG
1. **Application Twitch** : créer l'application sur dev.twitch.tv et déposer `TWITCH_CLIENT_ID` et `TWITCH_CLIENT_SECRET` dans les secrets du dépôt GitHub (les agents ne manipulent pas ces identifiants).
2. **Premiers accords** de streamers à inscrire dans la liste blanche.
3. **Metricool** : l'offre gratuite plafonne à 20 publications par mois (3 shorts par jour ≈ 90) ; relier le compte Instagram « ÇA ».
4. **Clear Assets** : sort des vidéos finance 008 (18/11) et 009 (20/11), nouveau nom et habillage de la chaîne.
