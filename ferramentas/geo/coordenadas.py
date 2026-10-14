"""Quadro de coordenadas, áreas e extensões das unidades (SIRGAS 2000).

Gera, para cada feição:
  - ponto de referência (ponto, centroide do polígono ou início/fim da linha)
  - latitude/longitude em graus decimais e em GMS
  - UTM SIRGAS 2000 (fuso detectado automaticamente)
  - área (m², ha) para polígonos; extensão (m) para linhas
"""
import math

import geopandas as gpd
import pandas as pd

SIRGAS = "EPSG:4674"


def fuso_utm(lon: float, lat: float) -> str:
    """EPSG SIRGAS 2000 / UTM (hemisfério sul: 31978..31985 = fusos 18S..25S)."""
    fuso = int((lon + 180) // 6) + 1
    if lat < 0:
        return f"EPSG:{31960 + fuso}"
    return f"EPSG:{31954 + fuso}"


def gms(valor: float, eixo: str) -> str:
    hemi = ("S" if valor < 0 else "N") if eixo == "lat" else ("W" if valor < 0 else "E")
    v = abs(valor)
    g = int(v)
    m = int((v - g) * 60)
    s = (v - g - m / 60) * 3600
    if round(s, 2) >= 60:
        m, s = m + 1, 0.0
    return f"{g}°{m:02d}'{s:05.2f}\" {hemi}"  # espaço inseparável: não quebra o hemisfério


def _ponto_ref(geom):
    t = geom.geom_type
    if t == "Point":
        return [("", geom)]
    if t in ("LineString", "MultiLineString"):
        linhas = list(geom.geoms) if t.startswith("Multi") else [geom]
        ini = linhas[0].coords[0]
        fim = linhas[-1].coords[-1]
        from shapely.geometry import Point
        return [("início", Point(ini)), ("fim", Point(fim))]
    return [("centroide", geom.representative_point() if not geom.centroid.within(geom) else geom.centroid)]


def quadro(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Uma linha por ponto de referência (linhas geram 2: início e fim)."""
    if gdf.empty:
        return pd.DataFrame()
    g = gdf.to_crs(SIRGAS)
    c = g.geometry.union_all().centroid
    epsg_utm = fuso_utm(c.x, c.y)
    g_utm = g.to_crs(epsg_utm)
    zona = f"{int(epsg_utm.split(':')[1]) - 31960}S" if c.y < 0 else ""

    linhas = []
    for (_, row), geom_utm in zip(g.iterrows(), g_utm.geometry):
        area = geom_utm.area if geom_utm.geom_type in ("Polygon", "MultiPolygon") else None
        ext = geom_utm.length if geom_utm.geom_type in ("LineString", "MultiLineString") else None
        for ref, pt in _ponto_ref(row.geometry):
            pt_utm = gpd.GeoSeries([pt], crs=SIRGAS).to_crs(epsg_utm).iloc[0]
            linhas.append({
                "unidade": row["nome"],
                "geometria": row.geometry.geom_type,
                "referencia": ref,
                "latitude": round(pt.y, 6),
                "longitude": round(pt.x, 6),
                "latitude_gms": gms(pt.y, "lat"),
                "longitude_gms": gms(pt.x, "lon"),
                "utm_e": round(pt_utm.x, 2),
                "utm_n": round(pt_utm.y, 2),
                "fuso": zona,
                "area_m2": None if area is None else round(area, 2),
                "area_ha": None if area is None else round(area / 1e4, 4),
                "extensao_m": None if ext is None else round(ext, 2),
            })
    df = pd.DataFrame(linhas)
    df.attrs["epsg_utm"] = epsg_utm
    return df
