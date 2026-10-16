"""Meio socioeconômico (3.7.1 Residências, condições do entorno) no padrão do MCE de Entre Rios.

Uso:
    python -m ferramentas.geo.socio <chave>

Para cada unidade, a partir de bases oficiais/abertas (com citação):
  - zona (urbana/rural – MapBiomas, classe Área Urbanizada) e distância ao núcleo da localidade/sede;
  - percurso das unidades lineares: vias que o traçado margeia, na ordem, com extensão e revestimento
    (OpenStreetMap, tag surface) e vias que cruza; unidades de área: via de acesso e revestimento;
  - pontos de interesse num raio de 600 m (igrejas, escolas, saúde, cemitérios, atrativos, equipamentos públicos),
    com nome e distância (OpenStreetMap);
  - histórico e formação administrativa do município (IBGE – Biblioteca, API pública) e indicadores do dossiê
    (população, PIB, saneamento – IBGE);
  - fotos de campo (fotos/fotos.gpkg, ferramentas.imagens.fotos): cada foto com GPS é ligada à via mais próxima e
    entra com legenda "Via X – via pavimentada/não pavimentada"; fotos/legendas.yaml (arquivo: legenda) prevalece
    (a IA confere cada foto nas folhas de contato e corrige a legenda ali).
Gera dados/SOCIO.md e dados/socio.yaml (texto em `texto`, usado pelo redator em {{auto.socio}}).
"""
import argparse
import datetime as dt
import re

import geopandas as gpd
import numpy as np
import yaml
from shapely.geometry import LineString, Point

from ferramentas.util import console_utf8, projeto, corrigir_nome
from ferramentas.garimpo import web, biblio
from ferramentas.dossie.coletores import overpass
from ferramentas.geo.acessos import revestimento, _nome_via

ANO = dt.date.today().year
CIT_OSM, CIT_IBGE_HIST, CIT_MB = f"OPENSTREETMAP, {ANO}", "IBGE, [20--]", "PROJETO MAPBIOMAS, 2024"
POI = ['nwr["amenity"~"^(school|kindergarten|college|place_of_worship|hospital|clinic|doctors|community_centre|'
       'townhall|police|fire_station|social_facility|library)$"]',
       'nwr["landuse"="cemetery"]', 'nwr["amenity"="grave_yard"]',
       'nwr["tourism"~"^(attraction|museum|viewpoint|picnic_site|camp_site|hotel|guest_house)$"]',
       'nwr["historic"]', 'nwr["leisure"~"^(park|sports_centre|stadium|pitch)$"]["name"]']
ROTULO_POI = {"school": "escola", "kindergarten": "centro de educação infantil", "college": "instituição de ensino",
              "place_of_worship": "templo religioso", "hospital": "hospital", "clinic": "unidade de saúde",
              "doctors": "consultório", "community_centre": "centro comunitário", "townhall": "sede administrativa",
              "police": "posto policial", "fire_station": "corpo de bombeiros", "social_facility": "equipamento social",
              "library": "biblioteca", "cemetery": "cemitério", "grave_yard": "cemitério", "attraction": "atrativo turístico",
              "museum": "museu", "viewpoint": "mirante", "picnic_site": "área de lazer", "camp_site": "área de camping",
              "hotel": "hotel", "guest_house": "pousada", "park": "parque", "sports_centre": "centro esportivo",
              "stadium": "estádio", "pitch": "campo esportivo"}


def _tipo_poi(tags):
    for k in ("amenity", "landuse", "tourism", "leisure"):
        if tags.get(k) in ROTULO_POI:
            return ROTULO_POI[tags[k]]
    if "historic" in tags:
        return "bem de interesse histórico"
    return None


def _fmt_m(m):
    return f"{m / 1000:.1f} km".replace(".", ",") if m >= 1000 else f"{int(round(m, -1))} m"


