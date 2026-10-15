"""Coletores do dossiê municipal. Cada coletor recebe o contexto e devolve:
    {"titulo": str, "dados": dict (vira {{dossie.<bloco>.<campo>}}), "linhas": [str] (texto do DOSSIE.md),
     "fontes": [chave do catálogo bibliográfico], "pendencias": [str]}
Falha de um coletor não interrompe os demais (o gerador registra o erro como pendência).
"""
import time

import geopandas as gpd
import requests

from ferramentas.garimpo import biblio, web

CURITIBA = (-49.2733, -25.4284)  # sede da capital (lon, lat)
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]


def _pct(v, tot):
    return round(100 * v / tot, 1) if tot else None


# ------------------------------------------------------------------ IBGE / SIDRA
def sidra_distribuicao(tabela: int, cod: int, periodo="2022") -> tuple[dict, str, dict]:
    """Distribuição por categorias da 1ª classificação da tabela (variável 1).
    Retorna ({categoria: valor}, nome da tabela, {categoria: nível hierárquico (0 = total)})."""
    meta = web.obter(f"https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados", json=True,
                     cache_horas=24 * 180)
    var = meta["variaveis"][0]["id"]
    cl = meta["classificacoes"][0]
    niveis = {c["nome"]: c.get("nivel", 1) for c in cl["categorias"]}
    url = f"https://apisidra.ibge.gov.br/values/t/{tabela}/n6/{cod}/v/{var}/p/{periodo}/c{cl['id']}/all"
    linhas = web.obter(url, json=True, cache_horas=24 * 90)[1:]
    out = {}
    for x in linhas:  # D1=município, D2=variável, D3=ano, D4=categoria da classificação
        try:
            out[x["D4N"]] = float(x["V"])
        except (ValueError, KeyError):
            continue
    return out, meta["nome"], niveis


def _eh_sub(pai, filho, niveis, dist):
    """Subcategoria (nível 2) pertence ao pai: na lista do IBGE vem logo depois dele."""
    ordem = list(niveis)
    if pai not in ordem or filho not in ordem:
        return False
    i, j = ordem.index(pai), ordem.index(filho)
    return j > i and all(niveis[c] == 2 for c in ordem[i + 1:j + 1])


def _ref_sidra(tabela, nome):
    abnt = (f"IBGE – INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA. Censo Demográfico 2022. Tabela {tabela}: {nome}. "
            f"Rio de Janeiro: IBGE, 2023. Disponível em: https://sidra.ibge.gov.br/tabela/{tabela}. "
            f"Acesso em: {biblio.data_acesso()}.")
    return biblio.registrar(f"ibge-sidra-{tabela}", abnt, "base", f"https://sidra.ibge.gov.br/tabela/{tabela}", "IBGE, 2023")


