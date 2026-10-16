"""Hidrologia, geologia e hidrogeologia do Paraná em fontes oficiais, por unidade do projeto.

Uso:
    python -m ferramentas.garimpo.aguas_pr <chave>

Fontes (baixadas uma vez para dados_comuns/cache/):
  - Carta das Águas Subterrâneas do Paraná: resumo executivo (BRASIL. MMA, 2015 – MMA, Governo do Paraná e
    Serviço Geológico do Brasil): bacias e rede hidrográfica (cap. 2.1), geologia por formação (2.2) e cada
    unidade aquífera – hidrodinâmica, vulnerabilidade (cap. 3);
  - IAT – shapefiles oficiais: Unidades Aquíferas do Paraná, Bacias Hidrográficas e Unidades Hidrográficas
    (Resolução CERH/PR nº 49/2006) -> em qual aquífero/bacia/unidade hidrográfica cada unidade do projeto está;
  - MENDES et al. (2002), geólogos da Sanepar: poços da Sanepar em cada aquífero.
A formação geológica vem da camada de litoestratigrafia do SGB (dados/oficiais, fontes.oficiais).
Gera dados/AGUAS_PR.md e dados/aguas_pr.yaml (usado pelo redator em hidrologia, geologia e hidrogeologia).
"""
import argparse
import io
import re
import zipfile

import geopandas as gpd
import yaml

from ferramentas.util import console_utf8, projeto, RAIZ
from ferramentas.garimpo import web, biblio

CACHE = RAIZ / "dados_comuns" / "cache"
IAT = "https://www.iat.pr.gov.br/sites/agua-terra/arquivos_restritos/files/documento/"
CARTA_URL = IAT + "2020-07/livror5.pdf"
MENDES_URL = "https://aguassubterraneas.abas.org/asubterraneas/article/download/22845/14995/82630"
SHAPES = {"aquiferos": ("2020-07/unidades_aquiferas_parana.zip", "Unidades_Aquiferas_Parana.shp"),
          "bacias": ("2020-07/bacias_hidrograficas_parana.zip", "Bacias_Hidrograficas_Parana.shp"),
          "uh": ("2020-07/unidades_hidrograficas_parana.zip", "Unidades_Hidrograficas_Parana.shp")}
CIT_CARTA, CIT_IAT, CIT_MENDES = "BRASIL, 2015", "IAT, [2020]", "MENDES et al., 2002"
ABNT_CARTA = ("BRASIL. Ministério do Meio Ambiente. Secretaria de Recursos Hídricos e Ambiente Urbano. Carta das águas "
              "subterrâneas do Paraná: resumo executivo. Brasília, DF: MMA, 2015. 337 p. ISBN 978-85-7738-260-6. "
              f"Disponível em: {CARTA_URL}. Acesso em: {{acesso}}.")
ABNT_IAT = ("PARANÁ. Instituto Água e Terra. Mapas e dados espaciais: unidades aquíferas, bacias hidrográficas e unidades "
            "hidrográficas do Paraná (shapefiles). Curitiba: IAT, [2020]. Disponível em: "
            "https://www.iat.pr.gov.br/Pagina/Mapas-e-Dados-Espaciais. Acesso em: {acesso}.")
# seção da Carta de cada aquífero; unidade do shapefile do IAT -> aquífero da Carta
AQUIFEROS = {"Embasamento Cristalino": "3.4", "Carste": "3.5", "Furnas": "3.6", "Itararé": "3.7", "Rio Bonito": "3.8",
             "Passa Dois": "3.9", "Guarani": "3.10", "Serra Geral": "3.11", "Caiuá": "3.12", "Guabirotuba": "3.13",
             "Litorâneo": "3.14"}
IAT_PARA_CARTA = {"Serra Geral Norte": "Serra Geral", "Serra Geral Sul": "Serra Geral", "Guarani": "Guarani",
                  "Caiuá": "Caiuá", "Karst": "Carste", "Prê-Cambriana": "Embasamento Cristalino",
                  "Paleozóica Inferior": "Furnas", "Paleozóica Média Superior": "Itararé",
                  "Paleozóica Superior": "Passa Dois", "Guabirutuba": "Guabirotuba", "Costeira": "Litorâneo"}
# formação geológica (nome no SGB) -> aquífero, quando a geologia é mais específica que o shapefile
GEO_PARA_AQUIFERO = [("Serra Geral", "Serra Geral"), ("Botucatu", "Guarani"), ("Pirambóia", "Guarani"),
                     ("Caiuá", "Caiuá"), ("Guabirotuba", "Guabirotuba"), ("Furnas", "Furnas"), ("Itararé", "Itararé"),
                     ("Campo do Tenente", "Itararé"), ("Mafra", "Itararé"), ("Rio do Sul", "Itararé"),
                     ("Rio Bonito", "Rio Bonito"), ("Passa Dois", "Passa Dois"), ("Irati", "Passa Dois"),
                     ("Serra Alta", "Passa Dois"), ("Teresina", "Passa Dois"), ("Rio do Rasto", "Passa Dois"),
                     ("Capiru", "Carste")]
