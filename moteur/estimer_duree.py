"""Estime la durée finale d'une vidéo AVANT de commander la voix au studio (évite de gaspiller le quota Azure).

Usage : python3 estimer_duree.py spec.json
Mesure le texte avec la voix locale, puis applique le coefficient de la voix studio de la spec
(mesuré sur la même phrase lors du casting du 02/11/2026). Code 0 si l'estimation ≥ 630 s (10 min 30 de marge), sinon 4.
"""
import glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voix import synthetiser
from produire2 import beats_de, rogner_silences, lire_wav

# durée voix studio / durée voix locale (Piper upmc locuteur 1, vitesse 0,97), même texte
COEF = {
    ('fr-FR-Marc:MAI-Voice-2.1', '+6%'): 1.17,
    ('fr-FR-Remy:DragonHDLatestNeural', '+6%'): 0.96,
    ('fr-FR-Remy:DragonHDLatestNeural', '+0%'): 1.02,
}
SEUIL = 630


def main():
    spec = json.load(open(sys.argv[1]))
    racine = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    m = glob.glob(os.path.join(os.environ.get('VOIX_DIR', os.path.join(racine, 'voix')), '**', 'fr_FR-upmc-medium.onnx'), recursive=True)[0]
    tmp = os.path.join(racine, '_estimation.wav')
    tot = 0.0
    beats = beats_de(spec)
    for b in beats:
        synthetiser(b['voix'], m, 1, tmp, 0.97)
        a, sr = lire_wav(tmp)
        tot += len(rogner_silences(a, sr)) / sr + (0.32 if b['fin_scene'] else 0.10)
    os.remove(tmp)
    vs = spec.get('voix_studio') or {}
    coef = COEF.get((vs.get('voix'), vs.get('debit', '+0%')), 1.0)
    est = tot * coef
    print(json.dumps({'plans': len(beats), 'mots': sum(len(b['voix'].split()) for b in beats),
                      'estimation_s': round(est), 'estimation': f"{int(est // 60)} min {int(est % 60):02d}",
                      'coef_voix': coef, 'ok': est >= SEUIL}, ensure_ascii=False))
    sys.exit(0 if est >= SEUIL else 4)


if __name__ == '__main__':
    main()
