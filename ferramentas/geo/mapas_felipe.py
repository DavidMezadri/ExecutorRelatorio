"""Mapas do Felipe (QGIS) -> legenda, fonte e classes para o texto.

Uso:
    python -m ferramentas.geo.mapas_felipe <chave>

Os mapas do documento são feitos pelo Felipe e salvos em projetos/<chave>/mapas/ com o nome usado no texto
(solos.png, uso_solo.png, geologia.png... – qualquer extensão de imagem ou PDF). Este script:
  - lista os mapas que o texto pede e os que já chegaram;
  - lê a legenda e a caixa de fontes de cada mapa (texto do PDF exportado do QGIS ou OCR em português da imagem);
  - cria/atualiza dados/mapas_felipe.yaml com, por mapa: arquivo, legenda lida (legenda_ocr), fonte lida
    (fonte_ocr) e os campos a confirmar `classes` e `fonte`.
Depois a IA confere cada mapa (Read na imagem), preenche `classes` (como estão na legenda) e `fonte` e roda o
redator: com `classes` preenchidas, o texto passa a usar as classes do mapa do Felipe (e não as da base pública);
o montador usa `fonte` na figura. Campos já preenchidos nunca são sobrescritos.
"""
import argparse
import re

import yaml

from ferramentas.util import console_utf8, projeto

EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf")
# legendas que não são classes temáticas
IGNORAR = re.compile(r"^(legenda|convenç|unidade|adutora|captaç|eta\b|ete\b|limite|curso|rio|nascente|rodovia|via|"
                     r"localiza|projeç|datum|fuso|sistema de|escala|fonte|elabora|sanepar|biocerne|n$|\d)", re.I)


def esperados(dir_proj):
    """Nomes de mapas (mapas/<nome>.<ext>) usados nas figuras dos textos."""
    nomes = []
    for md in sorted((dir_proj / "texto").glob("*.md")):
        for m in re.finditer(r"\]\(mapas/([\w\-]+)\.\w+\)", md.read_text(encoding="utf-8")):
            if m.group(1) not in nomes:
                nomes.append(m.group(1))
    return nomes


def arquivo(dir_proj, nome):
    for ext in EXT:
        for p in (dir_proj / "mapas").glob(f"{nome}{ext}"):
            return p
    return None


def ler_texto(arq):
    """Linhas de texto do mapa: camada de texto do PDF (QGIS) ou OCR da imagem."""
    import numpy as np
    from ferramentas.ingestao import pdf as pdf_ext
    if arq.suffix.lower() == ".pdf":
        import pymupdf
        doc = pymupdf.open(arq)
        txt = "\n".join(p.get_text() for p in doc)
        if len(txt.strip()) > 40:
            return [ln.strip() for ln in txt.splitlines() if ln.strip()]
        return [ln for p in doc for ln in pdf_ext.ocr_pagina(p, dpi=250).splitlines() if ln.strip()]
    from PIL import Image
    if pdf_ext._OCR is None:
        from rapidocr import RapidOCR
        pdf_ext._OCR = RapidOCR(params={"Rec.lang_type": "pt"})
    img = np.array(Image.open(arq).convert("RGB"))
    r = pdf_ext._OCR(img)
    return [t.strip() for t in (r.txts or []) if t.strip()]


def separar(linhas, unidades=None):
    """Legenda (entre 'LEGENDA' e a caixa de projeção/fontes) e texto da fonte."""
    leg, fonte, estado = [], [], None
    for ln in linhas:
        b = ln.lower()
        if b.startswith("legenda"):
            estado = "leg"
            continue
        if re.match(r"^(fontes?|base cartogr|dados)\b", b):
            estado = "fonte"
            resto = re.sub(r"^(fontes?)\s*:?\s*", "", ln, flags=re.I)
            if resto:
                fonte.append(resto)
            continue
        if re.match(r"^(projeç|datum|sistema de coord|elabora|escala)", b):
            estado = None if estado == "leg" else estado
            if estado != "fonte":
                continue
        if estado == "leg":
            leg.append(ln)
        elif estado == "fonte":
            if re.match(r"^(elabora|projeç|datum)", b):
                estado = None
            else:
                fonte.append(ln)
    fonte_txt = re.sub(r"(\s+\d{1,3}(\.\d{3})+)+\s*$", "", " ".join(fonte)).strip()  # coordenadas da grade
    classes = []
    com_sigla = sum(" - " in x for x in leg) >= 2  # legenda "SIGLA - Nome": linha sem " - " continua a anterior
    for x in leg:
        if IGNORAR.match(x) or len(x) <= 2 or any(u and (u.lower() in x.lower() or x.lower() in u.lower()) for u in unidades or []):
            continue
        if com_sigla and classes and " - " not in x and x[:1].isalpha():
            classes[-1] += " " + x
        else:
            classes.append(x)
    return leg, fonte_txt, classes


def gerar(chave):
    cfg = projeto(chave)
    d = cfg["dir"]
    arq_yaml = d / "dados" / "mapas_felipe.yaml"
    atual = (yaml.safe_load(arq_yaml.read_text(encoding="utf-8")) if arq_yaml.exists() else None) or {}
    ficha = yaml.safe_load((d / "projeto.yaml").read_text(encoding="utf-8")) or {}
    # nomes das unidades e partes deles ("Jangada do Sul - General Carneiro", "Adutora") não são classes
    unidades = {parte.strip() for u in ficha.get("unidades") or [] for parte in [u.get("nome", "")] + u.get("nome", "").split(" - ")}
    unidades |= {cfg.get("localidade") or "", cfg["municipio"]}
    rel = [f"# Mapas do Felipe – {cfg['municipio']}", "",
           "Mapas pedidos no texto e situação. Conferir a leitura (OCR) olhando o mapa; preencher `classes` e `fonte`",
           "em dados/mapas_felipe.yaml e rodar o redator + montar.", "",
           "| Mapa | Arquivo | Classes lidas na legenda | Fonte lida |", "|---|---|---|---|"]
    for nome in esperados(d):
        arq = arquivo(d, nome)
        e = atual.setdefault(nome, {"arquivo": None, "classes": None, "fonte": None})
        if not arq:
            e["arquivo"] = None
            for k in ("legenda_ocr", "fonte_ocr", "classes_sugeridas"):
                e.pop(k, None)
            rel.append(f"| {nome} | **falta** (salvar em mapas/{nome}.png) | – | – |")
            continue
        e["arquivo"] = f"mapas/{arq.name}"
        try:
            leg, fonte, classes = separar(ler_texto(arq), unidades)
        except Exception as ex:
            leg, fonte, classes = [f"(leitura falhou: {ex.__class__.__name__})"], "", []
        e["legenda_ocr"] = leg
        e["fonte_ocr"] = fonte or None
        e["classes_sugeridas"] = classes
        rel.append(f"| {nome} | {e['arquivo']} | {'; '.join(classes) or '–'} | {fonte or '–'} |")
    arq_yaml.write_text("# classes/fonte: CONFIRMAR olhando o mapa (o OCR pode errar). Vazio = texto genérico.\n"
                        + yaml.safe_dump(atual, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (d / "dados" / "MAPAS_FELIPE.md").write_text("\n".join(rel) + "\n", encoding="utf-8")
    return rel


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    a = ap.parse_args()
    print("\n".join(gerar(a.chave)))
    print("\n-> dados/mapas_felipe.yaml (preencher classes/fonte) e dados/MAPAS_FELIPE.md")


if __name__ == "__main__":
    main()
