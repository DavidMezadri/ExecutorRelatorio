"""Captura de páginas e documentos de sites oficiais (gov.br, Embrapa, IAT, IBGE, ANA...) com referência ABNT.

Uso:
    python -m ferramentas.garimpo.pagina URL [--projeto candoi] [--autor "EMBRAPA"] [--titulo "..."] [--ano 2021]

Salva o texto em referencias/web/<chave>.md (PDFs: texto extraído) e registra a referência:
    AUTOR. Título. Local: Editora, ano. Disponível em: URL. Acesso em: dd mmm. aaaa.
Autor/local são deduzidos do domínio (tabela ORGAOS); título e ano, da própria página. O que não puder ser
determinado vira [20--] / [s.l.] e a referência fica marcada [CONFERIR] para revisão.
Autores ("Autores:", "Autoria") e data ("Publicado em", "Atualizado em") são lidos do conteúdo da página.
"""
import argparse
import re
from urllib.parse import urlparse

from ferramentas.util import console_utf8, RAIZ
from ferramentas.garimpo import biblio, web

DIR = RAIZ / "referencias" / "web"
# domínio -> (autor ABNT, local: editora)
ORGAOS = {
    "embrapa.br": ("EMBRAPA – EMPRESA BRASILEIRA DE PESQUISA AGROPECUÁRIA", "Brasília, DF: Embrapa"),
    "iat.pr.gov.br": ("PARANÁ. Instituto Água e Terra", "Curitiba: IAT"),
    "aen.pr.gov.br": ("PARANÁ. Agência Estadual de Notícias", "Curitiba: AEN"),
    "sedest.pr.gov.br": ("PARANÁ. Secretaria do Desenvolvimento Sustentável", "Curitiba: SEDEST"),
    "pr.gov.br": ("PARANÁ", "Curitiba: Governo do Estado"),
    "ibge.gov.br": ("IBGE – INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA", "Rio de Janeiro: IBGE"),
    "ana.gov.br": ("ANA – AGÊNCIA NACIONAL DE ÁGUAS E SANEAMENTO BÁSICO", "Brasília, DF: ANA"),
    "snirh.gov.br": ("ANA – AGÊNCIA NACIONAL DE ÁGUAS E SANEAMENTO BÁSICO", "Brasília, DF: ANA"),
    "icmbio.gov.br": ("ICMBIO – INSTITUTO CHICO MENDES DE CONSERVAÇÃO DA BIODIVERSIDADE", "Brasília, DF: ICMBio"),
    "sgb.gov.br": ("SGB – SERVIÇO GEOLÓGICO DO BRASIL", "Brasília, DF: SGB"),
    "cprm.gov.br": ("SGB – SERVIÇO GEOLÓGICO DO BRASIL", "Brasília, DF: SGB"),
    "mma.gov.br": ("BRASIL. Ministério do Meio Ambiente e Mudança do Clima", "Brasília, DF: MMA"),
    "inmet.gov.br": ("INMET – INSTITUTO NACIONAL DE METEOROLOGIA", "Brasília, DF: INMET"),
    "iphan.gov.br": ("IPHAN – INSTITUTO DO PATRIMÔNIO HISTÓRICO E ARTÍSTICO NACIONAL", "Brasília, DF: IPHAN"),
    "sanepar.com.br": ("SANEPAR – COMPANHIA DE SANEAMENTO DO PARANÁ", "Curitiba: Sanepar"),
    "simepar.br": ("SIMEPAR – SISTEMA DE TECNOLOGIA E MONITORAMENTO AMBIENTAL DO PARANÁ", "Curitiba: Simepar"),
    "mapbiomas.org": ("PROJETO MAPBIOMAS", "[s.l.]: MapBiomas"),
    "gov.br": ("BRASIL", "Brasília, DF: Governo Federal"),
}


def orgao(url):
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for dom, val in ORGAOS.items():
        if host == dom or host.endswith("." + dom):
            return val
    return (None, "[s.l.]: [s.n.]")


RX_DATA = re.compile(r"(?i)(?:publicad[oa]|atualizad[oa]|migrado na íntegra|data de publicação|postado)\s*(?:em)?\s*:?\s*"
                     r"\n*\s*(\d{1,2}/\d{1,2}/(\d{4}))")
RX_NOME = re.compile(r"^[A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:d[aeo]s?|e|[A-ZÀ-Ú][a-zà-ú]+|[A-Z]\.)){1,6}$")
SITE = re.compile(r"(?i)portal|site|gov|embrapa|agência|instituto|governo|ibge|\bana\b|\biat\b|sanepar|ministério")


