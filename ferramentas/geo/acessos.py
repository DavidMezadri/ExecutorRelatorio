"""Alternativas de acesso a cada unidade: rotas (OSRM), vias percorridas e pavimentação (OpenStreetMap) + mapa.

Uso:
    python -m ferramentas.geo.acessos <chave> [--raio-km 3]

Para cada grupo de unidades próximas (até 1,5 km):
  - rotas de carro (OSRM) a partir da sede municipal, da localidade (projetos.yaml) e de pontos a norte, sul,
    leste e oeste (--raio-km); rotas que chegam pelas mesmas vias são agrupadas;
  - vias percorridas na ordem, com extensão e revestimento (tag `surface` do OSM, por trecho: o OSRM devolve os
    nós da rota e o Overpass diz a que via cada par de nós pertence); sem tag = "sem informação" (nunca supor);
  - vias acompanhadas pelo traçado das unidades lineares (adutoras, emissários), por extensão;
  - mapa mapas/acesso_<n>.png (satélite, rotas, pavimentada x não pavimentada).
Gera dados/ACESSOS.md (conferência), dados/acessos.yaml (texto pronto em `texto`, usado pelo redator como
{{auto.acessos}}) e registra as referências OSM/OSRM no projeto.
"""
import argparse
import datetime as dt
import math
import time

import geopandas as gpd
import yaml
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from ferramentas.util import console_utf8, projeto, corrigir_nome
from ferramentas.garimpo import web, biblio
from ferramentas.dossie.coletores import overpass

OSRM = "https://router.project-osrm.org"
ANO = dt.date.today().year
CIT_OSM, CIT_OSRM = f"OPENSTREETMAP, {ANO}", f"OSRM, {ANO}"

PAVIMENTADA = {"asphalt", "paved", "concrete", "concrete:plates", "concrete:lanes", "chipseal", "metal"}
CALCAMENTO = {"paving_stones", "sett", "cobblestone", "unhewn_cobblestone", "bricks", "grass_paver"}
CASCALHO = {"gravel", "fine_gravel", "compacted", "pebblestone", "shells"}
LEITO_NATURAL = {"unpaved", "dirt", "earth", "ground", "grass", "sand", "mud", "rock", "soil", "dirt/sand"}
CLASSE_VIA = {"motorway": "rodovia", "trunk": "rodovia", "primary": "rodovia", "secondary": "rodovia",
              "tertiary": "via", "unclassified": "estrada vicinal", "residential": "via urbana",
              "living_street": "via urbana", "service": "via de serviço", "track": "estrada rural"}


def revestimento(surface):
    s = (surface or "").lower()
    if s in PAVIMENTADA:
        return "pavimentada"
    if s in CALCAMENTO:
        return "pavimentada em calçamento"
    if s in CASCALHO:
        return "não pavimentada, em cascalho"
    if s in LEITO_NATURAL:
        return "não pavimentada, em leito natural"
    return "revestimento não informado"


def _pav(rev):
    return "pav" if rev.startswith("pavimentada") else "nao" if rev.startswith("não") else "si"


# ------------------------------------------------------------------ serviços
def _osrm(caminho, **params):
    time.sleep(1.1)  # servidor público de demonstração: 1 requisição/s
    return web.obter(f"{OSRM}/{caminho}", params=params or None, json=True, cache_horas=24 * 30)


def _encaixar(lon, lat):
    r = _osrm(f"nearest/v1/driving/{lon:.6f},{lat:.6f}")
    return tuple(r["waypoints"][0]["location"]) if r.get("code") == "Ok" else None


def _rota(orig, dest):
    r = _osrm(f"route/v1/driving/{orig[0]:.6f},{orig[1]:.6f};{dest[0]:.6f},{dest[1]:.6f}",
              overview="full", geometries="geojson", steps="true", annotations="nodes,distance")
    return r["routes"][0] if r.get("code") == "Ok" and r.get("routes") else None


def _lugar(nome, lon, lat, raio=40000):
    """Nó 'place' do OSM com o nome (sede municipal/localidade) mais próximo das unidades."""
    if not nome:
        return None
    q = (f'[out:json][timeout:60];node["place"~"^(city|town|village|suburb|hamlet|neighbourhood)$"]'
         f'["name"~"^{nome}$",i](around:{raio},{lat},{lon});out;')
    els = overpass(q).get("elements", [])
    if not els:
        return None
    e = min(els, key=lambda e: (e["lon"] - lon) ** 2 + (e["lat"] - lat) ** 2)
    return (e["lon"], e["lat"])


