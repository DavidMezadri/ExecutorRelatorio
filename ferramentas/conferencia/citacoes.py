"""Confere citações no texto x lista de referências do projeto (ABNT).

Uso:
    python -m ferramentas.conferencia.citacoes candoi

Aponta:
  - citações (AUTOR, ano) no texto sem referência correspondente
  - referências da lista que não são citadas no texto (podem ser removidas com biblio remover)
  - referências marcadas como não conferidas
Gera saida/CITACOES.md.
"""
import argparse
import re
import unicodedata

from ferramentas.util import console_utf8, projeto
from ferramentas.docx.montar import carregar_ficha, substituir_variaveis
from ferramentas.garimpo import biblio

RX_PAR = re.compile(r"\(([^()]*?(?:\b\d{4}[a-z]?|\[\d{2}--\]))\)")
RX_CIT = re.compile(r"([A-ZÀ-Ú][A-ZÀ-Ú0-9 .&/–-]+?(?:\s+et al\.)?)(?:;\s*[A-ZÀ-Ú][A-ZÀ-Ú .]+?)*,\s*(\d{4}[a-z]?|\[\d{2}--\])")


def _norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"\bET AL\.?", "", s)
    return re.sub(r"[^A-Z0-9]", "", s.split("–")[0].split(" - ")[0])


def citacoes_texto(texto):
    achadas = []
    for m in RX_PAR.finditer(texto):
        for parte in m.group(1).split(";"):
            c = RX_CIT.search(parte.strip())
            if c:
                autores = [a.strip() for a in parte.split(",")[0].split(";")]
                achadas.append((parte.strip(), _norm(autores[0]), c.group(2)))
    return achadas


def chave_ref(abnt, citacao=None):
    """(autor normalizado, ano) de uma referência – usa a citação registrada quando houver."""
    if citacao:
        a, _, ano = citacao.rpartition(",")
        return _norm(a.split(";")[0]), ano.strip()
    autor = re.split(r"\.\s|\s–\s", abnt, maxsplit=1)[0]
    anos = re.findall(r"(\d{4}|\[\d{2}--\])\.\s*(?:Disponível|DOI|$|Tabela|\d+ p)", abnt) or re.findall(r",\s*(\d{4}|\[\d{2}--\])", abnt)
    return _norm(autor), (anos[0] if anos else "")


def conferir(cfg):
    d = cfg["dir"]
    ficha = carregar_ficha(d)
    texto = "\n".join(f.read_text(encoding="utf-8") for f in sorted((d / "texto").glob("*.md")))
    texto = re.sub(r"<!--.*?-->", "", substituir_variaveis(texto, ficha), flags=re.S)
    cits = citacoes_texto(texto)
    cat = biblio.catalogo()
    refs = []
    for c in (biblio._ler(d / "referencias.yaml") or []):
        if c in cat:
            refs.append((cat[c]["abnt"], chave_ref(cat[c]["abnt"], cat[c].get("citacao")), cat[c].get("verificado", True)))
    for f in (biblio._ler(d / "dados" / "oficiais" / "FONTES.yaml") or {}).values():
        if isinstance(f, dict) and f.get("citacao"):
            refs.append((f["citacao"], chave_ref(f["citacao"]), True))
    refs = list({abnt: (abnt, k, ok) for abnt, k, ok in refs}.values())  # sem duplicatas (ex.: BC250 em 2 camadas)
    autores_ref = {(a, ano) for _, (a, ano), _ in refs}
    sem_ref = sorted({c for c, a, ano in cits if not any(a.startswith(ar[:6]) or ar.startswith(a[:6]) for ar, an in autores_ref
                                                        if an == ano or ano.startswith(an) or an.startswith(ano))})
    citadas = {(a, ano) for _, a, ano in cits}
    nao_citadas = [abnt for abnt, (a, ano), _ in refs
                   if not any((a.startswith(ca[:6]) or ca.startswith(a[:6])) and (ano == cano or ano.startswith(cano) or cano.startswith(ano))
                              for ca, cano in citadas)]
    nao_conferidas = [abnt for abnt, _, ok in refs if not ok]
    return cits, sem_ref, nao_citadas, nao_conferidas


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    a = ap.parse_args()
    cfg = projeto(a.chave)
    cits, sem_ref, nao_citadas, nao_conf = conferir(cfg)
    out = [f"# Conferência de citações – {cfg['municipio']}\n", f"{len(cits)} citações no texto.\n",
           f"\n## Citações sem referência na lista ({len(sem_ref)})\n"] + [f"- ({c})" for c in sem_ref] + \
          [f"\n## Referências não citadas no texto ({len(nao_citadas)})\n"] + [f"- {r[:200]}" for r in nao_citadas] + \
          [f"\n## Referências ainda não conferidas ({len(nao_conf)})\n"] + [f"- {r[:200]}" for r in nao_conf]
    md = "\n".join(out) + "\n"
    (cfg["dir"] / "saida" / "CITACOES.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
