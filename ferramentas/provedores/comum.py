"""Acesso comum aos serviços nacionais (ArcGIS REST da ANA, WFS do SGB/DNIT) com cache."""
import json

from ferramentas.garimpo import web

SNIRH = "https://www.snirh.gov.br/arcgis/rest/services/"
SGB_WFS = "https://geoservicos.sgb.gov.br/geoserver/wfs"
DNIT_WFS = "https://servicos.dnit.gov.br/dnitgeo/geoserver/ows"
CACHE_H = 24 * 60


def arcgis(servico, lon, lat, raio_graus=0.0, campos="*", camada=0, geometria=False):
    """Feições do serviço ArcGIS (MapServer) que cruzam o ponto ou o quadrado de lado 2*raio em volta dele."""
    if raio_graus:
        geo = json.dumps({"xmin": lon - raio_graus, "ymin": lat - raio_graus, "xmax": lon + raio_graus,
                          "ymax": lat + raio_graus, "spatialReference": {"wkid": 4326}})
        tipo = "esriGeometryEnvelope"
    else:
        geo, tipo = f"{lon},{lat}", "esriGeometryPoint"
    p = {"f": "json", "geometry": geo, "geometryType": tipo, "inSR": 4326, "outSR": 4326,
         "spatialRel": "esriSpatialRelIntersects", "outFields": campos, "returnGeometry": str(geometria).lower()}
    j = web.obter(f"{SNIRH}{servico}/MapServer/{camada}/query", params=p, json=True, cache_horas=CACHE_H)
    if j.get("error"):
        raise RuntimeError(f"{servico}: {j['error'].get('message')}")
    return j.get("features", [])


def wfs(endpoint, camada, cql=None, bbox=None, n=200):
    p = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": camada,
         "outputFormat": "application/json", "count": n}
    if cql:
        p["CQL_FILTER"] = cql
    if bbox:
        lon0, lat0, lon1, lat1 = bbox
        p["bbox"] = f"{lat0},{lon0},{lat1},{lon1},urn:ogc:def:crs:EPSG::4326"
    try:
        txt = web.obter(endpoint, params=p, cache_horas=CACHE_H, timeout=120)
    except Exception:
        return None  # camada inexistente nesta região/escala ou serviço fora do ar
    try:
        return json.loads(txt).get("features", [])
    except ValueError:
        return None  # camada inexistente/erro do servidor (resposta XML)


def num(v, casas=1):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def lista(xs):
    xs = [x for x in xs if x]
    return xs[0] if len(xs) == 1 else (", ".join(xs[:-1]) + " e " + xs[-1]) if xs else ""
