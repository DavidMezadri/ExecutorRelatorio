"""Literatura técnico-científica e estudos de caso (OpenAlex + Crossref), com referência ABNT completa.

Uso:
    python -m ferramentas.garimpo.literatura buscar "estação de tratamento de esgoto impacto ambiental" [-n 10]
            [--desde 2010] [--brasil] [--aberto] [--tipo article|dissertation|book]
    python -m ferramentas.garimpo.literatura doi 10.1590/2175-7860201566411 [--projeto candoi] [--baixar]
    python -m ferramentas.garimpo.literatura usar candoi W1234567890 [--baixar]     # id OpenAlex de uma busca

`buscar` lista os resultados (título, ano, periódico, citações, acesso aberto, DOI, id) e o resumo.
`doi`/`usar` registram a referência ABNT (montada com metadados do Crossref) no catálogo e no projeto;
--baixar salva o PDF de acesso aberto em referencias/literatura/ e extrai o texto (.md) para leitura.
"""
import argparse
import re

from ferramentas.util import console_utf8, RAIZ
from ferramentas.garimpo import biblio, web

OPENALEX = "https://api.openalex.org"
CROSSREF = "https://api.crossref.org/works/"
DIR = RAIZ / "referencias" / "literatura"
EMAIL = {"mailto": "relatorios@biocerne.local"}  # "polite pool" do OpenAlex/Crossref


def _resumo(inv):
    if not inv:
        return None
    pos = sorted((p, w) for w, ps in inv.items() for p in ps)
    return " ".join(w for _, w in pos)


def buscar(termo, n=10, desde=None, brasil=False, aberto=False, tipo=None):
    filtros = []
    if desde:
        filtros.append(f"from_publication_date:{desde}-01-01")
    if brasil:
        filtros.append("authorships.institutions.country_code:BR")
    if aberto:
        filtros.append("open_access.is_oa:true")
    if tipo:
        filtros.append(f"type:{tipo}")
    params = {"search": termo, "per-page": n, "sort": "relevance_score:desc", **EMAIL}
    if filtros:
        params["filter"] = ",".join(filtros)
    dados = web.obter(f"{OPENALEX}/works", params=params, json=True, cache_horas=24 * 7)
    out = []
    for w in dados.get("results", []):
        loc = w.get("primary_location") or {}
        oa = w.get("open_access") or {}
        out.append({
            "id": w["id"].rsplit("/", 1)[-1], "titulo": w.get("title"), "ano": w.get("publication_year"),
            "tipo": w.get("type"), "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
            "veiculo": ((loc.get("source") or {}).get("display_name")),
            "autores": [a["author"]["display_name"] for a in w.get("authorships", [])],
            "citacoes": w.get("cited_by_count"), "aberto": oa.get("is_oa"), "pdf": oa.get("oa_url"),
            "resumo": _resumo(w.get("abstract_inverted_index")),
        })
    return out


def _autor_abnt(nome: str) -> str:
    partes = nome.replace(",", " ").split()
    if len(partes) == 1:
        return partes[0].upper()
    particulas = {"da", "de", "do", "das", "dos", "e"}
    sobrenome = partes[-1]
    if sobrenome.lower() in ("junior", "júnior", "filho", "neto", "jr.", "jr") and len(partes) > 2:
        sobrenome = f"{partes[-2]} {partes[-1]}"
        partes = partes[:-1]
    prenomes = " ".join(p for p in partes[:-1])
    return f"{sobrenome.upper()}, {prenomes}".strip().rstrip(",")


def _autores_abnt(autores: list[str]) -> str:
    if not autores:
        return ""
    if len(autores) > 3:
        return f"{_autor_abnt(autores[0])} et al."
    return "; ".join(_autor_abnt(a) for a in autores)


def abnt_doi(doi: str) -> dict:
    """Referência ABNT a partir do Crossref (fallback: OpenAlex)."""
    try:
        m = web.obter(CROSSREF + doi, params=EMAIL, json=True, cache_horas=24 * 90)["message"]
    except Exception:
        m = None
    if m:
        autores = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in m.get("author", [])]
        titulo = (m.get("title") or [""])[0]
        sub = (m.get("subtitle") or [None])[0]
        veiculo = (m.get("container-title") or [None])[0]
        ano = None
        for k in ("published-print", "published-online", "issued", "created"):
            if m.get(k, {}).get("date-parts"):
                ano = m[k]["date-parts"][0][0]
                break
        partes = [p for p in (f"v. {m['volume']}" if m.get("volume") else None,
                              f"n. {m['issue']}" if m.get("issue") else None,
                              f"p. {m['page']}" if m.get("page") else None) if p]
        tipo = m.get("type")
        if tipo == "journal-article" and veiculo:
            corpo = f"{titulo}{': ' + sub if sub else ''}. {veiculo}, " + ", ".join(partes + [str(ano)]) + "."
        elif tipo in ("book", "monograph"):
            editora = m.get("publisher")
            corpo = f"{titulo}{': ' + sub if sub else ''}. {editora}, {ano}."
        else:
            corpo = f"{titulo}. {veiculo + ', ' if veiculo else ''}{ano}."
        abnt = f"{_autores_abnt(autores).rstrip('.')}. {corpo} DOI: {doi}. Disponível em: https://doi.org/{doi}. Acesso em: {biblio.data_acesso()}."
        primeiro = (m.get("author") or [{}])[0].get("family", "")
        citacao = f"{primeiro.upper()}{' et al.' if len(autores) > 2 else ''}, {ano}"
        return {"abnt": re.sub(r"\s+", " ", abnt).replace(" .", "."), "citacao": citacao, "titulo": titulo, "ano": ano,
                "verificado": True}
    w = web.obter(f"{OPENALEX}/works/https://doi.org/{doi}", params=EMAIL, json=True)
    autores = [a["author"]["display_name"] for a in w.get("authorships", [])]
    veic = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
    abnt = (f"{_autores_abnt(autores).rstrip('.')}. {w.get('title')}. {veic + ', ' if veic else ''}{w.get('publication_year')}. "
            f"DOI: {doi}. Disponível em: https://doi.org/{doi}. Acesso em: {biblio.data_acesso()}.")
    return {"abnt": abnt, "citacao": f"{_autor_abnt(autores[0]).split(',')[0] if autores else 'AUTOR'}, "
                                      f"{w.get('publication_year')}", "titulo": w.get("title"),
            "ano": w.get("publication_year"), "verificado": False}