def socioeconomia(ctx):
    from ferramentas.fontes import ibge
    info = ibge.info(ctx["cfg"]["municipio"])
    dados = {k: info.get(k) for k in ("populacao_2022", "area_km2", "densidade_hab_km2", "mesorregiao", "microrregiao",
                                      "regiao_imediata", "regiao_intermediaria", "limitrofes")}
    fontes = ["ibge-2023-censo"]
    try:  # PIB dos Municípios (tabela 5938, variável 37 = PIB a preços correntes, mil R$), último ano
        x = web.obter(f"https://apisidra.ibge.gov.br/values/t/5938/n6/{ctx['cod']}/v/37/p/last", json=True,
                      cache_horas=24 * 90)[1]
        dados["pib_mil_rs"] = float(x["V"])
        dados["pib_ano"] = int(x["D3C"])
        # per capita só quando o ano do PIB coincide com o Censo (mesma base populacional)
        dados["pib_per_capita_rs"] = (round(dados["pib_mil_rs"] * 1000 / dados["populacao_2022"], 2)
                                      if dados["pib_ano"] == 2022 and dados.get("populacao_2022") else None)
        abnt = (f"IBGE – INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA. Produto Interno Bruto dos Municípios. Tabela 5938. "
                f"Rio de Janeiro: IBGE, {dados['pib_ano'] + 2}. Disponível em: https://sidra.ibge.gov.br/tabela/5938. "
                f"Acesso em: {biblio.data_acesso()}.")
        fontes.append(biblio.registrar("ibge-sidra-5938", abnt, "base", "https://sidra.ibge.gov.br/tabela/5938",
                                       f"IBGE, {dados['pib_ano'] + 2}"))
    except Exception as e:
        dados["pib_mil_rs"] = dados["pib_per_capita_rs"] = None
        print(f"    PIB indisponível: {e.__class__.__name__}")
    lin = [f"- População (Censo 2022): {dados['populacao_2022']:,} habitantes".replace(",", "."),
           f"- Área territorial: {dados['area_km2']:,.2f} km²; densidade {dados['densidade_hab_km2']} hab/km²".replace(",", "X").replace(".", ",").replace("X", "."),
           f"- Mesorregião {dados['mesorregiao']}; Região Geográfica Imediata de {dados['regiao_imediata']}",
           f"- Municípios limítrofes: {', '.join(dados['limitrofes'] or [])}"]
    br = lambda v, c=2: f"{v:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if dados.get("pib_mil_rs"):
        lin.append(f"- PIB a preços correntes ({dados['pib_ano']}): R$ {br(dados['pib_mil_rs'] / 1000)} milhões")
    if dados.get("pib_per_capita_rs"):
        lin.append(f"- PIB per capita ({dados['pib_ano']}, calculado com a população do Censo 2022): R$ {br(dados['pib_per_capita_rs'])}")
    return {"titulo": "Socioeconomia", "dados": dados, "linhas": lin, "fontes": fontes}


def saneamento(ctx):
    dados, lin, fontes = {}, [], []
    tabelas = {"agua": (6803, "Abastecimento de água"), "esgoto": (6805, "Esgotamento sanitário"),
               "lixo": (6892, "Destino do lixo")}
    for chave, (tab, rot) in tabelas.items():
        dist, nome, niveis = sidra_distribuicao(tab, ctx["cod"])
        total = dist.get("Total") or sum(v for k, v in dist.items() if niveis.get(k) == 1)
        pcts = {k: _pct(v, total) for k, v in dist.items() if k != "Total" and v}
        dados[chave] = {"domicilios": int(total), "distribuicao_pct": pcts}
        fontes.append(_ref_sidra(tab, nome))
        partes = []  # categorias principais (nível 1) e, recuadas, as subcategorias (nível 2)
        for k, v in pcts.items():
            if niveis.get(k, 1) == 1:
                subs = [f"{s.removeprefix(k + ' - ')}: {pv}%" for s, pv in pcts.items()
                        if niveis.get(s) == 2 and _eh_sub(k, s, niveis, dist) and pv]
                partes.append(f"{k}: {v}%" + (f" (sendo {'; '.join(subs)})" if subs else ""))
        lin.append(f"- **{rot}** ({int(total):,} domicílios): ".replace(",", ".") + "; ".join(partes).replace(".", ","))
    pe = dados["esgoto"]["distribuicao_pct"]
    pa = dados["agua"]["distribuicao_pct"]
    dados["esgoto_rede_pct"] = pe.get("Rede geral ou pluvial")
    dados["esgoto_adequado_pct"] = pe.get("Rede geral, rede pluvial ou fossa ligada à rede")
    dados["esgoto_fossa_rudimentar_pct"] = pe.get("Fossa rudimentar ou buraco")
    dados["agua_rede_pct"] = next((v for k, v in pa.items() if k.startswith("Possui ligação à rede geral e a utiliza")), None)
    lin.append(f"- Indicadores: água da rede geral como forma principal {dados['agua_rede_pct']}%; esgoto em rede geral ou "
               f"pluvial {dados['esgoto_rede_pct']}%; fossa rudimentar {dados['esgoto_fossa_rudimentar_pct']}%".replace(".", ","))
    return {"titulo": "Saneamento (Censo 2022)", "dados": dados, "linhas": lin, "fontes": fontes}


