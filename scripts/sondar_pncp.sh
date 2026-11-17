#!/usr/bin/env bash
set -u
mkdir -p data/_sonda; rm -f data/_sonda/*
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
i=0
for url in \
 "https://pncp.gov.br/api/search/?q=limpeza&tipos_documento=contrato&ordenacao=-data&pagina=1&tam_pagina=100&ufs=PA&status=vigente" \
 "https://pncp.gov.br/api/search/?q=limpeza&tipos_documento=contrato&ordenacao=-data&pagina=1&tam_pagina=500&uf=PA&status=vigente" \
 "https://pncp.gov.br/api/search/?q=&tipos_documento=edital&ordenacao=-data&pagina=1&tam_pagina=500&status=recebendo_proposta" \
 "https://pncp.gov.br/api/search/?q=limpeza&tipos_documento=contrato&ordenacao=-data&pagina=1&tam_pagina=50&ufs=PA&municipios=3870&status=vigente" ; do
  i=$((i+1)); s=$(date +%s)
  curl -sS -m 120 -D "data/_sonda/h_$i.txt" -H "Accept: application/json" -A "$UA" "$url" -o "data/_sonda/r_$i.json" 2> "data/_sonda/e_$i.txt"
  echo "$i rc=$? t=$(( $(date +%s)-s ))s $url" >> data/_sonda/log.txt
done
