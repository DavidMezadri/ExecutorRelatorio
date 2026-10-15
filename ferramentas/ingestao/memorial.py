"""Extrator de dados técnicos de memoriais/projetos (texto já convertido em extraido/*.md).

Uso:
    python -m ferramentas.ingestao.memorial candoi                 # varre projetos/<chave>/extraido/*.md
    python -m ferramentas.ingestao.memorial candoi --aplicar       # preenche no projeto.yaml os campos vazios
                                                                   # com candidato ÚNICO (comentando a origem)
    python -m ferramentas.ingestao.memorial --arquivo memorial.md  # avulso

Procura vazões (L/s, m³/h, m³/dia), população e anos de plano, horizonte, per capita, K1/K2, portarias de outorga,
DN/DE, extensões, volumes, potências, Hm, processos de tratamento, eficiência de DBO, matrículas, cursos d'água e
classe. Gera dados/EXTRACAO_MEMORIAL.md com cada candidato, o trecho e a página de origem – a decisão final é humana.
"""
import argparse
import re
from collections import defaultdict
from pathlib import Path

import yaml

from ferramentas.util import console_utf8, projeto

NUM = r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)"
PADROES = {
    "vazao": (rf"{NUM}\s*(L/s|l/s|L/seg|m³/h|m3/h|m³/dia|m3/dia|m³/s|m3/s)\b", "Vazões"),
    "populacao": (rf"{NUM}\s*hab(?:itantes)?\b", "População"),
    "horizonte": (r"horizonte\s+(?:de\s+)?(?:projeto|plano|alcance)?[^.\n]{0,40}?(\d{1,2})\s*anos|((?:19|20)\d{2})\s*[–-]\s*((?:19|20)\d{2})", "Horizonte de projeto"),
    "per_capita": (rf"{NUM}\s*(?:L|l)\s*/\s*hab(?:itante)?\.?\s*(?:\.|x|/)?\s*dia", "Consumo per capita"),
    "coeficiente": (r"\b(K[12]|C\s*=|coeficiente de retorno)\s*=?\s*(\d+(?:,\d+)?)", "Coeficientes (K1, K2, C)"),
    "outorga": (r"Portaria\s*(?:IAT|ANA|IAP|AGUASPARAN[ÁA]|SUDERHSA)?\s*(?:n[ºo°.]*\s*)?(\d+[\d./-]*)", "Portarias (outorga)"),
    "diametro": (r"\b(DN|DE|Ø)\s?(\d{2,4})(?![\d.,])", "Diâmetros"),  # sensível a maiúsculas: "de" não é DE
    "extensao": (rf"{NUM}\s*(m|km)\b(?=[^.\n]{{0,30}}(?:extens|de rede|de adutora|de linha|de emiss|de interceptor))|extens[ãa]o\s+(?:total\s+)?(?:de\s+)?(?:aproximadamente\s+)?{NUM}\s*(m|km)\b", "Extensões"),
    "volume": (rf"{NUM}\s*(m³|m3)\b(?!\s*/)", "Volumes"),
    "potencia": (rf"{NUM}\s*(kW|CV|cv|HP)\b", "Potências"),
    "altura_manometrica": (rf"\bHm\s*=?\s*{NUM}\s*(mca|m\.c\.a\.|m)\b", "Altura manométrica"),
    "processo": (r"\b(UASB|RALF|reator anaer[óo]bio[^.\n]{0,40}|lagoa (?:facultativa|anaer[óo]bia|de matura[çc][ãa]o)|filtro biol[óo]gico[^.\n]{0,30}|lodos? ativados?|ciclo completo|filtra[çc][ãa]o (?:r[áa]pida|direta)|floculador(?:es)?|decantador(?:es)?[^.\n]{0,30}|desinfec[çc][ãa]o[^.\n]{0,30}|ETL|esta[çc][ãa]o de tratamento de lodo)", "Processo de tratamento"),
    "eficiencia": (r"(\d{2,3}(?:,\d+)?)\s*%[^.\n]{0,40}\bDBO|DBO[^.\n]{0,40}?(\d{2,3}(?:,\d+)?)\s*%", "Eficiência (DBO)"),
    "matricula": (r"matr[íi]cula\s*(?:n[ºo°.]*\s*)?([\d.]{3,})", "Matrículas de imóveis"),
    "curso_dagua": (r"\b((?:Rio|Ribeir[ãa]o|Arroio|C[óo]rrego|Lajeado|Sanga)\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ú][\wÀ-ú]+(?:\s+[A-ZÀ-Ú][\wÀ-ú]+)?)", "Cursos d'água citados"),
    "classe": (r"\bClasse\s+(\d|especial)\b", "Classe do corpo hídrico"),
}


def _paginas(texto):
    """[(posição inicial, nº da página)] a partir dos marcadores '## Página N' do extrator de PDF."""
    return [(m.start(), int(m.group(1))) for m in re.finditer(r"^## Página (\d+)", texto, re.M)]


def _pagina(marcas, pos):
    p = None
    for ini, n in marcas:
        if ini <= pos:
            p = n
        else:
            break
    return p


