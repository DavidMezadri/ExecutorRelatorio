"""Paraná: Atlas Geomorfológico do Estado do Paraná (OKA-FIORI et al., 2006) – subunidade morfoescultural de cada
unidade, texto do planalto e da subunidade (garimpo.geomorfologia_pr)."""
import re

from ferramentas.provedores.comum import lista

TEMA = "geomorfologia"
NOME = "PR – Atlas Geomorfológico do Estado do Paraná (MINEROPAR/UFPR)"
UFS = {"PR"}
BASES = ["MINEROPAR", "Atlas Geomorfológico", "UFPR", "ITCG", "IAT"]
MORFO = {"1": "Cinturão Orogênico do Atlântico", "2": "Bacia Sedimentar do Paraná",
         "3": "Bacias Sedimentares Cenozóicas e Depressões Tectônicas"}


def texto_subunidade(s, cit):
    tx = s.get("texto") or ""
    # tira as estatísticas da folha 1:250.000 (área da subunidade na folha) e reescreve o início
    tx = re.sub(r",? e ocupa uma área de [\d.,]+ km²,? que corresponde a [\d.,]+ ?% desta Folha", "", tx)
    tx = re.sub(r" (?:em|de) (?:uma área|um total)(?: total)? de [\d.,]+ km ?2?²?", "", tx)
    tx = re.sub(r"^A sub-unidade morfoescultural número [\d.]+, denominada (.+?), situada no ([^,]+), ",
                r"A subunidade \1, situada no \2, ", tx)
    tx = tx.replace("altitutudes", "altitudes").replace("m. s. n. m.", "m.").replace("m.. ", "m. ")
    tx = re.sub(r" \(metros sobre o nível do mar\)", "", tx)
    un = s.get("unidades_projeto") or []
    return (tx.rstrip(".") + f" ({cit}). Nessa subunidade "
            + ("situam-se as unidades " if len(un) > 1 else "situa-se a unidade ") + f"{lista(un)}.")


def consultar(ctx):
    from ferramentas.garimpo import geomorfologia_pr as gpr
    pr = gpr.para_projeto(ctx["cfg"]["chave"])
    subs = pr.get("subunidades") or []
    if not subs:
        return None
    cit = gpr.CIT
    s0 = subs[0]
    nomes = [f"{s['nome']} ({s['codigo']})" for s in subs]
    pars = [f"Segundo o Atlas Geomorfológico do Estado do Paraná ({cit}), o empreendimento insere-se na unidade "
            f"morfoestrutural {MORFO.get(s0['codigo'][0])}"
            + (f", unidade morfoescultural {s0['unidade']}" if s0.get("unidade") else "")
            + f", {'subunidades morfoesculturais' if len(subs) > 1 else 'subunidade morfoescultural'} {lista(nomes)}."]
    for un, tx in (pr.get("planaltos") or {}).items():
        if tx:
            pars.append(f"{tx if tx.endswith('s.n.m.') else tx.rstrip('.')} ({cit}).")
    pars += [texto_subunidade(s, cit) for s in subs]
    return {"paragrafos": pars, "refs": ["oka-fiori-2006"], "subunidades": subs,
            "resumo": [f"{n}: {x['codigo'] if x else '-'}" for n, x in (pr.get("por_unidade") or {}).items()]}
