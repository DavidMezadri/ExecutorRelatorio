"""Cria o template limpo a partir de um documento-modelo (.docx) já formatado.

Uso:
    python -m ferramentas.docx.template MODELO.docx [-o modelos/template_mce.docx]

Mantém: estilos, cabeçalhos/rodapés (logos), margens, Sumário, Lista de Quadros e Lista de Figuras
(como campos a atualizar). Remove todo o conteúdo e as imagens do corpo. O corpo passa a ter o
marcador {{CONTEUDO}}, onde `montar` insere o texto.
"""
import argparse
import copy
from pathlib import Path

import docx
from docx.oxml.ns import qn
from lxml import etree

from ferramentas.util import console_utf8, RAIZ
from ferramentas.docx.ooxml import el, campo, paragrafo, quebra_pagina, run_texto

MARCADOR = "{{CONTEUDO}}"
AVISO_CAMPO = "Atualize os campos: Ctrl+A e F9 (ou clique com o botão direito > Atualizar campo)."


def _texto(e):
    return "".join(t.text or "" for t in e.iter(qn("w:t")))


def _paragrafo_lista(estilo_entrada, rotulo):
    p = paragrafo(estilo=estilo_entrada, recuo_primeira=0)
    for r in campo(f'TOC \\h \\z \\c "{rotulo}"', AVISO_CAMPO):
        p.append(r)
    return p


def padronizar_estilos(d):
    """Padrão Biocerne para sumário, listas e títulos (aplicado no template e a cada montagem).

    - Sumário (toc 1-9), Lista de Quadros e Lista de Figuras (table of figures): espaçamento 0 antes
      e depois, entrelinhas 1,5, fonte do texto; listas sem negrito e alinhadas à esquerda.
    - Títulos (Heading 1-9): sem recuo da primeira linha (o Normal tem recuo de 1,25 cm).
    """
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
    from docx.shared import Emu, Pt
    nomes = {s.name: s for s in d.styles if s.type == 1}
    for nome, st in nomes.items():
        n = nome.lower()
        pf = st.paragraph_format
        if (n.startswith("toc ") and n[4:].isdigit()) or n == "table of figures":
            pf.space_before = Pt(0)
            pf.space_after = Pt(0)
            pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
            st.font.size = None  # mesmo tamanho do texto (o modelo tinha níveis 2 e 3 em 10 pt)
            if n.startswith("toc "):
                # recuo à esquerda (não de 1ª linha, herdado do Normal): título longo quebra alinhado
                nivel = int(n[4:])
                pf.first_line_indent = 0
                pf.left_indent = Emu(0 if nivel == 1 else 450215 + (nivel - 2) * 152400)
            if n == "table of figures":
                st.font.bold = False
                pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
                pf.first_line_indent = 0
        elif n.startswith("heading ") and n[8:].isdigit():
            pf.first_line_indent = 0


def criar(modelo: Path, saida: Path):
    d = docx.Document(modelo)
    body = d.element.body
    filhos = list(body.iterchildren())

    sdt = next(e for e in filhos if e.tag == qn("w:sdt"))
    tit_quadros = next(e for e in filhos if e.tag == qn("w:p") and _texto(e).strip() == "LISTA DE QUADROS")
    tit_figuras = next(e for e in filhos if e.tag == qn("w:p") and _texto(e).strip() == "LISTA DE FIGURAS")
    # estilo das entradas das listas (Índice de ilustrações)
    estilo_lista = None
    for e in filhos:
        instr = "".join(i.text or "" for i in e.iter(qn("w:instrText")))
        ps = e.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
        if '\\c "' in instr and ps is not None:
            estilo_lista = ps.get(qn("w:val"))
            break

    # sectPr da 1ª seção (tem as referências de cabeçalho com os logos)
    sect_paras = [e for e in filhos if e.tag == qn("w:p") and e.find(f"{qn('w:pPr')}/{qn('w:sectPr')}") is not None]
    sect0 = copy.deepcopy(sect_paras[0].find(f"{qn('w:pPr')}/{qn('w:sectPr')}")) if sect_paras else None
    final = body.find(qn("w:sectPr"))
    if sect0 is not None:
        tp = sect0.find(qn("w:type"))
        if tp is not None:
            sect0.remove(tp)
        final = sect0

    # Sumário: mantém o título, troca as entradas por um único campo TOC
    conteudo = sdt.find(qn("w:sdtContent"))
    paras = list(conteudo)
    titulo_sumario = paras[0]
    estilo_sum1 = paras[1].find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
    for p in paras[1:]:
        conteudo.remove(p)
    p = paragrafo(estilo=estilo_sum1.get(qn("w:val")) if estilo_sum1 is not None else None)
    for r in campo('TOC \\o "1-3" \\h \\z \\u', AVISO_CAMPO):
        p.append(r)
    conteudo.append(p)
    assert titulo_sumario is conteudo[0]

    novos = [
        sdt,
        quebra_pagina(),
        copy.deepcopy(tit_quadros),
        _paragrafo_lista(estilo_lista, "Quadro"),
        quebra_pagina(),
        copy.deepcopy(tit_figuras),
        _paragrafo_lista(estilo_lista, "Figura"),
        quebra_pagina(),
    ]
    marcador = el("w:p")
    marcador.append(run_texto(MARCADOR))
    novos.append(marcador)

    for e in filhos:
        body.remove(e)
    for e in novos:
        body.append(e)
    body.append(final)

    # remove relações órfãs (imagens do conteúdo antigo) para o template ficar leve
    xml = etree.tostring(d.element).decode()
    part = d.part
    for rid, rel in list(part.rels.items()):
        if rel.reltype.endswith(("/image", "/hyperlink", "/chart", "/oleObject", "/package")) and f'"{rid}"' not in xml:
            part.drop_rel(rid)

    padronizar_estilos(d)

    # Word atualiza sumário/listas/numeração ao abrir
    settings = d.settings.element
    if settings.find(qn("w:updateFields")) is None:
        settings.append(el("w:updateFields", **{"w:val": "true"}))

    cp = d.core_properties
    cp.title, cp.subject, cp.author, cp.comments = "", "", "", ""
    saida.parent.mkdir(parents=True, exist_ok=True)
    d.save(saida)
    return saida


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modelo")
    ap.add_argument("-o", "--saida", default=str(RAIZ / "modelos" / "template_mce.docx"))
    a = ap.parse_args()
    s = criar(Path(a.modelo), Path(a.saida))
    print(f"Template: {s} ({s.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
