"""Chaîne de production complète d'une vidéo longue (hors appels Metricool et régie, faits par l'agent).

Usage : python3 pipeline.py spec.json DOSSIER_SORTIE --studio CLONE_STUDIO --quai CLONE_QUAI [--duree-min 600] [--sans-publication]

Étapes : voix (studio Azure si « voix_studio » dans la spec, sinon/à défaut voix locale) → rendu v2 → contrôle de durée
→ miniature → description → dépôt sur le quai (release publique) → resultat.json
Codes : 0 succès · 4 durée insuffisante (le scénariste doit allonger le script) · 5 échec technique
"""
import argparse, json, os, subprocess, sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)


def run(cmd, **kw):
    print('$', ' '.join(cmd), flush=True)
    return subprocess.run(cmd, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('spec'); ap.add_argument('sortie')
    ap.add_argument('--studio'); ap.add_argument('--quai')
    ap.add_argument('--duree-min', type=float, default=600)
    ap.add_argument('--sans-publication', action='store_true')
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    os.makedirs(a.sortie, exist_ok=True)
    res = {'id': spec['id'], 'voix': 'locale'}

    # 1. voix
    args_voix = []
    if spec.get('voix_studio') and a.studio:
        audio = os.path.join(a.sortie, 'audio_studio')
        r = run([sys.executable, os.path.join(ICI, 'voix_studio.py'), a.spec, audio, '--depot', a.studio])
        if r.returncode == 0:
            args_voix = ['--voix', 'studio', '--audio-dir', audio]
            res['voix'] = 'studio:' + spec['voix_studio'].get('voix', '')
        else:
            res['alerte_voix'] = 'Studio indisponible : repli sur la voix locale.'

    # 2. rendu
    r = run([sys.executable, os.path.join(ICI, 'produire2.py'), a.spec, a.sortie, *args_voix], capture_output=True, text=True)
    print(r.stdout[-1500:], r.stderr[-1500:])
    if r.returncode:
        res['erreur'] = 'Rendu en échec'; json.dump(res, open(os.path.join(a.sortie, 'resultat.json'), 'w'), ensure_ascii=False, indent=1); sys.exit(5)
    prod = json.loads(r.stdout.strip().splitlines()[-1])
    res.update(prod)

    # 3. durée
    if prod['duree'] < a.duree_min:
        res['erreur'] = f"Durée {prod['duree']:.0f} s inférieure au plancher de {a.duree_min:.0f} s"
        json.dump(res, open(os.path.join(a.sortie, 'resultat.json'), 'w'), ensure_ascii=False, indent=1)
        print(res['erreur']); sys.exit(4)

    # 4. miniature + 5. description
    from miniature import miniature
    from packaging import description
    m = spec.get('miniature', {})
    mini = os.path.join(a.sortie, 'miniature.jpg')
    miniature(mini, m.get('chiffre', ''), m.get('l1', spec.get('titre', '')), m.get('l2', ''), m.get('ton', 'accent'))
    res['miniature'] = mini
    res['description'] = description(spec, prod)
    open(os.path.join(a.sortie, 'description.txt'), 'w').write(res['description'])

    # 6. quai
    if not a.sans_publication and a.quai:
        nom = f"{spec['id']}-{os.path.getsize(prod['fichier']) % 100000}"
        r = run([sys.executable, os.path.join(ICI, 'publier.py'), prod['fichier'], nom, '--depot', a.quai], capture_output=True, text=True)
        print(r.stdout[-800:], r.stderr[-800:])
        if r.returncode:
            res['erreur'] = 'Dépôt sur le quai en échec'; json.dump(res, open(os.path.join(a.sortie, 'resultat.json'), 'w'), ensure_ascii=False, indent=1); sys.exit(5)
        res['url_video'] = r.stdout.strip().splitlines()[-1]
        res['release'] = nom
    json.dump(res, open(os.path.join(a.sortie, 'resultat.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ('id', 'duree', 'voix', 'url_video') if k in res}, ensure_ascii=False))


if __name__ == '__main__':
    main()
