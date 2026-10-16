"""Legislação: texto oficial, ementa, referência ABNT e citação literal de artigos.

Uso:
    python -m ferramentas.garimpo.legislacao catalogo [--tema app]           # lista o catálogo (modelos/legislacao.yaml)
    python -m ferramentas.garimpo.legislacao buscar lei-12651-2012 [--projeto candoi]
        -> referencias/legislacao/<chave>.md (texto integral) + referência ABNT no catálogo bibliográfico
    python -m ferramentas.garimpo.legislacao artigo lei-12651-2012 4 [--inciso I] [--projeto candoi]
        -> texto literal do art. 4º (ou de um inciso), pronto para citação, com a referência
    python -m ferramentas.garimpo.legislacao procurar lei-12651-2012 "utilidade pública"
        -> trechos da norma que contêm o termo, com o artigo de cada um
    python -m ferramentas.garimpo.legislacao tema app --projeto candoi        # busca todas as normas do tema
    python -m ferramentas.garimpo.legislacao adicionar CHAVE URL --jurisdicao BRASIL [--orgao "..."] [--temas a,b]

A ementa, o tipo, o número e a data são lidos da página oficial (Planalto, DOU, legislacao.pr.gov.br...).
Se não for possível ler a página, a referência é marcada [CONFERIR] no catálogo.
"""
import argparse
import re

import yaml

from ferramentas.util import console_utf8, RAIZ
from ferramentas.garimpo import biblio, web

CAT = RAIZ / "modelos" / "legislacao.yaml"
DIR = RAIZ / "referencias" / "legislacao"
RX_TIT = re.compile(r"((?:LEI COMPLEMENTAR|LEI|DECRETO-LEI|DECRETO|RESOLUÇÃO|PORTARIA|INSTRUÇÃO NORMATIVA|MEDIDA PROVISÓRIA)"
                    r"[A-Za-zÀ-ú\s/.-]{0,30}?N[ºo°.]*\s*[\d.]+(?:/\d+)?,?\s*DE\s+\d{1,2}[ºo]?\s+DE\s+[A-ZÇÃ]+\s+DE\s+\d{4})",
                    re.I)
