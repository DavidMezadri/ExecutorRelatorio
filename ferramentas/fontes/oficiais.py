"""Download de bases oficiais recortadas pela área do empreendimento.

Uso:
    python -m ferramentas.fontes.oficiais candoi [--margem-km 5] [--so solos,geologia] [--forcar]

Grava em projetos/<chave>/dados/oficiais/:
    solos.gpkg, geologia.gpkg, geomorfologia.gpkg, vegetacao.gpkg   IBGE BDiA 1:250.000 (WFS)
    litoestratigrafia.gpkg, hidrogeologia.gpkg                       SGB/CPRM (WFS)
    drenagem.gpkg, massa_dagua.gpkg                                  IBGE BC250 (WFS)
    uph.gpkg, rios_ana.gpkg, ucs.gpkg                                ANA/SNIRH (ArcGIS REST)
    municipio.gpkg, municipios_uf.gpkg                               IBGE Malhas
    dem.tif                                                          Copernicus DEM GLO-30
    mapbiomas.tif                                                    MapBiomas Coleção 9 (2023)
    FONTES.yaml   origem, data de acesso e citação ABNT de cada camada
"""
import argparse
import datetime as dt
import io
import math
import os
from pathlib import Path

import geopandas as gpd
import requests
import yaml
from shapely.geometry import box

from ferramentas.util import console_utf8, projeto
from ferramentas.fontes import ibge

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("OGR_GEOJSON_MAX_OBJ_SIZE", "0")

TIMEOUT = 180
HOJE = dt.date.today()
ACESSO = f"{HOJE.day:02d} {['jan.', 'fev.', 'mar.', 'abr.', 'maio', 'jun.', 'jul.', 'ago.', 'set.', 'out.', 'nov.', 'dez.'][HOJE.month - 1]} {HOJE.year}"

IBGE_BDIA = "https://geoservicos.ibge.gov.br/geoserver/BDIA/wfs"
IBGE_CCAR = "https://geoservicos.ibge.gov.br/geoserver/CCAR/wfs"
SGB = "https://geoservicos.sgb.gov.br/geoserver/wfs"
ANA = "https://www.snirh.gov.br/arcgis/rest/services/DADOSABERTOS/"
DEM_URL = ("https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{lat}_00_{lon}_00_DEM/"
           "Copernicus_DSM_COG_10_{lat}_00_{lon}_00_DEM.tif")
MAPBIOMAS_URL = ("https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/collection_9/lclu/coverage/"
                 "brasil_coverage_{ano}.tif")

# nome -> (tipo, endpoint, camada, citação ABNT)
CAMADAS = {
    "solos": ("wfs", IBGE_BDIA, "BDIA:pedo_area",
              "IBGE – INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA. Banco de Dados de Informações Ambientais (BDiA): "
              "Pedologia 1:250.000. Rio de Janeiro: IBGE, 2023. Disponível em: https://bdiaweb.ibge.gov.br. Acesso em: {acesso}."),
    "geologia": ("wfs", IBGE_BDIA, "BDIA:geol_area",
                 "IBGE – INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA. Banco de Dados de Informações Ambientais (BDiA): "
                 "Geologia 1:250.000. Rio de Janeiro: IBGE, 2023. Disponível em: https://bdiaweb.ibge.gov.br. Acesso em: {acesso}."),
    "geomorfologia": ("wfs", IBGE_BDIA, "BDIA:geom_area",
                      "IBGE – INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA. Banco de Dados de Informações Ambientais (BDiA): "
                      "Geomorfologia 1:250.000. Rio de Janeiro: IBGE, 2023. Disponível em: https://bdiaweb.ibge.gov.br. Acesso em: {acesso}."),
    "vegetacao": ("wfs", IBGE_BDIA, "BDIA:vege_area",
                  "IBGE – INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA. Banco de Dados de Informações Ambientais (BDiA): "
                  "Vegetação 1:250.000. Rio de Janeiro: IBGE, 2023. Disponível em: https://bdiaweb.ibge.gov.br. Acesso em: {acesso}."),
    "litoestratigrafia": ("wfs", SGB, "geosgb:litoestratigrafia_1m",
                          "SGB – SERVIÇO GEOLÓGICO DO BRASIL. Litoestratigrafia 1:1.000.000 (GeoSGB). Brasília: SGB/CPRM. "
                          "Disponível em: https://geosgb.sgb.gov.br. Acesso em: {acesso}."),
    "hidrogeologia": ("wfs", SGB, "hidrogeologia:dominios_hidrogeologicos_2_5m",
                      "SGB – SERVIÇO GEOLÓGICO DO BRASIL. Domínios e subdomínios hidrogeológicos do Brasil, escala 1:2.500.000. "
                      "Brasília: SGB/CPRM. Disponível em: https://geosgb.sgb.gov.br. Acesso em: {acesso}."),
    "drenagem": ("wfs", IBGE_CCAR, "CCAR:BC250_2023_Trecho_Drenagem_L",
                 "IBGE – INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA. Base Cartográfica Contínua do Brasil, escala "
                 "1:250.000 – BC250, versão 2023. Rio de Janeiro: IBGE, 2023. Acesso em: {acesso}."),
    "massa_dagua": ("wfs", IBGE_CCAR, "CCAR:BC250_2023_Massa_Dagua_A",
                    "IBGE – INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA. Base Cartográfica Contínua do Brasil, escala "
                    "1:250.000 – BC250, versão 2023. Rio de Janeiro: IBGE, 2023. Acesso em: {acesso}."),
    "uph": ("ana", ANA + "Unidade_de_Planejamento_Hídrico_UPH/MapServer/0", None,
            "ANA – AGÊNCIA NACIONAL DE ÁGUAS E SANEAMENTO BÁSICO. Unidades de Planejamento Hídrico (UPH). Brasília: ANA. "
            "Disponível em: https://metadados.snirh.gov.br. Acesso em: {acesso}."),
    "rios_ana": ("ana", ANA + "Hidrografia_nível_5/MapServer/0", None,
                 "ANA – AGÊNCIA NACIONAL DE ÁGUAS E SANEAMENTO BÁSICO. Base Hidrográfica Ottocodificada – hidrografia nível 5. "
                 "Brasília: ANA. Disponível em: https://metadados.snirh.gov.br. Acesso em: {acesso}."),
    "ucs": ("ana", ANA + "Unidade_de_Conservação/MapServer/0", None,
            "ANA – AGÊNCIA NACIONAL DE ÁGUAS E SANEAMENTO BÁSICO. Unidades de Conservação (base MMA/CNUC). Brasília: ANA. "
            "Disponível em: https://metadados.snirh.gov.br. Acesso em: {acesso}."),
    "dem": ("dem", None, None,
            "EUROPEAN SPACE AGENCY. Copernicus Global Digital Elevation Model (GLO-30). Distribuído por OpenTopography/AWS, "
            "2021. DOI: 10.5069/G9028PQB. Acesso em: {acesso}."),
    "mapbiomas": ("mapbiomas", None, 2023,
                  "PROJETO MAPBIOMAS. Coleção 9 da Série Anual de Mapas de Cobertura e Uso da Terra do Brasil. "
                  "Disponível em: https://brasil.mapbiomas.org. Acesso em: {acesso}."),
}


