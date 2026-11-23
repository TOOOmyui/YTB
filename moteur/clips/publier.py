"""Agent Publication (shorts) — publie les shorts de la file.

Fournisseurs (réglage `publication.fournisseur`) :
  - « youtube_api » (défaut) : envoi direct par l'API YouTube Data v3, gratuit. Identifiants dans l'environnement :
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN. Tant que l'audit YouTube n'est pas accordé
    (`publication.youtube_verifie` faux), YouTube verrouille en privé toute vidéo envoyée par l'API : la publication
    automatique est alors suspendue (publication manuelle depuis le centre de contrôle) ; seul l'envoi de test
    (--test, en privé) est permis.
  - « upload_post » : service Upload-Post (UPLOAD_POST_API_KEY, profil `upload_post_user`).
  - « metricool » : publié par une session Claude programmée via le connecteur Metricool (skill regie-clips) ;
    ce script ne fait alors que le ménage des fichiers expirés.
  - « manuel » : aucune publication automatique.

Lancé toutes les heures par le workflow « Publier » (branche main), ou à la demande avec --id (publication immédiate
d'un short précis, même hors créneau et en mode manuel).

Règles : chaîne « active » ; mode « auto » = meilleur short de la file au créneau, mode « manuel » = shorts validés ;
un short par créneau, `max_par_jour` au plus, jamais deux fois de suite le même streamer s'il y a un autre choix ;
un short dont le fichier a expiré (release nettoyée) passe dans rejetes/.

Usage : python3 publier.py config.json etat_dir [--id ID] [--test] [--essai]
Codes : 0 = terminé (y compris « rien à faire ») ; 2 = échec de publication.
"""
import argparse, datetime as dt, json, os, re, sys, urllib.error, urllib.parse, urllib.request, uuid
from zoneinfo import ZoneInfo

UPLOAD_POST = 'https://api.upload-post.com/api/upload'
JETON_GOOGLE = 'https://oauth2.googleapis.com/token'
ENVOI_YT = 'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status'
EXPIRATION_H = 96  # les releases de shorts sont supprimées après 5 jours : marge d'un jour
UTC = dt.timezone.utc


class ErreurEnvoi(RuntimeError):
    def __init__(self, http, reponse):
        super().__init__(f'HTTP {http}')
        self.http, self.reponse = http, reponse


# ------------------------------------------------------------------ fichiers d'état
def lire(p, defaut):
    try:
        return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError):
        return defaut


