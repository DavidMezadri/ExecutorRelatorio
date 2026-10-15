"""Monta o .docx final a partir dos textos em Markdown do projeto + template.

Uso:
    python -m ferramentas.docx.montar candoi [--template modelos/template_mce.docx] [--sem-numeracao]

Lê projetos/<chave>/texto/*.md (ordem alfabética) e grava em projetos/<chave>/saida/.

Sintaxe suportada (resumo também no CLAUDE.md):
    # Título 1 / ## Título 2 / ### / ####      numerados automaticamente ("3.1 ..."); `{-}` no fim = sem número
    texto com **negrito**, *itálico*, [A VERIFICAR: ...] (marcado em amarelo)
    - item de lista
    {{municipio}}, {{eta.capacidade_nominal_ls|num:1}}   variáveis do projeto.yaml (null -> [A VERIFICAR])
    {{municipio_info.limitrofes|lista}}  -> "A, B e C";  {{sanepar.cnpj}} / {{biocerne.cnpj}} (dados_comuns/)
    @fig:id / @qua:id                                     referência cruzada -> "Figura 3" / "Quadro 2"
    ![Legenda](imagens/x.png){#fig:id fonte="Autor, 2026" largura=15}
    !quadro[Legenda](dados/coordenadas.xlsx){#qua:id colunas="unidade:Unidade,utm_e:E (m)" fonte="..."}
    !pdf[Legenda opcional](anexos/projeto.pdf){paginas=1-3 fonte="Sanepar, 2026"}
    ::: quadro {#qua:id fonte="Sanepar, 2026"} Legenda      (tabela Markdown dentro, fecha com :::)
    ::: paisagem                                           (conteúdo em página paisagem, fecha com :::)
    \\newpage
    !referencias                                          lista ABNT ordenada (catálogo do projeto + bases oficiais)
    <!-- comentários são ignorados -->
"""
import argparse
import datetime as dt
import hashlib
import re
from pathlib import Path

import docx
import yaml
from docx.oxml.ns import qn
from docx.shared import Cm
from docx.text.paragraph import Paragraph

from ferramentas.util import console_utf8, projeto, slug, RAIZ
from ferramentas.docx.ooxml import el, campo, paragrafo, quebra_pagina, run_texto, sectpr_orientado
from ferramentas.docx.template import MARCADOR

ANO = dt.date.today().year
FONTE_PADRAO = f"Autor, {ANO}."
COR_CABECALHO = "C5E0B3"
LARGURA_TEXTO_CM = {"retrato": 15.0, "paisagem": 23.0}
ALTURA_MAX_CM = {"retrato": 20.0, "paisagem": 13.0}

RE_ATTR = re.compile(r'#([\w:-]+)|(\w+)=("([^"]*)"|[^\s}]+)')
RE_FIG = re.compile(r"^!\[(.*?)\]\((.+?)\)\s*(\{.*\})?\s*$")
RE_DIR = re.compile(r"^!(quadro|pdf)\[(.*?)\]\((.+?)\)\s*(\{.*\})?\s*$")
RE_FENCE = re.compile(r"^:::\s*(\w+)\s*(\{.*?\})?\s*(.*)$")
RE_VAR = re.compile(r"\{\{\s*([\w.]+)\s*(?:\|\s*([\w]+)(?::(\w+))?)?\s*\}\}")
RE_INLINE = re.compile(r"(\*\*.+?\*\*|\*[^*\s][^*]*?\*|\[A VERIFICAR[^\]]*\])")
RE_REF = re.compile(r"@((?:fig|qua):[\w-]+)")


# ---------------------------------------------------------------- utilidades
def num_br(v, casas=2):
    s = f"{float(v):,.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def attrs(txt):
    out = {}
    if not txt:
        return out
    for m in RE_ATTR.finditer(txt):
        if m.group(1):
            out["id"] = m.group(1)
        else:
            out[m.group(2)] = m.group(4) if m.group(4) is not None else m.group(3)
    return out


def resolver(ficha, caminho):
    v = ficha
    for parte in caminho.split("."):
        if isinstance(v, list) and parte.isdigit() and int(parte) < len(v):
            v = v[int(parte)]
        elif isinstance(v, dict) and parte in v:
            v = v[parte]
        else:
            return None
    return v