def extrair(arquivos):
    achados = defaultdict(list)
    for arq in arquivos:
        texto = arq.read_text(encoding="utf-8", errors="replace")
        marcas = _paginas(texto)
        for campo, (rx, _) in PADROES.items():
            for m in re.finditer(rx, texto, 0 if campo in ("curso_dagua", "diametro") else re.I):
                ini, fim = max(0, m.start() - 110), min(len(texto), m.end() + 110)
                ctx = re.sub(r"\s+", " ", texto[ini:fim]).strip()
                valor = re.sub(r"\s+", " ", m.group(0)).strip()
                achados[campo].append({"valor": valor, "arquivo": arq.name, "pagina": _pagina(marcas, m.start()),
                                       "trecho": ctx})
    return achados


def relatorio(achados, titulo):
    out = [f"# Extração de dados técnicos – {titulo}\n",
           "Candidatos encontrados por padrão de texto. Conferir no documento de origem antes de usar; "
           "a decisão de qual valor é o correto é humana.\n"]
    for campo, (_, rot) in PADROES.items():
        itens = achados.get(campo, [])
        if not itens:
            continue
        unicos = {}
        for i in itens:
            unicos.setdefault(i["valor"].lower(), i)
        out.append(f"\n## {rot} ({len(unicos)} valores distintos)\n")
        for i in list(unicos.values())[:40]:
            org = f"{i['arquivo']}" + (f", p. {i['pagina']}" if i["pagina"] else "")
            out.append(f"- **{i['valor']}** — _{org}_ — …{i['trecho']}…")
    return "\n".join(out) + "\n"


def _num(s):
    return float(s.replace(".", "").replace(",", "."))


def aplicar(cfg, achados):
    """Preenche no projeto.yaml apenas campos vazios com candidato inequívoco. Retorna [(campo, valor, origem)]."""
    ficha_p = cfg["dir"] / "projeto.yaml"
    f = yaml.safe_load(ficha_p.read_text(encoding="utf-8"))
    feitos = []

    def setar(caminho, valor, origem):
        alvo = f
        partes = caminho.split(".")
        for p in partes[:-1]:
            alvo = alvo.setdefault(p, {}) or {}
        if alvo.get(partes[-1]) in (None, ""):
            alvo[partes[-1]] = valor
            feitos.append((caminho, valor, origem))

    hz = {m.group(1) for i in achados.get("horizonte", []) if (m := re.search(r"(\d{1,2})\s*anos", i["valor"]))}
    if len(hz) == 1:
        i = achados["horizonte"][0]
        setar("horizonte_projeto_anos", int(hz.pop()), f"{i['arquivo']} p.{i['pagina']}")
    portarias = {i["valor"] for i in achados.get("outorga", [])}
    if len(portarias) == 1:
        i = achados["outorga"][0]
        chave = "manancial.outorga_captacao" if cfg["sistema"] == "SAA" else "corpo_receptor.outorga_lancamento"
        setar(chave, i["valor"], f"{i['arquivo']} p.{i['pagina']}")
    for i in achados.get("vazao", []):  # capacidade nominal/máxima explicitamente rotuladas
        t = i["trecho"].lower()
        m = re.match(rf"{NUM}\s*(l/s)", i["valor"], re.I)
        if not m:
            continue
        if "capacidade nominal" in t and cfg["sistema"] == "SAA":
            setar("eta.capacidade_nominal_ls", _num(m.group(1)), f"{i['arquivo']} p.{i['pagina']}")
        if "capacidade máxima" in t and cfg["sistema"] == "SAA":
            setar("eta.capacidade_maxima_ls", _num(m.group(1)), f"{i['arquivo']} p.{i['pagina']}")
    if feitos:
        ficha_p.write_text(yaml.safe_dump(f, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
        log = cfg["dir"] / "dados" / "EXTRACAO_APLICADA.md"
        linhas = [f"- {c} = {v}  (fonte: {o})" for c, v, o in feitos]
        log.write_text("# Campos preenchidos automaticamente no projeto.yaml\n\n" + "\n".join(linhas) + "\n", encoding="utf-8")
    return feitos


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave", nargs="?")
    ap.add_argument("--arquivo", nargs="*")
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    if a.arquivo:
        arqs = [Path(x) for x in a.arquivo]
        titulo = ", ".join(x.name for x in arqs)
    else:
        if not a.chave:
            ap.error("informe a chave do projeto ou --arquivo")
        cfg = projeto(a.chave)
        arqs = sorted((cfg["dir"] / "extraido").glob("*.md"))
        titulo = f"{cfg['documento']} {cfg['sistema']} {cfg['municipio']}"
    achados = extrair(arqs)
    md = relatorio(achados, titulo)
    if a.chave and not a.arquivo:
        (cfg["dir"] / "dados" / "EXTRACAO_MEMORIAL.md").write_text(md, encoding="utf-8")
        print(f"Relatório: {cfg['dir'] / 'dados' / 'EXTRACAO_MEMORIAL.md'}")
        if a.aplicar:
            for c, v, o in aplicar(cfg, achados):
                print(f"  preenchido {c} = {v} ({o})")
    print(md)


if __name__ == "__main__":
    main()
