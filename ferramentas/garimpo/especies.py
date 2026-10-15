"""Fauna e flora: espécies registradas no entorno do projeto e enriquecimento de listas de espécies.

Uso:
    python -m ferramentas.garimpo.especies entorno candoi [--raio-km 10] [--reino plantas|animais|todos] [--max 400]
        -> dados/especies_<reino>.xlsx + dados/ESPECIES_<reino>.md (grupos, famílias, ameaçadas)
    python -m ferramentas.garimpo.especies lista "Araucaria angustifolia" "Ocotea puberula" [--projeto candoi] [-o x.xlsx]
    python -m ferramentas.garimpo.especies lista --arquivo especies.txt --projeto candoi   (uma espécie por linha)
        -> tabela com família, nome popular, origem no PR, endemismo, forma de vida, vegetação, ameaça (MMA e IUCN)
    python -m ferramentas.garimpo.especies especie "Leopardus guttulus"

Fontes (todas registradas em referencias/bibliografia.yaml, e no projeto quando --projeto/entorno):
    GBIF (ocorrências e categoria IUCN), Flora e Funga do Brasil (JBRJ), Portaria MMA nº 148/2022 (lista nacional),
    lida diretamente do Diário Oficial da União.
"""
import argparse
import io
import re
import urllib.parse
from collections import Counter

import geopandas as gpd
import pandas as pd
from shapely.geometry.polygon import orient

from ferramentas.util import console_utf8, projeto, RAIZ
from ferramentas.garimpo import biblio, web

GBIF = "https://api.gbif.org/v1"
JBRJ = "https://servicos.jbrj.gov.br/v2/flora/taxon/"
DOU_148 = "https://www.in.gov.br/en/web/dou/-/portaria-mma-n-148-de-7-de-junho-de-2022-406272733"
CACHE_MMA = RAIZ / "dados_comuns" / "cache" / "lista_mma_148_2022.csv"
REINOS = {"plantas": 6, "animais": 1}
CAT = {"CR": "Criticamente em Perigo", "EN": "Em Perigo", "VU": "Vulnerável", "EW": "Extinta na Natureza",
       "EX": "Extinta", "RE": "Regionalmente Extinta", "NT": "Quase Ameaçada", "LC": "Menos Preocupante",
       "DD": "Dados Insuficientes", "NE": "Não Avaliada"}
IUCN_COD = {"CRITICALLY_ENDANGERED": "CR", "ENDANGERED": "EN", "VULNERABLE": "VU", "NEAR_THREATENED": "NT",
            "LEAST_CONCERN": "LC", "DATA_DEFICIENT": "DD", "EXTINCT": "EX", "EXTINCT_IN_THE_WILD": "EW",
            "NOT_EVALUATED": "NE"}


# ------------------------------------------------------------ Lista nacional (Portaria MMA 148/2022)
def lista_mma() -> pd.DataFrame:
    """Espécies ameaçadas da Portaria MMA 148/2022, extraídas das tabelas publicadas no DOU."""
    if CACHE_MMA.exists():
        return pd.read_csv(CACHE_MMA)
    html = web.obter(DOU_148, cache_horas=24 * 365)
    tabelas = pd.read_html(io.StringIO(html))
    rx_sp = re.compile(r"^[A-Z][a-z]+ [a-z][a-z-]+( [a-z][a-z-]+)?$")
    rx_cat = re.compile(r"^(CR|EN|VU|EW|EX|RE)(\s*\(PEX\))?$")
    linhas, anexo = [], None
    for t in tabelas:
        primeira = str(t.iloc[0, 0])
        if primeira.startswith("ANEXO"):
            anexo = primeira[:7]
        for _, r in t.iterrows():
            cel = [str(c).strip() for c in r.tolist() if str(c) != "nan"]
            sp = next((c for c in cel if rx_sp.match(c)), None)
            cat = next((c for c in reversed(cel) if rx_cat.match(c)), None)
            if sp and cat:
                fam = next((c for c in cel if c.endswith(("aceae", "idae"))), None)
                grupo = "flora" if anexo == "ANEXO 1" else ("fauna aquática" if anexo == "ANEXO 3" else "fauna")
                linhas.append({"especie": sp, "categoria": cat[:2], "familia": fam, "grupo": grupo})
    df = pd.DataFrame(linhas).drop_duplicates("especie")
    CACHE_MMA.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CACHE_MMA, index=False)
    return df


