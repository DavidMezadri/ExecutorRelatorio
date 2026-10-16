"""Paraná: bacias/UH (IAT, CERH 49/2006), Carta das Águas Subterrâneas do PR (formações e aquíferos) e poços Sanepar
(MENDES et al., 2002). Complementa os provedores nacionais nos temas hidrologia, geologia e hidrogeologia."""
from ferramentas.provedores.comum import lista

TEMAS = ["hidrologia", "geologia", "hidrogeologia"]
TEMA = "hidrologia"
NOME = "PR – IAT, Carta das Águas Subterrâneas do Paraná e Mendes et al. (2002)"
UFS = {"PR"}
BASES = ["IAT", "ITCG", "AGUASPARANÁ", "SUDERHSA", "Carta das Águas", "MINEROPAR"]


def _baixa(s):
    return s[0].lower() + s[1:] if s else s


def consultar(ctx):
    from ferramentas.garimpo import aguas_pr
    cfg = ctx["cfg"]
    ag = aguas_pr.para_projeto(cfg["chave"])
    c = ag.get("citacoes") or {}
    carta, iat, mendes = c.get("carta", "BRASIL, 2015"), c.get("iat", "IAT, [2020]"), c.get("mendes", "MENDES et al., 2002")
    refs = ["brasil-2015-carta-aguas-pr", "iat-dados-espaciais"]
    out = {}

    # hidrologia: bacia (área oficial) e unidade hidrográfica CERH/PR
    pars = []
    rh = {"Litorânea": ("Atlântico Sul", "2,9%"), "Ribeira": ("Atlântico Sudeste", "4,9%")}
    for bacia, x in (ag.get("bacias") or {}).items():
        uhs = [u.title().replace(" Do ", " do ").replace(" Dos ", " dos ").replace(" Da ", " da ")
               for u in x.get("unidades_hidrograficas") or []]
        reg, pct = rh.get(bacia, ("Paraná", "92,2%"))
        pars.append(f"No âmbito estadual, o empreendimento situa-se na Bacia Hidrográfica do Rio {bacia}"
                    + (f", que ocupa {x['area_km2_carta']} km² do território paranaense ({carta})" if x.get("area_km2_carta") else "")
                    + (f", na Unidade Hidrográfica {lista(uhs)}, conforme a divisão estabelecida pela Resolução CERH/PR "
                       f"nº 49/2006 ({iat})" if uhs else "")
                    + f". A bacia integra a Região Hidrográfica do {reg}, que abrange {pct} do território paranaense ({carta}).")
    if pars:
        out["hidrologia"] = {"paragrafos": pars, "refs": refs, "cobre": ["uh_estadual"],
                             "resumo": [f"Bacias: {', '.join(ag.get('bacias') or {})}"]}

    # geologia: descrição da formação na Carta (cap. 2.2)
    pars = []
    for f, frases in (ag.get("formacoes") or {}).items():
        if frases:
            txt = " ".join(frases[:6]).rstrip(".")
            pars.append(f"No Paraná, {_baixa(txt)} ({carta}).")
    if pars:
        out["geologia"] = {"paragrafos": pars, "refs": refs, "resumo": [f"Formações: {', '.join(ag.get('formacoes') or {})}"]}

    # hidrogeologia: unidade aquífera (IAT), hidrodinâmica e vulnerabilidade (Carta), poços Sanepar (Mendes)
    pars = []
    estudo = (cfg.get("empresa") or {}).get("estudos_pocos")
    for aq, x in (ag.get("aquiferos") or {}).items():
        un = ", ".join(x.get("unidade_iat") or [])
        pars.append(f"No mapeamento das unidades aquíferas do Paraná, o empreendimento situa-se na unidade {un or aq} ({iat}), "
                    f"correspondente ao Aquífero {aq} descrito na Carta das Águas Subterrâneas do Paraná ({carta}).")
        if x.get("hidrodinamica"):
            pars.append(" ".join(x["hidrodinamica"]).rstrip(".") + f" ({carta}).")
        if x.get("vulnerabilidade"):
            pars.append("Quanto à vulnerabilidade natural à contaminação, " + _baixa(" ".join(x["vulnerabilidade"]).rstrip("."))
                        + f" ({carta}).")
        if x.get("sanepar") and estudo == "mendes-2002":
            pars.append("No abastecimento público, " + _baixa(x["sanepar"].rstrip(".")) + f" ({mendes}).")
            refs = refs + ["mendes-2002"]
    if pars:
        out["hidrogeologia"] = {"paragrafos": pars, "refs": refs, "resumo": [f"Aquíferos: {', '.join(ag.get('aquiferos') or {})}"]}
    return out or None
