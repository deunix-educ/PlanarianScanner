#!/bin/bash

if [ $# -lt 6 ]; then
    echo "Usage: $0 <input> <width> <height> <x> <y> <fps> [output] [crf]"
    echo "Exemple: $0 video.mp4 1280 856 0 84 5 output.mp4 18"
    exit 1
fi

input_file="$1"
width="$2"
height="$3"
x="$4"
y="$5"
fps="$6"
output_file="${7:-output.mp4}"
crf="${8:-28}"

if [ ! -f "$input_file" ]; then
    echo "Erreur: '$input_file' introuvable"
    exit 1
fi

echo "Crop: ${width}x${height} @ ($x,$y) | FPS: $fps | CRF: $crf"
ffmpeg -i "$input_file" -vf "crop=$width:$height:$x:$y,fps=$fps" -c:v libx264 -crf $crf "$output_file"

[ $? -eq 0 ] && echo "✓ Succès: $(ls -lh "$output_file" | awk '{print $9, $5}')" || echo "✗ Erreur"
