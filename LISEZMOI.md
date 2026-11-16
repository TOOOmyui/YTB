# Atelier de la régie

Branche « atelier » : tout ce qu'un agent programmé doit installer pour produire une vidéo.

- `entreprise/manuel.md` : organisation, fiches de poste, règles (à lire en premier).
- `entreprise/chaines/*.md` : une fiche par chaîne (ligne éditoriale, voix, charte, créneaux).
- `moteur/` : production (pipeline.py = chaîne complète ; produire2.py = rendu v2 ; voix_studio.py ; publier.py).
- `moteur/clips/` : shorts de clips Twitch (tournee.py = repérage, téléchargement, montage vertical ; lancé par le workflow « Clips » de `main`).
- `productions/*.json` : spécifications des vidéos produites (modèles pour les suivantes).

Autres branches du même dépôt : `studio` (studio voix, GitHub Actions) · `quai` (diffusion des vidéos par release publique) · `clips` (file d'attente et historique des shorts de clips).