def substituir_variaveis(texto, ficha):
    def troca(m):
        v = resolver(ficha, m.group(1))
        if v is None or v == "":
            return f"[A VERIFICAR: {m.group(1)}]"
        filtro, arg = m.group(2), m.group(3)
        if filtro == "num":
            try:
                return num_br(v, int(arg or 2))
            except (TypeError, ValueError):
                return str(v)
        if filtro == "lista" and isinstance(v, list):
            itens = [str(x) for x in v]
            return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]
        if filtro == "upper":
            return str(v).upper()
        if filtro == "lower":
            return str(v).lower()
        return str(v)
    return RE_VAR.sub(troca, texto)


# ---------------------------------------------------------------- parser
def parse(texto):
    """Markdown estendido -> lista de blocos (tuplas)."""
    texto = re.sub(r"<!--.*?-->", "", texto, flags=re.S)
    linhas = texto.splitlines()
    blocos, buf, pilha = [], [], []
    i = 0

    def flush():
        if buf:
            blocos.append(("par", " ".join(s.strip() for s in buf)))
            buf.clear()

    while i < len(linhas):
        ln = linhas[i]
        s = ln.strip()
        if not s:
            flush()
        elif s == "\\newpage":
            flush(); blocos.append(("pagina",))
        elif s == "!referencias":
            flush(); blocos.append(("referencias",))
        elif m := re.match(r"^(#{1,4})\s+(.*?)\s*(\{-\})?$", s):
            flush(); blocos.append(("titulo", len(m.group(1)), m.group(2), m.group(3) is None))
        elif m := RE_FIG.match(s):
            flush(); blocos.append(("figura", m.group(1), m.group(2), attrs(m.group(3))))
        elif m := RE_DIR.match(s):
            flush(); blocos.append((m.group(1), m.group(2), m.group(3), attrs(m.group(4))))
        elif s == ":::" and pilha:
            flush(); pilha.pop(); blocos.append(("paisagem_fim",))
        elif m := RE_FENCE.match(s):
            flush()
            tipo, at, leg = m.group(1), attrs(m.group(2)), m.group(3).strip()
            if tipo == "paisagem":
                pilha.append("paisagem"); blocos.append(("paisagem_ini",))
            elif tipo == "quadro":
                tab = []
                i += 1
                while i < len(linhas) and linhas[i].strip() != ":::":
                    tab.append(linhas[i]); i += 1
                blocos.append(("quadro_md", leg, tab, at))
            else:
                blocos.append(("aviso", f"bloco ::: {tipo} desconhecido"))
        elif s.startswith("|"):
            flush()
            tab = []
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                tab.append(linhas[i]); i += 1
            blocos.append(("quadro_md", "", tab, {"sem_legenda": "1"}))
            continue
        elif m := re.match(r"^[-*•]\s+(.*)$", s):
            flush(); blocos.append(("item", m.group(1)))
        elif m := re.match(r"^(\d+[.)]|[a-z][)])\s+(.*)$", s):
            flush(); blocos.append(("item_num", m.group(1), m.group(2)))
        else:
            buf.append(s)
        i += 1
    flush()
    return blocos


def tabela_md(linhas):
    rows = []
    for ln in linhas:
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cels = [c.strip() for c in s.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cels if c):
            continue
        rows.append(cels)
    return rows


