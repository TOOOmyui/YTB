"""Agent Publication — dépose une vidéo sur le quai GitHub (release publique) et renvoie son URL.

Usage : python3 publier.py video.mp4 NOM --depot CHEMIN_CLONE_QUAI [--morceau-mo 90] [--attente 900]
        python3 publier.py --nettoyer NOM --depot CHEMIN_CLONE_QUAI
Affiche l'URL publique sur la dernière ligne (code 0), sinon code 2/3.
Chaque envoi est un commit orphelin (l'historique ne grossit pas) ; GitHub Actions recolle et publie la release.
"""
import argparse, hashlib, os, shutil, subprocess, sys, time

WORKFLOW = os.path.join('.github', 'workflows', 'quai.yml')


def git(depot, *args, check=False):
    r = subprocess.run(['git', '-C', depot, *args], capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(r.stderr[-500:])
    return r


def envoyer(video, nom, depot, morceau_mo=90, attente=900):
    git(depot, 'fetch', '-q', 'origin', '+refs/heads/quai:refs/remotes/origin/quai', check=True)
    git(depot, 'checkout', '-q', '-f', 'quai')
    git(depot, 'reset', '-q', '--hard', 'origin/quai')
    wf = open(os.path.join(depot, WORKFLOW)).read()
    # commit orphelin : workflow + morceaux
    git(depot, 'checkout', '-q', '--orphan', 'envoi-tmp', check=True)
    git(depot, 'rm', '-rq', '--cached', '.')
    for f in os.listdir(depot):
        if f != '.git':
            p = os.path.join(depot, f)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    os.makedirs(os.path.join(depot, '.github', 'workflows'))
    open(os.path.join(depot, WORKFLOW), 'w').write(wf)
    d = os.path.join(depot, 'envoi', nom)
    os.makedirs(d)
    h = hashlib.sha256()
    taille = morceau_mo * 1024 * 1024
    with open(video, 'rb') as src:
        k = 0
        while True:
            bloc = src.read(taille)
            if not bloc:
                break
            h.update(bloc)
            open(os.path.join(d, f'part_{k:02d}'), 'wb').write(bloc)
            k += 1
    open(os.path.join(d, 'nom.txt'), 'w').write(os.path.basename(video))
    open(os.path.join(d, 'sha256.txt'), 'w').write(h.hexdigest())
    git(depot, 'add', '-A')
    git(depot, '-c', 'user.name=Regie', '-c', 'user.email=regie@users.noreply.github.com', 'commit', '-qm', f'envoi {nom}', check=True)
    git(depot, 'push', '-q', '-f', 'origin', 'envoi-tmp:quai', check=True)
    git(depot, 'checkout', '-q', '-B', 'quai', 'envoi-tmp')
    git(depot, 'branch', '-q', '-D', 'envoi-tmp')
    print(f'{nom} : {k} morceau(x) déposé(s), en attente de la publication…', flush=True)
    debut = time.time()
    while time.time() - debut < attente:
        time.sleep(15)
        git(depot, 'fetch', '-q', 'origin', '+refs/heads/quai:refs/remotes/origin/quai')
        r = git(depot, 'show', f'origin/quai:envoi/{nom}.url')
        if r.returncode == 0 and r.stdout.strip().startswith('https://'):
            url = r.stdout.strip()
            print(url)
            return url
    raise TimeoutError('Délai dépassé : la release n\'a pas été publiée.')


def nettoyer(nom, depot):
    git(depot, 'fetch', '-q', 'origin', '+refs/heads/quai:refs/remotes/origin/quai', check=True)
    git(depot, 'checkout', '-q', '-f', 'quai')
    git(depot, 'reset', '-q', '--hard', 'origin/quai')
    os.makedirs(os.path.join(depot, 'nettoyage'), exist_ok=True)
    open(os.path.join(depot, 'nettoyage', nom + '.txt'), 'w').write(nom)
    for f in (os.path.join(depot, 'envoi', nom + '.url'),):
        if os.path.exists(f):
            os.remove(f)
    git(depot, 'add', '-A')
    git(depot, '-c', 'user.name=Regie', '-c', 'user.email=regie@users.noreply.github.com', 'commit', '-qm', f'nettoyage {nom}', check=True)
    git(depot, 'push', '-q', 'origin', 'quai', check=True)
    print(f'Nettoyage de {nom} demandé.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('video', nargs='?'); ap.add_argument('nom', nargs='?')
    ap.add_argument('--depot', required=True); ap.add_argument('--morceau-mo', type=int, default=90)
    ap.add_argument('--attente', type=int, default=900); ap.add_argument('--nettoyer')
    a = ap.parse_args()
    try:
        if a.nettoyer:
            nettoyer(a.nettoyer, a.depot)
        else:
            envoyer(a.video, a.nom, a.depot, a.morceau_mo, a.attente)
    except TimeoutError as e:
        print(e); sys.exit(3)
    except Exception as e:
        print('Erreur :', e); sys.exit(2)