def conteudo_principal(html: str) -> str:
    """Só o miolo da página (<main>/<article>/#content), quando existir."""
    import lxml.html
    try:
        raiz = lxml.html.fromstring(html)
    except Exception:
        return html
    for xp in ("//main", "//article", "//*[@id='content' or @id='conteudo' or @id='main-content']",
               "//*[contains(@class,'journal-content-article')]"):
        nos = raiz.xpath(xp)
        if nos:
            maior = max(nos, key=lambda n: len(n.text_content()))
            if len(maior.text_content().strip()) > 300:
                return lxml.html.tostring(maior, encoding="unicode")
    return html


def autores_da_pagina(texto: str) -> list[str]:
    m = re.search(r"(?im)^\s*(Autores?|Autoria|Elaboração)\s*:?\s*$", texto)
    if not m:
        return []
    nomes = []
    for ln in texto[m.end():m.end() + 1500].split("\n"):
        ln = ln.strip()
        if not ln or ln.startswith("-"):
            continue
        if RX_NOME.match(ln):
            nomes.append(ln)
        elif nomes:
            break
    return nomes[:6]


def capturar(url, projeto_chave=None, autor=None, titulo=None, ano=None):
    bruto = web.obter(url, binario=True, cache_horas=24 * 30)
    eh_pdf = bruto[:5] == b"%PDF-"
    if eh_pdf:
        import pymupdf
        doc = pymupdf.open(stream=bruto, filetype="pdf")
        texto = "\n\n".join(p.get_text() for p in doc)
        meta = doc.metadata or {}
        titulo = titulo or (meta.get("title") or "").strip() or None
        ano = ano or (re.search(r"(\d{4})", meta.get("creationDate") or "") or [None, None])[1]
    else:
        html = web.decodificar(bruto)
        texto = web.html_texto(conteudo_principal(html))
        titulo = titulo or web.titulo_html(html)
        if not ano:
            m = re.search(r'(?:article:published_time|datePublished|dc\.date)["\'][^>]*content=["\'](\d{4})', html) or \
                re.search(r'"datePublished"\s*:\s*"(\d{4})', html)
            ano = m.group(1) if m else None
    if not ano:
        m = RX_DATA.search(texto)
        ano = m.group(2) if m else None
    aut, local = orgao(url)
    pessoas = [] if autor else autores_da_pagina(texto)
    if pessoas:
        from ferramentas.garimpo.literatura import _autores_abnt
        autor = _autores_abnt(pessoas).rstrip(".")
    autor = autor or aut
    if titulo:
        partes = re.split(r"\s+[|–-]\s+", titulo)
        while len(partes) > 1 and SITE.search(partes[-1]):  # tira " - Site X - Portal Y"
            partes.pop()
        titulo = " - ".join(partes).strip()
    ok = bool(autor and titulo and ano)
    ano_txt = str(ano) if ano else "[20--]"  # NBR 6023:2018: data provável entre colchetes (não usa s.d.)
    abnt = (f"{autor or '[AUTOR]'}. {titulo or '[Título]'}. {local}, {ano_txt}. Disponível em: {url}. "
            f"Acesso em: {biblio.data_acesso()}.")
    chave = biblio.chave_sugerida("web", urlparse(url).netloc.split(".")[-3 if urlparse(url).netloc.count('.') > 1 else 0],
                                  titulo or url)[:70]
    if pessoas:
        sobrenomes = [p.split(",")[0].strip() for p in autor.split(";")]
        citacao = (f"{sobrenomes[0]} et al., {ano_txt}" if len(pessoas) > 3 else f"{'; '.join(sobrenomes)}, {ano_txt}")
    else:
        citacao = f"{(autor or 'AUTOR').split('.')[0].split(' –')[0].strip()}, {ano_txt}"
    biblio.registrar(chave, abnt, "web", url, citacao, ok, projeto_chave, titulo=titulo)
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / f"{chave}.md").write_text(f"# {titulo or url}\n\n> {abnt}\n\n{texto}\n", encoding="utf-8")
    return {"abnt": abnt, "citacao": citacao, "verificado": ok, "arquivo": DIR / f"{chave}.md", "chave": chave}


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--projeto")
    ap.add_argument("--autor")
    ap.add_argument("--titulo")
    ap.add_argument("--ano")
    a = ap.parse_args()
    r = capturar(a.url, a.projeto, a.autor, a.titulo, a.ano)
    print(("" if r["verificado"] else "[CONFERIR] ") + r["abnt"])
    print(f"Citação no texto: ({r['citacao']})\nTexto: {r['arquivo']}\nChave: {r['chave']}")


if __name__ == "__main__":
    main()
