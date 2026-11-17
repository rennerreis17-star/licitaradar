"""
Monta a base de CONTRATOS assinados (PNCP) para a página Mercado:
  data/contratos/meta.json, data/contratos/XX.json (por UF), data/contratos/_estado.json

Cada execução busca os dias que ainda faltam (até DIAS_CONTRATOS para trás), em paralelo,
respeitando um tempo máximo. A base vai crescendo a cada coleta e mantém JANELA dias.
Só guarda fornecedores pessoa jurídica (CNPJ) — CPFs de pessoas físicas são descartados.
"""
import json, os, sys, time, datetime, threading
from concurrent.futures import ThreadPoolExecutor

URL = "https://pncp.gov.br/api/consulta/v1/contratos"
DIAS = int(os.getenv("DIAS_CONTRATOS", "30"))
JANELA = int(os.getenv("JANELA_CONTRATOS", "180"))
LIMITE = int(os.getenv("MINUTOS_CONTRATOS", "18")) * 60
PASTA = os.path.join(os.path.dirname(__file__), "..", "data", "contratos")
INICIO = time.time()
lock = threading.Lock()


def log(*a):
    with lock:
        print(f"[contratos {int(time.time()-INICIO):>4}s]", *a, flush=True)


def get(url):
    espera = 5
    for _ in range(5):
        if time.time() - INICIO > LIMITE:
            raise TimeoutError("tempo esgotado")
        try:
            import urllib.request, urllib.error
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "LicitaRadar/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                if r.status == 204:
                    return None
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            code = getattr(e, "code", None)
            if code == 204:
                return None
            if code and code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(espera); espera = min(espera * 2, 60)
    raise RuntimeError("sem resposta")


def curto(x):
    ni = "".join(ch for ch in str(x.get("niFornecedor") or "") if ch.isdigit())
    if len(ni) != 14:
        return None
    org = x.get("orgaoEntidade") or {}
    uo = x.get("unidadeOrgao") or {}
    return {
        "p": x.get("numeroControlePNCP") or "",
        "f": ni,
        "fn": (x.get("nomeRazaoSocialFornecedor") or "").strip()[:120],
        "o": (x.get("objetoContrato") or "").strip()[:300],
        "v": x.get("valorGlobal") or x.get("valorInicial"),
        "g": org.get("razaoSocial") or "",
        "u": uo.get("ufSigla") or "",
        "m": uo.get("municipioNome") or "",
        "d": (x.get("dataAssinatura") or x.get("dataPublicacaoPncp") or "")[:10],
    }


def coletar_dia(dia):
    d = dia.replace("-", "")
    itens, pagina = [], 1
    while True:
        try:
            j = get(f"{URL}?dataInicial={d}&dataFinal={d}&pagina={pagina}&tamanhoPagina=50")
        except Exception as e:
            log(f"{dia}: parou na página {pagina} ({e})")
            return dia, itens, False
        if not j:
            break
        dados = j.get("data") or []
        itens += [c for c in (curto(x) for x in dados) if c]
        tot = j.get("totalPaginas")
        if pagina == 1:
            log(f"{dia}: {tot} página(s)")
        if not dados or (tot and pagina >= tot):
            break
        pagina += 1
    return dia, itens, True


def main():
    os.makedirs(PASTA, exist_ok=True)
    est_path = os.path.join(PASTA, "_estado.json")
    estado = json.load(open(est_path)) if os.path.exists(est_path) else {"feitos": []}
    hoje = (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).date()
    feitos = set(estado.get("feitos", []))
    # ontem e anteontem sempre recoletados (contratos chegam com atraso)
    alvo = [(hoje - datetime.timedelta(days=i)).isoformat() for i in range(1, DIAS + 1)]
    pend = [d for i, d in enumerate(alvo) if i < 2 or d not in feitos]
    log(f"{len(pend)} dia(s) para coletar")

    novos, ok_dias = [], []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for dia, itens, ok in ex.map(coletar_dia, pend):
            novos += itens
            if ok:
                ok_dias.append(dia)

    # junta com a base existente
    por_uf = {}
    for f in os.listdir(PASTA):
        if f.endswith(".json") and len(f) == 7:
            por_uf[f[:2]] = json.load(open(os.path.join(PASTA, f)))
    limite = (hoje - datetime.timedelta(days=JANELA)).isoformat()
    idx = {}
    for uf, lst in por_uf.items():
        for c in lst:
            idx[c["p"] or (c["f"] + c["d"] + c["o"][:30])] = c
    for c in novos:
        idx[c["p"] or (c["f"] + c["d"] + c["o"][:30])] = c
    por_uf = {}
    for c in idx.values():
        if c["d"] and c["d"] >= limite and c["u"]:
            por_uf.setdefault(c["u"], []).append(c)
    for f in os.listdir(PASTA):
        if f.endswith(".json") and len(f) == 7:
            os.remove(os.path.join(PASTA, f))
    for uf, lst in por_uf.items():
        lst.sort(key=lambda c: c["d"], reverse=True)
        json.dump(lst, open(os.path.join(PASTA, f"{uf}.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    feitos = sorted(d for d in (feitos | set(ok_dias)) if d >= limite)
    json.dump({"feitos": feitos}, open(est_path, "w"))
    total = sum(len(v) for v in por_uf.values())
    meta = {"atualizado": (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S-03:00"),
            "total": total, "por_uf": {k: len(v) for k, v in sorted(por_uf.items())},
            "dias_cobertos": len(feitos), "novos_nesta_coleta": len(novos)}
    json.dump(meta, open(os.path.join(PASTA, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"total na base: {total} contratos · dias cobertos: {len(feitos)}")


if __name__ == "__main__":
    main()
