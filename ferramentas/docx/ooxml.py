"""Blocos OOXML de baixo nível compartilhados (campos, quebras, seções)."""
import copy

from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def el(tag, **attrs):
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn(k), str(v))
    return e


def run_texto(texto, negrito=False, italico=False, destaque=None, tamanho=None, fonte=None):
    r = el("w:r")
    rpr = el("w:rPr")
    if fonte:
        rpr.append(el("w:rFonts", **{"w:ascii": fonte, "w:hAnsi": fonte, "w:cs": fonte, "w:eastAsia": fonte}))
    if negrito:
        rpr.append(el("w:b"))
        rpr.append(el("w:bCs"))
    if italico:
        rpr.append(el("w:i"))
    if destaque:
        rpr.append(el("w:highlight", **{"w:val": destaque}))
    if tamanho:
        rpr.append(el("w:sz", **{"w:val": int(tamanho * 2)}))
        rpr.append(el("w:szCs", **{"w:val": int(tamanho * 2)}))
    if len(rpr):
        r.append(rpr)
    t = el("w:t")
    t.text = texto
    t.set(qn("xml:space"), "preserve")
    r.append(t)
    return r


def campo(instr: str, resultado: str = "", negrito=False):
    """Campo complexo do Word (begin/instr/separate/resultado/end) como lista de runs."""
    runs = []
    for tipo in ("begin",):
        r = el("w:r")
        r.append(el("w:fldChar", **{"w:fldCharType": tipo}))
        runs.append(r)
    r = el("w:r")
    it = el("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instr} "
    r.append(it)
    runs.append(r)
    r = el("w:r")
    r.append(el("w:fldChar", **{"w:fldCharType": "separate"}))
    runs.append(r)
    runs.append(run_texto(resultado, negrito=negrito))
    r = el("w:r")
    r.append(el("w:fldChar", **{"w:fldCharType": "end"}))
    runs.append(r)
    return runs


def paragrafo(estilo=None, alinhamento=None, recuo_primeira=None, simples=False, manter_com_proximo=False):
    """Parágrafo vazio com pPr. simples=True -> espaçamento simples sem espaço depois (padrão figura/legenda)."""
    p = el("w:p")
    ppr = el("w:pPr")
    if estilo:
        ppr.append(el("w:pStyle", **{"w:val": estilo}))
    if manter_com_proximo:
        ppr.append(el("w:keepNext"))
    if simples:
        ppr.append(el("w:spacing", **{"w:after": 0, "w:line": 240, "w:lineRule": "auto"}))
    if recuo_primeira is not None:
        ppr.append(el("w:ind", **{"w:firstLine": recuo_primeira}))
    if alinhamento:
        ppr.append(el("w:jc", **{"w:val": alinhamento}))
    p.append(ppr)
    return p


def quebra_pagina():
    p = el("w:p")
    r = el("w:r")
    r.append(el("w:br", **{"w:type": "page"}))
    p.append(r)
    return p


def sectpr_orientado(base_sectpr, paisagem: bool, tipo="nextPage"):
    """Cópia de um sectPr com orientação ajustada (troca largura/altura)."""
    s = copy.deepcopy(base_sectpr)
    pg = s.find(qn("w:pgSz"))
    w, h = int(pg.get(qn("w:w"))), int(pg.get(qn("w:h")))
    if paisagem != (w > h):
        pg.set(qn("w:w"), str(h))
        pg.set(qn("w:h"), str(w))
    if paisagem:
        pg.set(qn("w:orient"), "landscape")
    elif pg.get(qn("w:orient")):
        del pg.attrib[qn("w:orient")]
    tp = s.find(qn("w:type"))
    if tp is None:
        tp = el("w:type")
        s.insert(0, tp)
    tp.set(qn("w:val"), tipo)
    return s