def baixar_pdf(url: str, nome: str):
    from ferramentas.ingestao import pdf as pdf_ext
    DIR.mkdir(parents=True, exist_ok=True)
    destino = DIR / f"{nome}.pdf"
    dados = None
    for u in dict.fromkeys([url.replace("http://", "https://"), url]):
        try:
            dados = web.obter(u, binario=True, cache_horas=24 * 365, timeout=180)
            break
        except Exception as e:
            print(f"  falha ao baixar {u}: {e.__class__.__name__}")
    if dados is None:
        print("  baixe manualmente pelo DOI e salve em referencias/literatura/")
        return None
    if not dados[:5] == b"%PDF-":
        print("  o link de acesso aberto não devolveu um PDF (pode ser página do periódico): " + url)
        return None
    destino.write_bytes(dados)
    r = pdf_ext.extrair(destino, DIR)
    print(f"  PDF: {destino}\n  texto: {r['md']}")
    return destino


def registrar_doi(doi, projeto_chave=None, baixar=False, pdf_url=None):
    r = abnt_doi(doi)
    chave = biblio.chave_sugerida("doi", doi)
    biblio.registrar(chave, r["abnt"], "artigo", f"https://doi.org/{doi}", r["citacao"], r["verificado"],
                     projeto_chave, titulo=r["titulo"])
    print(("" if r["verificado"] else "[CONFERIR] ") + r["abnt"])
    print(f"Citação no texto: ({r['citacao']})")
    if baixar:
        if not pdf_url:
            w = web.obter(f"{OPENALEX}/works/https://doi.org/{doi}", params=EMAIL, json=True)
            pdf_url = (w.get("open_access") or {}).get("oa_url")
        if pdf_url:
            baixar_pdf(pdf_url, chave)
        else:
            print("  sem versão de acesso aberto.")
    return chave


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="acao", required=True)
    b = sub.add_parser("buscar"); b.add_argument("termo"); b.add_argument("-n", type=int, default=10)
    b.add_argument("--desde", type=int); b.add_argument("--brasil", action="store_true")
    b.add_argument("--aberto", action="store_true"); b.add_argument("--tipo")
    b.add_argument("--sem-resumo", action="store_true")
    d = sub.add_parser("doi"); d.add_argument("doi"); d.add_argument("--projeto"); d.add_argument("--baixar", action="store_true")
    u = sub.add_parser("usar"); u.add_argument("projeto"); u.add_argument("id"); u.add_argument("--baixar", action="store_true")
    a = ap.parse_args()
    if a.acao == "buscar":
        for i, r in enumerate(buscar(a.termo, a.n, a.desde, a.brasil, a.aberto, a.tipo), 1):
            print(f"\n[{i}] {r['titulo']} ({r['ano']}) – {r['tipo']}")
            print(f"    {', '.join(r['autores'][:4])}{' et al.' if len(r['autores']) > 4 else ''} | {r['veiculo'] or '-'}")
            print(f"    citações: {r['citacoes']} | acesso aberto: {'sim' if r['aberto'] else 'não'} | DOI: {r['doi'] or '-'} | id: {r['id']}")
            if r["resumo"] and not a.sem_resumo:
                print(f"    Resumo: {r['resumo'][:600]}{'…' if len(r['resumo']) > 600 else ''}")
    elif a.acao == "doi":
        registrar_doi(a.doi, a.projeto, a.baixar)
    else:
        w = web.obter(f"{OPENALEX}/works/{a.id}", params=EMAIL, json=True)
        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        if not doi:
            raise SystemExit("Obra sem DOI: registrar manualmente com biblio.")
        registrar_doi(doi, a.projeto, a.baixar, (w.get("open_access") or {}).get("oa_url"))


if __name__ == "__main__":
    main()