def _vias_dos_nos(nos):
    """{(nó_a, nó_b): tags da via} para os pares consecutivos de nós das rotas."""
    pares = {}
    ids = sorted(set(nos))
    for i in range(0, len(ids), 2500):
        lote = ",".join(map(str, ids[i:i + 2500]))
        els = overpass(f"[out:json][timeout:120];node(id:{lote});way(bn)[highway];out body;")["elements"]
        for w in els:
            nd, tags = w.get("nodes", []), w.get("tags", {})
            for a, b in zip(nd, nd[1:]):
                pares[(a, b)] = pares[(b, a)] = tags
    return pares


# ------------------------------------------------------------------ rota -> trechos
def _nome_via(tags, passo=None):
    ref = (tags or {}).get("ref") or (passo or {}).get("ref") or ""
    nome = (tags or {}).get("name") or (passo or {}).get("name") or ""
    ref = ref.split(";")[0].strip()
    if ref and nome and ref not in nome:
        return f"{ref} ({nome})"
    if ref or nome:
        return ref or nome
    hw = (tags or {}).get("highway", "")
    return f"{CLASSE_VIA.get(hw, 'via')} sem denominação"


def trechos(rota, pares):
    """Lista ordenada de trechos {via, km, revestimento} (consecutivos de mesma via e revestimento somados)."""
    out = []
    for perna in rota["legs"]:
        nos, dist = perna["annotation"]["nodes"], perna["annotation"]["distance"]
        for (a, b), d in zip(zip(nos, nos[1:]), dist):
            tags = pares.get((a, b))
            via, rev = _nome_via(tags), revestimento((tags or {}).get("surface"))
            if out and out[-1]["via"] == via and out[-1]["revestimento"] == rev:
                out[-1]["m"] += d
            else:
                out.append({"via": via, "revestimento": rev, "m": d})
    # trechos curtos (< 80 m) no meio da rota: absorvidos pelo anterior (cruzamentos, rotatórias)
    limpos = []
    for i, t in enumerate(out):
        if limpos and t["m"] < 80 and 0 < i < len(out) - 1:
            limpos[-1]["m"] += t["m"]
        elif limpos and limpos[-1]["via"] == t["via"] and limpos[-1]["revestimento"] == t["revestimento"]:
            limpos[-1]["m"] += t["m"]
        else:
            limpos.append(dict(t))
    return [{"via": t["via"], "revestimento": t["revestimento"], "km": round(t["m"] / 1000, 2)} for t in limpos]


def _pavimento_pct(tr):
    tot = sum(t["km"] for t in tr) or 1
    soma = {"pav": 0, "nao": 0, "si": 0}
    for t in tr:
        soma[_pav(t["revestimento"])] += t["km"]
    return {k: round(100 * v / tot) for k, v in soma.items()}


def _assinatura(tr, km_final=1.0):
    """Vias usadas no último km – rotas que chegam pelas mesmas vias são a mesma alternativa."""
    vias, acum = [], 0
    for t in reversed(tr):
        if t["via"] not in vias:
            vias.append(t["via"])
        acum += t["km"]
        if acum >= km_final:
            break
    return tuple(vias)


# ------------------------------------------------------------------ unidades lineares: vias acompanhadas
def vias_ao_longo(linha_utm, epsg, faixa=25):
    """Vias do OSM a até `faixa` m do traçado, com a extensão do traçado que as acompanha."""
    g = gpd.GeoSeries([linha_utm], crs=epsg).to_crs(4326).iloc[0]
    pts = [g.interpolate(f, normalized=True) for f in [i / 10 for i in range(11)]]
    partes = "".join(f"way[highway](around:{faixa + 60},{p.y:.6f},{p.x:.6f});" for p in pts)
    els = overpass(f"[out:json][timeout:90];({partes});out tags geom;")["elements"]
    res = {}
    for w in els:
        if "geometry" not in w:
            continue
        lw = gpd.GeoSeries([LineString([(c["lon"], c["lat"]) for c in w["geometry"]])], crs=4326).to_crs(epsg).iloc[0]
        junto = linha_utm.intersection(lw.buffer(faixa)).length
        if junto < 30:
            continue
        tags = w.get("tags", {})
        via = _nome_via(tags)
        r = res.setdefault(via, {"via": via, "m": 0, "revestimento": revestimento(tags.get("surface"))})
        r["m"] += junto
    tot = linha_utm.length
    return sorted([{"via": v["via"], "revestimento": v["revestimento"], "km": round(min(v["m"], tot) / 1000, 2),
                    "pct": round(100 * min(v["m"], tot) / tot)} for v in res.values()], key=lambda x: -x["km"])


