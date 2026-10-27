#!/usr/bin/env bash
# Installe l'atelier de la régie dans une session vierge (≈ 1 à 2 minutes).
# Usage : bash moteur/installer.sh   (depuis la racine du clone de la branche « atelier »)
set -e
RACINE="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$RACINE/voix" "$RACINE/moteur/polices"
pip install -q --break-system-packages piper-tts numpy pillow soundfile 2>&1 | grep -v WARNING || true
cd "$RACINE/voix"
for v in fr_FR-upmc-medium fr_FR-tom-medium fr_FR-siwis-medium; do
  if [ ! -d "vits-piper-$v" ]; then
    curl -sL -m 300 -o "$v.tar.bz2" "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-$v.tar.bz2"
    tar xjf "$v.tar.bz2" && rm -f "$v.tar.bz2"
  fi
done
if [ ! -f /usr/share/fonts/opentype/inter/Inter-Regular.otf ]; then
  cd "$RACINE/moteur/polices" && npm pack @fontsource/inter@5 --silent >/dev/null 2>&1 && tar xzf fontsource-inter-*.tgz \
    && cp package/files/inter-latin-{400,600,700,800}-normal.woff . && rm -rf package fontsource-inter-*.tgz
fi
command -v ffmpeg >/dev/null || { echo "ffmpeg manquant"; exit 1; }
echo "Atelier prêt : $RACINE"
