"""Agent Packaging — description YouTube (chapitres, sources, mention légale) à partir de la spec et du résultat de production.

Usage : python3 packaging.py spec.json resultat.json > description.txt
resultat.json = sortie JSON de produire.py ({"fichier","duree","chapitres"})
"""
import json, sys

MENTION = ("Cette vidéo est éducative : ce n'est pas un conseil en investissement personnalisé. "
           "Les chiffres cités sont vérifiés à la date indiquée et peuvent évoluer ; investir comporte un risque de perte en capital.")


def horo(t):
    t = int(t)
    return f"{t // 60}:{t % 60:02d}"


def description(spec, res):
    lignes = []
    if spec.get('accroche'):
        lignes += [spec['accroche'], '']
    chap = res.get('chapitres') or []
    if chap:
        if chap[0][0] > 0.5:
            chap = [[0, 'Introduction']] + chap
        lignes.append('Chapitres')
        lignes += [f"{horo(t)} {nom}" for t, nom in chap]
        lignes.append('')
    v = spec.get('verification', {})
    if v.get('sources'):
        d = v.get('date', '')
        d = '/'.join(reversed(d.split('-'))) if d.count('-') == 2 else d
        lignes.append(f"Sources (vérifiées le {d})")
        lignes += [f"- {s}" for s in v['sources'] if not s.startswith(('Calculs', 'Simulation'))]
        lignes.append('')
    lignes.append(MENTION)
    if spec.get('hashtags'):
        lignes += ['', ' '.join(spec['hashtags'])]
    return '\n'.join(lignes)


if __name__ == '__main__':
    spec = json.load(open(sys.argv[1]))
    res = json.load(open(sys.argv[2]))
    print(description(spec, res))
