"""Studio voix — exécuté par GitHub Actions (accès Internet), appelé par la régie.

Chaque fichier commandes/<nom>.json non encore traité produit sorties/<nom>/ puis est marqué traité.

Commande « casting » :
  {"mode": "casting", "langue": "fr", "max": 12, "recherche": ["news", "narration"]}
  → sorties/<nom>/voix.json (liste des voix) + apercus/<voice_id>.mp3 (échantillons d'origine)

Commande « essai » (même texte, plusieurs voix de la bibliothèque) :
  {"mode": "essai", "texte": "...", "voix": [{"voice_id": "...", "public_owner_id": "...", "nom": "..."}],
   "model_id": "eleven_multilingual_v2", "reglages": {...}}

Commande « tts » (une vidéo) :
  {"mode": "tts", "voice_id": "...", "model_id": "...", "reglages": {...},
   "beats": ["phrase 1", "phrase 2", ...]}
  → sorties/<nom>/bNNN.mp3 + bNNN.json (minutage mot à mot : [[t0, t1, "mot"], ...])
"""
import base64, json, os, sys, time, urllib.request, urllib.parse, urllib.error

API = 'https://api.elevenlabs.io/v1'
CLE = os.environ.get('ELEVENLABS_API_KEY', '')


def appel(methode, chemin, corps=None, params=None, brut=False):
    url = API + chemin + ('?' + urllib.parse.urlencode(params, doseq=True) if params else '')
    data = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(url, data=data, method=methode,
                                 headers={'xi-api-key': CLE, 'Content-Type': 'application/json', 'Accept': '*/*'})
    for essai in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                contenu = r.read()
                return contenu if brut else json.loads(contenu or b'{}')
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors='replace')[:500]
            if e.code in (429, 500, 502, 503) and essai < 3:
                time.sleep(5 * (essai + 1))
                continue
            raise RuntimeError(f'{methode} {chemin} -> {e.code} {msg}')


def mots_depuis_alignement(al):
    chars = al['characters']
    t0s, t1s = al['character_start_times_seconds'], al['character_end_times_seconds']
    mots, cur, deb, fin = [], '', None, None
    for c, a, b in zip(chars, t0s, t1s):
        if c.isspace():
            if cur:
                mots.append([round(deb, 3), round(fin, 3), cur])
            cur, deb = '', None
            continue
        if deb is None:
            deb = a
        cur += c
        fin = b
    if cur:
        mots.append([round(deb, 3), round(fin, 3), cur])
    return mots


def tts(voice_id, texte, model_id, reglages, prev=None, suiv=None):
    corps = {'text': texte, 'model_id': model_id, 'voice_settings': reglages or {}}
    if prev:
        corps['previous_text'] = prev
    if suiv:
        corps['next_text'] = suiv
    r = appel('POST', f'/text-to-speech/{voice_id}/with-timestamps', corps, {'output_format': 'mp3_44100_128'})
    return base64.b64decode(r['audio_base64']), mots_depuis_alignement(r.get('alignment') or r['normalized_alignment'])


def telecharger(url, chemin):
    with urllib.request.urlopen(url, timeout=60) as r:
        open(chemin, 'wb').write(r.read())


def casting(c, dossier):
    os.makedirs(os.path.join(dossier, 'apercus'), exist_ok=True)
    vues, liste = set(), []
    for terme in c.get('recherche', ['']):
        params = {'language': c.get('langue', 'fr'), 'page_size': 30, 'sort': 'cloned_by_count'}
        if terme:
            params['search'] = terme
        if c.get('genre'):
            params['gender'] = c['genre']
        r = appel('GET', '/shared-voices', params=params)
        for v in r.get('voices', []):
            if v['voice_id'] in vues:
                continue
            vues.add(v['voice_id'])
            liste.append({k: v.get(k) for k in ('voice_id', 'public_owner_id', 'name', 'gender', 'age', 'accent',
                                                 'descriptive', 'use_case', 'category', 'description', 'preview_url',
                                                 'cloned_by_count', 'language')})
    liste = liste[:c.get('max', 12)]
    for v in liste:
        if v.get('preview_url'):
            try:
                telecharger(v['preview_url'], os.path.join(dossier, 'apercus', v['voice_id'] + '.mp3'))
            except Exception as e:
                v['erreur_apercu'] = str(e)
    json.dump(liste, open(os.path.join(dossier, 'voix.json'), 'w'), ensure_ascii=False, indent=1)


def ajouter_voix(v):
    """Ajoute une voix de la bibliothèque partagée au compte (nécessaire pour l'utiliser)."""
    mes = appel('GET', '/voices').get('voices', [])
    if any(m['voice_id'] == v['voice_id'] for m in mes):
        return v['voice_id']
    r = appel('POST', f"/voices/add/{v['public_owner_id']}/{v['voice_id']}", {'new_name': v.get('nom') or v['voice_id']})
    return r.get('voice_id', v['voice_id'])


def essai(c, dossier):
    os.makedirs(dossier, exist_ok=True)
    rapport = []
    for v in c['voix']:
        try:
            vid = ajouter_voix(v) if v.get('public_owner_id') else v['voice_id']
            audio, mots = tts(vid, c['texte'], c.get('model_id', 'eleven_multilingual_v2'), c.get('reglages'))
            nom = (v.get('nom') or vid).replace('/', '-')
            open(os.path.join(dossier, nom + '.mp3'), 'wb').write(audio)
            rapport.append({'nom': nom, 'voice_id': vid, 'ok': True})
        except Exception as e:
            rapport.append({'nom': v.get('nom'), 'voice_id': v.get('voice_id'), 'ok': False, 'erreur': str(e)})
    json.dump(rapport, open(os.path.join(dossier, 'rapport.json'), 'w'), ensure_ascii=False, indent=1)


def production(c, dossier):
    os.makedirs(dossier, exist_ok=True)
    beats = c['beats']
    for i, txt in enumerate(beats):
        cible = os.path.join(dossier, f'b{i:03d}.mp3')
        if os.path.exists(cible):
            continue
        prev = ' '.join(beats[max(0, i - 2):i]) or None
        suiv = beats[i + 1] if i + 1 < len(beats) else None
        audio, mots = tts(c['voice_id'], txt, c.get('model_id', 'eleven_multilingual_v2'), c.get('reglages'), prev, suiv)
        open(cible, 'wb').write(audio)
        json.dump(mots, open(os.path.join(dossier, f'b{i:03d}.json'), 'w'), ensure_ascii=False)
        print(f'beat {i + 1}/{len(beats)}', flush=True)


def main():
    if not CLE:
        sys.exit('Secret ELEVENLABS_API_KEY absent : ajoute-le dans Settings > Secrets and variables > Actions.')
    os.makedirs('sorties', exist_ok=True)
    for f in sorted(os.listdir('commandes')):
        if not f.endswith('.json'):
            continue
        nom = f[:-5]
        chemin = os.path.join('commandes', f)
        c = json.load(open(chemin))
        if c.get('statut') == 'traitée':
            continue
        dossier = os.path.join('sorties', nom)
        try:
            {'casting': casting, 'essai': essai, 'tts': production}[c['mode']](c, dossier)
            c['statut'] = 'traitée'
        except Exception as e:
            c['statut'] = 'erreur'
            c['erreur'] = str(e)[:800]
            print('ERREUR', nom, e, flush=True)
        c['traitee_le'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        json.dump(c, open(chemin, 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