# ---------------------------------------------------------------- montador
class Montador:
    def __init__(self, template: Path, base: Path, ficha: dict, numerar=True):
        self.doc = docx.Document(template)
        self.base = base
        self.ficha = ficha
        self.numerar = numerar
        self.cache = base / ".cache"
        body = self.doc.element.body
        self.ancora = next(p for p in body.iter(qn("w:p")) if MARCADOR in "".join(t.text or "" for t in p.iter(qn("w:t"))))
        self.sect_base = body.find(qn("w:sectPr"))
        self.estilo = {n: self._estilo_id(n) for n in
                       ("Heading 1", "Heading 2", "Heading 3", "Heading 4", "Caption", "List Bullet", "List Paragraph")}
        self.cont_tit = [0, 0, 0, 0]
        self.cont = {"Figura": 0, "Quadro": 0}
        self.refs = {}
        self.orientacao = "retrato"
        self.titulo_atual = ""
        self.pendencias = []
        self.avisos = []

    def _estilo_id(self, nome):
        try:
            return self.doc.styles[nome].style_id
        except KeyError:
            return None

    def add(self, e):
        self.ancora.addprevious(e)
        return e

    # --- texto
    def _runs(self, p, texto, tamanho=None):
        texto = RE_REF.sub(lambda m: self.refs.get(m.group(1), f"[REF? {m.group(1)}]"), texto)
        for parte in RE_INLINE.split(texto):
            if not parte:
                continue
            if parte.startswith("**") and parte.endswith("**"):
                p.append(run_texto(parte[2:-2], negrito=True, tamanho=tamanho))
            elif parte.startswith("[A VERIFICAR"):
                p.append(run_texto(parte, negrito=True, destaque="yellow", tamanho=tamanho))
                self.pendencias.append((self.titulo_atual, parte))
            elif parte.startswith("*") and parte.endswith("*") and len(parte) > 2:
                p.append(run_texto(parte[1:-1], italico=True, tamanho=tamanho))
            else:
                p.append(run_texto(parte, tamanho=tamanho))
            if "[REF?" in parte:
                self.avisos.append(f"referência não encontrada: {parte}")

    def titulo(self, nivel, texto, numerar):
        if numerar and self.numerar:
            self.cont_tit[nivel - 1] += 1
            for k in range(nivel, 4):
                self.cont_tit[k] = 0
            numero = ".".join(str(c) for c in self.cont_tit[:nivel])
            texto = f"{numero} {texto}"
        if nivel == 1:
            texto = texto.upper()
        self.titulo_atual = texto
        p = self.add(paragrafo(estilo=self.estilo[f"Heading {nivel}"]))
        self._runs(p, texto)

    def par(self, texto):
        p = self.add(paragrafo())
        self._runs(p, texto)

    def _item(self, marcador, texto):
        # Normal com recuo deslocado (o estilo "List Bullet" do modelo é negrito e sem marcador)
        p = self.add(paragrafo())
        tabs = el("w:tabs")
        tabs.append(el("w:tab", **{"w:val": "left", "w:pos": 1069}))
        p[0].append(tabs)  # ordem do schema: tabs antes de ind
        p[0].append(el("w:ind", **{"w:left": 1069, "w:hanging": 360}))
        p.append(run_texto(marcador))
        r = el("w:r"); r.append(el("w:tab")); p.append(r)
        self._runs(p, texto)

    def item(self, texto):
        self._item("–", texto)

    def item_num(self, rotulo, texto):
        self._item(rotulo, texto)

    # --- legendas
    def legenda(self, rotulo, texto):
        self.cont[rotulo] += 1
        p = self.add(paragrafo(estilo=self.estilo["Caption"], alinhamento="center", simples=True, manter_com_proximo=True))
        p.append(run_texto(f"{rotulo} "))
        for r in campo(f"SEQ {rotulo} \\* ARABIC", str(self.cont[rotulo])):
            p.append(r)
        texto = texto.strip()
        if texto and not texto.endswith((".", "!", "?")):
            texto += "."
        self._runs(p, f": {texto}")

    def fonte(self, texto):
        p = self.add(paragrafo(alinhamento="center", recuo_primeira=0, simples=True))
        p.append(run_texto("Fonte:", negrito=True, tamanho=10))
        self._runs(p, " " + (texto or FONTE_PADRAO).strip(), tamanho=10)
        self.add(paragrafo())

    # --- referências (catálogo do garimpo + bases oficiais), ABNT: alinhadas à esquerda, espaço simples
    def referencias(self):
        from ferramentas.garimpo.biblio import lista_abnt_dir
        refs = lista_abnt_dir(self.base, detalhada=True)
        if not refs:
            self.par("[A VERIFICAR: nenhuma referência no catálogo do projeto – usar ferramentas.garimpo]")
            return
        for abnt, verificado in refs:
            p = self.add(paragrafo(alinhamento="left", recuo_primeira=0, simples=True))
            self._runs(p, abnt if verificado else f"{abnt} [A VERIFICAR: conferir referência]")
            self.add(paragrafo(recuo_primeira=0, simples=True))

    # --- figuras
    def _imagem_otimizada(self, caminho: Path) -> Path:
        from PIL import Image, ImageOps
        if caminho.suffix.lower() not in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"):
            return caminho
        with Image.open(caminho) as im:
            grande = max(im.size) > 2400 or caminho.stat().st_size > 1_500_000
            exotico = caminho.suffix.lower() in (".tif", ".tiff", ".bmp", ".webp")
            if not (grande or exotico):
                return caminho
            self.cache.mkdir(exist_ok=True)
            h = hashlib.md5(f"{caminho}{caminho.stat().st_mtime}".encode()).hexdigest()[:10]
            destino = self.cache / f"{caminho.stem}_{h}.jpg"
            if not destino.exists():
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((2400, 2400))
                im.save(destino, "JPEG", quality=85, optimize=True)
            return destino

    def _inserir_imagem(self, caminho: Path, largura_cm=None, altura_max_cm=None):
        from PIL import Image
        caminho = self._imagem_otimizada(caminho)
        with Image.open(caminho) as im:
            w, h = im.size
        larg = min(float(largura_cm or LARGURA_TEXTO_CM[self.orientacao]), LARGURA_TEXTO_CM[self.orientacao])
        alt_max = float(altura_max_cm or ALTURA_MAX_CM[self.orientacao])
        if larg * h / w > alt_max:
            larg = alt_max * w / h
        p_el = self.add(paragrafo(alinhamento="center", recuo_primeira=0, simples=True, manter_com_proximo=True))
        Paragraph(p_el, self.doc._body).add_run().add_picture(str(caminho), width=Cm(larg))

    def figura(self, leg, caminho, at):
        arq = (self.base / caminho)
        if arq.exists():
            self._inserir_imagem(arq, at.get("largura"), at.get("altura"))
        else:
            p = self.add(paragrafo(alinhamento="center", recuo_primeira=0, manter_com_proximo=True))
            self._runs(p, f"[A VERIFICAR: imagem não encontrada – {caminho}]")
        self.legenda("Figura", leg)
        self.fonte(at.get("fonte"))

    def pdf(self, leg, caminho, at):
        import pymupdf
        arq = self.base / caminho
        if not arq.exists():
            p = self.add(paragrafo(alinhamento="center", recuo_primeira=0))
            self._runs(p, f"[A VERIFICAR: PDF não encontrado – {caminho}]")
            return
        doc = pymupdf.open(arq)
        pags = list(range(1, doc.page_count + 1))
        if at.get("paginas"):
            pags = []
            for faixa in at["paginas"].split(","):
                a, _, b = faixa.partition("-")
                pags += list(range(int(a), int(b or a) + 1))
        self.cache.mkdir(exist_ok=True)
        for k, n in enumerate(pags):
            png = self.cache / f"{slug(arq.stem)[:40]}_p{n}.png"
            if not png.exists():
                doc[n - 1].get_pixmap(dpi=int(at.get("dpi", 150))).save(png)
            if k:
                self.add(quebra_pagina())
            self._inserir_imagem(png, at.get("largura"), at.get("altura", 22 if self.orientacao == "retrato" else 15))
        if leg:
            self.legenda("Figura", leg)
            self.fonte(at.get("fonte"))

    # --- quadros
    def _tabela(self, linhas, larguras=None, tamanho=10):
        n = max(len(l) for l in linhas)
        linhas = [l + [""] * (n - len(l)) for l in linhas]
        if larguras:
            larguras = [float(x) for x in larguras.split(",")]
        else:
            # coluna não pode ficar mais estreita que sua maior "palavra" (números, coordenadas)
            pesos = []
            for j in range(n):
                cel = [str(l[j]) for l in linhas]
                maior_palavra = max((len(w) for c in cel for w in c.split()), default=1)
                pesos.append(max(4, maior_palavra, 0.55 * min(40, max(len(c) for c in cel))))
            larguras = pesos
        larguras = [p / sum(larguras) for p in larguras]
        tbl = el("w:tbl")
        tp = el("w:tblPr")
        tp.append(el("w:tblW", **{"w:w": 5000, "w:type": "pct"}))
        tp.append(el("w:jc", **{"w:val": "center"}))
        bd = el("w:tblBorders")
        for lado, sz in (("top", 12), ("left", 12), ("bottom", 12), ("right", 12), ("insideH", 6), ("insideV", 6)):
            bd.append(el(f"w:{lado}", **{"w:val": "single", "w:sz": sz, "w:space": 0, "w:color": "auto"}))
        tp.append(bd)
        tp.append(el("w:tblLayout", **{"w:type": "autofit"}))
        tbl.append(tp)
        grid = el("w:tblGrid")
        for f in larguras:
            grid.append(el("w:gridCol", **{"w:w": int(8494 * f)}))
        tbl.append(grid)
        for i, linha in enumerate(linhas):
            tr = el("w:tr")
            if i == 0:
                trp = el("w:trPr")
                trp.append(el("w:tblHeader"))
                tr.append(trp)
            for j, txt in enumerate(linha):
                tc = el("w:tc")
                tcp = el("w:tcPr")
                tcp.append(el("w:tcW", **{"w:w": int(5000 * larguras[j]), "w:type": "pct"}))
                if i == 0:
                    tcp.append(el("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": COR_CABECALHO}))
                mar = el("w:tcMar")
                for lado, v in (("top", 60), ("left", 100), ("bottom", 60), ("right", 100)):
                    mar.append(el(f"w:{lado}", **{"w:w": v, "w:type": "dxa"}))
                tcp.append(mar)
                tcp.append(el("w:vAlign", **{"w:val": "center"}))
                tc.append(tcp)
                txt = str(txt)
                numerico = bool(re.fullmatch(r"[-\d.,%/ °'\"NSEW]+", txt)) and any(ch.isdigit() for ch in txt)
                p = paragrafo(alinhamento="center" if i == 0 or numerico else "left", recuo_primeira=0, simples=True)
                if i == 0:
                    p.append(run_texto(txt, negrito=True, tamanho=tamanho, fonte="Calibri"))
                else:
                    for parte in RE_INLINE.split(txt):
                        if not parte:
                            continue
                        neg = parte.startswith("**") and parte.endswith("**")
                        pend = parte.startswith("[A VERIFICAR")
                        if pend:
                            self.pendencias.append((self.titulo_atual, parte))
                        p.append(run_texto(parte[2:-2] if neg else parte, negrito=neg or pend,
                                           destaque="yellow" if pend else None, tamanho=tamanho, fonte="Calibri"))
                tc.append(p)
                tr.append(tc)
            tbl.append(tr)
        return tbl

    def _quadro(self, leg, linhas, at):
        if not linhas:
            self.avisos.append(f"quadro vazio: {leg}")
            return
        sem_leg = at.get("sem_legenda")
        if not sem_leg:
            self.legenda("Quadro", leg)
        self.add(self._tabela(linhas, at.get("larguras"), float(at.get("tamanho", 10))))
        if not sem_leg:
            self.fonte(at.get("fonte"))
        else:
            self.add(paragrafo())

    def quadro_md(self, leg, linhas, at):
        self._quadro(leg, tabela_md(linhas), at)

    def quadro(self, leg, caminho, at):
        import pandas as pd
        arq = self.base / caminho
        if not arq.exists():
            self.par(f"[A VERIFICAR: tabela não encontrada – {caminho}]")
            return
        df = pd.read_csv(arq) if arq.suffix.lower() == ".csv" else pd.read_excel(arq, sheet_name=at.get("aba", 0))
        if at.get("filtro"):
            df = df.query(at["filtro"])
        if at.get("colunas"):
            mapa = dict((c.split(":", 1) + [c])[:2] for c in at["colunas"].split(","))
            mapa = {k.strip(): v.strip() for k, v in mapa.items()}
            df = df[list(mapa)].rename(columns=mapa)
        casas = int(at.get("casas", 2))
        linhas = [list(df.columns)]
        for r in df.itertuples(index=False):
            linhas.append(["" if pd.isna(v) else (num_br(v, casas) if isinstance(v, float) else str(v)) for v in r])
        self._quadro(leg, linhas, at)

    # --- seções
    def paisagem(self, ligar: bool):
        if ligar == (self.orientacao == "paisagem"):
            return
        # fecha a seção atual com a orientação corrente
        p = el("w:p")
        ppr = el("w:pPr")
        ppr.append(sectpr_orientado(self.sect_base, paisagem=not ligar))
        p.append(ppr)
        self.add(p)
        self.orientacao = "paisagem" if ligar else "retrato"

    # --- execução
    def pre_numerar(self, blocos):
        cont = {"fig": 0, "qua": 0}
        for b in blocos:
            tipo = b[0]
            at = b[-1] if isinstance(b[-1], dict) else {}
            if tipo == "figura" or (tipo == "pdf" and b[1]):
                cont["fig"] += 1
                if at.get("id"):
                    self.refs[at["id"]] = f"Figura {cont['fig']}"
            elif tipo in ("quadro", "quadro_md") and not at.get("sem_legenda"):
                cont["qua"] += 1
                if at.get("id"):
                    self.refs[at["id"]] = f"Quadro {cont['qua']}"

    def montar(self, blocos):
        self.pre_numerar(blocos)
        for b in blocos:
            tipo, args = b[0], b[1:]
            if tipo == "pagina":
                self.add(quebra_pagina())
            elif tipo == "paisagem_ini":
                self.paisagem(True)
            elif tipo == "paisagem_fim":
                self.paisagem(False)
            elif tipo == "aviso":
                self.avisos.append(args[0])
            else:
                getattr(self, tipo)(*args)
        if self.orientacao == "paisagem":
            self.paisagem(False)
        if self.sect_base.find(qn("w:type")) is None:
            self.sect_base.insert(0, el("w:type", **{"w:val": "nextPage"}))
        self.ancora.getparent().remove(self.ancora)

    def salvar(self, destino: Path):
        destino.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.doc.save(destino)
        except PermissionError:
            destino = destino.with_name(destino.stem + f"_{dt.datetime.now():%H%M%S}.docx")
            self.doc.save(destino)
        return destino


