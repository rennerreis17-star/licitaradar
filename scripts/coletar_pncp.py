"""
Coleta as licitações com propostas abertas no PNCP (API pública de consultas)
e grava a base usada pelo painel:
  data/meta.json        -> data da atualização, totais por UF
  data/uf/XX.json       -> licitações de cada UF (campos curtos)

Roda no GitHub Actions (ver .github/workflows/atualizar.yml). Só usa a biblioteca padrão.
Variáveis de ambiente opcionais:
  DIAS     -> janela de encerramento das propostas (padrão 60)
  MINUTOS  -> tempo máximo de coleta (padrão 45)
  MODALIDADES -> códigos separados por vírgula (padrão 6,8,4,7,5,12)
"""
import json, os, sys, time, datetime, threading, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

BASE = "https://pncp.gov.br/api/consulta/v1/contratacoes/proposta"
DIAS = int(os.getenv("DIAS", "60"))
LIMITE = int(os.getenv("MINUTOS", "45")) * 60
MODS = [int(x) for x in os.getenv("MODALIDADES", "6,8,4,7,5,12").split(",") if x.strip()]
TAM = 50
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36 LicitaRadar/1.1"
BUSCA = "https://pncp.gov.br/api/search/"
LIMITE_BUSCA = int(os.getenv("MINUTOS_BUSCA", "12")) * 60
INICIO = time.time()
PASTA = os.path.join(os.path.dirname(__file__), "..", "data")
lock = threading.Lock()
erros = []


def log(*a):
    with lock:
        print(f"[{int(time.time()-INICIO):>5}s]", *a, flush=True)


def get(url):
    espera = 5
    for tentativa in range(6):
        if time.time() - INICIO > LIMITE:
            raise TimeoutError("tempo esgotado")
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                if r.status == 204:
                    return None
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 204:
                return None
            if e.code in (429, 500, 502, 503, 504):
                log(f"HTTP {e.code} — aguardando {espera}s")
                time.sleep(espera); espera = min(espera * 2, 120); continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            if isinstance(e, TimeoutError) and time.time() - INICIO > LIMITE:
                raise
            log(f"falha de rede ({e}) — tentando de novo em {espera}s")
            time.sleep(espera); espera = min(espera * 2, 120)
    raise RuntimeError("PNCP não respondeu após várias tentativas")


def curto(x, mc):
    org = x.get("orgaoEntidade") or {}
    uo = x.get("unidadeOrgao") or {}
    cnpj, ano, seq = org.get("cnpj"), x.get("anoCompra"), x.get("sequencialCompra")
    link = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if cnpj and ano and seq else (x.get("linkSistemaOrigem") or "")
    obj = (x.get("objetoCompra") or "").strip()
    return {
        "p": x.get("numeroControlePNCP") or "",
        "o": obj[:600],
        "g": org.get("razaoSocial") or "",
        "c": cnpj or "",
        "u": uo.get("ufSigla") or "",
        "m": uo.get("municipioNome") or "",
        "v": x.get("valorTotalEstimado"),
        "md": x.get("modalidadeNome") or "",
        "mc": mc,
        "a": x.get("dataAberturaProposta") or "",
        "e": x.get("dataEncerramentoProposta") or "",
        "l": link,
        "lo": x.get("linkSistemaOrigem") or "",
        "n": x.get("numeroCompra") or "",
        "s": 1 if x.get("srp") else 0,
    }


def coletar_modalidade(mc, data_final):
    """Consulta oficial (traz o valor estimado). Páginas em paralelo para caber no tempo."""
    url = lambda p: f"{BASE}?dataFinal={data_final}&codigoModalidadeContratacao={mc}&pagina={p}&tamanhoPagina={TAM}"
    try:
        j = get(url(1))
    except Exception as e:
        erros.append(f"modalidade {mc}, página 1: {e}"); return [], False
    if not j:
        return [], True
    itens = [curto(x, mc) for x in (j.get("data") or [])]
    tot = j.get("totalPaginas") or 1
    log(f"modalidade {mc}: {tot} páginas")
    completo = True
    def pag(p):
        try:
            r = get(url(p)); return [curto(x, mc) for x in ((r or {}).get("data") or [])], True
        except Exception as e:
            return [], False
    with ThreadPoolExecutor(max_workers=6) as ex:
        for lst, ok in ex.map(pag, range(2, tot + 1)):
            itens += lst; completo = completo and ok
    if not completo:
        erros.append(f"modalidade {mc}: algumas páginas não vieram")
    log(f"modalidade {mc}: {len(itens)} itens{'' if completo else ' (parcial)'}")
    return itens, completo


