"""Junta páginas de um PDF em painéis (grade) para conferência visual rápida.

Uso:
    python -m ferramentas.docx.painel ARQUIVO.pdf [--por-painel 8] [--colunas 4] [--dpi 70]

Gera <pdf>_painel_01.png, _02.png ... ao lado do PDF.
"""
import argparse
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

from ferramentas.util import console_utf8


def paineis(pdf: Path, por_painel=8, colunas=4, dpi=70) -> list[Path]:
    doc = pymupdf.open(pdf)
    imgs = []
    for pag in doc:
        pix = pag.get_pixmap(dpi=dpi)
        imgs.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    saidas = []
    for k in range(0, len(imgs), por_painel):
        grupo = imgs[k:k + por_painel]
        cw = max(i.width for i in grupo)
        ch = max(i.height for i in grupo)
        linhas = (len(grupo) + colunas - 1) // colunas
        painel = Image.new("RGB", (colunas * (cw + 10) + 10, linhas * (ch + 30) + 10), "#888")
        d = ImageDraw.Draw(painel)
        for j, im in enumerate(grupo):
            x = 10 + (j % colunas) * (cw + 10)
            y = 10 + (j // colunas) * (ch + 30)
            d.text((x, y), f"p. {k + j + 1}", fill="white")
            painel.paste(im, (x, y + 18))
        out = pdf.with_name(f"{pdf.stem}_painel_{k // por_painel + 1:02d}.png")
        painel.save(out)
        saidas.append(out)
    return saidas


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--por-painel", type=int, default=8)
    ap.add_argument("--colunas", type=int, default=4)
    ap.add_argument("--dpi", type=int, default=70)
    a = ap.parse_args()
    for p in paineis(Path(a.pdf), a.por_painel, a.colunas, a.dpi):
        print(p)


if __name__ == "__main__":
    main()
