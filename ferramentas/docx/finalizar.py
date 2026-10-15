"""Usa o Microsoft Word instalado para atualizar sumário/listas/numeração e gerar PDF de conferência.

Uso:
    python -m ferramentas.docx.finalizar ARQUIVO.docx [--sem-pdf] [--png]
    python -m ferramentas.docx.finalizar candoi          # pega o .docx mais recente de projetos/candoi/saida

--png  gera também imagens das páginas (saida/preview/) para conferência visual pela IA.
Requer Windows + Word + pywin32. Sem Word, o documento continua válido: os campos são
atualizados ao abrir (o Word pergunta "Atualizar campos?").
"""
import argparse
from pathlib import Path

from ferramentas.util import console_utf8, PROJETOS_DIR

WD_FORMAT_PDF = 17


def resolver_arquivo(alvo: str) -> Path:
    p = Path(alvo)
    if p.suffix.lower() == ".docx":
        return p.resolve()
    docs = sorted((PROJETOS_DIR / alvo / "saida").glob("*.docx"), key=lambda f: f.stat().st_mtime)
    docs = [d for d in docs if not d.name.startswith("~$")]
    if not docs:
        raise SystemExit(f"Nenhum .docx em projetos/{alvo}/saida")
    return docs[-1].resolve()


def finalizar(docx_path: Path, pdf=True) -> Path | None:
    import win32com.client
    import pythoncom
    pythoncom.CoInitialize()
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    pdf_path = None
    try:
        doc = word.Documents.Open(str(docx_path), ConfirmConversions=False, ReadOnly=False, AddToRecentFiles=False)
        doc.Fields.Update()
        for i in range(1, doc.TablesOfContents.Count + 1):
            doc.TablesOfContents(i).Update()
        for i in range(1, doc.TablesOfFigures.Count + 1):
            doc.TablesOfFigures(i).Update()
        doc.Fields.Update()  # 2ª passada: números de página após o sumário crescer
        doc.Save()
        if pdf:
            pdf_path = docx_path.with_suffix(".pdf")
            doc.ExportAsFixedFormat(str(pdf_path), WD_FORMAT_PDF)
        paginas = doc.ComputeStatistics(2)  # wdStatisticPages
        doc.Close(False)
        print(f"Atualizado: {docx_path} ({paginas} páginas)")
    finally:
        try:
            word.Quit()
        except Exception:  # Word 2007: a instância já encerrou ao fechar o último documento (RPC/atributo)
            pass
    return pdf_path


def png_paginas(pdf_path: Path, dpi=60) -> Path:
    import pymupdf
    destino = pdf_path.parent / "preview"
    destino.mkdir(exist_ok=True)
    for f in destino.glob("*.png"):
        f.unlink()
    doc = pymupdf.open(pdf_path)
    for i, pag in enumerate(doc, start=1):
        pag.get_pixmap(dpi=dpi).save(destino / f"pag_{i:03d}.png")
    return destino


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("alvo", help=".docx ou chave do projeto")
    ap.add_argument("--sem-pdf", action="store_true")
    ap.add_argument("--png", action="store_true")
    a = ap.parse_args()
    arq = resolver_arquivo(a.alvo)
    pdf = finalizar(arq, pdf=not a.sem_pdf)
    if pdf:
        print(f"PDF: {pdf}")
        if a.png:
            print(f"Páginas: {png_paginas(pdf)}")


if __name__ == "__main__":
    main()
