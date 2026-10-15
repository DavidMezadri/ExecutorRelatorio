"""Catálogo de referências (ABNT NBR 6023:2018) usado por todos os garimpeiros e pelo montador.

Uso:
    python -m ferramentas.garimpo.biblio listar [--projeto candoi] [--tipo lei]
    python -m ferramentas.garimpo.biblio abnt --projeto candoi      # lista ABNT ordenada, pronta para Referências
    python -m ferramentas.garimpo.biblio usar candoi CHAVE [CHAVE...]  # associa referências ao projeto
    python -m ferramentas.garimpo.biblio remover candoi CHAVE

Catálogo geral: referencias/bibliografia.yaml (chave -> {tipo, abnt, url, acesso, citacao, verificado, ...})
Por projeto:    projetos/<chave>/referencias.yaml (lista de chaves usadas no documento)
No texto, a linha `!referencias` (em texto/*_referencias.md) é expandida pelo montador com:
    referências do projeto + citações das bases oficiais (dados/oficiais/FONTES.yaml), em ordem alfabética.
"""
import argparse
import datetime as dt
import unicodedata

import yaml

from ferramentas.util import console_utf8, projeto, slug, RAIZ

CATALOGO = RAIZ / "referencias" / "bibliografia.yaml"
MESES = ["jan.", "fev.", "mar.", "abr.", "maio", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez."]


def data_acesso(d: dt.date | None = None) -> str:
    d = d or dt.date.today()
    return f"{d.day} {MESES[d.month - 1]} {d.year}"


def _ler(caminho):
    if not caminho.exists():
        return {}
    return yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}


def catalogo() -> dict:
    return _ler(CATALOGO)


def registrar(chave: str, abnt: str, tipo: str, url: str | None = None, citacao: str | None = None,
              verificado=True, projeto_chave: str | None = None, **extra) -> str:
    """Grava/atualiza a referência no catálogo e, se informado, associa ao projeto. Retorna a chave."""
    cat = catalogo()
    cat[chave] = {"tipo": tipo, "abnt": abnt.strip(), "url": url, "acesso": str(dt.date.today()),
                  "citacao": citacao, "verificado": verificado, **{k: v for k, v in extra.items() if v is not None}}
    CATALOGO.parent.mkdir(parents=True, exist_ok=True)
    CATALOGO.write_text(yaml.safe_dump(dict(sorted(cat.items())), allow_unicode=True, sort_keys=False, width=200),
                        encoding="utf-8")
    if projeto_chave:
        usar(projeto_chave, [chave])
    return chave


def usar(projeto_chave: str, chaves: list[str]):
    arq = projeto(projeto_chave)["dir"] / "referencias.yaml"
    atuais = _ler(arq) or []
    for c in chaves:
        if c not in atuais:
            atuais.append(c)
    arq.write_text(yaml.safe_dump(atuais, allow_unicode=True), encoding="utf-8")


def _ordem(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()


def lista_abnt(projeto_chave: str) -> list[str]:
    """Referências do projeto + bases oficiais, sem duplicatas, em ordem alfabética."""
    return lista_abnt_dir(projeto(projeto_chave)["dir"])


BASE = RAIZ / "modelos" / "referencias_base.yaml"
NORMAS_POR_DOC = {  # normas do catálogo de legislação buscadas no Planalto ao criar o esqueleto
    "mce_saa": ["lei-12651-2012", "lei-11428-2006", "lei-9433-1997"],
    "mce_ses": ["lei-12651-2012", "lei-11428-2006", "lei-9433-1997"],
    "pca_saa": ["lei-12651-2012", "lei-11428-2006", "lei-9433-1997", "lei-12305-2010", "lei-6496-1977"],
    "pca_ses": ["lei-12651-2012", "lei-11428-2006", "lei-9433-1997", "lei-12305-2010", "lei-6496-1977"],
}


def semear(projeto_chave: str, doc: str, online=True) -> list[str]:
    """Registra as referências base do tipo de documento no catálogo e no projeto. Retorna as chaves."""
    base = (yaml.safe_load(BASE.read_text(encoding="utf-8")) or {}).get("referencias", {})
    cat = catalogo()
    chaves = []
    for k, r in base.items():
        if doc not in r.get("docs", []):
            continue
        if k not in cat:
            registrar(k, r["abnt"], "base", None, r.get("citacao"), r.get("verificado", False))
        chaves.append(k)
    if online:
        from ferramentas.garimpo import legislacao
        for n in NORMAS_POR_DOC.get(doc, []):
            try:
                legislacao.buscar(n)
                chaves.append(f"norma-{n}")
            except Exception as e:
                print(f"  (norma {n} não obtida: {e.__class__.__name__})")
    usar(projeto_chave, chaves)
    return chaves


def lista_abnt_dir(d, detalhada=False):
    """Lista ABNT ordenada. detalhada=True -> [(abnt, verificado)]."""
    cat = catalogo()
    refs = {cat[c]["abnt"]: cat[c].get("verificado", True) for c in (_ler(d / "referencias.yaml") or []) if c in cat}
    fontes = _ler(d / "dados" / "oficiais" / "FONTES.yaml")
    for f in fontes.values():
        if isinstance(f, dict) and f.get("citacao"):
            refs.setdefault(f["citacao"], True)
    ordem = sorted(refs, key=_ordem)
    return [(r, refs[r]) for r in ordem] if detalhada else ordem


def chave_sugerida(*partes) -> str:
    return slug("-".join(str(p) for p in partes if p))[:80]


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="acao", required=True)
    l = sub.add_parser("listar"); l.add_argument("--projeto"); l.add_argument("--tipo")
    a = sub.add_parser("abnt"); a.add_argument("--projeto", required=True)
    u = sub.add_parser("usar"); u.add_argument("projeto"); u.add_argument("chaves", nargs="+")
    r = sub.add_parser("remover"); r.add_argument("projeto"); r.add_argument("chave")
    a_ = ap.parse_args()
    if a_.acao == "listar":
        cat = catalogo()
        chaves = cat.keys()
        if a_.projeto:
            chaves = _ler(projeto(a_.projeto)["dir"] / "referencias.yaml") or []
        for c in chaves:
            e = cat.get(c, {})
            if a_.tipo and e.get("tipo") != a_.tipo:
                continue
            flag = "" if e.get("verificado", True) else "  [CONFERIR]"
            print(f"{c}  ({e.get('tipo')}){flag}\n    {e.get('abnt')}\n    citação: {e.get('citacao')}")
    elif a_.acao == "abnt":
        for ref in lista_abnt(a_.projeto):
            print(ref + "\n")
    elif a_.acao == "usar":
        usar(a_.projeto, a_.chaves)
        print("ok")
    elif a_.acao == "remover":
        arq = projeto(a_.projeto)["dir"] / "referencias.yaml"
        atuais = [c for c in (_ler(arq) or []) if c != a_.chave]
        arq.write_text(yaml.safe_dump(atuais, allow_unicode=True), encoding="utf-8")
        print("ok")


if __name__ == "__main__":
    main()