def bbox_projeto(cfg, margem_km=5.0):
    """BBox (SIRGAS 2000 geográfico) das unidades + margem; inclui o município se não houver unidades."""
    unidades = cfg["dir"] / "dados" / "unidades.gpkg"
    if unidades.exists():
        g = gpd.read_file(unidades).to_crs("EPSG:31982")
    else:
        m = ibge.malha_municipal()
        g = m[m["cod_ibge"] == ibge.buscar(cfg["municipio"])["id"]].to_crs("EPSG:31982")
    caixa = box(*g.total_bounds).buffer(margem_km * 1000, join_style=2)
    return gpd.GeoSeries([caixa], crs="EPSG:31982").to_crs("EPSG:4674").total_bounds


def wfs(endpoint, camada, bb) -> gpd.GeoDataFrame:
    x0, y0, x1, y1 = bb
    params = {"service": "WFS", "version": "1.1.0", "request": "GetFeature", "typeName": camada,
              "outputFormat": "application/json", "bbox": f"{y0},{x0},{y1},{x1},urn:ogc:def:crs:EPSG:4674"}
    r = _get(endpoint, params)
    g = gpd.read_file(io.BytesIO(r.content))
    if g.crs is None:
        g = g.set_crs("EPSG:4674")
    return g


def _get(url, params):
    """GET com tolerância a certificado SSL inválido (servidores públicos com cadeia incompleta)."""
    from ferramentas.garimpo.web import NAVEGADOR  # alguns geoservers (FUNAI) bloqueiam clientes sem cabeçalho de navegador
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT, headers=NAVEGADOR)
    except requests.exceptions.SSLError:
        import urllib3
        urllib3.disable_warnings()
        print(f"  (aviso: certificado SSL inválido em {url.split('/')[2]}; leitura sem verificação)")
        r = requests.get(url, params=params, timeout=TIMEOUT, verify=False, headers=NAVEGADOR)
    r.raise_for_status()
    return r