# ------------------------------------------------------------------ clima
MESES = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
DIAS = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def koppen(t, p_mm):
    """Classificação de Köppen simplificada para climas A e C (suficiente para o Sul do Brasil)."""
    tmin, tmax = min(t), max(t)
    if tmin >= 18:
        seca = min(p_mm)
        return "Af" if seca >= 60 else ("Am" if seca >= 100 - sum(p_mm) / 25 else "Aw")
    if tmin > -3 and tmax >= 10:
        verao, inverno = p_mm[9:12] + p_mm[0:3], p_mm[3:9]  # hemisfério sul
        if min(verao) < 30 and max(inverno) >= 3 * min(verao):
            s = "s"
        elif min(inverno) < max(verao) / 10:
            s = "w"
        else:
            s = "f"
        terc = "a" if tmax >= 22 else ("b" if sum(1 for x in t if x >= 10) >= 4 else "c")
        return f"C{s}{terc}"
    return "indeterminado"


def clima(ctx):
    lon, lat = ctx["centro"]
    j = web.obter("https://power.larc.nasa.gov/api/temporal/climatology/point",
                  params={"parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR", "community": "AG", "longitude": round(lon, 4),
                          "latitude": round(lat, 4), "format": "JSON"}, json=True, cache_horas=24 * 365)
    p = j["properties"]["parameter"]
    t = [p["T2M"][m] for m in MESES]
    chuva = [round(p["PRECTOTCORR"][m] * d) for m, d in zip(MESES, DIAS)]
    dados = {"temp_media_anual_c": round(sum(t) / 12, 1), "temp_mes_mais_quente_c": max(t), "temp_mes_mais_frio_c": min(t),
             "temp_max_media_c": p["T2M_MAX"]["ANN"], "temp_min_media_c": p["T2M_MIN"]["ANN"],
             "precipitacao_anual_mm": sum(chuva), "precipitacao_mensal_mm": dict(zip(["jan", "fev", "mar", "abr", "mai", "jun",
                                                                                     "jul", "ago", "set", "out", "nov", "dez"], chuva)),
             "koppen": koppen(t, chuva), "altitude_modelo_m": j["geometry"]["coordinates"][2]}
    abnt = (f"NASA – NATIONAL AERONAUTICS AND SPACE ADMINISTRATION. Prediction Of Worldwide Energy Resources (POWER): "
            f"climatologia mensal (1991-2020) no ponto {lat:.4f}, {lon:.4f}. Hampton: NASA Langley Research Center. "
            f"Disponível em: https://power.larc.nasa.gov. Acesso em: {biblio.data_acesso()}.")
    fontes = [biblio.registrar(f"nasa-power-{ctx['cfg']['chave']}", abnt, "base", "https://power.larc.nasa.gov", "NASA, 2026")]
    try:
        from ferramentas.garimpo.literatura import abnt_doi
        r = abnt_doi("10.1127/0941-2948/2013/0507")  # Alvares et al. (2013) – Köppen para o Brasil
        fontes.append(biblio.registrar("alvares-2013-koppen", r["abnt"], "artigo", "https://doi.org/10.1127/0941-2948/2013/0507",
                                       r["citacao"], r["verificado"]))
    except Exception:
        pass
    lin = [f"- Classificação de Köppen (calculada): **{dados['koppen']}**",
           f"- Temperatura média anual: {dados['temp_media_anual_c']} °C (mês mais frio {min(t)} °C; mais quente {max(t)} °C)".replace(".", ","),
           f"- Precipitação média anual: {dados['precipitacao_anual_mm']:,} mm".replace(",", "."),
           "- Precipitação mensal (mm): " + ", ".join(f"{k} {v}" for k, v in dados["precipitacao_mensal_mm"].items())]
    return {"titulo": "Clima", "dados": dados, "linhas": lin, "fontes": fontes,
            "pendencias": ["Clima calculado de reanálise (NASA POWER); se houver estação INMET/Simepar próxima, preferir a normal climatológica oficial."]}


# ------------------------------------------------------------------ OpenStreetMap / OSRM
def overpass(consulta: str):
    """Consulta ao OpenStreetMap (Overpass) com cache em disco, espelhos e espera crescente se ocupado."""
    import hashlib
    cache = web.CACHE / ("ovp_" + hashlib.md5(consulta.encode()).hexdigest())
    if cache.exists() and time.time() - cache.stat().st_mtime < 30 * 86400:
        import json
        return json.loads(cache.read_text(encoding="utf-8"))
    for tentativa in range(4):
        for url in OVERPASS:
            try:
                r = requests.post(url, data={"data": consulta}, headers={"User-Agent": "ExecutorRelatorio/1.0"}, timeout=150)
                if r.status_code == 200 and r.text.lstrip().startswith("{"):
                    web.CACHE.mkdir(parents=True, exist_ok=True)
                    cache.write_text(r.text, encoding="utf-8")
                    return r.json()
            except requests.RequestException:
                continue
        time.sleep(10 * 2 ** tentativa)  # 10, 20, 40, 80 s
    raise RuntimeError("Overpass (OpenStreetMap) ocupado/indisponível – repetir mais tarde")


