"""Agent Publication (shorts) — publie les shorts de la file sur YouTube (et Instagram) via Upload-Post.

Lancé toutes les heures par le workflow « Publier » (branche main), ou à la demande depuis le centre de contrôle
avec --id (publication immédiate d'un short précis, même hors créneau et en mode manuel).

Règles (réglages `publication` de la chaîne) :
  - statut de la chaîne « active », sinon rien ;
  - mode « auto » : publie le meilleur short de la file au créneau ; mode « manuel » : seulement les shorts validés ;
  - un short par créneau, `max_par_jour` au plus, jamais deux fois de suite le même streamer s'il y a un autre choix ;
  - un short dont le fichier a expiré (release nettoyée) passe dans rejetes/.

Usage : python3 publier.py config.json etat_dir [--id ID] [--essai]
Codes : 0 = terminé (y compris « rien à faire ») ; 2 = échec de publication.
"""
import argparse, datetime as dt, json, os, sys, urllib.error, urllib.request, uuid
from zoneinfo import ZoneInfo

API = 'https://api.upload-post.com/api/upload'
EXPIRATION_H = 96  # les releases de shorts sont supprimées après 5 jours : marge d'un jour
UTC = dt.timezone.utc


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


def champs_post(cfg, man):
    pub = cfg.get('publication', {})
    plateformes = pub.get('plateformes') or ['youtube']
    titre = (man.get('titre_youtube') or man['clip']['titre_clip'])[:100]
    desc = man.get('description', '')
    tags = [t for t in man.get('tags', []) if t][:15]
    f = [('user', pub['upload_post_user']), ('video', man['url_video']), ('title', titre),
         ('description', desc), ('categoryId', '20'), ('privacyStatus', 'public'),
         ('selfDeclaredMadeForKids', 'false'), ('containsSyntheticMedia', 'false')]
    f += [('platform[]', p) for p in plateformes]
    f += [('tags[]', t) for t in tags]
    if 'instagram' in plateformes:
        # Légende Instagram : titre + crédit + hashtags (les liens ne sont pas cliquables sur Instagram)
        c = man['clip']
        f += [('instagram_title', f"{titre}\n\nCrédit : {c['streamer']} — twitch.tv/{c['login']}\n\n{' '.join(man.get('hashtags', []))}"[:2100]),
              ('media_type', 'REELS'), ('share_to_feed', 'true')]
    return f


def multipart(champs):
    borne = 'regie' + uuid.uuid4().hex
    morceaux = []
    for nom, val in champs:
        morceaux.append(f'--{borne}\r\nContent-Disposition: form-data; name="{nom}"\r\n\r\n{val}\r\n'.encode('utf-8'))
    morceaux.append(f'--{borne}--\r\n'.encode())
    return b''.join(morceaux), f'multipart/form-data; boundary={borne}'


def envoyer(champs, cle, cle_idem):
    corps, ctype = multipart(champs)
    req = urllib.request.Request(API, data=corps, method='POST', headers={
        'Authorization': 'Apikey ' + cle, 'Content-Type': ctype, 'Idempotency-Key': cle_idem})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            return r.status, json.loads(r.read().decode('utf-8') or '{}')
    except urllib.error.HTTPError as e:
        txt = e.read().decode('utf-8', 'replace')
        try:
            return e.code, json.loads(txt)
        except ValueError:
            return e.code, {'erreur': txt[:400]}


def publier(cfg, etat, id_force=None, cle=None, essai=False, maintenant=None, envoi=envoyer):
    maintenant = maintenant or dt.datetime.now(UTC)
    jp = os.path.join(etat, 'publications.json')
    journal = lire(jp, [])
    bilan = {'date': maintenant.isoformat(timespec='seconds'), 'publie': None, 'expires': [], 'note': None}

    # ménage : fichiers expirés
    for m in file_attente(etat):
        if age_h(m, maintenant) > EXPIRATION_H and m.get('id') != id_force:
            deplacer(etat, m, 'rejetes', statut='rejetée', motif='fichier expiré (non publié à temps)',
                     rejete=bilan['date'])
            bilan['expires'].append(m['id'])

    pub = cfg.get('publication', {})
    if not pub.get('upload_post_user'):
        bilan['note'] = 'profil Upload-Post non renseigné (Réglages → Publication)'
    elif id_force:
        m = next((x for x in file_attente(etat) if x['id'] == id_force), None)
        if not m:
            bilan['note'] = f'short introuvable en file : {id_force}'
        else:
            loc = maintenant.astimezone(ZoneInfo(pub.get('fuseau', 'Europe/Paris')))
            m['_creneau'] = (loc.strftime('%Y-%m-%d'), 'manuel ' + loc.strftime('%H:%M'))
    else:
        m, bilan['note'] = choisir(cfg, etat, maintenant, journal)

    code = 0
    if not bilan['note'] and m:
        jour, heure = m.pop('_creneau')
        champs = champs_post(cfg, m)
        if essai:
            bilan['essai'] = champs
            print(json.dumps(bilan, ensure_ascii=False, indent=1))
            return bilan, 0
        statut, rep = envoi(champs, cle, m['id'])
        ok = 200 <= statut < 300 and rep.get('success', True) is not False
        if ok:
            deplacer(etat, m, 'publies', statut='publiée', publication={
                'date': bilan['date'], 'creneau': heure, 'plateformes': pub.get('plateformes') or ['youtube'],
                'request_id': rep.get('request_id'), 'reponse': rep})
            journal.append({'id': m['id'], 'jour': jour, 'creneau': heure, 'date': bilan['date'],
                            'login': m['clip']['login'], 'titre': m.get('titre_youtube'), 'request_id': rep.get('request_id')})
            ecrire(jp, journal)
            bilan['publie'] = m['id']
        else:
            m['echecs'] = m.get('echecs', 0) + 1
            m['erreur_publication'] = {'date': bilan['date'], 'http': statut, 'reponse': rep}
            if m['echecs'] >= 2:
                m['statut'] = 'bloquée'
            ecrire(os.path.join(etat, 'file', m['id'] + '.json'), m)
            bilan['note'] = f'échec de publication (HTTP {statut}) : {json.dumps(rep, ensure_ascii=False)[:300]}'
            code = 2
    ecrire(os.path.join(etat, 'rapports', 'derniere-publication.json'), bilan)
    return bilan, code


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('config'); ap.add_argument('etat')
    ap.add_argument('--id', default=''); ap.add_argument('--essai', action='store_true')
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding='utf-8'))
    cle = os.environ.get('UPLOAD_POST_API_KEY', '')
    if not cle and not a.essai:
        print('Clé UPLOAD_POST_API_KEY absente : publication sautée.')
        sys.exit(0)
    b, code = publier(cfg, a.etat, a.id or None, cle, a.essai)
    print(json.dumps(b, ensure_ascii=False))
    sys.exit(code)