# ------------------------------------------------------------------ IBGE: histórico do município
def historico(cod):
    try:
        d = web.obter("https://servicodados.ibge.gov.br/api/v1/biblioteca", params={"aspas": 3, "codmun": str(cod)[:6]},
                      json=True, cache_horas=24 * 180)
    except Exception:
        return None
    x = next(iter(d.values()), {}) if isinstance(d, dict) else {}
    txt = (x.get("HISTORICO") or "").replace("&Prime;", "\"").replace("\r", "")
    if not txt:
        return None
    partes = re.split(r"\n\s*(?:Histórico|Formação Administrativa|Alteração toponímica[^\n]*|Gentílico[^\n]*)\s*\n", txt)
    hist = re.sub(r"\s+", " ", partes[1] if len(partes) > 1 else "").strip()
    hist = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", hist)).replace(" ,", ",")
    form = re.sub(r"\s+", " ", partes[2] if len(partes) > 2 else "").strip()
    distritos = re.findall(r"constituído de \d+ distritos?: ([^.]+)\.", form)
    return {"historico": hist, "formacao": form, "distritos_atual": distritos[-1] if distritos else None,
            "gentilico": x.get("GENTILICO"), "url": f"https://biblioteca.ibge.gov.br/visualizacao/dtbs/{x.get('ESTADO1', '')}/"
                                                    f"{x.get('VISUALIZACAO', '')}"}


# ------------------------------------------------------------------ zona urbana/rural (MapBiomas)
def _zona_fn(cfg):
    import rasterio
    arq = cfg["dir"] / "dados" / "oficiais" / "mapbiomas.tif"
    if not arq.exists():
        return None
    r = rasterio.open(arq)

    def zona(lon, lat):
        try:
            v = next(r.sample([(lon, lat)]))[0]
        except Exception:
            return None
        return "urbana" if int(v) == 24 else "rural"
    return zona


# ------------------------------------------------------------------ vias e percurso
def _vias(geo_wgs, raio=60):
    if geo_wgs.geom_type.endswith("LineString"):
        pts = [geo_wgs.interpolate(f, normalized=True) for f in np.linspace(0, 1, 12)]
    else:
        pts = [geo_wgs.centroid]
        raio = 400
    q = "".join(f"way[highway](around:{raio},{p.y:.6f},{p.x:.6f});" for p in pts)
    els = overpass(f"[out:json][timeout:90];({q});out tags geom;")["elements"]
    vias = []
    for w in els:
        if "geometry" in w and len(w["geometry"]) > 1 and w["tags"].get("highway") not in ("footway", "path", "steps", "cycleway"):
            vias.append({"via": _nome_via(w["tags"]), "rev": revestimento(w["tags"].get("surface")),
                         "geom": LineString([(c["lon"], c["lat"]) for c in w["geometry"]])})
    return vias