def _ref_osm():
    abnt = (f"OPENSTREETMAP CONTRIBUTORS. OpenStreetMap. Cambridge: OpenStreetMap Foundation, {biblio.dt.date.today().year}. "
            f"Disponível em: https://www.openstreetmap.org. Acesso em: {biblio.data_acesso()}.")
    return biblio.registrar("openstreetmap", abnt, "base", "https://www.openstreetmap.org", f"OPENSTREETMAP, {biblio.dt.date.today().year}")


def acesso(ctx):
    lon, lat = ctx["centro"]
    rota = web.obter(f"https://router.project-osrm.org/route/v1/driving/{lon},{lat};{CURITIBA[0]},{CURITIBA[1]}",
                     params={"overview": "false"}, json=True, cache_horas=24 * 90)["routes"][0]
    q = (f"[out:json][timeout:60];way[\"highway\"~\"^(motorway|trunk|primary|secondary)$\"][\"ref\"]"
         f"(around:15000,{lat},{lon});out tags;")
    vias = overpass(q)["elements"]
    refs = sorted({r.strip() for v in vias for r in v["tags"].get("ref", "").split(";") if r.strip()},
                  key=lambda s: (not s.startswith("BR"), s))
    dados = {"distancia_capital_km": round(rota["distance"] / 1000), "tempo_capital_h": round(rota["duration"] / 3600, 1),
             "rodovias_15km": refs}
    abnt = (f"OSRM – OPEN SOURCE ROUTING MACHINE. Rota rodoviária entre o empreendimento e Curitiba/PR. "
            f"[S.l.]: Project OSRM, {biblio.dt.date.today().year}. Disponível em: https://project-osrm.org. Acesso em: {biblio.data_acesso()}.")
    fontes = [_ref_osm(), biblio.registrar("osrm", abnt, "base", "https://project-osrm.org", f"OSRM, {biblio.dt.date.today().year}")]
    lin = [f"- Distância rodoviária até Curitiba: {dados['distancia_capital_km']} km (~{dados['tempo_capital_h']} h)".replace(".", ","),
           f"- Rodovias num raio de 15 km: {', '.join(refs) or 'nenhuma com código'}"]
    return {"titulo": "Acessos", "dados": dados, "linhas": lin, "fontes": fontes,
            "pendencias": ["Confirmar a rodovia de acesso e as condições de tráfego (pavimentação) em campo/Google Earth."]}


FILTRO_OSM = ['["amenity"~"^(school|kindergarten|college|hospital|clinic|doctors|place_of_worship)$"]',
              '["building"~"^(church|chapel|school|hospital)$"]', '["shop"]', '["landuse"="cemetery"]']


def _categoria(tags):
    a = tags.get("amenity", "")
    if a in ("school", "kindergarten", "college"):
        return "escola"
    if a in ("hospital", "clinic", "doctors"):
        return "saude"
    if a == "place_of_worship" or tags.get("building") in ("church", "chapel"):
        return "igreja"
    if tags.get("landuse") == "cemetery":
        return "cemiterio"
    if "shop" in tags:
        return "comercio"
    if "building" in tags:
        return "edificacao"
    return None


