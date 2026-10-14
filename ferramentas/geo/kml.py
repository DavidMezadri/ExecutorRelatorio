"""Leitura de KML/KMZ (Google Earth) para GeoDataFrame, preservando a hierarquia de pastas.

Uso:
    python -m ferramentas.geo.kml ARQUIVO.kmz            # lista pastas e placemarks
    python -m ferramentas.geo.kml ARQUIVO.kmz -o saida.gpkg [--pasta "Candói SAA"]
"""
import argparse
import zipfile
from pathlib import Path

import geopandas as gpd
from lxml import etree
from shapely.geometry import LineString, Point, Polygon, MultiLineString, MultiPoint, MultiPolygon
from shapely.geometry.base import BaseGeometry

from ferramentas.util import console_utf8

WGS84 = "EPSG:4326"


def _ln(el) -> str:
    return etree.QName(el).localname


def _filho(el, nome):
    for c in el:
        if isinstance(c.tag, str) and _ln(c) == nome:
            return c
    return None


def _texto(el, nome):
    c = _filho(el, nome)
    return c.text.strip() if c is not None and c.text else None


def _coords(el):
    pts = []
    for tok in (el.text or "").split():
        partes = tok.split(",")
        if len(partes) >= 2:
            pts.append((float(partes[0]), float(partes[1])))
    return pts


def _geom(el) -> BaseGeometry | None:
    nome = _ln(el)
    if nome == "Point":
        c = _coords(_filho(el, "coordinates"))
        return Point(c[0]) if c else None
    if nome == "LineString":
        c = _coords(_filho(el, "coordinates"))
        return LineString(c) if len(c) >= 2 else None
    if nome == "Polygon":
        aneis = []
        for b in el.iter():
            if isinstance(b.tag, str) and _ln(b) in ("outerBoundaryIs", "innerBoundaryIs"):
                lr = next((x for x in b.iter() if isinstance(x.tag, str) and _ln(x) == "coordinates"), None)
                aneis.append((_ln(b), _coords(lr)))
        ext = [c for t, c in aneis if t == "outerBoundaryIs"]
        ints = [c for t, c in aneis if t == "innerBoundaryIs" and len(c) >= 4]
        return Polygon(ext[0], ints) if ext and len(ext[0]) >= 4 else None
    if nome == "MultiGeometry":
        partes = [g for c in el if isinstance(c.tag, str) and (g := _geom(c)) is not None]
        if not partes:
            return None
        tipos = {g.geom_type for g in partes}
        if tipos == {"Point"}:
            return MultiPoint(partes)
        if tipos == {"LineString"}:
            return MultiLineString(partes)
        if tipos == {"Polygon"}:
            return MultiPolygon(partes)
        from shapely.geometry import GeometryCollection
        return GeometryCollection(partes)
    return None


def _raiz_xml(caminho: Path):
    caminho = Path(caminho)
    if caminho.suffix.lower() == ".kmz":
        with zipfile.ZipFile(caminho) as z:
            nome = next(n for n in z.namelist() if n.lower().endswith(".kml"))
            dados = z.read(nome)
    else:
        dados = caminho.read_bytes()
    parser = etree.XMLParser(recover=True, huge_tree=True)
    return etree.fromstring(dados, parser)


def ler(caminho, pasta: str | None = None) -> gpd.GeoDataFrame:
    """Lê KML/KMZ. Colunas: pasta (caminho 'A/B'), nome, descricao, geometry (WGS84).

    `pasta` filtra pelos placemarks cuja hierarquia contenha esse nome (sem diferenciar maiúsculas).
    """
    raiz = _raiz_xml(caminho)
    linhas = []

    def visitar(el, hierarquia):
        for c in el:
            if not isinstance(c.tag, str):
                continue
            n = _ln(c)
            if n in ("Folder", "Document"):
                nome = _texto(c, "name")
                visitar(c, hierarquia + ([nome] if nome and n == "Folder" else []))
            elif n == "Placemark":
                g = None
                for gc in c:
                    if isinstance(gc.tag, str) and _ln(gc) in ("Point", "LineString", "Polygon", "MultiGeometry"):
                        g = _geom(gc)
                if g is None:
                    continue
                attrs = {}
                for sd in c.iter():
                    if isinstance(sd.tag, str) and _ln(sd) in ("SimpleData", "Data"):
                        chave = sd.get("name")
                        val = sd.text if _ln(sd) == "SimpleData" else _texto(sd, "value")
                        if chave:
                            attrs[chave] = val
                linhas.append({
                    "pasta": "/".join(hierarquia),
                    "nome": _texto(c, "name"),
                    "descricao": _texto(c, "description"),
                    **attrs,
                    "geometry": g,
                })

    visitar(raiz, [])
    gdf = gpd.GeoDataFrame(linhas, geometry="geometry", crs=WGS84)
    if pasta:
        alvo = pasta.lower()
        gdf = gdf[gdf["pasta"].str.lower().str.split("/").apply(lambda p: alvo in p)]
    return gdf.reset_index(drop=True)


def resumo(gdf: gpd.GeoDataFrame) -> str:
    out = []
    for pasta, g in gdf.groupby("pasta", sort=False):
        tipos = g.geometry.geom_type.value_counts().to_dict()
        out.append(f"[{pasta or '(raiz)'}] {len(g)} feições {tipos}")
        if len(g) <= 30:
            out += [f"    - {n} ({t})" for n, t in zip(g["nome"], g.geometry.geom_type)]
    return "\n".join(out)


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivo")
    ap.add_argument("--pasta")
    ap.add_argument("-o", "--saida", help=".gpkg ou .geojson")
    a = ap.parse_args()
    gdf = ler(a.arquivo, a.pasta)
    print(resumo(gdf))
    if a.saida:
        gdf.to_file(a.saida)
        print(f"Salvo: {a.saida}")


if __name__ == "__main__":
    main()
