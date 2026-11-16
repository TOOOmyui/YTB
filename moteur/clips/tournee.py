"""Tournée de clipping — repère, télécharge, monte et met en file d'attente les shorts d'une chaîne de clips.

Tourne dans GitHub Actions (Twitch n'est pas joignable depuis les sessions Claude). Ne publie rien :
elle dépose les shorts montés dans `sorties/` et un manifeste par short dans `<etat>/file/`. Une session
Claude (skill regie-clips) contrôle ensuite chaque short, soigne le titre et programme dans Metricool.

Usage : python3 tournee.py config.json etat_dir sorties_dir [--base-url URL] [--heures N] [--max N] [--sans-sous-titres]
Codes : 0 = terminé (y compris « rien à faire ») ; 2 = erreur.
"""
import argparse, datetime as dt, json, os, re, subprocess, sys, unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twitch import Twitch, ErreurTwitch
import reperer, monter


def ecrire(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(obj, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def slug(t):
    t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')[:24]


def telecharger(url, dest):
    """Téléchargement du clip (yt-dlp)."""
    subprocess.run([sys.executable, '-m', 'yt_dlp', '-q', '--no-warnings', '--no-playlist', '-f', 'best[height<=1080]/best',
                    '--merge-output-format', 'mp4', '-o', dest, url], check=True, timeout=600)
    return dest


def accroche_defaut(titre):
    t = re.sub(r'[\U0001F000-\U0001FFFF☀-➿]', '', titre).strip(' .-_')
    return t[:60]


def emballer(cfg, c, res, url_video):
    """Packaging par défaut ; la session Claude réécrit titre et accroche avant programmation."""
    p = cfg['packaging']
    titre = f"{accroche_defaut(c['titre_clip'])} — {c['streamer']} sur {cfg['jeu']['nom_court']}"
    if len(titre) > 95:
        titre = titre[:94].rstrip() + '…'
    desc = '\n'.join([
        f"{c['streamer']} en direct sur {cfg['jeu']['nom_court']}.",
        '',
        f"Clip original : {c['url']}",
        f"Chaîne Twitch : https://www.twitch.tv/{c['login']}",
        f"Crédit : {c['streamer']} — tout le mérite du moment lui revient. Abonne-toi à sa chaîne Twitch.",
        "Streamer concerné et tu veux un retrait ou un autre crédit ? Écris en commentaire, c'est fait dans la journée.",
        '',
        ' '.join(p['hashtags']),
    ])
    return {'titre_youtube': titre, 'description': desc, 'tags': p['tags'] + [c['streamer']], 'hashtags': p['hashtags'],
            'categorie': 'GAMING', 'url_video': url_video}


def tournee(cfg, etat, sorties, base_url='', heures=None, maxi=None, sous_titres=True, tw=None, telech=telecharger):
    os.makedirs(sorties, exist_ok=True)
    file_dir = os.path.join(etat, 'file')
    os.makedirs(file_dir, exist_ok=True)
    hist_p = os.path.join(etat, 'historique.json')
    hist = reperer.lire_json(hist_p, {})
    jour = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d')
    bilan = {'date': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'produits': [], 'echecs': [], 'notes': []}

    sel = reperer.reperer(cfg, etat, heures, tw)
    bilan['notes'] += sel.get('notes', []) + ([sel['note']] if sel.get('note') else [])

    en_file = len([f for f in os.listdir(file_dir) if f.endswith('.json')])
    place = max(0, cfg['reperage'].get('file_max', 8) - en_file)
    maxi = min(maxi or cfg['reperage'].get('max_par_tournee', 3), place)
    if place == 0:
        bilan['notes'].append(f'file pleine ({en_file} shorts en attente de programmation)')

    for c in sel['retenus'][:maxi]:
        nom = f"{cfg['chaine']}-{jour}-{slug(c['login'])}-{c['id'][-6:].lower()}"
        nom = re.sub(r'[^a-z0-9-]', '', nom)
        try:
            brut = telech(c['url'], os.path.join(sorties, '_brut_' + nom + '.mp4'))
            res = monter.monter(brut, os.path.join(sorties, nom + '.mp4'), accroche_defaut(c['titre_clip']), c['streamer'],
                                c['login'], c.get('facecam'), sous_titres=sous_titres, langue=c.get('langue') or 'fr')
            os.remove(brut)
            man = {'id': nom, 'chaine': cfg['chaine'], 'statut': 'montée', 'clip': c,
                   'montage': {k: res[k] for k in ('duree', 'sous_titres', 'facecam')},
                   **emballer(cfg, c, res, f'{base_url}/{nom}.mp4' if base_url else ''),
                   'url_couverture': f'{base_url}/{nom}.jpg' if base_url else '', 'cree': bilan['date']}
            ecrire(os.path.join(file_dir, nom + '.json'), man)
            hist[c['id']] = {'short': nom, 'date': bilan['date'], 'streamer': c['login']}
            bilan['produits'].append(nom)
            print(f'  monté : {nom} ({res["duree"]} s, {res["sous_titres"]} blocs de sous-titres)', flush=True)
        except Exception as e:
            hist[c['id']] = {'echec': str(e)[:200], 'date': bilan['date'], 'streamer': c['login']}
            bilan['echecs'].append({'clip': c['id'], 'erreur': str(e)[:200]})
            print(f'  échec : {c["id"]} — {e}', flush=True)
    ecrire(hist_p, hist)
    ecrire(os.path.join(etat, 'rapports', 'derniere-tournee.json'), bilan)
    return bilan


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('config'); ap.add_argument('etat'); ap.add_argument('sorties')
    ap.add_argument('--base-url', default=''); ap.add_argument('--heures', type=int); ap.add_argument('--max', type=int)
    ap.add_argument('--sans-sous-titres', action='store_true')
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding='utf-8'))
    if not Twitch().configure:
        print('Identifiants Twitch absents (secrets TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET) : tournée sautée.')
        sys.exit(0)
    try:
        b = tournee(cfg, a.etat, a.sorties, a.base_url, a.heures, a.max, not a.sans_sous_titres)
        print(json.dumps(b, ensure_ascii=False))
    except ErreurTwitch as e:
        print('Erreur Twitch :', e)
        sys.exit(2)
