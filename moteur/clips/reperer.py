"""Agent Repéreur — choisit les clips Twitch à monter.

Mode « ouvert » (décision du PDG du 16/11/2026) : meilleurs clips du jeu dans la langue visée, tous streamers
confondus sauf `streamers_exclus`. Mode « liste_blanche » : seulement les streamers listés dans `streamers`.
Dans tous les cas, un clip dont on ne peut pas établir le crédit (login de la chaîne) est écarté.

Usage : python3 reperer.py config.json etat_dir [--heures 24] > selection.json
"""
import argparse, datetime as dt, json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twitch import Twitch

UTC = dt.timezone.utc


def rfc(t):
    return t.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def age_heures(clip, maintenant):
    cree = dt.datetime.strptime(clip['created_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)
    return max(0.25, (maintenant - cree).total_seconds() / 3600)


def score(clip, maintenant):
    """Vues par heure, lissées : privilégie ce qui monte vite, sans écraser les très gros clips."""
    h = age_heures(clip, maintenant)
    return round(clip['view_count'] / math.sqrt(h + 2), 2)


def titre_propre(t):
    t = re.sub(r'\s+', ' ', t or '').strip()
    return t


def interdit(titre, mots):
    bas = (titre or '').lower()
    return next((m for m in mots if m.lower() in bas), None)


def lire_json(p, defaut):
    try:
        return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError):
        return defaut


def reperer(cfg, etat_dir, heures=None, tw=None, maintenant=None):
    tw = tw or Twitch()
    maintenant = maintenant or dt.datetime.now(UTC)
    r = cfg['reperage']
    heures = heures or r.get('fenetre_heures', 24)
    debut, fin = rfc(maintenant - dt.timedelta(hours=heures)), rfc(maintenant)
    deja = set(lire_json(os.path.join(etat_dir, 'historique.json'), {}).keys())

    jeu_id, jeu_nom = (cfg['jeu'].get('id'), cfg['jeu'].get('nom')) if cfg['jeu'].get('id') else tw.trouver_jeu(cfg['jeu']['noms'])
    if not jeu_id:
        return {'jeu': None, 'retenus': [], 'prospects': [], 'note': 'catégorie Twitch introuvable (jeu pas encore référencé ?)'}

    regles = {x['login'].lower(): x for x in cfg.get('streamers', []) if x.get('login')}
    exclus = {l.lower() for l in cfg.get('streamers_exclus', [])}
    ouvert = cfg.get('mode', 'liste_blanche') == 'ouvert'

    def garder(c, raisons):
        if c['id'] in deja:
            return False
        if c.get('game_id') != jeu_id:
            return False
        if r.get('langues') and c.get('language') not in r['langues']:
            return False
        if not (r['duree_min'] <= c.get('duration', 0) <= r['duree_max']):
            return False
        if c['view_count'] < r['vues_min']:
            return False
        m = interdit(c.get('title'), r.get('mots_interdits', []))
        if m:
            raisons.append(f"{c['id']} écarté (mot interdit : {m})")
            return False
        return True

    notes = []
    bruts = tw.clips(debut, fin, jeu_id=jeu_id, pages=r.get('pages_prospection', 3))
    ids = sorted({c['broadcaster_id'] for c in bruts if garder(c, [])})
    # le crédit exige le login exact de la chaîne (twitch.tv/<login>) : on le demande à Twitch
    logins = {}
    for i in range(0, len(ids), 100):
        for u in tw.get('users', id=ids[i:i + 100]).get('data', []):
            logins[u['id']] = (u['login'].lower(), u.get('display_name') or u['login'])
    par_streamer = {}
    for c in bruts:
        if not garder(c, notes):
            continue
        login, nom = logins.get(c['broadcaster_id'], (None, None))
        if not login:
            notes.append(f"{c['id']} écarté (chaîne introuvable : crédit impossible)")
            continue
        if login in exclus or (not ouvert and login not in regles):
            continue
        par_streamer.setdefault(login, []).append({
            'id': c['id'], 'url': c['url'], 'titre_clip': titre_propre(c['title']), 'streamer': nom, 'login': login,
            'clippeur': c.get('creator_name'), 'vues': c['view_count'], 'duree': c['duration'],
            'langue': c.get('language'), 'cree': c['created_at'], 'score': score(c, maintenant),
            'facecam': regles.get(login, {}).get('facecam'),
        })
    retenus = []
    for login, l in par_streamer.items():
        l.sort(key=lambda x: -x['score'])
        retenus += l[:r.get('max_par_streamer', 2)]
    retenus.sort(key=lambda x: -x['score'])
    return {'jeu': {'id': jeu_id, 'nom': jeu_nom}, 'fenetre': [debut, fin], 'retenus': retenus, 'prospects': [], 'notes': notes}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('config'); ap.add_argument('etat'); ap.add_argument('--heures', type=int)
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding='utf-8'))
    print(json.dumps(reperer(cfg, a.etat, a.heures), ensure_ascii=False, indent=1))
