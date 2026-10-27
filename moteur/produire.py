"""Production complète d'une vidéo à partir d'une spécification JSON.

Usage : python3 produire.py spec.json dossier_sortie [--format long|reel] [--scenes 1-5]
Spec : {"id","chaine","titre","voix":{"modele","locuteur","vitesse"},"theme","scenes":[{"voix","visuel"}...]}
"""
import json, os, sys, subprocess, wave, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from voix import synthetiser
from rendu import rendre_video

PAUSE = 0.35  # silence entre deux scènes (s)
SR = 22050


def lire_wav(p):
    with wave.open(p) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768, w.getframerate()


def ecrire_wav(p, x, sr):
    x = np.clip(x, -1, 1)
    with wave.open(p, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def musique(duree, sr=44100, graine=7):
    """Nappe d'ambiance générée (libre de droits) : accords lents, filtrés, sans percussion."""
    rng = np.random.default_rng(graine)
    t = np.arange(int(duree * sr)) / sr
    # progression i–VI–III–VII en la mineur (fréquences des fondamentales)
    accords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [261.63, 329.63, 392.0], [196.0, 246.94, 293.66]]
    seg = 8.0
    out = np.zeros_like(t)
    for k in range(int(duree / seg) + 2):
        acc = accords[k % 4]
        deb = k * seg
        env = np.clip(1 - np.abs((t - deb - seg / 2) / (seg * 0.75)), 0, 1) ** 1.5
        for f in acc:
            for det in (-0.6, 0.6):
                ph = rng.uniform(0, 2 * np.pi)
                out += env * np.sin(2 * np.pi * (f / 2) * (1 + det / 1000) * t + ph) * 0.08
                out += env * np.sin(2 * np.pi * f * (1 + det / 1000) * t + ph) * 0.04
    out *= 0.7 + 0.3 * np.sin(2 * np.pi * 0.05 * t)
    # filtrage doux (moyenne glissante)
    k = 32
    out = np.convolve(out, np.ones(k) / k, mode='same')
    fade = int(3 * sr)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out / (np.max(np.abs(out)) + 1e-9) * 0.5, sr


def produire(spec, dossier, taille=(1920, 1080), plage=None):
    os.makedirs(dossier, exist_ok=True)
    tmp = os.path.join(dossier, '_tmp'); os.makedirs(tmp, exist_ok=True)
    scenes = spec['scenes']
    if plage:
        scenes = scenes[plage[0] - 1:plage[1]]
    v = dict(spec['voix'])
    if not os.path.exists(v['modele']):
        import glob as _g
        c = _g.glob(os.path.join(os.environ.get('VOIX_DIR', os.path.join(os.path.dirname(__file__), '..', 'voix')), '**', v['modele']), recursive=True)
        v['modele'] = c[0]
    audio, durees = [], []
    for i, sc in enumerate(scenes):
        p = os.path.join(tmp, f's{i:02d}.wav')
        synthetiser(sc['voix'], v['modele'], v.get('locuteur', 0), p, v.get('vitesse', 1.0))
        x, sr = lire_wav(p)
        lead = np.zeros(int(0.15 * sr), np.float32)
        tail = np.zeros(int(PAUSE * sr), np.float32)
        seg = np.concatenate([lead, x, tail])
        audio.append(seg)
        durees.append(len(seg) / sr)
        print(f'  voix scène {i + 1}/{len(scenes)} : {durees[-1]:.1f} s', flush=True)
    voix_wav = os.path.join(tmp, 'voix.wav')
    ecrire_wav(voix_wav, np.concatenate(audio), sr)
    duree = sum(durees)

    muet = os.path.join(tmp, 'muet.mp4')
    print(f'  rendu visuel ({duree:.0f} s)…', flush=True)
    rendre_video([s['visuel'] for s in scenes], durees, muet, spec.get('theme', 'finance'), taille)

    mus, msr = musique(duree + 1)
    mus_wav = os.path.join(tmp, 'musique.wav')
    ecrire_wav(mus_wav, mus, msr)

    sortie = os.path.join(dossier, spec['id'] + ('' if taille[0] > taille[1] else '-reel') + '.mp4')
    # mixage : voix normalisée, musique à -24 dB sous la voix avec ducking léger ; barre de progression
    filtre = ("[1:a]aresample=44100,loudnorm=I=-16:TP=-1.5:LRA=11,asplit[v][vs];"
              "[2:a]volume=0.10[m];[m][vs]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=400[md];"
              "[v][md]amix=inputs=2:normalize=0:duration=first[a];"
              f"[0:v]drawbox=x=0:y=ih-6:w='iw*t/{duree:.3f}':h=6:color=0xF5B83D:t=fill[vid]")
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', muet, '-i', voix_wav, '-i', mus_wav,
                    '-filter_complex', filtre, '-map', '[vid]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast',
                    '-crf', '21', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', sortie], check=True)
    # chapitres pour la description
    chap, t = [], 0.0
    for s, d in zip(scenes, durees):
        if s['visuel']['type'] == 'section' or s.get('chapitre'):
            chap.append((t, s.get('chapitre') or s['visuel'].get('titre')))
        t += d
    return sortie, duree, chap


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('spec'); ap.add_argument('sortie')
    ap.add_argument('--scenes', default=None)
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    plage = tuple(map(int, a.scenes.split('-'))) if a.scenes else None
    out, d, chap = produire(spec, a.sortie, plage=plage)
    print(json.dumps({'fichier': out, 'duree': round(d, 1), 'chapitres': chap}, ensure_ascii=False))