# aquífero da Carta -> seção de Mendes et al. (2002)
MENDES = {"Serra Geral": "Aqüífero Serra Geral", "Guarani": "Aqüífero Guarani", "Caiuá": "Aqüífero Caiuá",
          "Carste": "Aqüífero Carste", "Embasamento Cristalino": "Aqüífero Cristalino", "Guabirotuba": "Aqüífero Guabirotuba",
          "Litorâneo": "Aqüífero Costeiro", "Furnas": "Aqüífero Paleozóico", "Itararé": "Aqüífero Paleozóico",
          "Rio Bonito": "Aqüífero Paleozóico", "Passa Dois": "Aqüífero Paleozóico"}


# ------------------------------------------------------------------ download e texto
def _arquivo(nome, url, timeout=600):
    arq = CACHE / nome
    if not arq.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        arq.write_bytes(web.obter(url, binario=True, cache_horas=24 * 365, timeout=timeout))
    return arq


def _texto_pdf(nome, url):
    txt = CACHE / (nome + ".txt")
    if not txt.exists():
        import pymupdf
        doc = pymupdf.open(_arquivo(nome, url))
        txt.write_text("\n".join(p.get_text() for p in doc), encoding="utf-8")
    return txt.read_text(encoding="utf-8")


def _shape(chave):
    zipn, shp = SHAPES[chave]
    pasta = CACHE / f"iat_{chave}"
    if not (pasta / shp).exists():
        dados = web.obter(IAT + zipn, binario=True, cache_horas=24 * 365, timeout=300)
        zipfile.ZipFile(io.BytesIO(dados)).extractall(pasta)
    return gpd.read_file(pasta / shp)


LIXO = re.compile(r"^(Figura|Tabela|Fonte|Foto|CARTA DAS ÁGUAS|RESUMO EXECUTIVO|Quadro)\b|^\d+(\.\d+)*\s+Aquífero|^[!\"/.\s]+$")


def _prosa(trecho):
    """Só a prosa: tira tabelas (linhas curtas/numéricas), legendas, cabeçalhos; junta hifenização."""
    linhas = []
    for ln in trecho.splitlines():
        s = ln.strip()
        if not s or LIXO.match(s) or re.fullmatch(r"[\d.,\s%()\-–]+", s):
            continue
        if len(s) < 28 and not s.endswith((".", ":", ";", ",")):
            continue
        linhas.append(s)
    t = ""
    for s in linhas:
        t = t[:-1] + s if t.endswith("-") else (t + " " + s if t else s)
    t = re.sub(r"\s+", " ", t)
    t = t.replace("m3h-1", "m³/h").replace(" km ;", " km²;").replace(" km )", " km²)")
    t = re.sub(r"\(m³/h\s*\)\s*m-1", "(m³/h)/m", t)
    t = re.sub(r"\s*\((?:ver |vide )?(?:Figuras?|Tabelas?|Quadros?) [\d.]+(?: e [\d.]+)?\)", "", t)  # "(Figura 3.76)"
    t = re.sub(r"\(m³/h\)/m(?=[a-z])", "(m³/h)/m ", t)
    # título da subseção grudado no início ("Vulnerabilidade à contaminação no aquífero X ...")
    t = re.sub(r"^(?:Caracterização (?:hidrodinâmica|hidroquímica)|Vulnerabilidade à contaminação)"
               r"(?:\s+(?:no|do) aquífero [A-ZÁ][\wÀ-ú ]*?)?\s+(?=[A-Z])", "", t.strip())
    frases = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕ])", t)
    legenda_foto = re.compile(r"(?:,| -| –) em [A-ZÁÉÍÓÚ][\wÀ-ú ]+\.$|^(?:Contato|Pedreira|Afloramento|Arenito com|Siltito com)"
                              r"|^(?:Formação|Grupo|Membro) [\wÀ-ú ]+ [-–] ")
    # frases que ainda remetem a figuras/tabelas ("pode ser observado na Figura 3.70") e legendas de foto soltas
    return [f for f in frases if not re.search(r"\b(Figura|Tabela|Foto|Quadro)s?\s+\d", f) and len(f) > 45
            and not f.startswith(("Capta ", "Poço ", "Foto")) and not (len(f) < 160 and legenda_foto.search(f))]


