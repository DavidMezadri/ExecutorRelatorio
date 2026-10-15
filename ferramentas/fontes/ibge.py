"""Dados oficiais do IBGE: código, população/área (Censo 2022), regiões e municípios limítrofes.

Uso:
    python -m ferramentas.fontes.ibge "Candói" [--uf PR]

Malha municipal da UF é baixada uma vez para dados_comuns/cache/ (usada também nos mapas).
Fontes: API de Localidades, SIDRA (tabela 4714 – Censo 2022) e API de Malhas v3.
"""
import argparse
import json

import geopandas as gpd
import requests

from ferramentas.util import console_utf8, slug, RAIZ
from ferramentas.garimpo import web  # GET com cache e tolerância a certificado SSL inválido

CACHE = RAIZ / "dados_comuns" / "cache"
UF_COD = {"PR": 41, "SC": 42, "RS": 43, "SP": 35}
TIMEOUT = 60


def municipios(uf="PR") -> list[dict]:
    arq = CACHE / f"municipios_{uf}.json"
    if not arq.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
        arq.write_text(web.obter(url, cache_horas=0), encoding="utf-8")
    return json.loads(arq.read_text(encoding="utf-8"))


def buscar(nome: str, uf="PR") -> dict | None:
    alvo = slug(nome)
    return next((m for m in municipios(uf) if slug(m["nome"]) == alvo), None)


def malha_municipal(uf="PR") -> gpd.GeoDataFrame:
    """Limites municipais da UF (SIRGAS 2000), com colunas cod_ibge e nome."""
    arq = CACHE / f"malha_municipios_{uf}.geojson"
    if not arq.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = (f"https://servicodados.ibge.gov.br/api/v3/malhas/estados/{UF_COD[uf]}"
               "?formato=application/vnd.geo+json&intrarregiao=municipio&qualidade=intermediaria")
        arq.write_text(web.obter(url, cache_horas=0), encoding="utf-8")
    g = gpd.read_file(arq)
    if g.crs is None:
        g = g.set_crs("EPSG:4674")
    g["cod_ibge"] = g["codarea"].astype(int)
    nomes = {m["id"]: m["nome"] for m in municipios(uf)}
    g["nome"] = g["cod_ibge"].map(nomes)
    return g[["cod_ibge", "nome", "geometry"]]


def censo2022(cod: int) -> dict:
    url = f"https://apisidra.ibge.gov.br/values/t/4714/n6/{cod}/v/93,6318,614/p/2022"
    dados = web.obter(url, json=True, cache_horas=24 * 30)[1:]
    out = {}
    for x in dados:
        v = x["V"]
        try:
            v = float(v)
        except ValueError:
            continue
        if x["D2C"] == "93":
            out["populacao_2022"] = int(v)
        elif x["D2C"] == "6318":
            out["area_km2"] = round(v, 2)
        elif x["D2C"] == "614":
            out["densidade_hab_km2"] = round(v, 2)
    return out


def limitrofes(cod: int, uf="PR") -> list[str]:
    g = malha_municipal(uf).to_crs("EPSG:31982")
    alvo = g[g["cod_ibge"] == cod].geometry.iloc[0].buffer(50)
    viz = g[g.geometry.intersects(alvo) & (g["cod_ibge"] != cod)]
    return sorted(viz["nome"].dropna().tolist())


def info(nome: str, uf="PR") -> dict:
    m = buscar(nome, uf)
    if not m:
        return {}
    cod = m["id"]
    out = {"cod_ibge": cod, "nome_oficial": m["nome"], "uf": uf}
    mic = m.get("microrregiao") or {}
    ri = m.get("regiao-imediata") or {}
    out["mesorregiao"] = (mic.get("mesorregiao") or {}).get("nome")
    out["microrregiao"] = mic.get("nome")
    out["regiao_imediata"] = ri.get("nome")
    out["regiao_intermediaria"] = (ri.get("regiao-intermediaria") or {}).get("nome")
    try:
        out.update(censo2022(cod))
    except (requests.RequestException, ValueError):
        pass
    try:
        out["limitrofes"] = limitrofes(cod, uf)
    except (requests.RequestException, ValueError, IndexError):
        pass
    out["fonte"] = "IBGE – Censo Demográfico 2022 (SIDRA 4714); API de Localidades e Malhas"
    return out


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("municipio")
    ap.add_argument("--uf", default="PR")
    a = ap.parse_args()
    for k, v in info(a.municipio, a.uf).items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