def coletar_busca():
    """Busca do portal PNCP: lista COMPLETA de editais recebendo propostas (sem valor estimado)."""
    out, pagina, total = [], 1, None
    ini = time.time()
    while time.time() - ini < LIMITE_BUSCA:
        try:
            j = get(f"{BUSCA}?q=&tipos_documento=edital&ordenacao=-data&pagina={pagina}&tam_pagina=500&status=recebendo_proposta")
        except Exception as e:
            erros.append(f"busca página {pagina}: {e}"); break
        its = (j or {}).get("items") or []
        total = (j or {}).get("total", total)
        for x in its:
            iu = x.get("item_url") or ""
            link = "https://pncp.gov.br/app/editais/" + iu.split("/compras/", 1)[1] if "/compras/" in iu else ("https://pncp.gov.br/app" + iu if iu else "")
            try: mc = int(x.get("modalidade_licitacao_id") or 0)
            except Exception: mc = 0
            out.append({"p": x.get("numero_controle_pncp") or "", "o": (x.get("description") or "").strip()[:600], "g": x.get("orgao_nome") or "",
                        "c": x.get("orgao_cnpj") or "", "u": x.get("uf") or "", "m": x.get("municipio_nome") or "", "v": None,
                        "md": x.get("modalidade_licitacao_nome") or "", "mc": mc, "a": x.get("data_inicio_vigencia") or "",
                        "e": x.get("data_fim_vigencia") or "", "l": link, "lo": "", "n": x.get("title") or "", "s": 0})
        if pagina == 1 or pagina % 10 == 0:
            log(f"busca: página {pagina} — {len(out)}/{total}")
        if not its or (total and len(out) >= total):
            break
        pagina += 1
    return out, bool(total and len(out) >= total * 0.98)


def main():
    hoje = datetime.datetime.utcnow() - datetime.timedelta(hours=3)
    data_final = (hoje + datetime.timedelta(days=DIAS)).strftime("%Y%m%d")
    log(f"Coletando modalidades {MODS} com encerramento até {data_final}")

    busca, busca_ok = coletar_busca()
    log(f"busca do portal: {len(busca)} editais abertos")
    resultados = []
    for m in MODS:
        resultados.append(coletar_modalidade(m, data_final))

    vistos, por_uf = {}, {}
    agora_iso = hoje.strftime("%Y-%m-%dT%H:%M:%S")
    completo = busca_ok or all(c for _, c in resultados)
    oficial = {}
    for itens, _ in resultados:
        for it in itens:
            if it["p"]: oficial[it["p"]] = it
    def chave(it): return it["p"] or (it["c"] + it["n"] + it["o"][:40])
    for it in busca:
        of = oficial.get(it["p"])
        if of:  # completa com valor, link do sistema de origem e SRP
            it = {**it, "v": of["v"], "lo": of["lo"], "s": of["s"], "n": of["n"] or it["n"], "md": of["md"] or it["md"], "mc": of["mc"] or it["mc"]}
        vistos[chave(it)] = it
    for it in oficial.values():
        if chave(it) not in vistos: vistos[chave(it)] = it
    for it in vistos.values():
        if it["e"] and it["e"] < agora_iso:
            continue
        por_uf.setdefault(it["u"] or "BR", []).append(it)

    total = sum(len(v) for v in por_uf.values())
    log(f"Total: {total} licitações abertas")

    meta_path = os.path.join(PASTA, "meta.json")
    if total == 0:
        log("Nenhum dado coletado — mantendo a base anterior.")
        print("::warning::Coleta do PNCP sem resultados; base anterior mantida. Erros: " + "; ".join(erros[:5]))
        return 0

    os.makedirs(os.path.join(PASTA, "uf"), exist_ok=True)
    for f in os.listdir(os.path.join(PASTA, "uf")):
        if f.endswith(".json"):
            os.remove(os.path.join(PASTA, "uf", f))
    for uf, lista in por_uf.items():
        lista.sort(key=lambda x: x["e"] or "9999")
        with open(os.path.join(PASTA, "uf", f"{uf}.json"), "w", encoding="utf-8") as fh:
            json.dump(lista, fh, ensure_ascii=False, separators=(",", ":"))

    meta = {
        "atualizado": hoje.strftime("%Y-%m-%dT%H:%M:%S-03:00"),
        "total": total,
        "por_uf": {uf: len(v) for uf, v in sorted(por_uf.items())},
        "modalidades": MODS,
        "janela_dias": DIAS,
        "completo": completo,
        "erros": erros[:20],
        "duracao_s": int(time.time() - INICIO),
    }
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
    log("Base gravada em data/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
