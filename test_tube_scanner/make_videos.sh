#!/bin/bash

# Génère 24 vidéos pour simuler le balayage d'un multi-puit de 6x24 
#   A1..A6, B1..B6, C1..C6, D1..D6
#  

PATH="data"
default_width=1000      # px
default_height=1000     # px
default_diameter=16.0   # mm

declare -A arguments=(
    # key count len width sec fps seed thigmotaxis bg-color arena-color arena-border shadow-color body-color body-dark body-light head-color
    ["F0"]="1  0.90 0.30  60  5    64     0.45     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5A7896    #3C5570   #8CA0B4     #46645F"
)

declare -A arguments2=(
    # key count len width sec fps seed thigmotaxis bg-color arena-color arena-border shadow-color body-color body-dark body-light head-color
    ["D1"]="3  0.90 0.30  60  5    64     0.45     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5A7896    #3C5570   #8CA0B4     #46645F"
    ["D2"]="2  0.75 0.40  60  5    96     0.50     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5B7896    #3D5570   #8DA0B4     #47645F"
    ["D3"]="1  0.80 0.50  60  5    42     0.60     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["D4"]="1  0.85 0.40  60  5    28     0.70     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["D5"]="3  0.60 0.35  60  5    132    0.65     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["D6"]="2  0.65 0.35  60  5    256    0.85     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["C6"]="1  0.90 0.30  60  5    64     0.45     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5A7896    #3C5570   #8CA0B4     #46645F"
    ["C5"]="3  0.75 0.40  60  5    96     0.50     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5B7896    #3D5570   #8DA0B4     #47645F"
    ["C4"]="2  0.80 0.50  60  5    42     0.60     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["C3"]="1  0.85 0.40  60  5    28     0.70     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["C2"]="2  0.60 0.35  60  5    132    0.65     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["C1"]="3  0.65 0.35  60  5    256    0.85     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["B1"]="2  0.90 0.30  60  5    64     0.45     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5A7896    #3C5570   #8CA0B4     #46645F"
    ["B2"]="1  0.75 0.40  60  5    96     0.50     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5B7896    #3D5570   #8DA0B4     #47645F"
    ["B3"]="1  0.80 0.50  60  5    42     0.60     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["B4"]="3  0.85 0.40  60  5    28     0.70     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["B5"]="1  0.60 0.35  60  5    132    0.65     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["B6"]="2  0.65 0.35  60  5    256    0.85     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["A6"]="1  0.90 0.30  60  5    64     0.45     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5A7896    #3C5570   #8CA0B4     #46645F"
    ["A5"]="1  0.75 0.40  60  5    96     0.50     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5B7896    #3D5570   #8DA0B4     #47645F"
    ["A4"]="3  0.80 0.50  60  5    42     0.60     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["A3"]="1  0.85 0.40  60  5    28     0.70     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["A2"]="1  0.60 0.35  60  5    132    0.65     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"
    ["A1"]="4  0.65 0.35  60  5    256    0.85     #D4DADC  #BDBDF0       #B4AFA8      #BEBCB6     #5C7896    #3E5570   #8EA0B4     #48645F"   
)


for key in "${!arguments[@]}"; do
    args="${arguments[$key]}"
    read -r count length width duration fps seed thigmotaxis bg_color arena_color arena_border shadow_color body_color body_dark body_light head_color <<< "$args"
    
    echo "==== Exécution de $PATH/$key.mp4"
    
    ./planarian_sim.py --output "$PATH/$key.mp4" --default_width "$default_width" --default_height "$default_height" --default_diameter "$default_diameter" \
        --count "$count" --length "$length" --width "$width" --duration "$duration" --fps "$fps" --seed "$seed" --thigmotaxis "$thigmotaxis" \
        --bg-color  "$bg_color" --arena-color "$arena_color" --arena-border "$arena_border" --shadow-color "$shadow_color" \
        --body-color "$body_color" --body-dark  "$body_dark" --body-light "$body_light" --head-color "$head_color"  --no-csv
done
