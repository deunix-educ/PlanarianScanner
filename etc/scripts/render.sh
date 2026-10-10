#!/bin/bash
# render.sh <template.in> <dest>  — remplace les @VARS@ par l'environnement
set -e
sed -e "s#@ROOT@#${ROOT}#g" -e "s#@USER@#${APP_USER}#g" \
    -e "s#@HOSTNAME@#${SCANNER_HOSTNAME}#g" -e "s#@REDUCT_DATA@#${REDUCT_DATA}#g" \
    -e "s#@REDUCT_BIN@#${REDUCT_BIN}#g" -e "s#@WEB_CMD@#${WEB_CMD}#g" \
    -e "s#@RS_TOKEN@#${RS_TOKEN}#g" -e "s#@SUP_BIND@#${SUP_BIND:-0.0.0.0}#g" "$1" > "$2"
