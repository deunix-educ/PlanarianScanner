#!/bin/bash

# Génère 24 vidéos pour simuler le balayage d'un multi-puit de 6x24 
#   A1..A6, B1..B6, C1..C6, D1..D6
#  
MODE="$1"
PATH="./media/simulation"
default_width=1000      # px
default_height=1000     # px
default_diameter=16.0   # mm

     #fps duration bg-color arena-color arena-border shadow-color body-color body-dark body-light head-color thresh-immobile thresh-mobile
BASE="15  60       #EBEBEB  #FAFAFA     #8C8C8C      #C8C8C8      #A5A5A5    #373737   #D2D2D2    #828282    0.2             1.5"

        #photo-mode photo-strength photo-x photo-y photo-sine-freq photo-radius
PHOTO_0="none       0.50           0.50    0.50    0.10            0.30"
PHOTO_1="fixed      0.50           0.50    0.50    0.10            0.40"
PHOTO_2="sine       0.50           0.50    0.50    0.10            0.50"
PHOTO_3="radial     0.50           0.50    0.50    0.10            0.60"

        #chemo-strength chemo-x chemo-y chemo-radius
CHEMO_0="0.0            0.70    0.70    2.0"
CHEMO_1="0.5            0.70    0.70    2.0"
CHEMO_2="1.0            0.70    0.70    2.0"

        #avoid-strength avoid-radius aggreg-strength aggreg-radius chem-repulsion chem-decay
AVOID_0="0.0            3.0          0.0             6.0           0.0            0.95"
AVOID_1="0.5            3.0          0.0             6.0           0.5            0.75"
AVOID_2="1.0            3.0          0.0             6.0           1.0            0.65"

       #length width
SIZE_0="0.40   0.30"
SIZE_1="0.45   0.35"
SIZE_2="0.50   0.40"
SIZE_3="0.55   0.45"
SIZE_4="0.65   0.45"
SIZE_5="0.7    0.25"

declare -A DEFAULT
declare -A ALL

#=========================== count size    seed  base  thigmotaxis photo    chemo    avoid
DEFAULT[default_simulation]="4     $SIZE_0  32   $BASE 0.45        $PHOTO_0 $CHEMO_0 $AVOID_1"

    
#======= count size    seed  base  thigmotaxis photo    chemo    avoid
ALL[A1]="4     $SIZE_0  32   $BASE 0.45        $PHOTO_0 $CHEMO_0 $AVOID_0"
ALL[A2]="4     $SIZE_1  64   $BASE 0.50        $PHOTO_1 $CHEMO_1 $AVOID_1"
ALL[A3]="4     $SIZE_2  96   $BASE 0.55        $PHOTO_1 $CHEMO_2 $AVOID_2"
ALL[A4]="4     $SIZE_3  128  $BASE 0.60        $PHOTO_2 $CHEMO_0 $AVOID_1"   
ALL[A5]="4     $SIZE_4  192  $BASE 0.65        $PHOTO_2 $CHEMO_1 $AVOID_0"
ALL[A6]="4     $SIZE_5  240  $BASE 0.75        $PHOTO_3 $CHEMO_2 $AVOID_2"
ALL[B1]="4     $SIZE_0  32   $BASE 0.45        $PHOTO_3 $CHEMO_0 $AVOID_0"
ALL[B2]="4     $SIZE_1  64   $BASE 0.50        $PHOTO_0 $CHEMO_1 $AVOID_1"    
ALL[B3]="4     $SIZE_2  96   $BASE 0.55        $PHOTO_0 $CHEMO_2 $AVOID_0"
ALL[B4]="4     $SIZE_3  128  $BASE 0.65        $PHOTO_0 $CHEMO_1 $AVOID_2" 
ALL[B5]="4     $SIZE_4  192  $BASE 0.85        $PHOTO_0 $CHEMO_2 $AVOID_0"
ALL[B6]="4     $SIZE_5  240  $BASE 0.95        $PHOTO_0 $CHEMO_0 $AVOID_0" 
ALL[C1]="4     $SIZE_0  32   $BASE 0.40        $PHOTO_0 $CHEMO_0 $AVOID_1"    
ALL[C2]="4     $SIZE_1  64   $BASE 0.30        $PHOTO_0 $CHEMO_0 $AVOID_0"      
ALL[C3]="4     $SIZE_2  96   $BASE 0.55        $PHOTO_0 $CHEMO_1 $AVOID_0"    
ALL[C4]="4     $SIZE_3  128  $BASE 0.45        $PHOTO_0 $CHEMO_2 $AVOID_2"    
ALL[C5]="4     $SIZE_4  192  $BASE 0.50        $PHOTO_0 $CHEMO_0 $AVOID_0"    
ALL[C6]="4     $SIZE_5  240  $BASE 0.65        $PHOTO_0 $CHEMO_1 $AVOID_0"    
ALL[D1]="4     $SIZE_0  32   $BASE 0.70        $PHOTO_0 $CHEMO_2 $AVOID_1"    
ALL[D2]="4     $SIZE_1  64   $BASE 0.65        $PHOTO_0 $CHEMO_0 $AVOID_0"
ALL[D3]="4     $SIZE_2  96   $BASE 0.75        $PHOTO_0 $CHEMO_1 $AVOID_2"    
ALL[D4]="4     $SIZE_3  128  $BASE 0.85        $PHOTO_0 $CHEMO_0 $AVOID_0"
ALL[D5]="4     $SIZE_4  192  $BASE 0.65        $PHOTO_0 $CHEMO_2 $AVOID_0"    
ALL[D6]="4     $SIZE_5  240  $BASE 0.45        $PHOTO_0 $CHEMO_0 $AVOID_0"        


