"""Converte um .docx em Markdown (títulos, parágrafos, legendas, tabelas) para a IA ler.

Uso:
    python -m ferramentas.ingestao.docx_texto ARQUIVO.docx [-o saida.md]

Imagens viram a linha "[IMAGEM]"; legendas e fontes são mantidas na posição original.
"""
import argparse
from pathlib import Path

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from ferramentas.util import console_utf8


def converter(caminho: Path) -> str:
    d = docx.Document(caminho)
    out = [f"<!-- extraído de {caminho.name} -->\n"]
    for el in d.element.body.iterchildren():
        if el.tag == qn("w:p"):
            p = Paragraph(el, d._body)
            txt = p.text.strip()
            estilo = p.style.name if p.style is not None else ""
            if el.findall(f".//{qn('w:drawing')}") or el.findall(".//{urn:schemas-microsoft-com:vml}imagedata"):
                out.append("[IMAGEM]\n")
            if not txt:
                continue
            if estilo.startswith("Heading"):
                nivel = int(estilo.split()[-1]) if estilo.split()[-1].isdigit() else 1
                out.append(f"\n{'#' * nivel} {txt}\n")
            elif estilo == "Caption":
                out.append(f"*{txt}*\n")
            elif estilo.startswith(("table of figures", "TOC")):
                continue
            else:
                out.append(txt + "\n")
        elif el.tag == qn("w:tbl"):
            t = Table(el, d._body)
            linhas = [[c.text.strip().replace("\n", " ") for c in r.cells] for r in t.rows]
            if not linhas:
                continue
            n = max(len(l) for l in linhas)
            out.append("| " + " | ".join(linhas[0]) + " |")
            out.append("|" + "---|" * n)
            out += ["| " + " | ".join(l) + " |" for l in linhas[1:]]
            out.append("")
        elif el.tag == qn("w:sdt"):
            continue
    return "\n".join(out)


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx")
    ap.add_argument("-o", "--saida")
    a = ap.parse_args()
    md = converter(Path(a.docx))
    if a.saida:
        Path(a.saida).parent.mkdir(parents=True, exist_ok=True)
        Path(a.saida).write_text(md, encoding="utf-8")
        print(a.saida)
    else:
        print(md)


if __name__ == "__main__":
    main()
