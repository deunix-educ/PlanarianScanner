#!/bin/bash
# Installe le binaire précompilé ReductStore (évite ~16 min de compilation cargo sur RPi4).
# usage: sudo reductstore.sh   -> /usr/local/bin/reductstore
set -e
case "$(uname -m)" in
    aarch64) T=aarch64-unknown-linux-gnu ;;
    x86_64)  T=x86_64-unknown-linux-gnu ;;
    *) echo "architecture non supportée: $(uname -m)"; exit 1 ;;
esac
if command -v reductstore >/dev/null && [ -z "$FORCE" ]; then
    echo "reductstore déjà installé: $(command -v reductstore)"; exit 0
fi
D=$(mktemp -d); trap 'rm -rf "$D"' EXIT
curl -fL --retry 3 -o "$D/rs.tar.gz" \
    "https://github.com/reductstore/reductstore/releases/latest/download/reductstore.$T.tar.gz"
tar -xzf "$D/rs.tar.gz" -C "$D"
install -m 755 "$(find "$D" -name reductstore -type f | head -1)" /usr/local/bin/reductstore
echo "installé: $(/usr/local/bin/reductstore --version 2>&1 | head -1)"