# ------------------------------------------------------------------ texto
def _km(v):
    return f"{v:.1f}".replace(".", ",") if v >= 1 else f"{round(v * 1000):d} m".replace(",", ".")


def _fmt_km(v):
    return f"{_km(v)} km" if v >= 1 else _km(v)


def _desc_trechos(tr, max_trechos=7):
    vis = tr if len(tr) <= max_trechos else tr[-max_trechos:]
    partes = [f"{t['via']} ({_fmt_km(t['km'])}, {t['revestimento']})" for t in vis]
    if len(partes) == 1:
        return f"pela {partes[0]}"
    return "pela " + ", pela ".join(partes[:-1]) + f" e pela {partes[-1]}"


DIRECOES = {"N": "Norte", "S": "Sul", "L": "Leste", "O": "Oeste"}


def _rotulo_origem(o):
    return {"sede": "a partir da sede municipal", "localidade": "a partir do núcleo urbano da localidade"}.get(
        o, f"Acesso {DIRECOES.get(o, o)}")


def rotulo(origens):
    """['sede', 'O'] -> 'A partir da sede municipal (também Acesso Oeste)'; ['N','S'] -> 'Acessos Norte e Sul'."""
    lugares = [_rotulo_origem(o) for o in origens if o not in DIRECOES]
    dirs = [DIRECOES[o] for o in origens if o in DIRECOES]
    txt_dir = ""
    if dirs:
        txt_dir = f"Acesso {dirs[0]}" if len(dirs) == 1 else "Acessos " + ", ".join(dirs[:-1]) + " e " + dirs[-1]
    if lugares:
        base = " e ".join(lugares)
        base = base[0].upper() + base[1:]
        return f"{base} (também {txt_dir})" if txt_dir else base
    return txt_dir


def _principal(g, artigo):
    """Via final de acesso (mais comum entre as alternativas) e rodovia de ligação (maior trecho pavimentado)."""
    from collections import Counter
    alts = [a for a in g["alternativas"] if a["trechos"]]
    if not alts:
        return []
    via_final = Counter(a["trechos"][-1]["via"] for a in alts).most_common(1)[0][0]
    rev_final = next(a["trechos"][-1]["revestimento"] for a in alts if a["trechos"][-1]["via"] == via_final)
    ref = next((a for a in alts if "sede" in a["origens"]), alts[0])
    pav = [t for t in ref["trechos"] if t["revestimento"].startswith("pavimentada") and t["via"] != via_final]
    rodovia = max(pav, key=lambda t: t["km"]) if pav else None
    frase = f"O acesso final {artigo} se dá pela {via_final} ({rev_final})"
    if rodovia:
        frase += (f", a partir da {rodovia['via']}, via {rodovia['revestimento']} que constitui a principal ligação "
                  f"com a sede municipal ({_fmt_km(rodovia['km'])} do percurso de {_fmt_km(ref['km'])})")
    return [frase + f" ({CIT_OSRM}; {CIT_OSM}).", ""]