def apud(frases, cit):
    """Citações de terceiros dentro do texto da Carta viram citação de citação (ABNT): (LICHT, 2012 apud BRASIL, 2015)."""
    nome = r"[A-ZÁÉÍÓÚ][\wÀ-ú'´]+(?:\s(?:&|e)\s[A-ZÁÉÍÓÚ][\wÀ-ú'´]+|\set\.?\sal\.?)?"
    out = []
    for f in frases:
        f = f.replace(" neste trabalho,", "").replace(" neste trabalho", "")
        f = re.sub(rf"\(({nome}),?\s*\(?(\d{{4}}[a-z]?)\)?\)",
                   lambda m: f"({m.group(1).upper().replace(' & ', '; ').replace(' E ', '; ').replace('ET AL', 'et al')}, "
                             f"{m.group(2)} apud {cit})", f)
        f = re.sub(rf"\b({nome}),?\s\((\d{{4}}[a-z]?)\)", lambda m: f"{m.group(1).replace(' & ', ' e ')} ({m.group(2)} apud {cit})", f)
        out.append(f)
    return out


def _secao(t, ini, fim, apos=20000):
    a = t.find(ini, apos)
    if a < 0:
        return ""
    b = t.find(fim, a + len(ini)) if fim else -1
    return t[a + len(ini):b if b > 0 else a + 12000]


# ------------------------------------------------------------------ conteúdo por tema
def aquifero_texto(t, aq, bacia=None):
    num = AQUIFEROS[aq]
    prox = f"3.{int(num.split('.')[1]) + 1} "
    hid = _prosa(_secao(t, f"{num}.1", f"{num}.2"))
    vul = _prosa(_secao(t, f"{num}.3", prox))
    # hidrodinâmica: frases de vazão, capacidade específica, profundidade/nível e as que citam a bacia do projeto
    chave = re.compile(r"vazão mediana|capacidade específica|profundidade perfurada|Nível Estático|risco|produtiv", re.I)
    sel = [f for f in hid if chave.search(f) or (bacia and bacia.lower() in f.lower())]
    return {"hidrodinamica": apud(sel[:6], CIT_CARTA), "vulnerabilidade": apud(vul[:3], CIT_CARTA)}


def formacao_texto(t, nome):
    """Texto da Carta (cap. 2.2) sobre a formação/grupo geológico."""
    base = re.sub(r"^(Grupo|Formação|Supergrupo|Subgrupo|Complexo)\s+", "", nome).strip()
    m = re.search(rf"2\.2\.\d(?:\.\d)*(?:\.\d)?\s+(?:Formação|Grupo)\s+{re.escape(base)}\s*\n", t[20000:])
    if not m:
        return []
    a = 20000 + m.end()
    nxt = re.search(r"\n2\.\d(?:\.\d)+\s+[A-ZÁÉÍÓÚ]", t[a:])
    return apud(_prosa(t[a:a + (nxt.start() if nxt else 4000)]), CIT_CARTA)


def bacia_area_carta(t, bacia):
    m = re.search(rf"{re.escape(bacia)} \(([\d.]+,\d+) km", t)
    return m.group(1) if m else None


def mendes_texto(t, secao):
    a = t.find(secao + " \n")
    if a < 0:
        a = t.find(secao)
    if a < 0:
        return None
    trecho = t[a:a + 4000]
    m = re.search(r"(Atualmente,? (?:a Sanepar opera|encontram-se em operação|a Sanepar possui).+?\.)(?:\s|$)(.+?\.)?",
                  re.sub(r"\s+", " ", trecho))
    txt = " ".join(x for x in (m.group(1), m.group(2)) if x) if m else None
    if not txt:
        return None
    txt = re.sub(r"(\d)\s*m3/h", r"\1 m³/h", txt.replace("Aqüífero", "Aquífero").replace("aqüífero", "aquífero"))
    return re.sub(r"\bm3\b", "m³", txt)


