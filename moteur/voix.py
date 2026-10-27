"""Agent Voix — normalisation de prononciation + synthèse Piper."""
import re, wave, io, os, subprocess, json
import numpy as np

LETTRES = {'A': 'a', 'B': 'bé', 'C': 'cé', 'D': 'dé', 'E': 'eu', 'F': 'èf', 'G': 'gé', 'H': 'ache',
           'I': 'i', 'J': 'ji', 'K': 'ka', 'L': 'èl', 'M': 'èm', 'N': 'èn', 'O': 'o', 'P': 'pé',
           'Q': 'ku', 'R': 'èr', 'S': 'èss', 'T': 'té', 'U': 'u', 'V': 'vé', 'W': 'double vé',
           'X': 'iks', 'Y': 'i grec', 'Z': 'zèd'}
# Sigles prononcés comme des mots (ne pas épeler)
MOTS = {'SPIVA': 'spiva', 'UNESCO': 'unesco', 'OCDE': 'o cé dé eu', 'SASU': 'sazu',
        'NASDAQ': 'nasdaq', 'INSEE': 'insé', 'CAC': 'cac', 'PIB': 'pé i bé'}
# Corrections lexicales (appliquées avant tout)
LEXIQUE = {
    r'\bS&P\b': 'èss and pi', r'\bS&amp;P\b': 'èss and pi',
    r'\bDow Jones\b': 'dao djones', r'\bMd€': ' milliards d\'euros', r'\bMd\b': 'milliards',
    r'\bk€': ' mille euros', r'\bvs\b': 'contre', r'\bETFs\b': 'é té èf',
    r'\b1er\b': 'premier', r'\b1re\b': 'première',
}


def epeler(sigle):
    return '-'.join(LETTRES.get(c, c) for c in sigle)


def normaliser(texte):
    t = texte
    for motif, rempl in LEXIQUE.items():
        t = re.sub(motif, rempl, t)
    t = t.replace('€', ' euros').replace('%', ' pour cent').replace('≈', 'environ ')
    t = t.replace('«', '').replace('»', '').replace('—', ', ').replace('–', ', ')
    t = re.sub(r'(\d)\s(\d{3})', r'\1\2', t)  # 15 700 -> 15700 (lecture correcte)

    def sigle(m):
        s = m.group(0)
        if s in MOTS:
            return MOTS[s]
        return epeler(s)
    t = re.sub(r'\b[A-Z]{2,6}\b', sigle, t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


_VOIX = {}


def charger(modele):
    from piper import PiperVoice
    if modele not in _VOIX:
        _VOIX[modele] = PiperVoice.load(modele)
    return _VOIX[modele]


def synthetiser(texte, modele, locuteur, sortie_wav, vitesse=1.0):
    """Synthétise le texte normalisé vers un WAV ; renvoie la durée (s)."""
    from piper import SynthesisConfig
    voix = charger(modele)
    cfg = SynthesisConfig(speaker_id=locuteur, length_scale=1.0 / vitesse)
    with wave.open(sortie_wav, 'wb') as wf:
        voix.synthesize_wav(normaliser(texte), wf, syn_config=cfg)
    with wave.open(sortie_wav) as wf:
        return wf.getnframes() / wf.getframerate()
