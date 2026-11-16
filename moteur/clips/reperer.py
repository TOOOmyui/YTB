"""Agent Repéreur — choisit les clips Twitch à monter.

Deux sorties :
  - `retenus`   : clips de streamers AUTORISÉS (liste blanche de la config), classés par score ;
  - `prospects` : streamers non autorisés dont les clips marchent le mieux → à contacter pour obtenir leur accord.

Règle de l'entreprise (manuel, poste Vérificateur) : aucun extrait protégé sans accord. Un clip d'un streamer
absent de la liste blanche n'est JAMAIS téléchargé ni monté.

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

    autorises = {s['login'].lower(): s for s in cfg.get('streamers_autorises', []) if s.get('login') and s.get('accord')}
    exclus = {l.lower() for l in cfg.get('streamers_exclus', [])}
    comptes = tw.utilisateurs(list(autorises)) if autorises else {}

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

    notes, retenus = [], []
    for login, s in autorises.items():
        u = comptes.get(login)
        if not u:
            notes.append(f'streamer autorisé introuvable sur Twitch : {login}')
            continue
        par_streamer = []
        for c in tw.clips(debut, fin, diffuseur_id=u['id'], pages=1):
            if garder(c, notes):
                par_streamer.append({
                    'id': c['id'], 'url': c['url'], 'titre_clip': titre_propre(c['title']),
                    'streamer': u.get('display_name') or c['broadcaster_name'], 'login': login,
                    'clippeur': c.get('creator_name'), 'vues': c['view_count'], 'duree': c['duration'],
                    'langue': c.get('language'), 'cree': c['created_at'], 'score': score(c, maintenant),
                    'accord': s['accord'], 'facecam': s.get('facecam'),
                })
        par_streamer.sort(key=lambda x: -x['score'])
        retenus += par_streamer[:r.get('max_par_streamer', 2)]
    retenus.sort(key=lambda x: -x['score'])

    # Prospection : qui faudrait-il convaincre ?
    prosp = {}
    for c in tw.clips(debut, fin, jeu_id=jeu_id, pages=r.get('pages_prospection', 3)):
        login = (c.get('broadcaster_name') or '').lower()
        if r.get('langues') and c.get('language') not in r['langues']:
            continue
        p = prosp.setdefault(c['broadcaster_id'], {'streamer': c['broadcaster_name'], 'clips': 0, 'vues': 0, 'meilleur': None})
        p['clips'] += 1
        p['vues'] += c['view_count']
        if not p['meilleur'] or c['view_count'] > p['meilleur']['vues']:
            p['meilleur'] = {'url': c['url'], 'titre': titre_propre(c['title']), 'vues': c['view_count']}
    noms_ok = {(comptes[l].get('display_name') or l).lower() for l in comptes} | set(autorises)
    prospects = sorted((p for p in prosp.values() if p['streamer'].lower() not in noms_ok and p['streamer'].lower() not in exclus),
                       key=lambda p: -p['vues'])[:r.get('max_prospects', 15)]

    return {'jeu': {'id': jeu_id, 'nom': jeu_nom}, 'fenetre': [debut, fin], 'retenus': retenus,
            'prospects': prospects, 'notes': notes}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('config'); ap.add_argument('etat'); ap.add_argument('--heures', type=int)
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding='utf-8'))
    print(json.dumps(reperer(cfg, a.etat, a.heures), ensure_ascii=False, indent=1))
