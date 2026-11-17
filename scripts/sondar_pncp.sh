#!/usr/bin/env bash
# Sonda a busca do PNCP (usada pelo site deles) para entender o formato e o CORS.
set -u
mkdir -p data/_sonda
CNPJ="${1:-00000000000191}"
UA="LicitaRadar/1.0"
for st in "" "&status=vigente"; do
  n=$([ -z "$st" ] && echo todos || echo vigente)
  curl -s -m 60 -D "data/_sonda/h_${n}.txt" -H "Origin: https://rennerreis17-star.github.io" -A "$UA" \
    "https://pncp.gov.br/api/search/?q=${CNPJ}&tipos_documento=contrato&ordenacao=-data&pagina=1&tam_pagina=5${st}" -o "data/_sonda/r_${n}.json"
done
curl -s -m 60 -X OPTIONS -D data/_sonda/h_options.txt -H "Origin: https://rennerreis17-star.github.io" -H "Access-Control-Request-Method: GET" \
  "https://pncp.gov.br/api/search/?q=${CNPJ}&tipos_documento=contrato" -o /dev/null
curl -s -m 60 -D data/_sonda/h_consulta.txt -H "Origin: https://rennerreis17-star.github.io" -A "$UA" \
  "https://pncp.gov.br/api/consulta/v1/contratacoes/proposta?dataFinal=20261231&pagina=1&tamanhoPagina=10&codigoModalidadeContratacao=6" -o /dev/null
curl -s -m 60 -D data/_sonda/h_brasilapi.txt -H "Origin: https://rennerreis17-star.github.io" "https://brasilapi.com.br/api/cnpj/v1/00000000000191" -o /dev/null
ls -la data/_sonda