def entorno(ctx, raio=500):
    u = ctx["unidades_wgs"]
    linhas, dados = [], {}
    for _, row in u.iterrows():
        g = row.geometry
        pts = [g.centroid] if not g.geom_type.endswith("LineString") else \
            [g.interpolate(f, normalized=True) for f in (0, 0.25, 0.5, 0.75, 1)]
        partes = "".join(f"nwr{f}(around:{raio},{p.y:.6f},{p.x:.6f});" for p in pts for f in FILTRO_OSM)
        res = overpass(f"[out:json][timeout:90];({partes});out tags center;")["elements"]  # 1 consulta por unidade
        cont = {c: {"quantidade": 0, "nomes": []} for c in ("escola", "saude", "igreja", "edificacao", "comercio", "cemiterio")}
        vistos = set()
        for e in res:
            if e["id"] in vistos:
                continue
            vistos.add(e["id"])
            cat = _categoria(e.get("tags", {}))
            if cat:
                cont[cat]["quantidade"] += 1
                nome = e["tags"].get("name")
                if nome and nome not in cont[cat]["nomes"] and len(cont[cat]["nomes"]) < 10:
                    cont[cat]["nomes"].append(nome)
        # edificações: só a contagem (consulta leve; trazer todas as feições estoura o serviço público)
        cnt = "".join(f'way["building"](around:{raio},{p.y:.6f},{p.x:.6f});' for p in pts)
        r = overpass(f"[out:json][timeout:90];({cnt});out count;")["elements"]
        cont["edificacao"]["quantidade"] = int(r[0]["tags"].get("ways", 0)) if r else 0
        dados[row["nome"]] = cont
        time.sleep(2)  # respeita o limite do serviço público
        desc = "; ".join(f"{c}: {v['quantidade']}" + (f" ({', '.join(v['nomes'][:4])})" if v["nomes"] else "")
                         for c, v in cont.items() if v["quantidade"])
        linhas.append(f"- **{row['nome']}** (até {raio} m{' em pontos do traçado' if len(pts) > 1 else ''}): {desc or 'nada mapeado'}")
    try:  # estabelecimentos de saúde do município (CNES – Ministério da Saúde)
        cnes = web.obter("https://apidadosabertos.saude.gov.br/cnes/estabelecimentos",
                         params={"codigo_municipio": str(ctx["cod"])[:6], "limit": 200}, json=True, cache_horas=24 * 30)
        est = cnes.get("estabelecimentos", [])
        dados["_cnes_estabelecimentos_municipio"] = len(est)
        linhas.append(f"- Estabelecimentos de saúde cadastrados no município (CNES): {len(est)}")
        abnt = (f"BRASIL. Ministério da Saúde. Cadastro Nacional de Estabelecimentos de Saúde (CNES): API de dados abertos. "
                f"Brasília, DF: Ministério da Saúde. Disponível em: https://apidadosabertos.saude.gov.br. Acesso em: {biblio.data_acesso()}.")
        fontes = [biblio.registrar("ms-cnes", abnt, "base", "https://apidadosabertos.saude.gov.br", "BRASIL, 2026")]
    except Exception:
        fontes = []
    return {"titulo": "Entorno das unidades (OpenStreetMap)", "dados": dados, "linhas": linhas, "fontes": [_ref_osm()] + fontes,
            "pendencias": ["OpenStreetMap pode estar incompleto em área rural: confirmar residências e equipamentos em campo/Google Earth."]}


