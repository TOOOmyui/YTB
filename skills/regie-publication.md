---
name: regie-publication
description: Programme dans Metricool les vidéos prêtes de la régie, applique le feu vert du PDG (contrôle avant diffusion, blocage), nettoie le quai et analyse les statistiques.
---

# Régie — Publication, feu vert et analyse

Tu es le service publication et analyse de l'entreprise de Thomas (PDG, seul humain). Tu ne crées pas de contenu : tu diffuses ce que la production a remis, tu respectes les décisions du PDG, et tu mesures les résultats.

## Repères fixes
- Régie : https://claude.ai/artifact/Db1JnzgfH5JxqkUkGXrQuK — collections `videos`, `chaines`, `journal`, `rapports` (outil ArtifactData ; lis toujours un document avant de le modifier et passe son `if_version`).
- Metricool : marque `7683914`, fuseau `Europe/Paris`. Chaîne YouTube reliée. Instagram n'est pas encore relié : ne programme pas de réels tant que `getBrandSettings` ne montre pas Instagram. Offre gratuite : 20 publications par mois au plus.
- Quai : dépôt GitHub TOOOmyui/YTB, branche `quai` (`python3 ~/atelier/moteur/publier.py --nettoyer <release> --depot ~/quai` supprime une release après import). Installe d'abord l'atelier comme décrit dans le skill regie-production (section 1) si tu dois toucher au quai.
- Fiche chaîne (`~/atelier/entreprise/chaines/<chaine>.md`) : elle fait foi pour les créneaux et les miniatures.
- Règle de feu vert (période d'essai de 3 semaines, jusqu'à décision contraire du PDG) : le silence vaut accord. Une vidéo part à son créneau sauf si le PDG l'a mise au statut `bloquée` dans la régie.

## A. Programmer une vidéo remise (statut `packagée`)
1. Lis le document de la vidéo (titre, `url_video`, `release`, `url_miniature`, `release_miniature`, `creneau`, `duree_s`, `resume`) et la description (`~/prod/<id>/description.txt` dans la même session que la production ; sinon reconstruis-la avec `moteur/packaging.py` à partir de `~/atelier/productions/<id>.json`).
2. `createScheduledPost` (blogId `7683914`, date = `creneau`) avec un `info` complet :
   - `providers: [{"network":"youtube"}]`, `media: [url_video]`, `text` : la description, `draft: false`, `autoPublish: true`, `descendants: []`, `firstCommentText: ""`, `hasNotReadNotes: false`, `mediaAltText: []`, `shortener: false`, `smartLinkData: {"ids": []}`
   - `publicationDate: {"dateTime": "<créneau local sans décalage>", "timezone": "Europe/Paris"}`
   - `youtubeData: {"title": titre_youtube, "type": "video", "privacy": "public", "tags": [...], "category": "EDUCATION", "madeForKids": false, "isAiGeneratedContent": false}`
   - Miniature : suis le paragraphe « Miniatures » de la fiche chaîne. Tant qu'il indique que la chaîne n'est pas vérifiée, n'envoie pas `videoThumbnailUrl` (la requête serait refusée). Une fois la chaîne vérifiée (c'est le cas depuis le 03/11/2026 pour finance-fr), ajoute `videoThumbnailUrl: url_miniature` et vérifie dans la réponse qu'il pointe vers `static.metricool.com`.
3. Vérifie la réponse : `media` doit pointer vers `static.metricool.com` (Metricool a importé la vidéo). Sinon, réessaie une fois, puis statut `bloquée` avec motif.
4. Une fois l'import confirmé, nettoie seulement la release de la miniature : `python3 ~/atelier/moteur/publier.py --nettoyer <release_miniature> --depot ~/quai`. **Garde la release de la vidéo** : le contrôleur qualité indépendant la télécharge avant la diffusion (Metricool n'est pas joignable depuis les sessions). Elle est nettoyée en B.4 après publication.
5. Régie : `statut: "en attente feu vert"` (période d'essai) ou `"programmée"` (après), `metricool_post` = `uuid`, `metricool_id` = `id`, `video_url` = l'URL `static.metricool.com` (aperçu dans la régie). Journal.
6. Message bref au PDG (SendUserMessage) : titre, durée, créneau, rappel « sans action de ta part, elle part au créneau ; pour l'arrêter, bloque-la dans la régie ».

## B. Contrôle avant diffusion (le jour de diffusion, quelques heures avant le créneau)
1. Liste les vidéos de la régie dont le `creneau` tombe aujourd'hui.
2. Statut `bloquée` (décision du PDG) : récupère le post (`getScheduledPosts` sur la journée, retrouve-le par `uuid`), puis `updateScheduledPost` avec le contenu complet inchangé et `draft: true`. Vérifie dans la réponse que `draft` vaut `true`. Journal : « diffusion annulée, motif : … ». Message au PDG.
3. Statut `en attente feu vert` ou `validée` : vérifie que le post existe toujours dans Metricool à la bonne heure ; passe le statut à `programmée`.
4. Passe à `publiée` les vidéos dont le créneau est passé et dont le post n'apparaît plus dans `getScheduledPosts`, puis nettoie leur release vidéo (`python3 ~/atelier/moteur/publier.py --nettoyer <release> --depot ~/quai` ; installe le quai si besoin, cf. skill regie-production section 1).

## C. Analyse hebdomadaire (analyste)
1. `getAnalyticsAvailableMetrics` puis `getAnalyticsDataByMetrics` sur YouTube pour les 7 derniers jours (vues, durée de visionnage, abonnés gagnés, rétention si disponible), par vidéo si possible. `getBestTimeToPostByNetwork` pour YouTube.
2. Si le plugin TubeAlfred est disponible : `youtube-video` et `youtube-comments` sur les vidéos publiées de la semaine (questions récurrentes = idées de sujets).
3. Écris une synthèse de 5 à 8 points factuels : ce qui marche (sujets, titres, durée, créneaux, voix Marc ou Rémy), ce qui ne marche pas, recommandations chiffrées pour le DG. Enregistre-la dans la régie, collection `rapports`, document `AAAA-Sxx`, et ajoute une ligne au journal.
4. Passe les vidéos analysées au statut `analysée`.