def redigir(cfg, grupos):
    fig_fonte = f"OpenStreetMap; OSRM; Esri World Imagery; elaborado pelo autor, {ANO}."
    out = []
    for g in grupos:
        nomes = g["unidades"]
        nomes_txt = nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]
        artigo = "à unidade" if len(nomes) == 1 else "às unidades"
        out += _principal(g, artigo)
        out.append(f"O acesso {artigo} {nomes_txt} (@fig:{g['fig']}) foi levantado a partir de rotas calculadas sobre a "
                   f"malha viária do OpenStreetMap ({CIT_OSRM}; {CIT_OSM}), considerando diferentes pontos de origem do "
                   f"deslocamento. As alternativas de acesso identificadas são apresentadas a seguir:")
        out.append("")
        for alt in g["alternativas"]:
            orig = rotulo(alt["origens"])
            pct = alt["pavimento_pct"]
            pav = (f"{pct['pav']}% do percurso em vias pavimentadas, {pct['nao']}% em vias não pavimentadas"
                   + (f" e {pct['si']}% em vias sem revestimento informado na base consultada" if pct["si"] else ""))
            cauda = "" if len(alt["trechos"]) <= 7 else " (trecho final)"
            out.append(f"- {orig}: percurso de {_fmt_km(alt['km'])}{cauda}, seguindo "
                       f"{_desc_trechos(alt['trechos'])}, via que dá acesso à unidade; {pav};")
        out[-1] = out[-1].rstrip(";") + "."
        out.append("")
        for lin in g["lineares"]:
            if lin["vias"]:
                vias = "; ".join(f"{v['via']} ({_fmt_km(v['km'])}, {v['pct']}% do traçado, {v['revestimento']})"
                                 for v in lin["vias"][:5])
                out.append(f"O traçado da unidade {lin['nome']} ({_fmt_km(lin['km'])}) acompanha as seguintes vias, "
                           f"o que facilita o acesso para implantação e manutenção: {vias} ({CIT_OSM}).")
            else:
                out.append(f"O traçado da unidade {lin['nome']} ({_fmt_km(lin['km'])}) não acompanha vias mapeadas "
                           f"no OpenStreetMap ({CIT_OSM}); o acesso ao longo do traçado se dá pela faixa de servidão "
                           f"a partir das vias indicadas acima.")
            out.append("")
        out.append(f"![Alternativas de acesso {artigo} {nomes_txt}](mapas/{g['mapa']}.png)"
                   f"{{#fig:{g['fig']} fonte=\"{fig_fonte}\"}}")
        out.append("")
    out.append("<!-- Revestimento das vias conforme o OpenStreetMap (tag surface): conferir em campo/Google Earth "
               "e, se divergir, corrigir no OSM ou no texto. -->")
    return "\n".join(out).strip() + "\n"


# ------------------------------------------------------------------ mapa
def mapa(cfg, g, rotas_utm, n):
    from ferramentas.geo import mapas
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    ctx = mapas.contexto(cfg)
    u = ctx["unidades"]
    sel = u[u["nome"].map(corrigir_nome).isin(g["unidades"]) | u["nome"].isin(g["unidades"])]
    base = unary_union(list(sel.geometry))
    janela = base.buffer(1500).bounds
    ctx = dict(ctx, extent=janela, unidades=sel)
    m = mapas.Mapa(ctx, f"Alternativas de acesso – {g['titulo_mapa']}", paisagem=True)
    m.satelite()
    cores = ["#ffd400", "#00e5ff", "#ff4fd8", "#7CFC00", "#ff8c00", "#ffffff"]
    n_alt = len(rotas_utm)
    for i, (alt, geoms) in enumerate(rotas_utm):
        cor = cores[i % len(cores)]
        lw = 2.0 + 1.6 * (n_alt - 1 - i)  # a 1ª é a mais larga: rotas que se sobrepõem ficam visíveis
        for geo, pav in geoms:
            ls = "-" if pav == "pav" else (0, (3, 2)) if pav == "nao" else (0, (1, 1.5))
            for parte in getattr(geo, "geoms", [geo]):
                xs, ys = parte.xy
                m.ax.plot(xs, ys, color="black", lw=lw + 1.2, zorder=6 + i * 0.1, solid_capstyle="round")
                m.ax.plot(xs, ys, color=cor, lw=lw, ls=ls, zorder=6.05 + i * 0.1)
        m.handles.append(Line2D([], [], color=cor, lw=2, label=alt))
    m.unidades()
    m.handles += [Line2D([], [], color="#444", lw=1.5, ls="-", label="Via pavimentada"),
                  Line2D([], [], color="#444", lw=1.5, ls=(0, (3, 2)), label="Via não pavimentada"),
                  Line2D([], [], color="#444", lw=1.5, ls=(0, (1, 1.5)), label="Revestimento sem informação")]
    m.fontes += ["Vias: OpenStreetMap", "Rotas: OSRM", f"Sanepar ({ANO})"]
    m._enquadrar()
    nome = f"acesso_{n}"
    m.salvar(nome)
    plt.close("all")
    # registra a fonte no índice de mapas (o montador usa a fonte daqui na figura)
    idx = ctx["dir_mapas"] / "MAPAS.md"
    linhas = idx.read_text(encoding="utf-8").splitlines() if idx.exists() else [
        f"# Mapas – {cfg['municipio']}", "", "| Mapa | Fontes (usar no campo fonte= da figura) |", "|---|---|"]
    linhas = [ln for ln in linhas if not ln.startswith(f"| mapas/{nome}.png ")]
    linhas.append(f"| mapas/{nome}.png | {ctx['gerados'][nome]}; elaborado pelo autor, {ANO}. |")
    idx.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return nome


