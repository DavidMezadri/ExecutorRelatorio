"""Hidrogeologia nacional (SGB): domínio/subdomínio hidrogeológico e poços cadastrados no SIAGAS no entorno."""
import statistics as st
from collections import Counter

from ferramentas.garimpo import biblio
from ferramentas.provedores.comum import wfs, SGB_WFS, num, lista

TEMA = "hidrogeologia"
NOME = "SGB – Domínios hidrogeológicos e SIAGAS"
UFS = None
BASES = ["SGB", "CPRM", "SIAGAS", "Domínios hidrogeológicos"]
CIT_DOM, CIT_SIAGAS = "SGB, [20--]", "SGB, [20--]"
RAIO_KM = 15


def _float(v):
    try:
        x = float(str(v).replace(",", "."))
        return x if x > 0 else None
    except (TypeError, ValueError):
        return None


def consultar(ctx):
    pars, por, doms = [], {}, {}
    lons = [p[0] for pts in ctx["pontos"].values() for p in pts]
    lats = [p[1] for pts in ctx["pontos"].values() for p in pts]
    for nome, pts in ctx["pontos"].items():
        lon, lat = pts[len(pts) // 2]
        fs = wfs(SGB_WFS, "hidrogeologia:dominios_hidrogeologicos_2_5m", cql=f"INTERSECTS(geom,POINT({lat} {lon}))", n=1) or []
        if fs:
            p = fs[0]["properties"]
            doms[(p.get("dom"), p.get("subdom"), p.get("nome_unida"))] = p
            por[nome] = {"dominio": p.get("dom"), "subdominio": p.get("subdom"), "unidade": p.get("nome_unida")}
    if doms:
        partes = [f"domínio {d}" + (f", subdomínio {s}" if s and s != d else "") + (f" (unidade {u})" if u else "")
                  for d, s, u in doms]
        pars.append(f"Segundo o mapa de domínios e subdomínios hidrogeológicos do Brasil, a área do empreendimento insere-se no "
                    f"{lista(partes)} ({CIT_DOM}).")
    # poços do SIAGAS num raio de ~15 km
    d = RAIO_KM / 111
    lon0, lat0 = sum(lons) / len(lons), sum(lats) / len(lats)
    pocos = wfs(SGB_WFS, "hidrogeologia:siagas", bbox=(lon0 - d, lat0 - d, lon0 + d, lat0 + d), n=1000) or []
    pocos = [f["properties"] for f in pocos if "tubular" in str(f["properties"].get("natureza_ponto", "")).lower()]
    if pocos:
        prof = [x for x in (_float(p.get("profundidade_m")) for p in pocos) if x]
        ne = [x for x in (_float(p.get("ne_m")) for p in pocos) if x]
        q = [x for x in (_float(p.get("vazao_especifica_m")) for p in pocos) if x]
        aq = Counter(str(p.get("aquifero")).strip().title().replace(" Da ", " da ").replace(" De ", " de ")
                     for p in pocos if p.get("aquifero"))
        txt = (f"No Sistema de Informações de Águas Subterrâneas (SIAGAS), mantido pelo Serviço Geológico do Brasil, constam "
               f"{'mais de ' + str(len(pocos)) if len(pocos) >= 500 else len(pocos)} poços tubulares cadastrados num raio de "
               f"aproximadamente {RAIO_KM} km do empreendimento")  # o serviço devolve no máximo 500 registros
        if aq:
            txt += f", captando principalmente o aquífero {lista([a for a, _ in aq.most_common(2)])}"
        det = []
        if len(prof) >= 3:
            det.append(f"profundidade mediana de {num(st.median(prof), 0)} m")
        if len(ne) >= 3:
            det.append(f"nível estático mediano de {num(st.median(ne), 1)} m")
        if len(q) >= 3:
            det.append(f"vazão específica mediana de {num(st.median(q), 2)} (m³/h)/m")
        if det:
            txt += f"; os registros com informação indicam {lista(det)}"
        pars.append(txt + f" ({CIT_SIAGAS}).")
    if not pars:
        return None
    a = biblio.data_acesso()
    refs = [biblio.registrar("sgb-dominios-hidrogeologicos",
                             "SGB – SERVIÇO GEOLÓGICO DO BRASIL. Domínios e subdomínios hidrogeológicos do Brasil, escala "
                             "1:2.500.000. Brasília, DF: SGB/CPRM, [20--]. Disponível em: https://geosgb.sgb.gov.br. Acesso em: "
                             + a + ".", "base", "https://geosgb.sgb.gov.br", CIT_DOM),
            biblio.registrar("sgb-siagas",
                             "SGB – SERVIÇO GEOLÓGICO DO BRASIL. SIAGAS – Sistema de Informações de Águas Subterrâneas. "
                             "Brasília, DF: SGB/CPRM, [20--]. Disponível em: https://siagasweb.sgb.gov.br. Acesso em: " + a + ".",
                             "base", "https://siagasweb.sgb.gov.br", CIT_SIAGAS)]
    return {"paragrafos": pars, "por_unidade": por, "refs": refs,
            "resumo": [f"Domínios: {list(doms)}", f"SIAGAS ({RAIO_KM} km): {len(pocos)} poços tubulares"]}