# ------------------------------------------------------------------ territórios protegidos
def territorios(ctx, raio_km=10, busca_km=50):
    u = ctx["unidades_utm"]
    area = gpd.GeoSeries([u.geometry.buffer(raio_km * 1000).union_all()], crs=u.crs).to_crs("EPSG:4674")
    x0, y0, x1, y1 = gpd.GeoSeries([u.geometry.buffer(busca_km * 1000).union_all()], crs=u.crs).to_crs("EPSG:4674").total_bounds
    dados, linhas, fontes = {}, [], []
    try:
        cap = web.obter("https://geoserver.funai.gov.br/geoserver/Funai/ows?service=WFS&request=GetCapabilities",
                        cache_horas=24 * 30)
        import re
        camada = next(n for n in re.findall(r"<Name>([^<]+)</Name>", cap) if "tis_poligonais" in n.lower())
        from ferramentas.fontes.oficiais import wfs
        ti = wfs("https://geoserver.funai.gov.br/geoserver/Funai/ows", camada, (x0, y0, x1, y1))
        campo = next((c for c in ti.columns if c.lower() in ("terrai_nome", "terrai_nom", "nome", "terra_indigena")), None)
        perto = ti[ti.intersects(area.iloc[0])] if len(ti) else ti
        dados["terras_indigenas"] = sorted(perto[campo].astype(str).unique()) if len(perto) and campo else []
        linhas.append(f"- Terras indígenas num raio de {raio_km} km: {', '.join(dados['terras_indigenas']) or 'nenhuma'}")
        if len(ti) and campo:  # a mais próxima (até busca_km), com distância às unidades
            t_utm = ti.to_crs(u.crs)
            dist = t_utm.distance(u.geometry.union_all())
            i = dist.idxmin()
            extra = {k: str(ti.loc[i, k]) for k in ("etnia_nome", "fase_ti", "municipio_nome") if k in ti.columns}
            dados["ti_mais_proxima"] = {"nome": str(ti.loc[i, campo]), "distancia_km": round(float(dist[i]) / 1000, 1), **extra}
            linhas.append(f"- Terra indígena mais próxima: TI {dados['ti_mais_proxima']['nome']}"
                          + (f" ({extra.get('etnia_nome')}; {extra.get('fase_ti')})" if extra else "")
                          + f", a {str(dados['ti_mais_proxima']['distancia_km']).replace('.', ',')} km das unidades")
        else:
            dados["ti_mais_proxima"] = None
            linhas.append(f"- Nenhuma terra indígena num raio de {busca_km} km")
        abnt = (f"FUNAI – FUNDAÇÃO NACIONAL DOS POVOS INDÍGENAS. Terras indígenas (polígonos): serviço WFS. Brasília, DF: FUNAI. "
                f"Disponível em: https://geoserver.funai.gov.br. Acesso em: {biblio.data_acesso()}.")
        fontes.append(biblio.registrar("funai-tis", abnt, "base", "https://geoserver.funai.gov.br", "FUNAI, 2026"))
    except Exception as e:
        dados["terras_indigenas"] = None
        linhas.append(f"- Terras indígenas: consulta automática indisponível ({e.__class__.__name__})")
    ucs = ctx["cfg"]["dir"] / "dados" / "oficiais" / "ucs.gpkg"
    if ucs.exists():
        g = gpd.read_file(ucs)
        campo = next((c for c in g.columns if c.lower() in ("nome", "nome_uc", "nm_uc")), g.columns[0])
        dados["unidades_conservacao"] = sorted(g[campo].astype(str).unique())
    else:
        dados["unidades_conservacao"] = []
    linhas.append(f"- Unidades de Conservação (ANA/MMA) na área das bases: {', '.join(dados['unidades_conservacao']) or 'nenhuma'}")
    pend = []
    if dados.get("terras_indigenas"):
        pend.append(f"Terra indígena a menos de {raio_km} km das unidades ({', '.join(dados['terras_indigenas'])}): "
                    "tratar no diagnóstico (PCA 3.13 / entorno do MCE) e avaliar com o IAT a necessidade de manifestação da FUNAI.")
    if dados.get("unidades_conservacao"):
        pend.append("Unidade de Conservação na área: verificar zona de amortecimento e necessidade de autorização do órgão gestor.")
    return {"titulo": "Territórios protegidos", "dados": dados, "linhas": linhas, "fontes": fontes, "pendencias": pend}