# ------------------------------------------------------------------ principal
def _grupos(u, dist=1500):
    grupos = []
    for i, geo in enumerate(u.geometry):
        alvo = next((gr for gr in grupos if any(geo.distance(u.geometry.iloc[j]) <= dist for j in gr)), None)
        (alvo.append(i) if alvo is not None else grupos.append([i]))
    return grupos


def _geom_trechos(rota, pares, epsg):
    """Geometria da rota em pedaços com o tipo de revestimento (para o estilo da linha no mapa)."""
    coords = rota["geometry"]["coordinates"]
    nos = [n for perna in rota["legs"] for n in perna["annotation"]["nodes"]]
    if len(nos) != len(coords):  # geometria e nós desalinhados: tudo como sem informação
        return [(gpd.GeoSeries([LineString(coords)], crs=4326).to_crs(epsg).iloc[0], "si")]
    pedacos, atual, tipo = [], [coords[0]], None
    for k in range(1, len(coords)):
        t = _pav(revestimento((pares.get((nos[k - 1], nos[k])) or {}).get("surface")))
        if tipo is not None and t != tipo:
            pedacos.append((atual, tipo))
            atual = [coords[k - 1]]
        atual.append(coords[k])
        tipo = t
    pedacos.append((atual, tipo or "si"))
    return [(gpd.GeoSeries([LineString(c)], crs=4326).to_crs(epsg).iloc[0], t) for c, t in pedacos if len(c) > 1]


