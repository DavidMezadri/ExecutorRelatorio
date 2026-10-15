"""Cruza as unidades do empreendimento com as bases oficiais e resume o que ocorre em cada uma.

Uso:
    python -m ferramentas.geo.tematico candoi

Gera projetos/<chave>/dados/RESUMO_TEMATICO.md (para a IA redigir o meio físico/biótico) e
resumo_tematico.yaml, além de dados/app.gpkg (faixas de APP calculadas pela Lei 12.651/2012).
Requer: iniciar_projeto + fontes.oficiais.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml

from ferramentas.util import console_utf8, projeto
from ferramentas.geo import raster
from ferramentas.geo.coordenadas import fuso_utm
from ferramentas.geo.legendas import APP_NASCENTE_M, DECLIVIDADE, MAPBIOMAS, app_por_largura

FAIXA_LINHA_M = 15  # meia-largura da faixa de obra considerada para unidades lineares

# camada -> (campo principal, campos complementares, rótulo)
VETORES = {
    "solos": ("legenda", ["relevo", "textura"], "Pedologia (IBGE BDiA 1:250.000)"),
    "geologia": ("nm_unidade", ["nm_lito1", "nm_tempo_g", "nm_provincia"], "Geologia (IBGE BDiA 1:250.000)"),
    "litoestratigrafia": ("nome", ["hierarquia", "litotipos", "era_min", "sistema_min"], "Litoestratigrafia (SGB 1:1.000.000)"),
    "geomorfologia": ("nm_unidade", ["nm_regiao", "nm_dominio", "compartimento", "forma", "dens_dren", "aprof_inci"],
                      "Geomorfologia (IBGE BDiA 1:250.000)"),
    "hidrogeologia": ("nome_unida", ["dom", "subdom", "potenc"], "Hidrogeologia (SGB 1:2.500.000)"),
    "vegetacao": ("legenda_2", ["nm_sec1", "leg_sup"], "Vegetação atual (IBGE BDiA 1:250.000)"),
    "vegetacao:nm_pretet": ("nm_pretet", [], "Vegetação original / fitogeografia (IBGE BDiA 1:250.000)"),
    "uph": ("UPH_SG", ["UPH_NM"], "Unidade de Planejamento Hídrico (ANA)"),
    "ucs": ("nome", [], "Unidades de Conservação (ANA/MMA)"),
}


def unidades(cfg):
    u = gpd.read_file(cfg["dir"] / "dados" / "unidades.gpkg")
    c = u.to_crs("EPSG:4674").geometry.union_all().centroid
    epsg = fuso_utm(c.x, c.y)
    u = u.to_crs(epsg)
    u["area_ref"] = [g.buffer(FAIXA_LINHA_M) if g.geom_type.endswith("LineString") else g for g in u.geometry]
    return u, epsg


def hidrografia(cfg, epsg):
    """Rios (com faixa de APP) e nascentes: camadas do cliente em dados/ têm prioridade sobre a BC250."""
    d = cfg["dir"] / "dados"
    rios = [p for p in d.glob("*.gpkg") if "rio" in p.stem.lower() and "nascente" not in p.stem.lower()]
    nasc = [p for p in d.glob("*.gpkg") if "nascente" in p.stem.lower()]
    if rios:
        r = gpd.read_file(rios[0]).to_crs(epsg)
        r["app_m"] = r["HIDRO"].map(app_por_largura) if "HIDRO" in r else 30
        fonte_r = f"{rios[0].stem} (fornecido)"
    elif (d / "oficiais" / "drenagem.gpkg").exists():
        r = gpd.read_file(d / "oficiais" / "drenagem.gpkg").to_crs(epsg)
        r["app_m"] = 30
        fonte_r = "IBGE BC250"
    else:
        r, fonte_r = gpd.GeoDataFrame(geometry=[], crs=epsg), None
    n = gpd.read_file(nasc[0]).to_crs(epsg) if nasc else gpd.GeoDataFrame(geometry=[], crs=epsg)
    return r, n, fonte_r


def faixas_app(rios, nascentes):
    partes = []
    if len(rios):
        partes.append(gpd.GeoDataFrame({"tipo": ["curso d'água"] * len(rios), "faixa_m": rios["app_m"].values},
                                       geometry=rios.geometry.buffer(rios["app_m"]).values, crs=rios.crs))
    if len(nascentes):
        partes.append(gpd.GeoDataFrame({"tipo": ["nascente"] * len(nascentes), "faixa_m": APP_NASCENTE_M},
                                       geometry=nascentes.geometry.buffer(APP_NASCENTE_M).values, crs=nascentes.crs))
    if not partes:
        return gpd.GeoDataFrame(geometry=[], crs=rios.crs)
    return pd.concat(partes, ignore_index=True)


def _nomes_rios(cfg, epsg, pontos):
    """Nome do rio mais próximo (ANA/BC250) para cada ponto de travessia."""
    of = cfg["dir"] / "dados" / "oficiais"
    fontes = [(of / "rios_ana.gpkg", "NORIOCOMP"), (of / "drenagem.gpkg", "nome")]
    nomes = []
    for p in pontos:
        nome = None
        for arq, campo in fontes:
            if arq.exists():
                g = gpd.read_file(arq).to_crs(epsg)
                g = g[g[campo].notna() & (g[campo].astype(str).str.strip() != "")]
                if len(g):
                    dist = g.distance(p)
                    if dist.min() < 150:
                        nome = g.loc[dist.idxmin(), campo]
                        break
        nomes.append(nome or "curso d'água sem denominação")
    return nomes


def resumir(cfg) -> dict:
    u, epsg = unidades(cfg)
    of = cfg["dir"] / "dados" / "oficiais"
    res = {"crs_utm": epsg, "unidades": {}, "camadas": {}}
    for _, row in u.iterrows():
        res["unidades"][row["nome"]] = {"geometria": row.geometry.geom_type}

    # vetores temáticos
    for camada, (campo, extras, rotulo) in VETORES.items():
        arq = of / f"{camada.split(':')[0]}.gpkg"  # "arquivo:campo" reaproveita a mesma camada
        if not arq.exists():
            continue
        g = gpd.read_file(arq).to_crs(epsg)
        if campo not in g:
            continue
        g["geometry"] = g.geometry.buffer(0)
        geral = Counter()
        for _, row in u.iterrows():
            inter = g[g.intersects(row["area_ref"])]
            if inter.empty:
                continue
            areas = inter.geometry.intersection(row["area_ref"]).area
            tot = areas.sum() or 1
            classes = {}
            for (_, f), a in zip(inter.iterrows(), areas):
                chave = str(f[campo]).strip()
                classes[chave] = classes.get(chave, 0) + a / tot * 100
                geral[chave] += a
            res["unidades"][row["nome"]][camada.replace("vegetacao:nm_pretet", "fitogeografia")] ={k: round(v, 1) for k, v in sorted(classes.items(), key=lambda x: -x[1])}
        detalhes = {}
        for chave in geral:
            f = g[g[campo].astype(str).str.strip() == chave].iloc[0]
            detalhes[chave] = {e: (str(f[e]).replace("\n", " ").strip()[:400]) for e in extras
                               if e in g and pd.notna(f[e]) and str(f[e]).strip()}
        res["camadas"][camada.replace("vegetacao:nm_pretet", "fitogeografia")] = {"rotulo": rotulo, "classes": detalhes}

    # relevo
    if (of / "dem.tif").exists():
        dem, tr, nd = raster.para_utm(of / "dem.tif", epsg)
        decl = raster.declividade_pct(np.where(dem == nd, np.nan, dem), 30.0)
        for _, row in u.iterrows():
            z = raster.valores_na_geometria(dem, tr, row["area_ref"], nd)
            s = raster.valores_na_geometria(decl, tr, row["area_ref"])
            s = s[~np.isnan(s)]
            info = res["unidades"][row["nome"]]
            if z.size:
                info["altitude_m"] = {"min": round(float(z.min())), "max": round(float(z.max())), "media": round(float(z.mean()))}
            if s.size:
                classes, ant = {}, 0
                for lim, nome, _ in DECLIVIDADE:
                    pct = float(((s >= ant) & (s < lim)).mean() * 100)
                    if pct >= 0.5:
                        classes[nome] = round(pct, 1)
                    ant = lim
                info["declividade"] = classes
                info["declividade_media_pct"] = round(float(s.mean()), 1)

    # uso do solo
    if (of / "mapbiomas.tif").exists():
        from rasterio.enums import Resampling
        mb, tr, nd = raster.para_utm(of / "mapbiomas.tif", epsg, reamostragem=Resampling.nearest)
        # distância até a área urbanizada mais próxima (IN 37 Anexo XI 2.1 g – ETE x núcleos populacionais)
        from rasterio.transform import xy
        lin, col = np.nonzero(mb == 24)
        if lin.size:
            xs, ys = xy(tr, lin, col)
            urb = gpd.GeoSeries(gpd.points_from_xy(xs, ys), crs=epsg)
            for _, row in u.iterrows():
                if not row.geometry.geom_type.endswith("LineString"):
                    d = float(urb.distance(row.geometry).min())
                    res["unidades"][row["nome"]]["distancia_area_urbana_m"] = round(max(0, d - 15))
        for _, row in u.iterrows():
            v = raster.valores_na_geometria(mb, tr, row["area_ref"], 0)
            if v.size:
                cont = Counter(v.tolist())
                tot = sum(cont.values())
                res["unidades"][row["nome"]]["uso_solo_mapbiomas"] = {
                    MAPBIOMAS.get(k, (f"classe {k}", ""))[0]: round(c / tot * 100, 1)
                    for k, c in cont.most_common() if c / tot >= 0.005}

    # hidrografia e APP
    rios, nasc, fonte_r = hidrografia(cfg, epsg)
    app = faixas_app(rios, nasc)
    if len(app):
        app_union = app.geometry.union_all()
        gpd.GeoDataFrame(geometry=[app_union], crs=epsg).to_file(cfg["dir"] / "dados" / "app.gpkg", driver="GPKG")
        for _, row in u.iterrows():
            info = res["unidades"][row["nome"]]
            geom = row.geometry
            dentro = geom.intersection(app_union)
            if geom.geom_type.endswith("LineString"):
                info["extensao_em_app_m"] = round(dentro.length)
                cruz = geom.intersection(rios.geometry.union_all()) if len(rios) else None
                pts = [] if cruz is None or cruz.is_empty else (list(cruz.geoms) if hasattr(cruz, "geoms") else [cruz])
                pts = [p.centroid for p in pts]
                if pts:
                    info["travessias"] = len(pts)
                    info["cursos_atravessados"] = sorted(set(_nomes_rios(cfg, epsg, pts)))
            else:
                info["area_em_app_m2"] = round(dentro.area)
            if len(nasc):
                info["nascentes_ate_100m"] = int((nasc.distance(geom) <= 100).sum())
        res["app"] = {"fonte_hidrografia": fonte_r, "criterio": "Lei 12.651/2012 art. 4º: 30 m (<10 m de largura), "
                      "50 m (10–50 m), 100 m (50–200 m); raio de 50 m em nascentes"}
    return res


def para_markdown(cfg, res) -> str:
    out = [f"# Resumo temático – {cfg['municipio']} ({cfg['documento']} {cfg['sistema']})\n",
           f"Gerado do cruzamento das unidades (faixa de {FAIXA_LINHA_M} m para cada lado nas lineares) com as bases "
           f"oficiais em dados/oficiais/ (ver FONTES.yaml). Percentuais = fração da área da unidade.\n"]
    for nome, info in res["unidades"].items():
        out.append(f"\n## {nome}\n")
        for chave, val in info.items():
            if chave == "geometria":
                continue
            if isinstance(val, dict):
                txt = "; ".join(f"{k}: {v}%" if isinstance(v, (int, float)) and chave not in ("altitude_m",) else f"{k}: {v}"
                                for k, v in val.items())
                out.append(f"- **{chave}**: {txt}")
            elif isinstance(val, list):
                out.append(f"- **{chave}**: {', '.join(map(str, val))}")
            else:
                out.append(f"- **{chave}**: {val}")
    out.append("\n# Descrição das classes encontradas\n")
    for camada, d in res["camadas"].items():
        out.append(f"\n## {d['rotulo']}\n")
        for classe, det in d["classes"].items():
            extra = "; ".join(f"{k}: {v}" for k, v in det.items())
            out.append(f"- **{classe}**" + (f" – {extra}" if extra else ""))
    if "app" in res:
        out.append(f"\n## APP\n- Hidrografia: {res['app']['fonte_hidrografia']}\n- Critério: {res['app']['criterio']}")
    return "\n".join(out) + "\n"


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    a = ap.parse_args()
    cfg = projeto(a.chave)
    res = json.loads(json.dumps(resumir(cfg), default=float))  # numpy -> tipos nativos
    d = cfg["dir"] / "dados"
    (d / "resumo_tematico.yaml").write_text(yaml.safe_dump(res, allow_unicode=True, sort_keys=False, width=200),
                                           encoding="utf-8")
    md = para_markdown(cfg, res)
    (d / "RESUMO_TEMATICO.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
