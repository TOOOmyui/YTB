"""Client du studio voix (branche « studio » du dépôt GitHub de la régie).

Usage : python3 voix_studio.py spec.json dossier_audio --depot CHEMIN_CLONE_STUDIO [--attente 1500]
Code de sortie : 0 = audio livré dans dossier_audio (bNNN.mp3 + bNNN.json) ; 2 = erreur studio (message affiché) ;
3 = délai dépassé. En cas d'échec, la production bascule sur la voix locale (Piper).

La spec doit contenir "voix_studio": {"fournisseur": "azure", "voix": "fr-FR-…", "debit": "+6%", "style": null, ...}
"""
import json, os, sys, time, shutil, subprocess, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from produire2 import beats_de


def git(depot, *args):
    return subprocess.run(['git', '-C', depot, *args], capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('spec'); ap.add_argument('sortie'); ap.add_argument('--depot', required=True)
    ap.add_argument('--attente', type=int, default=1500); ap.add_argument('--scenes')
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    vs = spec.get('voix_studio')
    if not vs:
        print('Pas de voix_studio dans la spec.'); sys.exit(2)
    plage = tuple(map(int, a.scenes.split('-'))) if a.scenes else None
    beats = [b['voix'] for b in beats_de(spec, plage)]
    nom = f"{spec['id']}-{time.strftime('%Y%m%d%H%M%S')}"
    commande = dict(vs)
    commande.update({'mode': 'tts', 'beats': beats})
    commande.setdefault('fournisseur', 'azure')
    git(a.depot, 'pull', '-q', '--rebase', 'origin', 'studio')
    os.makedirs(os.path.join(a.depot, 'commandes'), exist_ok=True)
    json.dump(commande, open(os.path.join(a.depot, 'commandes', nom + '.json'), 'w'), ensure_ascii=False, indent=1)
    git(a.depot, 'add', 'commandes')
    git(a.depot, '-c', 'user.name=Regie', '-c', 'user.email=regie@users.noreply.github.com', 'commit', '-qm', f'commande {nom}')
    r = git(a.depot, 'push', '-q', 'origin', 'studio')
    if r.returncode:
        print('Envoi au studio impossible :', r.stderr[-400:]); sys.exit(2)
    print(f'Commande {nom} envoyée ({len(beats)} phrases), en attente du studio…', flush=True)
    debut = time.time()
    while time.time() - debut < a.attente:
        time.sleep(20)
        git(a.depot, 'pull', '-q', '--rebase', 'origin', 'studio')
        c = json.load(open(os.path.join(a.depot, 'commandes', nom + '.json')))
        if c.get('statut') == 'traitée':
            src = os.path.join(a.depot, 'sorties', nom)
            os.makedirs(a.sortie, exist_ok=True)
            for f in os.listdir(src):
                shutil.copy(os.path.join(src, f), os.path.join(a.sortie, f))
            print(f'Audio livré : {len(beats)} phrases en {int(time.time() - debut)} s.')
            sys.exit(0)
        if c.get('statut') == 'erreur':
            print('Erreur du studio :', c.get('erreur')); sys.exit(2)
    print('Délai dépassé.'); sys.exit(3)


if __name__ == '__main__':
    main()