def gerar(chave, raio_km=3.0):
    from ferramentas.geo.tematico import unidades
    cfg = projeto(chave)
    u, epsg = unidades(cfg)
    u["nome"] = u["nome"].map(corrigir_nome)
    uw = u.to_crs(4326)
    c_all = uw.geometry.union_all().centroid
    sede = _lugar(cfg["municipio"], c_all.x, c_all.y)
    loc = _lugar(cfg.get("localidade"), c_all.x, c_all.y, raio=30000) if cfg.get("localidade") else None
    grupos, rotas_por_grupo, todos_nos = [], [], []

    for n, idx in enumerate(_grupos(u), start=1):
        sub, subw = u.iloc[idx], uw.iloc[idx]
        # destino: centroide das unidades de área (ou o início da 1ª linear), encaixado na via mais próxima
        pol = subw[~subw.geometry.geom_type.str.contains("LineString")]
        alvo = pol.geometry.iloc[0].centroid if len(pol) else Point(subw.geometry.iloc[0].coords[0])
        dest = _encaixar(alvo.x, alvo.y) or (alvo.x, alvo.y)
        origens = []
        if sede:
            origens.append(("sede", sede))
        if loc and (not sede or abs(loc[0] - sede[0]) + abs(loc[1] - sede[1]) > 0.005):
            origens.append(("localidade", loc))
        dlat = raio_km / 111.0
        dlon = raio_km / (111.0 * math.cos(math.radians(alvo.y)))
        for rot, (dx, dy) in {"N": (0, dlat), "S": (0, -dlat), "L": (dlon, 0), "O": (-dlon, 0)}.items():
            p = _encaixar(alvo.x + dx, alvo.y + dy)
            if p:
                origens.append((rot, p))
        rotas = []
        for rot, o in origens:
            r = _rota(o, dest)
            if r and r["distance"] > 50:
                rotas.append((rot, r))
                todos_nos += [nn for perna in r["legs"] for nn in perna["annotation"]["nodes"]]
        rotas_por_grupo.append((n, idx, sub, rotas))

    pares = _vias_dos_nos(todos_nos) if todos_nos else {}
    for n, idx, sub, rotas in rotas_por_grupo:
        alts = {}
        for rot, r in rotas:
            tr = trechos(r, pares)
            ass = _assinatura(tr)
            if ass in alts:
                alts[ass]["origens"].append(rot)
                continue
            alts[ass] = {"origens": [rot], "km": round(r["distance"] / 1000, 2), "trechos": tr,
                         "pavimento_pct": _pavimento_pct(tr), "_rota": r}
        lineares = [{"nome": row["nome"], "km": round(row.geometry.length / 1000, 2),
                     "vias": vias_ao_longo(row.geometry, epsg)} for _, row in sub.iterrows()
                    if row.geometry.geom_type.endswith("LineString")]
        g = {"unidades": list(sub["nome"]), "fig": f"acesso-{n}", "mapa": f"acesso_{n}",
             "titulo_mapa": sub["nome"].iloc[0] if len(sub) == 1 else "unidades do empreendimento",
             "alternativas": list(alts.values()), "lineares": lineares}
        rotas_utm = [(rotulo(a["origens"]),
                      _geom_trechos(a["_rota"], pares, epsg)) for a in g["alternativas"]]
        mapa(cfg, g, rotas_utm, n)
        for a in g["alternativas"]:
            a.pop("_rota")
        grupos.append(g)

    d = cfg["dir"] / "dados"
    texto = redigir(cfg, grupos)
    (d / "acessos.yaml").write_text(yaml.safe_dump({"gerado_em": str(dt.date.today()), "sede": sede, "localidade": loc,
                                                    "grupos": grupos, "texto": texto}, allow_unicode=True,
                                                   sort_keys=False), encoding="utf-8")
    md = [f"# Acessos às unidades – {cfg['municipio']}\n",
          f"Fontes: rotas OSRM ({CIT_OSRM}); vias e revestimento OpenStreetMap ({CIT_OSM}). "
          "'Revestimento não informado' = via sem tag surface no OSM (conferir).\n"]
    for g in grupos:
        md.append(f"## {', '.join(g['unidades'])} (mapas/{g['mapa']}.png)\n")
        for a in g["alternativas"]:
            md.append(f"### {rotulo(a['origens'])} – {_fmt_km(a['km'])} "
                      f"(pav. {a['pavimento_pct']['pav']}%, não pav. {a['pavimento_pct']['nao']}%, s/ inf. {a['pavimento_pct']['si']}%)\n")
            md += [f"- {t['via']}: {_fmt_km(t['km'])} – {t['revestimento']}" for t in a["trechos"]]
            md.append("")
        for lin in g["lineares"]:
            md.append(f"### Traçado de {lin['nome']} ({_fmt_km(lin['km'])})\n")
            md += [f"- {v['via']}: {_fmt_km(v['km'])} ({v['pct']}%) – {v['revestimento']}" for v in lin["vias"]] or ["- nenhuma via mapeada junto ao traçado"]
            md.append("")
    md.append("## Texto gerado ({{auto.acessos}})\n")
    md.append(texto)
    (d / "ACESSOS.md").write_text("\n".join(md), encoding="utf-8")

    abnt_osm = (f"OPENSTREETMAP CONTRIBUTORS. OpenStreetMap. Cambridge: OpenStreetMap Foundation, {ANO}. "
                f"Disponível em: https://www.openstreetmap.org. Acesso em: {biblio.data_acesso()}.")
    abnt_osrm = (f"OSRM – OPEN SOURCE ROUTING MACHINE. Rotas rodoviárias de acesso às unidades do empreendimento. "
                 f"[S.l.]: Project OSRM, {ANO}. Disponível em: https://project-osrm.org. Acesso em: {biblio.data_acesso()}.")
    biblio.usar(chave, [biblio.registrar("openstreetmap", abnt_osm, "base", "https://www.openstreetmap.org", CIT_OSM),
                        biblio.registrar("osrm", abnt_osrm, "base", "https://project-osrm.org", CIT_OSRM)])
    return grupos


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    ap.add_argument("--raio-km", type=float, default=3.0, help="distância dos pontos de origem N/S/L/O (padrão 3 km)")
    a = ap.parse_args()
    for g in gerar(a.chave, a.raio_km):
        print(f"{', '.join(g['unidades'])}: {len(g['alternativas'])} alternativa(s), mapa mapas/{g['mapa']}.png")
    print("Detalhes: dados/ACESSOS.md")


if __name__ == "__main__":
    main()
