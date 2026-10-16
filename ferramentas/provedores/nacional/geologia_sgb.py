"""Geologia nacional (SGB): unidade litoestratigráfica na melhor escala disponível + descrição oficial (legenda)."""
import re

from ferramentas.garimpo import biblio
from ferramentas.provedores.comum import wfs, SGB_WFS, lista

TEMA = "geologia"
NOME = "SGB – Litoestratigrafia (melhor escala disponível)"
UFS = None
BASES = ["SGB", "CPRM", "GeoSGB", "Serviço Geológico"]
# da mais detalhada para a menos detalhada
CAMADAS = ["geosgb:litoestratigrafia_25k", "geosgb:litoestratigrafia_50k", "geosgb:litoestratigrafia_100k",
           "geosgb:litoestratigrafia_150k", "geosgb:litoestratigrafia_250k", "geosgb:litoestratigrafia_estados",
           "geosgb:litoestratigrafia_1m"]
CIT = "SGB, [20--]"


def _no_ponto(lon, lat):
    achados = []
    for c in CAMADAS:
        fs = wfs(SGB_WFS, c, cql=f"INTERSECTS(geom,POINT({lat} {lon}))", n=2)
        if fs:
            achados.append((c, fs[0]["properties"]))
    return achados


def _idade(p):
    s = " ".join(x for x in (p.get("sistema_min"), p.get("epoca_min")) if x)
    era = (p.get("era_min") or "").replace("ó", "o")
    era = {"Mesozoico": "Mesozoica", "Paleozoico": "Paleozoica", "Cenozoico": "Cenozoica"}.get(era, era)
    return f"{s} (Era {era})" if s and era else s


def _legenda(p):
    leg = (p.get("legenda") or "").strip()
    leg = re.split(r"\s\d{2,4}(?:,\d+)? ?± ?|\s{2,}", leg)[0].strip().rstrip(".")  # sem datações radiométricas
    return leg[0].lower() + leg[1:] if leg else ""


def consultar(ctx):
    vistos, pars, por = {}, [], {}
    for nome, pts in ctx["pontos"].items():
        lon, lat = pts[len(pts) // 2]
        ach = _no_ponto(lon, lat)
        por[nome] = [{"camada": c, "nome": p.get("nome"), "escala": p.get("escala"), "mapa": p.get("mapa")} for c, p in ach]
        for c, p in ach:
            vistos.setdefault(p.get("nome"), (c, p, []))[2].append(nome)
    if not vistos:
        return None
    # unidade mais detalhada primeiro; a de 1:1.000.000 dá o enquadramento regional
    ordem = sorted(vistos.values(), key=lambda v: CAMADAS.index(v[0]))
    det = ordem[0]
    c, p, un = det
    mapa = re.sub(r"\s*[-–]\s*1:[\d.]+\s*$", "", p.get("mapa") or "mapeamento do Serviço Geológico do Brasil")
    pars.append(f"Do ponto de vista geológico, segundo o {mapa}"
                f" (escala {p.get('escala')}), as unidades do empreendimento assentam-se sobre a {p.get('hierarquia', '').lower()} "
                f"{re.sub(r'^(Formação|Grupo|Suíte|Complexo|Membro)\s+', '', p.get('nome') or '')}"
                .replace("a grupo", "o Grupo").replace("a formação", "a Formação").replace("a membro", "o Membro")
                .replace("a suíte", "a Suíte").replace("a complexo", "o Complexo")
                + (f", do {_idade(p)}" if _idade(p) else "")
                + (f", integrante do {p['nome_pai'].split(' - ', 1)[-1]}" if p.get("nome_pai") else "")
                + (f", com litotipos de {p['litotipos'].lower()}" if p.get("litotipos") else "") + f" ({CIT}).")
    if _legenda(p):
        pars.append(f"A unidade é descrita pelo Serviço Geológico do Brasil como {_legenda(p)} ({CIT}).")
    reg = next((v for v in ordem[1:] if v[0] == "geosgb:litoestratigrafia_1m" and v[1].get("nome") != p.get("nome")), None)
    if reg and _legenda(reg[1]):
        pars.append(f"Em escala regional (1:1.000.000), a área insere-se no {reg[1].get('nome')}, "
                    f"descrito como {_legenda(reg[1])} ({CIT}).")
    a = biblio.data_acesso()
    refs = [biblio.registrar("sgb-litoestratigrafia",
                             "SGB – SERVIÇO GEOLÓGICO DO BRASIL. Litoestratigrafia (GeoSGB): mapas geológicos nas escalas "
                             "1:25.000 a 1:1.000.000 e mapas estaduais. Brasília, DF: SGB/CPRM, [20--]. Disponível em: "
                             "https://geosgb.sgb.gov.br. Acesso em: " + a + ".", "base", "https://geosgb.sgb.gov.br", CIT)]
    resumo = [f"{n}: " + "; ".join(f"{x['nome']} ({x['escala']})" for x in lst) for n, lst in por.items()]
    return {"paragrafos": pars, "por_unidade": por, "refs": refs, "resumo": resumo,
            "unidade": {"nome": p.get("nome"), "escala": p.get("escala"), "mapa": p.get("mapa"), "nome_pai": p.get("nome_pai")}}
