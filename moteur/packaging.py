"""Agent Packaging — description YouTube (chapitres, sources, mention légale) à partir de la spec et du résultat de production.

Usage : python3 packaging.py spec.json resultat.json > description.txt
resultat.json = sortie JSON de produire.py ({"fichier","duree","chapitres"})
"""
import json, re, sys

MENTION = ("Cette vidéo est éducative : ce n'est pas un conseil en investissement personnalisé. "
           "Les chiffres cités sont vérifiés à la date indiquée et peuvent évoluer ; investir comporte un risque de perte en capital.")


LIMITE_OCTETS = 4900  # YouTube : 5 000 octets maximum


def propre(texte):
    """YouTube refuse les caractères < et > dans une description."""
    texte = re.sub(r'\s*>=\s*', ' au moins ', texte)
    texte = re.sub(r'\s*<=\s*', ' au plus ', texte)
    texte = re.sub(r'\s*>\s*', ' plus de ', texte)
    texte = re.sub(r'\s*<\s*', ' moins de ', texte)
    return texte.replace('≥', 'au moins').replace('≤', 'au plus')


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
        internes = ('calcul', 'simulation', 're-vérification', 'reverification', 'note', 'vérificateur')
        lignes += [f"- {s}" for s in v['sources'] if not s.strip().lower().startswith(internes)]
        lignes.append('')
    fin = [MENTION]
    if spec.get('hashtags'):
        fin += ['', ' '.join(spec['hashtags'])]
    lignes = [propre(l) for l in lignes]
    # Respect de la limite YouTube : on retire les dernières sources si nécessaire
    while len('\n'.join(lignes + fin).encode('utf-8')) > LIMITE_OCTETS and any(l.startswith('- ') for l in lignes):
        i = max(k for k, l in enumerate(lignes) if l.startswith('- '))
        del lignes[i]
    return '\n'.join(lignes + fin)


if __name__ == '__main__':
    spec = json.load(open(sys.argv[1]))
    res = json.load(open(sys.argv[2]))
    print(description(spec, res))