def ana(url_camada, bb) -> gpd.GeoDataFrame:
    x0, y0, x1, y1 = bb
    params = {"geometry": f"{x0},{y0},{x1},{y1}", "geometryType": "esriGeometryEnvelope", "inSR": 4674,
              "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "outSR": 4674, "f": "geojson"}
    r = requests.get(url_camada + "/query", params=params, timeout=TIMEOUT)
    r.raise_for_status()
    g = gpd.read_file(io.BytesIO(r.content))
    if g.crs is None:
        g = g.set_crs("EPSG:4674")
    return g


def dem(bb, destino: Path):
    import rasterio
    from rasterio.merge import merge
    x0, y0, x1, y1 = bb
    urls = []
    for lat in range(math.floor(y0), math.floor(y1) + 1):
        for lon in range(math.floor(x0), math.floor(x1) + 1):
            la = f"{'S' if lat < 0 else 'N'}{abs(lat):02d}"
            lo = f"{'W' if lon < 0 else 'E'}{abs(lon):03d}"
            urls.append("/vsicurl/" + DEM_URL.format(lat=la, lon=lo))
    srcs = [rasterio.open(u) for u in urls]
    arr, transf = merge(srcs, bounds=(x0, y0, x1, y1))
    perfil = srcs[0].profile | {"height": arr.shape[1], "width": arr.shape[2], "transform": transf,
                                "driver": "GTiff", "compress": "deflate", "tiled": False}
    perfil.pop("blockxsize", None); perfil.pop("blockysize", None)
    with rasterio.open(destino, "w", **perfil) as dst:
        dst.write(arr)


def mapbiomas(bb, destino: Path, ano=2023):
    import rasterio
    from rasterio.windows import from_bounds
    with rasterio.open("/vsicurl/" + MAPBIOMAS_URL.format(ano=ano)) as src:
        w = from_bounds(*bb, transform=src.transform)
        arr = src.read(1, window=w)
        perfil = {"driver": "GTiff", "dtype": arr.dtype, "count": 1, "height": arr.shape[0], "width": arr.shape[1],
                  "crs": src.crs, "transform": src.window_transform(w), "compress": "deflate", "nodata": 0}
    with rasterio.open(destino, "w", **perfil) as dst:
        dst.write(arr, 1)


def baixar(cfg, margem_km=5.0, so=None, forcar=False):
    destino = cfg["dir"] / "dados" / "oficiais"
    destino.mkdir(parents=True, exist_ok=True)
    fontes_path = destino / "FONTES.yaml"
    fontes = yaml.safe_load(fontes_path.read_text(encoding="utf-8")) if fontes_path.exists() else {}
    bb = bbox_projeto(cfg, margem_km)
    print(f"Área de recorte (SIRGAS 2000): {', '.join(f'{v:.4f}' for v in bb)}")

    # limites municipais (mapa regional)
    if (not so or "municipio" in so) and (forcar or not (destino / "municipio.gpkg").exists()):
        malha = ibge.malha_municipal()
        malha.to_file(destino / "municipios_uf.gpkg", driver="GPKG")
        cod = ibge.buscar(cfg["municipio"])["id"]
        malha[malha["cod_ibge"] == cod].to_file(destino / "municipio.gpkg", driver="GPKG")
        fontes["municipio"] = {"arquivo": "municipio.gpkg", "acesso": str(HOJE), "citacao":
                               f"IBGE – INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA. Malha Municipal Digital do Brasil. "
                               f"Rio de Janeiro: IBGE. Disponível em: https://servicodados.ibge.gov.br/api/docs/malhas. Acesso em: {ACESSO}."}
        print("  ok   municipio / municipios_uf")

    for nome, (tipo, endpoint, camada, citacao) in CAMADAS.items():
        if so and nome not in so:
            continue
        ext = ".tif" if tipo in ("dem", "mapbiomas") else ".gpkg"
        arq = destino / f"{nome}{ext}"
        if arq.exists() and not forcar:
            print(f"  já existe {arq.name}")
            continue
        try:
            if tipo == "wfs":
                g = wfs(endpoint, camada, bb)
            elif tipo == "ana":
                g = ana(endpoint, bb)
            elif tipo == "dem":
                dem(bb, arq); g = None
            else:
                mapbiomas(bb, arq, camada); g = None
            if g is not None:
                if g.empty:
                    print(f"  vazio {nome} (nenhuma feição na área)")
                    fontes[nome] = {"arquivo": None, "acesso": str(HOJE), "obs": "sem feições na área"}
                    continue
                g = g.loc[:, ~g.columns.duplicated()]
                g.to_file(arq, driver="GPKG")
            fontes[nome] = {"arquivo": arq.name, "acesso": str(HOJE), "citacao": citacao.format(acesso=ACESSO)}
            print(f"  ok   {arq.name}" + (f" ({len(g)} feições)" if g is not None else ""))
        except Exception as e:  # serviço fora do ar não deve parar os demais
            print(f"  ERRO {nome}: {e.__class__.__name__}: {str(e)[:150]}")
    fontes_path.write_text(yaml.safe_dump(fontes, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
    return destino


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    ap.add_argument("--margem-km", type=float, default=5.0)
    ap.add_argument("--so", help="lista separada por vírgula (ex.: solos,dem)")
    ap.add_argument("--forcar", action="store_true")
    a = ap.parse_args()
    d = baixar(projeto(a.chave), a.margem_km, a.so.split(",") if a.so else None, a.forcar)
    print(f"Bases em {d}")


if __name__ == "__main__":
    main()