def ref_mma(projeto_chave=None) -> str:
    html = web.obter(DOU_148, cache_horas=24 * 365)
    pub = re.search(r"Publicado em:\s*</?[^>]*>?\s*(\d{2})/(\d{2})/(\d{4}).{0,400}?Edição:\s*</?[^>]*>?\s*(\d+)"
                    r".{0,400}?Seção:\s*</?[^>]*>?\s*(\d+).{0,400}?Página:\s*</?[^>]*>?\s*(\d+)",
                    re.sub(r"\s+", " ", html), re.S)
    ementa = re.search(r'class="ementa"[^>]*>(.*?)</p>', html, re.S)
    ementa = web.html_texto(ementa.group(1)) if ementa else (
        "Altera os Anexos da Portaria nº 443, de 17 de dezembro de 2014, da Portaria nº 444, de 17 de dezembro de "
        "2014, e da Portaria nº 445, de 17 de dezembro de 2014, referentes à atualização da Lista Nacional de "
        "Espécies Ameaçadas de Extinção")
    dou = ""
    if pub:
        d, m, a, ed, sec, pag = pub.groups()
        dou = f" Diário Oficial da União: seção {sec}, Brasília, DF, n. {ed}, p. {pag}, {int(d)} {biblio.MESES[int(m) - 1]} {a}."
    abnt = (f"BRASIL. Ministério do Meio Ambiente. Portaria MMA nº 148, de 7 de junho de 2022. {ementa.rstrip('.')}."
            f"{dou} Disponível em: {DOU_148}. Acesso em: {biblio.data_acesso()}.")
    return biblio.registrar("brasil-portaria-mma-148-2022", abnt, "lei", DOU_148, "BRASIL, 2022",
                            verificado=bool(pub), projeto_chave=projeto_chave)


# ------------------------------------------------------------ Flora e Funga do Brasil
def flora_brasil(nome: str, uf="PR") -> dict:
    try:
        dados = web.obter(JBRJ + urllib.parse.quote(nome), json=True, cache_horas=24 * 90)
    except Exception:
        return {}
    if not dados:
        return {}
    e = next((x for x in dados if x["taxon"].get("taxonomicstatus") == "NOME_ACEITO"), dados[0])
    t = e["taxon"]
    dist = e.get("distribuition") or []
    no_uf = next((x for x in dist if x.get("locationid") == f"BR-{uf}"), None)
    rem = (dist[0].get("occurrenceremarks") or {}) if dist else {}
    perfil = e.get("specie_profile") or {}
    return {
        "nome_aceito": t.get("scientificname"),
        "familia": t.get("family"),
        "nomes_populares": ", ".join(list(dict.fromkeys(v["vernacularname"] for v in e.get("vernacular_name") or []))[:5]) or None,
        "origem_uf": no_uf.get("establishmentmeans") if no_uf else "não registrada na UF",
        "endemismo": rem.get("endemism"),
        "dominios": ", ".join(rem.get("phytogeographicDomain") or []) or None,
        "forma_vida": ", ".join(perfil.get("lifeForm") or []) or None,
        "vegetacao": ", ".join(perfil.get("vegetationType") or []) or None,
        "fonte_flora": _citacao_flora(t.get("source") or t.get("bibliographiccitation")),
    }


def _citacao_flora(fonte):
    """O JBRJ devolve várias citações em HTML; fica a mais recente (Flora e Funga / Flora do Brasil 2020)."""
    if not fonte:
        return None
    partes = [web.html_texto(p) for p in re.split(r"(?i)<br\s*/?>\s*<br\s*/?>", fonte)]
    partes = [re.sub(r"\s+", " ", p).strip() for p in partes if p.strip()]
    preferida = next((p for p in partes if "Flora e Funga" in p), None) or \
        next((p for p in partes if "Flora do Brasil 2020" in p), None)
    return preferida or (partes[0] if partes else None)


def ref_flora(projeto_chave=None) -> str:
    abnt = (f"FLORA E FUNGA DO BRASIL. Jardim Botânico do Rio de Janeiro. Disponível em: "
            f"http://floradobrasil.jbrj.gov.br/. Acesso em: {biblio.data_acesso()}.")
    return biblio.registrar("flora-e-funga-do-brasil", abnt, "base", "http://floradobrasil.jbrj.gov.br/",
                            "FLORA E FUNGA DO BRASIL, 2026", projeto_chave=projeto_chave)


