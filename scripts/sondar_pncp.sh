#!/usr/bin/env bash
set -u
mkdir -p data/_sonda; rm -f data/_sonda/*
CNPJ="${1:-00000000000191}"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
i=0
for url in \
 "https://pncp.gov.br/api/search/?q=${CNPJ}&tipos_documento=contrato&ordenacao=-data&pagina=1&tam_pagina=5" \
 "https://pncp.gov.br/api/search?q=${CNPJ}&tipos_documento=contrato&pagina=1&tam_pagina=5" \
 "https://pncp.gov.br/api/search/?q=${CNPJ}&tipos_documento=contrato&ordenacao=-data&pagina=1&tam_pagina=5&status=vigente" \
 "https://pncp.gov.br/api/search/?q=limpeza&tipos_documento=edital&ordenacao=-data&pagina=1&tam_pagina=2&status=recebendo_proposta" ; do
  i=$((i+1))
  curl -sS -m 90 -D "data/_sonda/h_$i.txt" -H "Origin: https://rennerreis17-star.github.io" -H "Accept: application/json" -H "Referer: https://pncp.gov.br/app/contratos" -A "$UA" "$url" -o "data/_sonda/r_$i.json" 2> "data/_sonda/e_$i.txt"
  echo "$i rc=$? $url" >> data/_sonda/log.txt
done