def hidrologia(ctx):
    """Rio nomeado mais próximo das unidades-chave (captação/ETE), bacia (UPH ANA) e classe por regra da CONAMA 357."""
    of = ctx["cfg"]["dir"] / "dados" / "oficiais"
    u = ctx["unidades_utm"]
    chave = u[u["nome"].str.contains(r"capta|ETE|ETA", case=False, regex=True)]
    alvo = chave if len(chave) else u
    rios = []
    for arq, campo in ((of / "rios_ana.gpkg", "NORIOCOMP"), (of / "drenagem.gpkg", "nome")):
        if arq.exists():
            g = gpd.read_file(arq).to_crs(u.crs)
            g = g[g[campo].notna() & (g[campo].astype(str).str.strip() != "")]
            rios += [(str(r[campo]).strip(), r.geometry, arq.stem) for _, r in g.iterrows()]
    dados, linhas = {"por_unidade": {}}, []
    for _, row in alvo.iterrows():
        if not rios:
            break
        nome, geom, fonte = min(rios, key=lambda r: r[1].distance(row.geometry))
        d = round(geom.distance(row.geometry))
        dados["por_unidade"][row["nome"]] = {"rio_mais_proximo": nome, "distancia_m": d, "base": fonte}
        linhas.append(f"- {row['nome']}: rio nomeado mais próximo **{nome}** a {d:,} m ({'ANA' if 'ana' in fonte else 'IBGE BC250'})".replace(",", "."))
    nomes = sorted({v["rio_mais_proximo"] for v in dados["por_unidade"].values()})
    dados["rio_principal"] = nomes[0] if len(nomes) == 1 else None
    uph = of / "uph.gpkg"
    if uph.exists():
        g = gpd.read_file(uph).to_crs(u.crs)
        g["a"] = g.geometry.intersection(u.geometry.buffer(15).union_all()).area
        top = g.sort_values("a", ascending=False).iloc[0]
        dados["uph"] = str(top.get("UPH_SG"))
        linhas.append(f"- Unidade de Planejamento Hídrico (ANA): {dados['uph']}")
    rios_ana = of / "rios_ana.gpkg"
    if rios_ana.exists():
        g = gpd.read_file(rios_ana).to_crs(u.crs)
        if "COBACIA" in g:
            i = g.distance(alvo.geometry.union_all()).idxmin()
            dados["ottobacia"] = str(g.loc[i, "COBACIA"])
            linhas.append(f"- Ottobacia (código ANA) do curso d'água mais próximo: {dados['ottobacia']}")
    dados["classe_sugerida"] = "Classe 2"
    linhas.append("- Classe do corpo hídrico: **Classe 2** por regra geral (Resolução CONAMA nº 357/2005, art. 42: enquanto "
                  "não aprovado o enquadramento, as águas doces são consideradas classe 2, salvo se as condições de "
                  "qualidade atuais forem melhores)")
    abnt = ("BRASIL. Conselho Nacional do Meio Ambiente. Resolução CONAMA nº 357, de 17 de março de 2005. Dispõe sobre a "
            "classificação dos corpos de água e diretrizes ambientais para o seu enquadramento, bem como estabelece as "
            "condições e padrões de lançamento de efluentes, e dá outras providências. Brasília, DF, 2005.")
    fontes = [biblio.registrar("conama-357-2005", abnt, "lei", None, "BRASIL, 2005", verificado=False)]
    return {"titulo": "Hidrologia (manancial / corpo receptor)", "dados": dados, "linhas": linhas, "fontes": fontes,
            "pendencias": ["Confirmar com a Sanepar/outorga o nome do manancial ou corpo receptor (o rio mais próximo é só candidato).",
                           "Verificar no IAT se há enquadramento específico do curso d'água (Portarias SUREHMA/IAP por bacia)."]}


def consultas_manuais(ctx):
    mun = ctx["cfg"]["municipio"]
    itens = {
        "IPHAN – sítios arqueológicos (CNSA/SICG)": "https://sicg.iphan.gov.br/sicg/pesquisarBem",
        "IPHAN – bens tombados": "https://www.gov.br/iphan/pt-br/patrimonio-cultural/patrimonio-material/bens-tombados",
        "INCRA – territórios quilombolas": "https://certificacao.incra.gov.br/csv_shp/export_shp.py",
        "Fundação Cultural Palmares – comunidades certificadas": "https://www.gov.br/palmares/pt-br/departamentos/protecao-preservacao-e-articulacao/certificacao-quilombola",
        f"Plano Diretor / zoneamento de {mun}": "site da Prefeitura / Câmara Municipal",
        f"Plano Municipal de Saneamento Básico de {mun}": "site da Prefeitura / Sanepar",
        "CAR/SICAR – imóveis e Reserva Legal": "https://www.car.gov.br/publico/imoveis/index",
    }
    return {"titulo": "Consultas manuais (sem serviço automatizável)", "dados": {"lista": list(itens)},
            "linhas": [f"- [ ] {k}: {v}" for k, v in itens.items()], "fontes": [],
            "pendencias": [f"Consultar {k}" for k in itens]}


COLETORES = {  # ordem padrão do dossiê – igual para toda localidade
    "socioeconomia": socioeconomia, "saneamento": saneamento, "clima": clima, "acesso": acesso,
    "entorno": entorno, "territorios": territorios, "hidrologia": hidrologia, "consultas_manuais": consultas_manuais,
}