def carregar_ficha(dir_proj: Path) -> dict:
    f = dir_proj / "projeto.yaml"
    ficha = yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}
    for comum in sorted((RAIZ / "dados_comuns").glob("*.yaml")):
        ficha.setdefault(comum.stem, yaml.safe_load(comum.read_text(encoding="utf-8")))
    dossie = dir_proj / "dados" / "dossie.yaml"  # {{dossie.<bloco>.<campo>}} (ferramentas.dossie.gerar)
    if dossie.exists():
        ficha.setdefault("dossie", yaml.safe_load(dossie.read_text(encoding="utf-8")))
    ficha.setdefault("ano", ANO)
    ficha.setdefault("hoje", dt.date.today().strftime("%d/%m/%Y"))
    return ficha


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    ap.add_argument("--template", default=str(RAIZ / "modelos" / "template_mce.docx"))
    ap.add_argument("--sem-numeracao", action="store_true", help="não numera títulos automaticamente")
    a = ap.parse_args()

    cfg = projeto(a.chave)
    d = cfg["dir"]
    arquivos = sorted((d / "texto").glob("*.md"))
    if not arquivos:
        raise SystemExit(f"Nenhum texto em {d / 'texto'}. Rode: python -m ferramentas.docx.esqueleto {a.chave}")
    ficha = carregar_ficha(d)
    texto = "\n\n".join(f.read_text(encoding="utf-8") for f in arquivos)
    blocos = parse(substituir_variaveis(texto, ficha))

    m = Montador(Path(a.template), d, ficha, numerar=not a.sem_numeracao)
    m.montar(blocos)
    nome = f"{cfg['documento']}_{cfg['sistema']}_{slug(cfg['municipio']).replace('-', '_')}_{dt.date.today():%Y-%m-%d}.docx"
    saida = m.salvar(d / "saida" / nome)

    print(f"Documento: {saida}")
    print(f"  {m.cont['Figura']} figuras, {m.cont['Quadro']} quadros, {len(m.pendencias)} pendências [A VERIFICAR]")
    for av in m.avisos:
        print(f"  AVISO: {av}")
    rel = [f"# Pendências – {nome}\n"]
    secao = None
    for tit, txt in m.pendencias:
        if tit != secao:
            rel.append(f"\n## {tit or '(início)'}")
            secao = tit
        rel.append(f"- {txt}")
    (d / "saida" / "PENDENCIAS.md").write_text("\n".join(rel) + "\n", encoding="utf-8")
    print(f"  Lista de pendências: {d / 'saida' / 'PENDENCIAS.md'}")


if __name__ == "__main__":
    main()