# ------------------------------------------------------------ GBIF
def gbif_especie(chave_ou_nome) -> dict:
    if isinstance(chave_ou_nome, (int, str)) and str(chave_ou_nome).isdigit():
        sp = web.obter(f"{GBIF}/species/{chave_ou_nome}", json=True, cache_horas=24 * 90)
    else:
        sp = web.obter(f"{GBIF}/species/match", params={"name": chave_ou_nome}, json=True, cache_horas=24 * 90)
        sp = web.obter(f"{GBIF}/species/{sp['usageKey']}", json=True, cache_horas=24 * 90) if sp.get("usageKey") else {}
    if not sp:
        return {}
    k = sp.get("acceptedKey") or sp["key"]
    out = {"gbif_key": k, "especie": sp.get("canonicalName") or sp.get("scientificName"), "reino": sp.get("kingdom"),
           "classe": sp.get("class"), "ordem": sp.get("order"), "familia": sp.get("family")}
    try:
        vn = web.obter(f"{GBIF}/species/{k}/vernacularNames", params={"limit": 100}, json=True, cache_horas=24 * 90)
        pt = [v["vernacularName"] for v in vn.get("results", []) if v.get("language") in ("por", "pt")]
        out["nome_popular_gbif"] = ", ".join(dict.fromkeys(x.strip().capitalize() for x in pt[:4])) or None
    except Exception:
        pass
    try:
        iu = web.obter(f"{GBIF}/species/{k}/iucnRedListCategory", json=True, cache_horas=24 * 90)
        out["iucn"] = IUCN_COD.get(iu.get("category"), iu.get("code"))
    except Exception:
        out["iucn"] = None
    return out


def ref_gbif(url_busca, descricao, projeto_chave=None, chave="gbif-ocorrencias") -> str:
    # a URL completa (com o polígono) fica no catálogo para reproduzir a busca; na ABNT vai a URL base
    abnt = (f"GBIF.ORG. GBIF Occurrence Search: {descricao}. Copenhague: GBIF Secretariat, {biblio.dt.date.today().year}. "
            f"Disponível em: https://www.gbif.org/occurrence/search. Acesso em: {biblio.data_acesso()}.")
    return biblio.registrar(chave, abnt, "base", url_busca, f"GBIF.ORG, {biblio.dt.date.today().year}",
                            projeto_chave=projeto_chave,
                            obs="URL completa da busca no campo url. Para publicação formal, o GBIF recomenda citar o DOI de um download")


def ref_iucn(projeto_chave=None) -> str:
    abnt = (f"IUCN. The IUCN Red List of Threatened Species. Disponível em: https://www.iucnredlist.org. "
            f"Acesso em: {biblio.data_acesso()}.")
    return biblio.registrar("iucn-red-list", abnt, "base", "https://www.iucnredlist.org", "IUCN, 2026",
                            projeto_chave=projeto_chave)


def area_busca(cfg, raio_km):
    from ferramentas.geo.tematico import unidades
    u, epsg = unidades(cfg)
    area = gpd.GeoSeries([u.geometry.buffer(raio_km * 1000).union_all().convex_hull], crs=epsg).to_crs("EPSG:4326")
    poli = orient(area.iloc[0].simplify(0.002), sign=1.0)  # GBIF exige anti-horário
    return poli.wkt


def entorno(cfg, raio_km=10.0, reino="todos", maximo=400) -> pd.DataFrame:
    wkt = area_busca(cfg, raio_km)
    reinos = list(REINOS.items()) if reino == "todos" else [(reino, REINOS[reino])]
    mma = lista_mma().set_index("especie")
    linhas = []
    for nome_reino, kk in reinos:
        params = {"geometry": wkt, "kingdomKey": kk, "hasCoordinate": "true", "hasGeospatialIssue": "false",
                  "occurrenceStatus": "PRESENT", "limit": 0, "facet": "speciesKey", "facetLimit": maximo}
        res = web.obter(f"{GBIF}/occurrence/search", params=params, json=True, cache_horas=24 * 30)
        contagens = res["facets"][0]["counts"] if res.get("facets") else []
        print(f"  {nome_reino}: {res.get('count', 0)} registros, {len(contagens)} espécies")

        def detalhar(c, nome_reino=nome_reino):
            info = gbif_especie(int(c["name"]))
            if not info:
                return None
            info["registros_gbif"] = c["count"]
            info["ameaca_mma_148"] = mma["categoria"].get(info["especie"]) if info["especie"] in mma.index else None
            if nome_reino == "plantas":
                info.update({k: v for k, v in flora_brasil(info["especie"]).items() if k not in ("familia",)})
            return info

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as ex:
            linhas += [i for i in ex.map(detalhar, contagens) if i]
        url = ("https://www.gbif.org/occurrence/search?" +
               urllib.parse.urlencode({"geometry": wkt, "taxon_key": kk, "has_coordinate": "true",
                                       "has_geospatial_issue": "false"}))
        ref_gbif(url, f"ocorrências de {'Plantae' if kk == 6 else 'Animalia'} em raio de {raio_km:g} km do "
                      f"empreendimento em {cfg['municipio']}/PR", cfg["chave"], f"gbif-{cfg['chave']}-{nome_reino}")
    ref_mma(cfg["chave"])
    ref_iucn(cfg["chave"])
    if any(r == "plantas" for r, _ in reinos):
        ref_flora(cfg["chave"])
    return pd.DataFrame(linhas)