def ecrire(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(obj, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def deplacer(etat, man, dossier, **champs):
    man.update(champs)
    ecrire(os.path.join(etat, dossier, man['id'] + '.json'), man)
    try:
        os.remove(os.path.join(etat, 'file', man['id'] + '.json'))
    except OSError:
        pass


def file_attente(etat):
    d = os.path.join(etat, 'file')
    out = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if f.endswith('.json'):
            m = lire(os.path.join(d, f), None)
            if m:
                out.append(m)
    return out


def age_h(man, maintenant):
    try:
        cree = dt.datetime.fromisoformat(man['cree'].replace('Z', '+00:00'))
    except (KeyError, ValueError):
        return 0
    return (maintenant - cree).total_seconds() / 3600


# ------------------------------------------------------------------ choix du short
def creneau_courant(pub, maintenant):
    """Renvoie (jour, 'HH:MM') du créneau ouvert (dans l'heure qui suit son début), sinon None."""
    loc = maintenant.astimezone(ZoneInfo(pub.get('fuseau', 'Europe/Paris')))
    for c in sorted(pub.get('creneaux', []), reverse=True):
        h, m = map(int, c.split(':'))
        debut = loc.replace(hour=h, minute=m, second=0, microsecond=0)
        if debut <= loc < debut + dt.timedelta(minutes=59):
            return loc.strftime('%Y-%m-%d'), c
    return None


def choisir(cfg, etat, maintenant, journal):
    pub = cfg.get('publication', {})
    if cfg.get('statut', 'active') != 'active':
        return None, 'chaîne en pause'
    cr = creneau_courant(pub, maintenant)
    if not cr:
        return None, 'hors créneau'
    jour, heure = cr
    du_jour = [p for p in journal if p.get('jour') == jour]
    if any(p.get('creneau') == heure for p in du_jour):
        return None, f'créneau {heure} déjà servi'
    if len(du_jour) >= pub.get('max_par_jour', 4):
        return None, 'quota du jour atteint'
    mode = pub.get('mode', 'manuel')
    elig = [m for m in file_attente(etat)
            if m.get('statut') == 'validée' or (mode == 'auto' and m.get('statut') == 'montée')]
    if not elig:
        return None, 'aucun short ' + ('en file' if mode == 'auto' else 'validé')
    elig.sort(key=lambda m: (m.get('statut') != 'validée', -(m.get('clip', {}).get('score') or 0)))
    dernier = journal[-1].get('login') if journal else None
    autre = [m for m in elig if m.get('clip', {}).get('login') != dernier]
    m = (autre or elig)[0]
    m['_creneau'] = (jour, heure)
    return m, None


# ------------------------------------------------------------------ HTTP
def http(url, data=None, entetes=None, methode=None, delai=600):
    """Requête HTTP → (statut, entêtes, corps). Ne lève pas sur 4xx/5xx."""
    req = urllib.request.Request(url, data=data, headers=entetes or {}, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=delai) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read()


def jsonou(corps):
    try:
        return json.loads(corps.decode('utf-8') or '{}')
    except ValueError:
        return {'erreur': corps.decode('utf-8', 'replace')[:400]}


def propre_yt(t):
    """YouTube refuse < et > dans le titre et la description."""
    return re.sub(r'[<>]', '', t or '')


# ------------------------------------------------------------------ fournisseur : API YouTube
def jeton_youtube(env, h=http):
    corps = urllib.parse.urlencode({'client_id': env['YT_CLIENT_ID'], 'client_secret': env['YT_CLIENT_SECRET'],
                                    'refresh_token': env['YT_REFRESH_TOKEN'], 'grant_type': 'refresh_token'}).encode()
    st, _, c = h(JETON_GOOGLE, corps, {'Content-Type': 'application/x-www-form-urlencoded'}, 'POST', 60)
    rep = jsonou(c)
    if st != 200 or 'access_token' not in rep:
        raise ErreurEnvoi(st, {'etape': 'jeton Google', **rep})
    return rep['access_token']


def publier_youtube(cfg, man, env, prive=False, h=http):
    jeton = jeton_youtube(env, h)
    # 1. récupérer le fichier monté (release GitHub)
    st, _, video = h(man['url_video'], None, {}, 'GET', 300)
    if st != 200 or len(video) < 10000:
        raise ErreurEnvoi(st, {'etape': 'téléchargement du short', 'url': man['url_video']})
    titre = propre_yt(man.get('titre_youtube') or man['clip']['titre_clip'])[:100]
    meta = {'snippet': {'title': titre, 'description': propre_yt(man.get('description', ''))[:4900],
                        'tags': [t for t in man.get('tags', []) if t][:15], 'categoryId': '20',
                        'defaultLanguage': 'fr', 'defaultAudioLanguage': 'fr'},
            'status': {'privacyStatus': 'private' if prive else 'public', 'selfDeclaredMadeForKids': False,
                       'containsSyntheticMedia': False, 'embeddable': True}}
    # 2. ouvrir une session d'envoi reprenable
    st, ent, c = h(ENVOI_YT, json.dumps(meta).encode(), {
        'Authorization': 'Bearer ' + jeton, 'Content-Type': 'application/json; charset=UTF-8',
        'X-Upload-Content-Type': 'video/mp4', 'X-Upload-Content-Length': str(len(video))}, 'POST', 60)
    lieu = {k.lower(): v for k, v in ent.items()}.get('location')
    if st != 200 or not lieu:
        raise ErreurEnvoi(st, {'etape': 'ouverture de l’envoi', **jsonou(c)})
    # 3. envoyer la vidéo (deux reprises en cas de coupure)
    for essai in range(3):
        st, _, c = h(lieu, video, {'Authorization': 'Bearer ' + jeton, 'Content-Type': 'video/mp4'}, 'PUT', 900)
        if st in (200, 201):
            rep = jsonou(c)
            return {'video_id': rep.get('id'), 'url': f"https://youtube.com/shorts/{rep.get('id')}",
                    'statut_youtube': rep.get('status', {}), 'prive': prive}
        if st not in (500, 502, 503, 504):
            break
    raise ErreurEnvoi(st, {'etape': 'envoi de la vidéo', **jsonou(c)})


# ------------------------------------------------------------------ fournisseur : Upload-Post
def multipart(champs):
    borne = 'regie' + uuid.uuid4().hex
    morceaux = [f'--{borne}\r\nContent-Disposition: form-data; name="{n}"\r\n\r\n{v}\r\n'.encode('utf-8') for n, v in champs]
    morceaux.append(f'--{borne}--\r\n'.encode())
    return b''.join(morceaux), f'multipart/form-data; boundary={borne}'


def champs_upload_post(cfg, man):
    pub = cfg.get('publication', {})
    plateformes = pub.get('plateformes') or ['youtube']
    titre = (man.get('titre_youtube') or man['clip']['titre_clip'])[:100]
    f = [('user', pub['upload_post_user']), ('video', man['url_video']), ('title', titre),
         ('description', man.get('description', '')), ('categoryId', '20'), ('privacyStatus', 'public'),
         ('selfDeclaredMadeForKids', 'false'), ('containsSyntheticMedia', 'false')]
    f += [('platform[]', p) for p in plateformes]
    f += [('tags[]', t) for t in man.get('tags', []) if t][:15]
    if 'instagram' in plateformes:
        c = man['clip']
        f += [('instagram_title', f"{titre}\n\nCrédit : {c['streamer']} — twitch.tv/{c['login']}\n\n{' '.join(man.get('hashtags', []))}"[:2100]),
              ('media_type', 'REELS'), ('share_to_feed', 'true')]
    return f


def publier_upload_post(cfg, man, env, prive=False, h=http):
    corps, ctype = multipart(champs_upload_post(cfg, man))
    st, _, c = h(UPLOAD_POST, corps, {'Authorization': 'Apikey ' + env['UPLOAD_POST_API_KEY'], 'Content-Type': ctype,
                                      'Idempotency-Key': man['id']}, 'POST', 900)
    rep = jsonou(c)
    if not (200 <= st < 300) or rep.get('success') is False:
        raise ErreurEnvoi(st, rep)
    return {'request_id': rep.get('request_id'), 'reponse': rep}


FOURNISSEURS = {
    'youtube_api': (publier_youtube, ('YT_CLIENT_ID', 'YT_CLIENT_SECRET', 'YT_REFRESH_TOKEN'), ['youtube']),
    'upload_post': (publier_upload_post, ('UPLOAD_POST_API_KEY',), None),
}


# ------------------------------------------------------------------ tournée de publication
def publier(cfg, etat, id_force=None, env=None, essai=False, test=False, maintenant=None, h=http):
    env = os.environ if env is None else env
    maintenant = maintenant or dt.datetime.now(UTC)
    jp = os.path.join(etat, 'publications.json')
    journal = lire(jp, [])
    bilan = {'date': maintenant.isoformat(timespec='seconds'), 'publie': None, 'expires': [], 'note': None}
    pub = cfg.get('publication', {})
    fourn = pub.get('fournisseur', 'youtube_api')

    for m in file_attente(etat):  # ménage : fichiers expirés
        if age_h(m, maintenant) > EXPIRATION_H and m.get('id') != id_force:
            deplacer(etat, m, 'rejetes', statut='rejetée', motif='fichier expiré (non publié à temps)', rejete=bilan['date'])
            bilan['expires'].append(m['id'])

    m = None
    if fourn == 'metricool':
        bilan['note'] = 'publication par la session Claude programmée (Metricool) : rien à faire ici'
    elif fourn not in FOURNISSEURS:
        bilan['note'] = 'publication automatique désactivée (fournisseur « manuel ») : publier depuis le centre de contrôle'
    elif any(not env.get(k) for k in FOURNISSEURS[fourn][1]):
        bilan['note'] = 'identifiants absents : ' + ', '.join(k for k in FOURNISSEURS[fourn][1] if not env.get(k))
    elif fourn == 'upload_post' and not pub.get('upload_post_user'):
        bilan['note'] = 'profil Upload-Post non renseigné (Réglages → Publication)'
    elif fourn == 'youtube_api' and not pub.get('youtube_verifie') and not test:
        bilan['note'] = ('audit YouTube en attente : tout envoi par l’API serait verrouillé en privé, publication '
                         'automatique suspendue (publier à la main depuis le centre de contrôle)')
    elif id_force:
        m = next((x for x in file_attente(etat) if x['id'] == id_force), None)
        if not m:
            bilan['note'] = f'short introuvable en file : {id_force}'
        else:
            loc = maintenant.astimezone(ZoneInfo(pub.get('fuseau', 'Europe/Paris')))
            m['_creneau'] = (loc.strftime('%Y-%m-%d'), ('test ' if test else 'manuel ') + loc.strftime('%H:%M'))
    elif test:
        file_ = sorted(file_attente(etat), key=lambda x: -(x.get('clip', {}).get('score') or 0))
        m = file_[0] if file_ else None
        if m:
            m['_creneau'] = (None, 'test')
        else:
            bilan['note'] = 'aucun short en file pour le test'
    else:
        m, bilan['note'] = choisir(cfg, etat, maintenant, journal)

    code = 0
    if m and not bilan['note']:
        jour, heure = m.pop('_creneau')
        fonction, _, plat = FOURNISSEURS[fourn]
        if essai:
            bilan['essai'] = {'fournisseur': fourn, 'short': m['id'], 'test': test}
            return bilan, 0
        try:
            res = fonction(cfg, m, env, prive=test, h=h)
            if test:  # le short reste en file : l'essai ne compte pas comme une publication
                bilan['test'] = {'short': m['id'], **res}
                bilan['note'] = 'envoi de test réussi (vidéo privée sur la chaîne, à supprimer dans YouTube Studio)'
            else:
                deplacer(etat, m, 'publies', statut='publiée', publication={
                    'date': bilan['date'], 'creneau': heure, 'fournisseur': fourn,
                    'plateformes': plat or pub.get('plateformes') or ['youtube'], **res})
                journal.append({'id': m['id'], 'jour': jour, 'creneau': heure, 'date': bilan['date'],
                                'login': m['clip']['login'], 'titre': m.get('titre_youtube'), 'url': res.get('url'),
                                'request_id': res.get('request_id')})
                ecrire(jp, journal)
                bilan['publie'] = m['id']
        except ErreurEnvoi as e:
            bilan['note'] = f'échec de publication (HTTP {e.http}) : {json.dumps(e.reponse, ensure_ascii=False)[:300]}'
            code = 2
            if not test:
                m['echecs'] = m.get('echecs', 0) + 1
                m['erreur_publication'] = {'date': bilan['date'], 'http': e.http, 'reponse': e.reponse}
                if m['echecs'] >= 2:
                    m['statut'] = 'bloquée'
                ecrire(os.path.join(etat, 'file', m['id'] + '.json'), m)
    ecrire(os.path.join(etat, 'rapports', 'derniere-publication.json'), bilan)
    return bilan, code


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('config'); ap.add_argument('etat')
    ap.add_argument('--id', default=''); ap.add_argument('--test', action='store_true'); ap.add_argument('--essai', action='store_true')
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding='utf-8'))
    b, code = publier(cfg, a.etat, a.id or None, essai=a.essai, test=a.test)
    print(json.dumps(b, ensure_ascii=False))
    sys.exit(code)