# ------------------------------------------------------------------ projeto
def para_projeto(chave):
    from ferramentas.geo.tematico import unidades
    cfg = projeto(chave)
    u, epsg = unidades(cfg)
    carta = _texto_pdf("carta_aguas_subterraneas_pr_2015.pdf", CARTA_URL)
    try:
        mendes = _texto_pdf("mendes_2002_mananciais_pr.pdf", MENDES_URL)
    except Exception:
        mendes = ""
    aqf, bac, uh = (_shape(k).to_crs(epsg) for k in ("aquiferos", "bacias", "uh"))
    lit = cfg["dir"] / "dados" / "oficiais" / "litoestratigrafia.gpkg"
    lit = gpd.read_file(lit).to_crs(epsg) if lit.exists() else None

    def no_ponto(gdf, geom, campo):
        p = geom.centroid if not geom.geom_type.endswith("LineString") else geom.interpolate(0.5, normalized=True)
        hit = gdf[gdf.contains(p)]
        if hit.empty:
            hit = gdf.iloc[[gdf.distance(p).idxmin()]] if len(gdf) else hit
        return None if hit.empty else hit.iloc[0][campo]

    por_unidade = {}
    for _, row in u.iterrows():
        g = row.geometry
        geo = None
        if lit is not None:
            p = g.centroid if not g.geom_type.endswith("LineString") else g.interpolate(0.5, normalized=True)
            hit = lit[lit.contains(p)]
            geo = hit.iloc[0].to_dict() if not hit.empty else None
        aq_iat = no_ponto(aqf, g, "TIPO_UNIDA")
        aq = next((a for k, a in GEO_PARA_AQUIFERO if geo and k.lower() in str(geo.get("nome", "")).lower()), None) \
            or IAT_PARA_CARTA.get(aq_iat)
        por_unidade[row["nome"]] = {"aquifero_iat": aq_iat, "aquifero": aq, "bacia": no_ponto(bac, g, "NOME"),
                                    "unidade_hidrografica": no_ponto(uh, g, "UNIDADES_H"),
                                    "formacao": geo.get("nome") if geo else None}
    bacias = sorted({x["bacia"] for x in por_unidade.values() if x["bacia"]})
    aquiferos = sorted({x["aquifero"] for x in por_unidade.values() if x["aquifero"]})
    formacoes = sorted({x["formacao"] for x in por_unidade.values() if x["formacao"]})
    dados = {
        "por_unidade": por_unidade,
        "bacias": {b: {"area_km2_carta": bacia_area_carta(carta, b),
                       "unidades_hidrograficas": sorted({x["unidade_hidrografica"] for x in por_unidade.values()
                                                         if x["bacia"] == b and x["unidade_hidrografica"]})} for b in bacias},
        "aquiferos": {a: {**aquifero_texto(carta, a, bacias[0] if bacias else None),
                          "unidade_iat": sorted({x["aquifero_iat"] for x in por_unidade.values() if x["aquifero"] == a}),
                          "sanepar": mendes_texto(mendes, MENDES[a]) if mendes and a in MENDES else None}
                      for a in aquiferos},
        "formacoes": {f: formacao_texto(carta, f) for f in formacoes},
        # descrição oficial do SGB (campo legenda da litoestratigrafia 1:1.000.000) e idade de cada formação
        "formacoes_sgb": {f: {k: v for k, v in (lit[lit["nome"] == f].iloc[0].to_dict() if lit is not None and
                                                 (lit["nome"] == f).any() else {}).items()
                              if k in ("sigla", "hierarquia", "nome_pai", "legenda", "litotipos", "era_min",
                                       "sistema_min", "epoca_min", "idade_min", "idade_max")}
                          for f in formacoes},
        "citacoes": {"carta": CIT_CARTA, "iat": CIT_IAT, "mendes": CIT_MENDES},
    }
    refs = [biblio.registrar("brasil-2015-carta-aguas-pr", ABNT_CARTA.format(acesso=biblio.data_acesso()), "base",
                             CARTA_URL, CIT_CARTA),
            biblio.registrar("iat-dados-espaciais", ABNT_IAT.format(acesso=biblio.data_acesso()), "base",
                             "https://www.iat.pr.gov.br/Pagina/Mapas-e-Dados-Espaciais", CIT_IAT)]
    if mendes:
        refs.append("mendes-2002")
    biblio.usar(chave, refs)
    d = cfg["dir"] / "dados"
    (d / "aguas_pr.yaml").write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=False), encoding="utf-8")
    md = [f"# Águas e geologia – fontes oficiais do Paraná – {cfg['municipio']}", ""]
    for n, x in por_unidade.items():
        md.append(f"- {n}: bacia {x['bacia']} / UH {x['unidade_hidrografica']} / aquífero {x['aquifero']} "
                  f"(IAT: {x['aquifero_iat']}) / formação {x['formacao']}")
    for a, x in dados["aquiferos"].items():
        md += ["", f"## Aquífero {a} ({CIT_CARTA})", "", "**Hidrodinâmica:** " + " ".join(x["hidrodinamica"]), "",
               "**Vulnerabilidade:** " + " ".join(x["vulnerabilidade"]), "", f"**Sanepar ({CIT_MENDES}):** {x['sanepar']}"]
    for f, x in dados["formacoes"].items():
        md += ["", f"## {f} ({CIT_CARTA})", "", " ".join(x) or "(sem seção na Carta)"]
    (d / "AGUAS_PR.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return dados


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    a = ap.parse_args()
    para_projeto(a.chave)
    print((projeto(a.chave)["dir"] / "dados" / "AGUAS_PR.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