def resumo_md(df: pd.DataFrame, titulo: str) -> str:
    out = [f"# {titulo}\n", f"{len(df)} espécies; {int(df['registros_gbif'].sum())} registros (GBIF).\n"]
    for col, rot in (("classe", "Por classe"), ("familia", "Famílias mais representadas")):
        c = Counter(df[col].dropna())
        out.append(f"\n## {rot}\n" + "\n".join(f"- {k}: {v} espécies" for k, v in c.most_common(15)))
    ame = df[df["ameaca_mma_148"].notna() | df["iucn"].isin(["CR", "EN", "VU"])]
    out.append("\n## Espécies ameaçadas (Portaria MMA 148/2022 e/ou IUCN CR/EN/VU)\n")
    out += [f"- *{r.especie}* ({r.familia}) – MMA: {r.ameaca_mma_148 or '-'}; IUCN: {r.iucn or '-'}"
            + (f" – {r.nome_popular_gbif}" if isinstance(r.nome_popular_gbif, str) else "")
            for r in ame.itertuples()] or ["- nenhuma"]
    out.append("\nRegistros secundários (coleções e observações publicadas no GBIF): indicam ocorrência potencial na "
               "região, não substituem levantamento de campo.")
    return "\n".join(out) + "\n"


def enriquecer_lista(nomes, projeto_chave=None) -> pd.DataFrame:
    mma = lista_mma().set_index("especie")
    linhas = []
    for n in nomes:
        n = n.strip()
        if not n:
            continue
        info = {"nome_informado": n, **gbif_especie(n)}
        fb = flora_brasil(n)
        if fb:
            info.update(fb)
        esp = info.get("especie") or n
        info["ameaca_mma_148"] = mma["categoria"].get(esp) if esp in mma.index else None
        linhas.append(info)
    ref_mma(projeto_chave); ref_iucn(projeto_chave)
    if any(l.get("fonte_flora") for l in linhas):
        ref_flora(projeto_chave)
    return pd.DataFrame(linhas)


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="acao", required=True)
    e = sub.add_parser("entorno"); e.add_argument("chave"); e.add_argument("--raio-km", type=float, default=10)
    e.add_argument("--reino", choices=["plantas", "animais", "todos"], default="todos"); e.add_argument("--max", type=int, default=400)
    l = sub.add_parser("lista"); l.add_argument("nomes", nargs="*"); l.add_argument("--arquivo")
    l.add_argument("--projeto"); l.add_argument("-o", "--saida")
    s = sub.add_parser("especie"); s.add_argument("nome")
    a = ap.parse_args()

    if a.acao == "entorno":
        cfg = projeto(a.chave)
        df = entorno(cfg, a.raio_km, a.reino, a.max)
        d = cfg["dir"] / "dados"
        for reino in (["plantas", "animais"] if a.reino == "todos" else [a.reino]):
            parte = df[df["reino"] == ("Plantae" if reino == "plantas" else "Animalia")]
            if parte.empty:
                continue
            parte.to_excel(d / f"especies_{reino}.xlsx", index=False)
            md = resumo_md(parte, f"{'Flora' if reino == 'plantas' else 'Fauna'} registrada no entorno de "
                                  f"{a.raio_km:g} km – {cfg['municipio']}")
            (d / f"ESPECIES_{reino}.md").write_text(md, encoding="utf-8")
            print(md)
        print(f"Tabelas em {d}")
    elif a.acao == "lista":
        nomes = list(a.nomes)
        if a.arquivo:
            nomes += open(a.arquivo, encoding="utf-8").read().splitlines()
        df = enriquecer_lista(nomes, a.projeto)
        print(df.drop(columns=[c for c in ("fonte_flora", "gbif_key") if c in df]).to_string(index=False))
        if a.saida or a.projeto:
            out = a.saida or projeto(a.projeto)["dir"] / "dados" / "especies_lista.xlsx"
            df.to_excel(out, index=False)
            print(f"Tabela: {out}")
    else:
        info = gbif_especie(a.nome)
        info.update(flora_brasil(a.nome))
        mma = lista_mma().set_index("especie")
        esp = info.get("especie") or a.nome
        info["ameaca_mma_148"] = mma["categoria"].get(esp) if esp in mma.index else "não consta"
        for k, v in info.items():
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()