def percurso_linear(linha_utm, epsg, vias, passo=15, faixa=30):
    """Sequência de vias ao longo do traçado: [(via, rev, metros)] e vias cruzadas."""
    gv = gpd.GeoSeries([v["geom"] for v in vias], crs=4326).to_crs(epsg) if vias else gpd.GeoSeries([], crs=epsg)
    seq = []
    n = max(2, int(linha_utm.length // passo))
    for i in range(n + 1):
        p = linha_utm.interpolate(i / n, normalized=True)
        d = gv.distance(p) if len(gv) else None
        j = int(d.idxmin()) if d is not None and len(d) and d.min() <= faixa else None
        chave = (vias[j]["via"], vias[j]["rev"]) if j is not None else (None, None)
        if seq and seq[-1][0] == chave:
            seq[-1][1] += linha_utm.length / n
        else:
            seq.append([chave, linha_utm.length / n])
    seq = [(k[0], k[1], m) for k, m in seq if m >= 40 or k[0] is None]
    # junta trechos repetidos separados por pequenas interrupções
    limpo = []
    for v, r, m in seq:
        if limpo and limpo[-1][0] == v:
            limpo[-1] = (v, r, limpo[-1][2] + m)
        else:
            limpo.append((v, r, m))
    margeia = {v for v, _, m in limpo if v}
    cruzadas = []
    for k, g in enumerate(gv):
        v = vias[k]["via"]
        if v not in margeia and g.intersects(linha_utm) and v not in cruzadas and "sem denominação" not in v:
            cruzadas.append(v)
    return limpo, cruzadas


# ------------------------------------------------------------------ pontos de interesse
def pontos_interesse(geo_wgs, geo_utm, epsg, raio=600):
    pts = [geo_wgs.interpolate(f, normalized=True) for f in (0, .25, .5, .75, 1)] if geo_wgs.geom_type.endswith("LineString") \
        else [geo_wgs.centroid]
    q = "".join(f"{f}(around:{raio},{p.y:.6f},{p.x:.6f});" for p in pts for f in POI)
    els = overpass(f"[out:json][timeout:90];({q});out tags center;")["elements"]
    out, vistos = [], set()
    for e in els:
        tags = e.get("tags", {})
        tipo = _tipo_poi(tags)
        lat, lon = (e.get("lat"), e.get("lon")) if "lat" in e else ((e.get("center") or {}).get("lat"), (e.get("center") or {}).get("lon"))
        if not tipo or lat is None:
            continue
        chave = (tipo, tags.get("name"), round(lat, 3), round(lon, 3))
        if chave in vistos:
            continue
        vistos.add(chave)
        p = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(epsg).iloc[0]
        out.append({"tipo": tipo, "nome": tags.get("name"), "dist_m": round(p.distance(geo_utm))})
    return sorted(out, key=lambda x: x["dist_m"])


# ------------------------------------------------------------------ fotos
def fotos_vias(cfg, epsg, vias_todas):
    arq = cfg["dir"] / "fotos" / "fotos.gpkg"
    if not arq.exists():
        return []
    leg_arq = cfg["dir"] / "fotos" / "legendas.yaml"
    legendas = (yaml.safe_load(leg_arq.read_text(encoding="utf-8")) or {}) if leg_arq.exists() else {}
    f = gpd.read_file(arq).to_crs(epsg)
    gv = gpd.GeoSeries([v["geom"] for v in vias_todas], crs=4326).to_crs(epsg) if vias_todas else None
    out = []
    for _, r in f.iterrows():
        via = None
        if gv is not None and len(gv):
            d = gv.distance(r.geometry)
            if d.min() <= 40:
                via = vias_todas[int(d.idxmin())]
        leg = legendas.get(r["arquivo"])
        if not leg and via:
            leg = f"{via['via']} – {('via ' + via['rev']) if not via['rev'].startswith('revestimento') else 'revestimento a confirmar'}"
        out.append({"arquivo": r["arquivo"], "unidade": r.get("unidade"), "via": via["via"] if via else None,
                    "legenda": leg or f"[A VERIFICAR: descrever foto – {r.get('unidade')}]",
                    "ano": str(r.get("data") or ANO)[:4] if str(r.get("data") or "")[:4].isdigit() else str(ANO)})
    return out


# ------------------------------------------------------------------ texto
def _lista(xs):
    xs = [x for x in xs if x]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " e " + xs[-1] if xs else ""


def redigir(cfg, dados):
    loc = cfg.get("localidade")
    mun = cfg["municipio"]
    pars = []
    for nome, u in dados["unidades"].items():
        lugar = f"do núcleo urbano de {loc}" if loc else f"da sede de {mun}"
        dist = f", a cerca de {_fmt_m(u['dist_nucleo_m'])} {lugar}" if u.get("dist_nucleo_m") is not None else ""
        zona = u.get("zona") or "[A VERIFICAR: zona]"
        if u["tipo"] == "linear":
            trechos = [t for t in u["percurso"] if t[0]]
            sem = sum(m for v, _, m in u["percurso"] if not v)
            frase = (f"O traçado da unidade {nome} ({_fmt_m(u['extensao_m'])}) desenvolve-se em área {zona}{dist}.")
            if trechos:
                frase += (" Ao longo de seu percurso, segue margeando " + _lista(
                    [f"a {v} ({r}) por cerca de {_fmt_m(m)}" for v, r, m in trechos]) + f" ({CIT_OSM})")
                frase += (f", e cruza {_lista(['a ' + c for c in u['cruzadas']])}" if u["cruzadas"] else "") + "."
            if sem >= 50:
                frase += (f" Cerca de {_fmt_m(sem)} do traçado não acompanham vias mapeadas, sendo implantados em faixa de "
                          f"servidão ou área de terceiros.")
        else:
            a = u.get("acesso")
            junto = a and a["dist_m"] < 25
            frase = (f"A unidade {nome} localiza-se em área {zona}{dist}"
                     + (f", com acesso pela {a['via']} ({a['rev']})"
                        + (", lindeira à unidade" if junto else f", distante cerca de {_fmt_m(a['dist_m'])} da unidade")
                        if a else "") + f" ({CIT_OSM}).")
        pars.append(frase)
    if any(u.get("zona") for u in dados["unidades"].values()):
        pars[-1] += f" A classificação da área como urbana ou rural baseia-se no mapeamento de uso do solo ({CIT_MB})."

    h = dados.get("historico")
    if h and h.get("historico"):
        pars.append(f"Segundo o histórico municipal registrado pelo IBGE, {h['historico'][0].lower() + h['historico'][1:]} "
                    f"({CIT_IBGE_HIST}).".replace(". (", " ("))
        if h.get("distritos_atual"):
            pars.append(f"Na atual divisão territorial, o município é constituído pelos distritos de {h['distritos_atual']}"
                        + (f", sendo {loc} a localidade onde se insere o empreendimento" if loc and loc in h["distritos_atual"] else "")
                        + f" ({CIT_IBGE_HIST}).")
    s = dados.get("socioeconomia") or {}
    sa = dados.get("saneamento") or {}
    if s.get("populacao_2022"):
        pars.append(f"O município de {mun} possui população de {s['populacao_2022']:,} habitantes".replace(",", ".")
                    + (f" e densidade demográfica de {str(s['densidade_hab_km2']).replace('.', ',')} hab/km²" if s.get("densidade_hab_km2") else "")
                    + " (IBGE, 2023)"
                    + (f". Quanto ao saneamento, {str(sa['agua_rede_pct']).replace('.', ',')}% dos domicílios utilizam a rede geral de "
                       f"abastecimento de água como forma principal" if sa.get("agua_rede_pct") else "")
                    + (f" e {str(sa['esgoto_rede_pct']).replace('.', ',')}% destinam o esgoto à rede geral ou pluvial"
                       if sa.get("esgoto_rede_pct") else "")
                    + (" (IBGE, 2023)" if sa else "") + ".")
    pois = []
    for nome, u in dados["unidades"].items():
        for p in u["pois"]:
            desc = f"{p['tipo']}" + (f" {p['nome']}" if p.get("nome") else "")
            if all(desc not in x for x in pois):
                pois.append(f"{desc} (a cerca de {_fmt_m(p['dist_m'])} da unidade {nome})")
    if pois:
        pars.append(f"No entorno das unidades (raio de 600 m), a base colaborativa OpenStreetMap registra: {_lista(pois[:10])} "
                    f"({CIT_OSM}). A identificação desses locais permite reconhecer os elementos de relevância social, "
                    f"religiosa e cultural próximos ao empreendimento e subsidia a avaliação de eventuais interferências das "
                    f"obras sobre eles e sobre seu acesso, como alterações temporárias no tráfego, ruídos e poeira.")
    else:
        pars.append(f"Não há escolas, templos religiosos, estabelecimentos de saúde, cemitérios ou atrativos turísticos "
                    f"registrados na base OpenStreetMap num raio de 600 m das unidades ({CIT_OSM}); a ausência deve ser "
                    f"confirmada na vistoria de campo.")
    vias_txt = sorted({(v, r) for u in dados["unidades"].values() for v, r, _ in u.get("percurso", []) if v}
                      | {(u["acesso"]["via"], u["acesso"]["rev"]) for u in dados["unidades"].values() if u.get("acesso")})
    if vias_txt:
        nao_pav = [v for v, r in vias_txt if r.startswith("não")]
        if nao_pav:
            pars.append(f"Nos trechos em vias não pavimentadas ({_lista(nao_pav)}), o tráfego de veículos e máquinas da obra "
                        f"tende a gerar poeira em períodos secos e lama em períodos chuvosos, devendo-se prever umectação das "
                        f"vias, sinalização e recomposição do leito ao final das obras.")
    texto = "\n\n".join(pars)
    if dados["fotos"]:
        texto += "\n\n" + "\n\n".join(
            f"![{f['legenda']}](fotos/{f['arquivo']}){{#fig:socio-{i} fonte=\"Autor, {f['ano']}.\" largura=12}}"
            for i, f in enumerate(dados["fotos"], start=1))
    else:
        texto += ("\n\n[A VERIFICAR: fotos de campo das vias de acesso e do entorno (pavimentação, residências, igrejas) – "
                  "colocar em fotos/brutas/, rodar python -m ferramentas.imagens.fotos e o redator.]")
    return texto + "\n"


def gerar(chave):
    from ferramentas.geo.tematico import unidades
    cfg = projeto(chave)
    d = cfg["dir"] / "dados"
    u, epsg = unidades(cfg)
    u["nome"] = u["nome"].map(corrigir_nome)
    uw = u.to_crs(4326)
    zona_fn = _zona_fn(cfg)
    ac = yaml.safe_load((d / "acessos.yaml").read_text(encoding="utf-8")) if (d / "acessos.yaml").exists() else {}
    nucleo = ac.get("localidade") or ac.get("sede")
    dos = yaml.safe_load((d / "dossie.yaml").read_text(encoding="utf-8")) if (d / "dossie.yaml").exists() else {}
    dados = {"unidades": {}, "fotos": []}
    vias_todas = []
    for (_, r), (_, rw) in zip(u.iterrows(), uw.iterrows()):
        g, gw = r.geometry, rw.geometry
        vias = _vias(gw)
        vias_todas += vias
        x = {"tipo": "linear" if g.geom_type.endswith("LineString") else "area"}
        pts_z = [gw.interpolate(t, normalized=True) for t in np.linspace(0, 1, 9)] if x["tipo"] == "linear" else [gw.centroid]
        zonas = [zona_fn(p.x, p.y) for p in pts_z] if zona_fn else []
        zonas = [z for z in zonas if z]
        if zonas:
            x["zona"] = zonas[0] if len(set(zonas)) == 1 else \
                ("predominantemente " + max(set(zonas), key=zonas.count) + ", com trechos em área "
                 + min(set(zonas), key=zonas.count))
        if nucleo:
            pn = gpd.GeoSeries([Point(*nucleo)], crs=4326).to_crs(epsg).iloc[0]
            x["dist_nucleo_m"] = round(pn.distance(g))
        if x["tipo"] == "linear":
            x["extensao_m"] = round(g.length)
            x["percurso"], x["cruzadas"] = percurso_linear(g, epsg, vias)
        else:
            gv = gpd.GeoSeries([v["geom"] for v in vias], crs=4326).to_crs(epsg) if vias else None
            if gv is not None and len(gv):
                dd = gv.distance(g)
                j = int(dd.idxmin())
                x["acesso"] = {"via": vias[j]["via"], "rev": vias[j]["rev"], "dist_m": round(float(dd.min()))}
        x["pois"] = pontos_interesse(gw, g, epsg)
        dados["unidades"][r["nome"]] = x
    cod = cfg.get("cod_ibge") or (yaml.safe_load((cfg["dir"] / "projeto.yaml").read_text(encoding="utf-8")) or {}).get("cod_ibge")
    if not cod:
        from ferramentas.fontes import ibge
        cod = ibge.buscar(cfg["municipio"], cfg["uf"])["id"]
    dados["historico"] = historico(cod)
    dados["socioeconomia"] = (dos or {}).get("socioeconomia")
    dados["saneamento"] = (dos or {}).get("saneamento")
    dados["fotos"] = fotos_vias(cfg, epsg, vias_todas)
    for x in dados["unidades"].values():
        if "percurso" in x:
            x["percurso"] = [[v, r, round(m)] for v, r, m in x["percurso"]]
    texto = redigir(cfg, dados)
    refs = [biblio.registrar("openstreetmap", f"OPENSTREETMAP CONTRIBUTORS. OpenStreetMap. Cambridge: OpenStreetMap "
                             f"Foundation, {ANO}. Disponível em: https://www.openstreetmap.org. Acesso em: {biblio.data_acesso()}.",
                             "base", "https://www.openstreetmap.org", CIT_OSM)]
    if dados["historico"]:
        refs.append(biblio.registrar(
            f"ibge-historico-{cod}", f"IBGE – INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA. Biblioteca: histórico do "
            f"município de {cfg['municipio']} (PR). Rio de Janeiro: IBGE, [20--]. Disponível em: "
            f"https://servicodados.ibge.gov.br/api/v1/biblioteca?aspas=3&codmun={str(cod)[:6]}. Acesso em: {biblio.data_acesso()}.",
            "base", dados["historico"]["url"], CIT_IBGE_HIST))
    biblio.usar(chave, refs)
    dados_out = {**{k: v for k, v in dados.items() if k != "historico"}, "historico": dados["historico"], "texto": texto}
    for x in dados_out["unidades"].values():
        x.pop("geom", None)
    (d / "socio.yaml").write_text(yaml.safe_dump(dados_out, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (d / "SOCIO.md").write_text(f"# Meio socioeconômico – {cfg['municipio']}\n\n" + texto, encoding="utf-8")
    return dados_out


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    a = ap.parse_args()
    print(gerar(a.chave)["texto"])


if __name__ == "__main__":
    main()