MESES_EXT = {m: i for i, m in enumerate(["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                                         "setembro", "outubro", "novembro", "dezembro"])}


def catalogo() -> dict:
    return (yaml.safe_load(CAT.read_text(encoding="utf-8")) or {}).get("normas", {})


def _titulo_formatado(t: str) -> str:
    """'LEI Nº 12.651, DE 25 DE MAIO DE 2012' -> 'Lei nº 12.651, de 25 de maio de 2012'."""
    t = re.sub(r"\s+", " ", t.strip().rstrip("."))
    tipo, resto = re.split(r"\s+N[ºo°.]*\s*", t, maxsplit=1, flags=re.I) if re.search(r"\sN[ºo°.]", t, re.I) else (t, "")
    tipo = tipo.capitalize().replace("complementar", "Complementar") if tipo.isupper() else tipo
    resto = re.sub(r"\bDE\b", "de", resto)
    resto = re.sub(r"de ([A-ZÇÃ]+) de", lambda m: f"de {m.group(1).lower()} de", resto)
    resto = re.sub(r"(\d)[ºo] de", r"\1º de", resto)
    return f"{tipo} nº {resto}".replace(" ,", ",")


def ler_norma(chave: str, info: dict) -> dict:
    html = web.obter(info["url"], cache_horas=24 * 30)
    texto = web.html_texto(html, remover_riscado=True)
    m = RX_TIT.search(texto[:6000])
    titulo = _titulo_formatado(m.group(1)) if m else None
    ementa = None
    if m:
        # ementa = bloco entre o título e a fórmula de promulgação, sem as notas do Planalto
        bloco = re.split(r"\b(?:O|A) (?:PRESIDENTE|PRESIDENTA|VICE-PRESIDENTE|GOVERNADOR|GOVERNADORA|MINISTRO|MINISTRA|"
                         r"CONSELHO|ASSEMBLEIA|DIRETOR|DIRETORA|SECRET[ÁA]RI[OA])\b|\bO CONGRESSO NACIONAL\b",
                         texto[m.end():m.end() + 4000], maxsplit=1)[0]
        bloco = re.sub(r"\((?:Vide|Redação dada|Incluído|Regulamento|Revogado|Produção)[^)]*\)", "", bloco)
        linhas = [ln.strip() for ln in bloco.split("\n\n")]
        ruido = re.compile(r"^\(?(Texto compilado|Mensagem de veto|Vide|Regulamento|Conversão|Produção de efeito|"
                           r"Vigência|Promulgação|Convertid|Partes? mantid|Republicad|Publicad)", re.I)
        linhas = [ln for ln in linhas if ln and not ruido.match(ln)]
        if linhas:
            ementa = re.sub(r"\s+", " ", " ".join(linhas)).strip()
            # a ementa começa no primeiro verbo típico (descarta notas do Planalto grudadas antes dela)
            v = re.search(r"\b(Dispõe|Institui|Estabelece|Regulamenta|Altera|Atualiza|Fixa|Define|Aprova|Cria|Determina|"
                          r"Autoriza|Acrescenta|Revoga|Organiza|Declara|Torna|Introduz|Modifica|Disciplina|Proíbe|"
                          r"Consolida|Reconhece|Homologa)\b", ementa)
            if v:
                ementa = ementa[v.start():]
            ementa = re.sub(r'"\s*([^"]*?)\s*"', r'"\1"', ementa)
            ementa = re.sub(r"\((?:Vide|Redação dada|Incluído|Revogado)[^)]*\)", "", ementa)
            ementa = re.sub(r"\bn\s+[ºo](s?)\b", r"nº\1", ementa)  # "n o 6.938" (sobrescrito perdido) -> "nº 6.938"
            ementa = re.sub(r"(§\s*\d+)o\b", r"\1º", ementa)
            ementa = ementa.strip(" .;") or None
    return {"titulo": titulo, "ementa": ementa, "texto": texto, "ano": re.search(r"(\d{4})$", titulo).group(1) if titulo else None}


def abnt_norma(info: dict, lida: dict) -> tuple[str, bool]:
    jur = info.get("jurisdicao", "BRASIL").upper()
    orgao = f" {info['orgao']}." if info.get("orgao") else ""
    titulo = lida.get("titulo") or info["titulo"]
    ementa = lida.get("ementa")
    local = {"BRASIL": "Brasília, DF: Presidência da República", "PARANÁ": "Curitiba: Casa Civil"}.get(jur, "")
    if info.get("orgao"):
        local = "Brasília, DF" if jur == "BRASIL" else "Curitiba"
    ano = lida.get("ano") or ""
    ok = bool(lida.get("titulo") and ementa)
    abnt = (f"{jur}.{orgao} {titulo}. " + (f"{ementa.rstrip('.')}. " if ementa else "")
            + f"{local}, [{ano}]. Disponível em: {info['url']}. Acesso em: {biblio.data_acesso()}.")
    return re.sub(r"\s+", " ", abnt), ok


def buscar(chave: str, projeto_chave=None) -> dict:
    info = catalogo().get(chave)
    if not info:
        raise SystemExit(f"'{chave}' não está em {CAT}. Use 'adicionar'.")
    try:
        lida = ler_norma(chave, info)
    except Exception as e:
        print(f"  não foi possível ler {info['url']}: {e.__class__.__name__}")
        lida = {}
    abnt, ok = abnt_norma(info, lida)
    citacao = f"{info.get('jurisdicao', 'BRASIL').upper()}, {lida.get('ano') or '[ano]'}"
    biblio.registrar(f"norma-{chave}", abnt, "lei", info["url"], citacao, verificado=ok, projeto_chave=projeto_chave,
                     titulo=lida.get("titulo") or info["titulo"])
    if lida.get("texto"):
        DIR.mkdir(parents=True, exist_ok=True)
        (DIR / f"{chave}.md").write_text(f"# {lida.get('titulo') or info['titulo']}\n\n> {abnt}\n\n{lida['texto']}\n",
                                        encoding="utf-8")
    return {"abnt": abnt, "citacao": citacao, "verificado": ok, **lida}


def _artigos(texto: str) -> dict:
    """{'4': 'Art. 4º Considera-se ...'} – texto vigente (ignora trechos riscados entre parênteses de redação)."""
    partes = re.split(r"\n\s*(?=Art\.\s*\d+\s*[ºo°-]?[A-Z]?\b)", "\n" + texto)
    arts = {}
    for p in partes:
        m = re.match(r"Art\.\s*(\d+)\s*[ºo°]?(-[A-Z])?", p.strip())
        if m:
            n = m.group(1) + (m.group(2) or "")
            arts.setdefault(n, re.sub(r"\n\s*\n", "\n", p.strip()))  # redação revogada já removida (riscado)
    return arts


def artigo(chave, numero, inciso=None, projeto_chave=None) -> str:
    r = buscar(chave, projeto_chave)
    arts = _artigos(r.get("texto", ""))
    txt = arts.get(str(numero))
    if not txt:
        return f"Artigo {numero} não localizado no texto obtido."
    if inciso:
        m = re.search(rf"(?m)^\s*{inciso}\s*[-–].*?(?=^\s*[IVXLC]+\s*[-–]|^\s*§|\Z)", txt, re.S)
        txt = m.group(0).strip() if m else f"Inciso {inciso} não localizado no art. {numero}."
    txt = re.sub(r"[ \t]+", " ", txt)
    return f"{txt}\n\nFonte: {r['citacao']}.\nReferência: {r['abnt']}"


def procurar(chave, termo, contexto=250):
    r = buscar(chave)
    texto = r.get("texto", "")
    arts = _artigos(texto)
    achados = []
    for n, t in arts.items():
        for m in re.finditer(re.escape(termo), t, re.I):
            a, b = max(0, m.start() - contexto), min(len(t), m.end() + contexto)
            trecho = re.sub(r"\s+", " ", t[a:b])
            achados.append(f"Art. {n}: …{trecho}…")
    return achados


def adicionar(chave, url, jurisdicao, orgao=None, temas=None, titulo=None):
    dados = yaml.safe_load(CAT.read_text(encoding="utf-8")) or {}
    dados.setdefault("normas", {})[chave] = {"titulo": titulo or chave, "jurisdicao": jurisdicao,
                                             "temas": temas or [], "url": url, **({"orgao": orgao} if orgao else {})}
    CAT.write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="acao", required=True)
    c = sub.add_parser("catalogo"); c.add_argument("--tema")
    b = sub.add_parser("buscar"); b.add_argument("chave"); b.add_argument("--projeto")
    a = sub.add_parser("artigo"); a.add_argument("chave"); a.add_argument("numero"); a.add_argument("--inciso")
    a.add_argument("--projeto")
    p = sub.add_parser("procurar"); p.add_argument("chave"); p.add_argument("termo")
    t = sub.add_parser("tema"); t.add_argument("tema"); t.add_argument("--projeto")
    d = sub.add_parser("adicionar"); d.add_argument("chave"); d.add_argument("url")
    d.add_argument("--jurisdicao", default="BRASIL"); d.add_argument("--orgao"); d.add_argument("--temas")
    d.add_argument("--titulo")
    x = ap.parse_args()
    if x.acao == "catalogo":
        for k, v in catalogo().items():
            if not x.tema or x.tema in v.get("temas", []):
                print(f"{k:22} {v['titulo']}  [{', '.join(v.get('temas', []))}]")
    elif x.acao == "buscar":
        r = buscar(x.chave, x.projeto)
        print(("" if r["verificado"] else "[CONFERIR] ") + r["abnt"])
        print(f"Citação no texto: ({r['citacao']})")
    elif x.acao == "artigo":
        print(artigo(x.chave, x.numero, x.inciso, x.projeto))
    elif x.acao == "procurar":
        for a_ in procurar(x.chave, x.termo) or ["nada encontrado"]:
            print("-", a_, "\n")
    elif x.acao == "tema":
        for k, v in catalogo().items():
            if x.tema in v.get("temas", []):
                r = buscar(k, x.projeto)
                print(("" if r["verificado"] else "[CONFERIR] ") + r["abnt"] + "\n")
    else:
        adicionar(x.chave, x.url, x.jurisdicao.upper(), x.orgao, x.temas.split(",") if x.temas else None, x.titulo)
        r = buscar(x.chave)
        print(("" if r["verificado"] else "[CONFERIR] ") + r["abnt"])


if __name__ == "__main__":
    main()