export_video() {
    local -n arguments=$1
    
    for key in "${!arguments[@]}"; do
        args="${arguments[$key]}"
        read -r count length width seed fps duration bg_color arena_color arena_border shadow_color \
                body_color body_dark body_light head_color thresh_immobile thresh_mobile thigmotaxis \
                photo_mode photo_strength photo_x photo_y photo_sine_freq photo_radius chemo_strength chemo_x chemo_y chemo_radius \
                avoid_strength avoid_radius aggreg_strength aggreg_radius chem_repulsion chem_decay <<< "$args"
                
        echo "==== Exécution de $PATH/$key.mp4"
        
        ./planarian_sim.py --output "$PATH/$key.mp4" --default_width "$default_width" --default_height "$default_height" --default_diameter "$default_diameter"  --no-csv \
            --count "$count" --length "$length" --width "$width" --duration "$duration" --fps "$fps" --seed "$seed" \
            --bg-color "$bg_color" --arena-color "$arena_color" --arena-border "$arena_border" --shadow-color "$shadow_color" \
            --body-color "$body_color" --body-dark  "$body_dark" --body-light "$body_light" --head-color "$head_color" \
            --thresh-immobile "$thresh_immobile" --thresh-mobile "$thresh_mobile" --thigmotaxis "$thigmotaxis"  \
            --photo-mode "$photo_mode" --photo-strength "$photo_strength" --photo-x "$photo_x" --photo-y "$photo_y" --photo-sine-freq "$photo_sine_freq" --photo-radius "$photo_radius"  \
            --chemo-strength "$chemo_strength" --chemo-x "$chemo_x" --chemo-y "$chemo_y" --chemo-radius "$chemo_radius"  \
            --avoid-strength "$avoid_strength" --avoid-radius "$avoid_radius" --aggreg-strength "$aggreg_strength" --aggreg-radius "$aggreg_radius" \
            --chem-repulsion "$chem_repulsion" --chem-decay "$chem_decay"
    done
}

if [ "$MODE" = "all" ]; then
    export_video ALL
else
    export_video DEFAULT
fi

