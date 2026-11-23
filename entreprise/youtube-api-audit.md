# Publication YouTube par l'API — mise en place et dossier d'audit

Décision du PDG (23/11/2026) : publication YouTube gratuite par notre propre projet Google (API YouTube Data v3), sans intermédiaire payant. Tant que l'audit n'est pas accordé, YouTube verrouille en privé toute vidéo envoyée par l'API (sans appel possible) : la publication automatique est suspendue (`publication.youtube_verifie: false`) et les shorts sont postés à la main depuis le centre de contrôle (⬇ Télécharger, puis ✓ Marquer publié).

## 1. Mise en place (PDG, environ 20 minutes)

### A. Projet Google Cloud
1. console.cloud.google.com → sélecteur de projet → **Nouveau projet** → nom « Regie Clips » → Créer.
2. **API et services → Bibliothèque** → « YouTube Data API v3 » → **Activer**.
3. **Google Auth Platform** (écran de consentement OAuth) → Commencer :
   - nom de l'application « Regie Clips », e-mail d'assistance : ton adresse ;
   - audience **Externe** ; coordonnées : ton adresse ; accepter → Créer.
4. **Accès aux données** (Data access) → Ajouter des champs d'application → cocher `.../auth/youtube.upload` → Mettre à jour → Enregistrer.
5. **Audience** → **Publier l'application** → Confirmer (statut « En production »). Indispensable : en mode « Test », le jeton expire au bout de 7 jours.
6. **Clients** → Créer un client → type **Application Web** → nom « Regie Clips » → URI de redirection autorisés : `https://developers.google.com/oauthplayground` → Créer. Copier l'**ID client** et le **code secret du client**.

### B. Jeton d'actualisation (OAuth Playground)
1. developers.google.com/oauthplayground → roue dentée (en haut à droite) → cocher **Use your own OAuth credentials** → coller l'ID client et le code secret.
2. Étape 1, champ « Input your own scopes » : `https://www.googleapis.com/auth/youtube.upload` → **Authorize APIs**.
3. Choisir le compte Google de la chaîne, puis **la chaîne** (Clear Assets) si un choix de chaîne s'affiche. Écran « Google n'a pas validé cette application » → Paramètres avancés → Accéder à Regie Clips → Continuer.
4. Étape 2 → **Exchange authorization code for tokens** → copier le **Refresh token**.

### C. Secrets GitHub (dépôt TOOOmyui/YTB → Settings → Secrets and variables → Actions → New repository secret)
- `YT_CLIENT_ID` : l'ID client.
- `YT_CLIENT_SECRET` : le code secret du client.
- `YT_REFRESH_TOKEN` : le refresh token.

### D. Vérification
Centre de contrôle → Tableau de bord → **Tester l'envoi YouTube (privé)**. Une vidéo privée apparaît dans YouTube Studio (à supprimer ensuite) : la chaîne d'envoi fonctionne.

### E. Demande d'audit
Formulaire : https://support.google.com/youtube/contact/yt_api_form — réponses ci-dessous (en anglais, langue de traitement). Le **numéro de projet** se trouve sur le tableau de bord de la console Google Cloud.
À réception de l'accord : Réglages → Publication → cocher « Audit accordé par YouTube » → la publication automatique démarre au créneau suivant.

## 2. Réponses du formulaire d'audit (à coller)

- **Request type** : Complete a compliance audit (unverified API project — uploads currently locked to private).
- **Organization** : Individual / sole operator — Thomas Kames, France. Category : Media & Entertainment (Gaming).
- **API Client name** : Régie Clips
- **API Client description** :
  > Régie Clips is a private, internal automation tool used by a single operator to publish YouTube Shorts to one channel that he owns. It takes short Twitch gameplay clips (Grand Theft Auto VI), reformats them to vertical 9:16, adds a text hook, automatic subtitles and an on-screen credit to the original streamer (twitch.tv/<name>), then uploads them to the operator's own channel. Every video description links to the original clip and the streamer's channel, and removal requests are honoured within a day. The tool has no other users, no public interface and no login for third parties.
- **How users access the API Client** : Not accessible to anyone but the operator. It runs as a scheduled GitHub Actions job and a private control page used only by the operator.
- **YouTube API Services used** : YouTube Data API v3 — `videos.insert` only. OAuth scope : `https://www.googleapis.com/auth/youtube.upload`, granted by the channel owner for his own channel.
- **Expected volume** : up to 4 uploads per day; the default quota is sufficient — no quota increase requested.
- **Data stored** : the OAuth refresh token (encrypted GitHub secret) and, for each upload, its title, video ID and date in private records to prevent duplicates. No data about viewers or other users is accessed or stored.
- **Data sharing / monetization of API data** : none. API data is not sold, shared or used for advertising. The channel itself may earn YouTube Partner Program revenue under standard YouTube rules.
- **Privacy policy URL** : https://github.com/TOOOmyui/YTB/blob/main/docs/confidentialite.md
- **Compliance** : I have read and agree to the YouTube API Services Terms of Service and Developer Policies.

## 3. Risque à connaître
L'audit contrôle le respect des conditions de YouTube, y compris les droits sur les contenus publiés. Des clips de streamers repris sans leur accord, même crédités, peuvent motiver un refus. Les réponses ci-dessus décrivent l'usage tel qu'il est : ne pas l'enjoliver. En cas de refus : formulaire d'appel (https://support.google.com/youtube/contact/yt_api_appeals), ou bascule vers des streamers ayant donné leur accord (`mode: liste_blanche`).
