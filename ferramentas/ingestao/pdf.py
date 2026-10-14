"""Extração de texto, tabelas e imagens de PDF para Markdown (para a IA ler).

Uso:
    python -m ferramentas.ingestao.pdf ARQUIVO.pdf [-o pasta_saida] [--tabelas] [--imagens]

Gera <saida>/<nome>.md com o texto por página (marcador "## Página N").
Páginas com pouco texto são marcadas como [ESCANEADA? precisa OCR].
"""
import argparse
from pathlib import Path

import pymupdf

from ferramentas.util import console_utf8, slug

MIN_CHARS_PAGINA = 40


def _tabela_md(tabela) -> str:
    linhas = [[(c or "").replace("\n", " ").strip() for c in l] for l in tabela if l]
    if not linhas:
        return ""
    n = max(len(l) for l in linhas)
    linhas = [l + [""] * (n - len(l)) for l in linhas]
    out = ["| " + " | ".join(linhas[0]) + " |", "|" + "---|" * n]
    out += ["| " + " | ".join(l) + " |" for l in linhas[1:]]
    return "\n".join(out)


def extrair(pdf: Path, saida: Path, tabelas=False, imagens=False) -> dict:
    pdf, saida = Path(pdf), Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    base = slug(pdf.stem)[:80]
    doc = pymupdf.open(pdf)
    partes = [f"# {pdf.name}\n", f"Páginas: {doc.page_count}\n"]
    escaneadas = []

    plumb = None
    if tabelas:
        import pdfplumber
        plumb = pdfplumber.open(pdf)

    for i, pag in enumerate(doc, start=1):
        texto = pag.get_text("text").strip()
        partes.append(f"\n## Página {i}\n")
        if len(texto) < MIN_CHARS_PAGINA:
            escaneadas.append(i)
            partes.append("[ESCANEADA? precisa OCR]\n")
        partes.append(texto + "\n")
        if plumb is not None:
            for j, t in enumerate(plumb.pages[i - 1].extract_tables(), start=1):
                md = _tabela_md(t)
                if md:
                    partes.append(f"\n**Tabela {i}.{j}**\n\n{md}\n")
        if imagens:
            dir_img = saida / f"{base}_imagens"
            for k, info in enumerate(pag.get_images(full=True), start=1):
                pix = pymupdf.Pixmap(doc, info[0])
                if pix.width < 150 or pix.height < 150:
                    continue
                if pix.n - pix.alpha >= 4:
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                dir_img.mkdir(exist_ok=True)
                pix.save(dir_img / f"p{i:03d}_{k:02d}.png")

    md_path = saida / f"{base}.md"
    md_path.write_text("".join(partes), encoding="utf-8")
    return {"arquivo": str(pdf), "md": str(md_path), "paginas": doc.page_count, "escaneadas": escaneadas}


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", nargs="+")
    ap.add_argument("-o", "--saida", default="extraido")
    ap.add_argument("--tabelas", action="store_true")
    ap.add_argument("--imagens", action="store_true")
    a = ap.parse_args()
    for p in a.pdf:
        r = extrair(Path(p), Path(a.saida), a.tabelas, a.imagens)
        aviso = f"  páginas sem texto: {r['escaneadas']}" if r["escaneadas"] else ""
        print(f"{r['paginas']:>4} págs -> {r['md']}{aviso}")


if __name__ == "__main__":
    main()
