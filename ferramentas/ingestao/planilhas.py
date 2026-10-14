"""Leitura de planilhas (Lista de documentos, Matriz Anexo VI/VII) para Markdown e registros.

Uso:
    python -m ferramentas.ingestao.planilhas ARQUIVO.xlsx [-o pasta_saida]

O cabeçalho de cada aba é detectado pela primeira linha que começa com "Item".
Linhas de uma única célula antes do cabeçalho viram metadados; depois dele, títulos de grupo.
"""
import argparse
from pathlib import Path

import openpyxl

from ferramentas.util import console_utf8, slug


def _limpa(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def ler(xlsx: Path) -> dict:
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    abas = {}
    for ws in wb.worksheets:
        meta, itens, cab, grupo = {}, [], None, None
        for row in ws.iter_rows(values_only=True):
            vals = [_limpa(v) for v in row]
            preenchidas = [v for v in vals if v]
            if not preenchidas:
                continue
            if cab is None:
                if vals[0] and vals[0].lower().startswith("item"):
                    cab = [v or f"col{i}" for i, v in enumerate(vals)]
                elif len(preenchidas) == 2 and preenchidas[0].endswith(":"):
                    meta[preenchidas[0].rstrip(":")] = preenchidas[1]
                elif len(preenchidas) == 1:
                    meta.setdefault("titulo", preenchidas[0])
                continue
            if len(preenchidas) == 1 and vals[0]:
                grupo = vals[0]
                continue
            reg = {k: v for k, v in zip(cab, vals) if v is not None}
            reg["_grupo"] = grupo
            itens.append(reg)
        abas[ws.title] = {"meta": meta, "cabecalho": cab, "itens": itens}
    return abas


def para_markdown(nome: str, abas: dict) -> str:
    out = [f"# {nome}\n"]
    for aba, d in abas.items():
        out.append(f"\n## Aba: {aba}\n")
        for k, v in d["meta"].items():
            out.append(f"- **{k}:** {v}")
        grupo = object()
        for it in d["itens"]:
            if it["_grupo"] != grupo:
                grupo = it["_grupo"]
                if grupo:
                    out.append(f"\n### {grupo}\n")
            campos = [(k, v) for k, v in it.items() if k != "_grupo"]
            if not campos:
                continue
            out.append(f"- **{campos[0][1]}**")
            out += [f"  - {k}: {v}" for k, v in campos[1:]]
    return "\n".join(out) + "\n"


def extrair(xlsx: Path, saida: Path) -> Path:
    xlsx, saida = Path(xlsx), Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    md = saida / f"{slug(xlsx.stem)[:80]}.md"
    md.write_text(para_markdown(xlsx.name, ler(xlsx)), encoding="utf-8")
    return md


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xlsx", nargs="+")
    ap.add_argument("-o", "--saida", default="extraido")
    a = ap.parse_args()
    for x in a.xlsx:
        print(extrair(Path(x), Path(a.saida)))


if __name__ == "__main__":
    main()
