"""Hidrografia nacional (ANA): BHO 2017 (rio, domínio, área de drenagem), divisão hidrográfica e outorgas próximas."""
from collections import defaultdict

from ferramentas.garimpo import biblio
from ferramentas.provedores.comum import arcgis, num, lista

TEMA = "hidrologia"
NOME = "ANA – Base Hidrográfica Ottocodificada e divisão hidrográfica"
UFS = None
BASES = ["ANA", "BHO", "Ottocodificada", "SNIRH"]
CIT_BHO, CIT_DIV, CIT_CNARH = "ANA, 2018", "ANA, [20--]", "ANA, [20--]"


def _refs():
    a = biblio.data_acesso()
    return [
        biblio.registrar("ana-bho-2017",
                         "ANA – AGÊNCIA NACIONAL DE ÁGUAS E SANEAMENTO BÁSICO. Base Hidrográfica Ottocodificada (BHO 2017), "
                         "versão 1.05. Brasília, DF: ANA, 2018. Disponível em: https://metadados.snirh.gov.br. Acesso em: " + a + ".",
                         "base", "https://metadados.snirh.gov.br", CIT_BHO),
        biblio.registrar("ana-divisao-hidrografica",
                         "ANA – AGÊNCIA NACIONAL DE ÁGUAS E SANEAMENTO BÁSICO. Regiões hidrográficas e unidades hidrográficas "
                         "estaduais. Brasília, DF: ANA, [20--]. Disponível em: https://www.snirh.gov.br. Acesso em: " + a + ".",
                         "base", "https://www.snirh.gov.br", CIT_DIV),
        biblio.registrar("ana-cnarh-outorgas",
                         "ANA – AGÊNCIA NACIONAL DE ÁGUAS E SANEAMENTO BÁSICO. Outorgas de direito de uso de recursos hídricos "
                         "(federais e estaduais) – Cadastro Nacional de Usuários de Recursos Hídricos (CNARH). Brasília, DF: ANA, "
                         "[20--]. Disponível em: https://www.snirh.gov.br. Acesso em: " + a + ".",
                         "base", "https://www.snirh.gov.br", CIT_CNARH),
    ]


def _trecho(lon, lat):
    """Trecho da BHO 2017 mais próximo (busca em quadrados crescentes)."""
    for r in (0.003, 0.01, 0.03):
        fs = arcgis("Atlas2020/Bho_2017_BR", lon, lat, r)
        nomeados = [f["attributes"] for f in fs if (f["attributes"].get("noriocomp") or "").strip()]
        if nomeados:
            # o de maior área de drenagem a montante é o rio principal da vizinhança
            return max(nomeados, key=lambda a: a.get("nuareamont") or 0), r
    return None, None


def consultar(ctx):
    sigla = (ctx["cfg"].get("empresa") or {}).get("sigla", "")
    por, rios, regioes, uhs, outorgas = {}, defaultdict(list), set(), set(), {}
    for nome, pts in ctx["pontos"].items():
        lon, lat = pts[len(pts) // 2]
        t, raio = _trecho(lon, lat)
        x = {}
        if t:
            x = {"rio": t.get("noriocomp"), "dominio": t.get("dedominial"), "area_montante_km2": t.get("nuareamont"),
                 "comprimento_curso_km": t.get("nucompcda"), "strahler": t.get("nustrahler"), "cobacia": t.get("cobacia")}
            rios[x["rio"]].append((nome, x))
        for f in arcgis("DADOSABERTOS/Regiões_Hidrográficas", lon, lat):
            regioes.add(f["attributes"].get("RHI_NM", "").title())
        for f in arcgis("SGI/Unidades_Hidrograficas_Estaduais", lon, lat):
            uhs.add(f["attributes"].get("UHE_NM", "").title())
        for serv in ("DADOSABERTOS/outorgas_estaduais_superficial", "DADOSABERTOS/outorgas_federais_superficial"):
            try:
                for f in arcgis(serv, lon, lat, 0.045):
                    a = f["attributes"]
                    k = (a.get("emp_nm_empreendimento"), a.get("int_nm_corpohidrico"))
                    outorgas[k] = a
            except Exception:
                pass
        por[nome] = x
    pars = []
    for rio, lst in rios.items():
        un = lista([n for n, _ in lst])
        x = max((v for _, v in lst), key=lambda v: v.get("area_montante_km2") or 0)
        pars.append(
            f"Segundo a Base Hidrográfica Ottocodificada (BHO 2017) da Agência Nacional de Águas e Saneamento Básico, o curso "
            f"d'água principal mais próximo {'das unidades' if len(lst) > 1 else 'da unidade'} {un} é o {rio}, de domínio "
            f"{(x.get('dominio') or '').lower() or 'não informado'}"
            + (f", com área de drenagem de aproximadamente {num(x['area_montante_km2'], 0)} km² a montante do trecho"
               if x.get("area_montante_km2") else "")
            + (f" e extensão total de {num(x['comprimento_curso_km'], 1)} km do curso d'água"
               if x.get("comprimento_curso_km") else "") + f" ({CIT_BHO}).")
    opcionais = {}
    if regioes:
        com_do = {"Paraná", "Paraguai", "Uruguai", "São Francisco", "Parnaíba", "Tocantins-Araguaia"}
        nomes = [("do " + r if r in com_do else r) for r in sorted(regioes)]
        pars.append(f"Na divisão hidrográfica nacional, a área do empreendimento insere-se na Região Hidrográfica "
                    f"{lista(nomes)} ({CIT_DIV}).")
    if uhs:  # some quando um provedor estadual descreve a unidade hidrográfica oficial do estado
        opcionais["uh_estadual"] = (f"Segundo a compilação das unidades hidrográficas estaduais da ANA, a área insere-se na "
                                    f"unidade {lista(sorted(uhs))} ({CIT_DIV}).")
    if outorgas:
        proprias = [a for (emp, _), a in outorgas.items() if sigla and emp and sigla.lower() in emp.lower()]
        txt = (f"No cadastro de outorgas de direito de uso de recursos hídricos disponibilizado pela ANA, constam "
               f"{len(outorgas)} outorgas de captação superficial num raio de aproximadamente 5 km do empreendimento")
        if proprias:
            corpos = lista(sorted({a.get("int_nm_corpohidrico") for a in proprias if a.get("int_nm_corpohidrico")}))
            txt += (f", entre elas {'outorgas' if len(proprias) > 1 else 'outorga'} em nome de "
                    f"{lista(sorted({a.get('emp_nm_empreendimento') for a in proprias}))}"
                    + (f" no {corpos}" if corpos else ""))
        pars.append(txt + f" ({CIT_CNARH}).")
    if not pars:
        return None
    resumo = [f"{n}: {x.get('rio')} ({x.get('dominio')}), área a montante {x.get('area_montante_km2')} km²" for n, x in por.items()]
    resumo += [f"Região hidrográfica: {', '.join(regioes)}; UH estadual: {', '.join(uhs)}",
               f"Outorgas num raio de ~5 km: {len(outorgas)}"]
    return {"paragrafos": pars, "opcionais": opcionais, "por_unidade": por, "refs": _refs(), "resumo": resumo,
            "outorgas": [{"empreendimento": k[0], "corpo_hidrico": k[1], "vazao_maxima": v.get("int_qt_vazaomaxima")}
                         for k, v in outorgas.items()]}
