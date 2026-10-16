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


ROTULOS_EXTRA = {"portaria_florestal": "Portarias florestais/ambientais (NÃO são outorga)"}
MESES = r"(?:janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
FLORESTAL = re.compile(r"supress|ASV|vegeta|resgate|florest|Mata Atl[âa]ntica|flora|fauna|desmat", re.I)
# Regras de classificação: campo da ficha <- (tipo de padrão, palavras com peso, sistemas)
# Peso positivo = indica o campo; negativo = afasta. Vale a palavra até ~150 caracteres do valor.
REGRAS = {
    "eta.capacidade_nominal_ls": ("vazao", {"nominal": 4, "capacidade": 2, r"\bETA\b": 1, "tratamento de água": 1,
                                             "outorg": -3, "esgoto": -3, "máxima": -2, "lavagem": -3}, {"SAA"}),
    "eta.capacidade_maxima_ls": ("vazao", {r"m[áa]xim": 4, "capacidade": 2, r"\bETA\b": 1, "outorg": -3, "esgoto": -3,
                                            "nominal": -4, "lavagem": -3}, {"SAA"}),
    "manancial.vazao_outorgada_ls": ("vazao", {"outorg": 4, "capta": 2, "manancial": 1, "lançamento": -3}, {"SAA", "SES"}),
    "ete.vazao_media_ls": ("vazao", {r"m[ée]dia": 4, r"\bETE\b": 2, "esgoto": 2, "tratamento de esgoto": 1,
                                     "água bruta": -3, "outorg": -2}, {"SES"}),
    "ete.vazao_maxima_ls": ("vazao", {r"m[áa]xim": 4, r"\bETE\b": 2, "esgoto": 2, "água bruta": -3}, {"SES"}),
    "ete.vazao_fim_plano_ls": ("vazao", {r"fi(m|nal) de plano": 4, "alcance": 3, r"\bETE\b": 2, "esgoto": 1}, {"SES"}),
    "corpo_receptor.vazao_outorgada_ls": ("vazao", {"lançamento": 4, "outorg": 3, "corpo receptor": 2, "capta": -3}, {"SES"}),
    "populacao.demanda_m3_dia": ("vazao", {"demanda": 4, "produção": 2, "consumo": 2}, {"SAA"}),
    "populacao.inicio_plano_hab": ("populacao", {r"in[íi]cio de plano": 5, r"inicial": 3, r"atendida": 1,
                                                 r"fi(m|nal) de plano": -4, "censo": -3, "IBGE": -3}, {"SAA", "SES"}),
    "populacao.final_plano_hab": ("populacao", {r"fi(m|nal) de plano": 5, "saturação": 3, "alcance": 3,
                                                r"in[íi]cio de plano": -4, "censo": -3, "IBGE": -3}, {"SAA", "SES"}),
    "horizonte_projeto_anos": ("horizonte", {"horizonte": 4, "alcance": 2, "plano": 1}, {"SAA", "SES"}),
    "manancial.outorga_captacao": ("outorga", {"capta": 4, "manancial": 2, "outorg": 2, "lançamento": -4}, {"SAA", "SES"}),
    "corpo_receptor.outorga_lancamento": ("outorga", {"lançamento": 4, "efluente": 2, "receptor": 2, "capta": -4}, {"SES"}),
    "ete.eficiencia_dbo_pct": ("eficiencia", {"eficiência": 3, "remoção": 2, "DBO": 2}, {"SES"}),
    "manancial.nome": ("curso_dagua", {"capta": 4, "manancial": 4, "lançamento": -4, "receptor": -4}, {"SAA", "SES"}),
    "corpo_receptor.nome": ("curso_dagua", {"lançamento": 4, "corpo receptor": 4, "receptor": 2, "capta": -4}, {"SES"}),
}
# Mapa de páginas: assunto -> palavras (a IA lê primeiro as páginas com mais ocorrências)
ASSUNTOS = {
    "População e demanda": ["população", "habitantes", "projeção", "per capita", "demanda", "horizonte", "crescimento"],
    "Vazões de projeto": ["vazão", "L/s", "m³/h", "m³/dia", "nominal", "máxima", "K1", "K2"],
    "Captação / manancial": ["captação", "manancial", "tomada d'água", "barragem", "poço"],
    "Tratamento (ETA/ETE)": ["tratamento", "floculação", "decantação", "filtração", "reator", "UASB", "RALF", "lagoa", "desinfecção"],
    "Lodo e resíduos": ["lodo", "ETL", "desaguamento", "resíduo", "caçamba", "gradeamento", "areia"],
    "Outorgas e licenças": ["outorga", "portaria", "licença", "IAT", "AGUASPARANÁ"],
    "Corpo receptor e lançamento": ["lançamento", "corpo receptor", "emissário", "classe", "efluente"],
    "Unidades e tubulações": ["adutora", "rede", "interceptor", "elevatória", "reservatório", "DN", "extensão"],
    "Desapropriação e imóveis": ["desapropriação", "servidão", "matrícula", "proprietário", "imóvel"],
    "Obras, cronograma e mão de obra": ["cronograma", "mão de obra", "canteiro", "prazo", "meses", "trabalhadores"],
    "Produtos químicos": ["cloro", "hipoclorito", "sulfato", "PAC", "policloreto", "cal", "flúor", "ácido"],
}
CONV_LS = {"l/s": 1, "l/seg": 1, "m³/h": 1 / 3.6, "m3/h": 1 / 3.6, "m³/dia": 1 / 86.4, "m3/dia": 1 / 86.4,
           "m³/s": 1000, "m3/s": 1000}


def _valor_normalizado(tipo, valor):
    if tipo == "vazao":
        m = re.match(rf"{NUM}\s*(\S+)", valor)
        if m and m.group(2).lower() in CONV_LS:
            return round(_num(m.group(1)) * CONV_LS[m.group(2).lower()], 2), m.group(2)
    if tipo == "populacao":
        m = re.match(NUM, valor)
        return (int(_num(m.group(1))), "hab") if m else (None, None)
    if tipo == "horizonte":
        m = re.search(r"(\d{1,2})\s*anos", valor)
        if m:
            return int(m.group(1)), "anos"
        m = re.findall(r"(?:19|20)\d{2}", valor)
        if len(m) == 2:
            return int(m[1]) - int(m[0]) + 1, "anos"  # 2029–2048 = 20 anos (extremos incluídos)
    if tipo == "eficiencia":
        m = re.search(r"(\d{2,3}(?:,\d+)?)\s*%", valor)
        return (float(m.group(1).replace(",", ".")), "%") if m else (None, None)
    return valor, None


def classificar(achados, sistema):
    """{campo: [candidatos ordenados por pontuação]} – cada candidato com valor normalizado, unidade e origem."""
    out = {}
    for campo, (tipo, palavras, sistemas) in REGRAS.items():
        if sistema not in sistemas:
            continue
        cands = []
        for i in achados.get(tipo, []):
            jan = i["trecho"]
            pos = jan.find(i["valor"])
            if pos >= 0:
                antes, depois = jan[max(0, pos - 90):pos], jan[pos + len(i["valor"]):pos + len(i["valor"]) + 45]
            else:
                antes, depois = jan, ""
            # palavras antes do valor indicam o que ele é; as de depois pesam metade
            pont = sum(p for k, p in palavras.items() if re.search(k, antes, re.I)) + \
                sum(p / 2 for k, p in palavras.items() if re.search(k, depois, re.I) and not re.search(k, antes, re.I))
            if pont <= 0:
                continue
            v, un = _valor_normalizado(tipo, i["valor"])
            if v in (None, ""):
                continue
            if tipo == "vazao" and campo.endswith("_m3_dia"):
                orig = re.match(rf"{NUM}\s*(m³/dia|m3/dia)", i["valor"], re.I)
                v, un = (_num(orig.group(1)) if orig else round(v * 86.4, 1)), "m³/dia"  # sem ida-e-volta de conversão
            elif tipo == "vazao":
                un = "L/s"
            c = {**i, "pontuacao": pont, "normalizado": v, "unidade": un}
            if tipo == "populacao":  # ano do plano: o mais próximo antes do valor
                anos = re.findall(r"(?:19|20)\d{2}", antes)
                c["ano"] = int(anos[-1]) if anos else None
            cands.append(c)
        # mesmo valor em vários lugares soma confiança
        agrup = {}
        for c in sorted(cands, key=lambda c: -c["pontuacao"]):
            k = c["normalizado"]
            if isinstance(k, (int, float)):  # 117,28 L/s e 422,24 m³/h (=117,29) são o mesmo valor
                k = next((x for x in agrup if isinstance(x, (int, float)) and x and abs(x - k) / abs(x) < 0.01), k)
            if k in agrup:
                agrup[k]["pontuacao"] += 1
                agrup[k]["ocorrencias"] += 1
            else:
                agrup[k] = {**c, "ocorrencias": 1}
        out[campo] = sorted(agrup.values(), key=lambda c: -c["pontuacao"])[:4]
    return out


def mapa_paginas(arquivos):
    """{assunto: [(arquivo, página, ocorrências)]} – páginas mais relevantes de cada assunto."""
    mapa = {}
    for assunto, termos in ASSUNTOS.items():
        conta = []
        for arq in arquivos:
            texto = arq.read_text(encoding="utf-8", errors="replace")
            partes = re.split(r"^## Página (\d+)", texto, flags=re.M)
            paginas = [(None, partes[0])] + [(int(partes[k]), partes[k + 1]) for k in range(1, len(partes) - 1, 2)]
            for pg, txt in paginas:
                n = sum(len(re.findall(re.escape(t), txt, re.I)) for t in termos)
                if n >= 3:
                    conta.append((arq.name, pg, n))
        mapa[assunto] = sorted(conta, key=lambda x: -x[2])[:6]
    return mapa


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
                resto = texto[m.end():m.end() + 30]
                if campo == "diametro" and re.match(rf"\s*(?:de|DE)\s+{MESES}", resto, re.I):
                    continue  # "DE 18 DE ABRIL" é data, não diâmetro
                if campo == "curso_dagua" and (valor.lower() == "rio de janeiro" or
                                               re.match(r"\s+do\s+(?:Sul|Norte)", resto)):
                    continue  # estados/cidades, não cursos d'água
                if campo == "outorga" and FLORESTAL.search(ctx):
                    campo_dest = "portaria_florestal"
                else:
                    campo_dest = campo
                achados[campo_dest].append({"valor": valor, "arquivo": arq.name, "pagina": _pagina(marcas, m.start()),
                                       "trecho": ctx})
    return achados


def relatorio(achados, titulo, sugestoes=None, mapa=None, diverg=None):
    out = [f"# Extração de dados técnicos – {titulo}\n",
           "Gerado por `ferramentas.ingestao.memorial`. Os memoriais não têm padrão: os valores são achados pela unidade "
           "(L/s, hab, DN...) e classificados pelo contexto. Conferir no documento de origem antes de usar.\n"]
    if sugestoes:
        out.append("\n## Sugestões para a ficha (projeto.yaml)\n")
        out.append("| Campo | 1º candidato | Pontos | Origem | Outros candidatos |\n|---|---|---|---|---|")
        for campo, cands in sugestoes.items():
            if not cands:
                continue
            c = cands[0]
            val = f"{c['normalizado']}" + (f" {c['unidade']}" if c.get("unidade") and c["unidade"] not in ("hab",) else "")
            if c.get("ano"):
                val += f" (ano {c['ano']})"
            if campo.endswith(("_ls", "_m3_dia")) and c["valor"].split()[-1] not in (c.get("unidade") or ""):
                val += f" (de {c['valor']})"
            org = f"{c['arquivo']}" + (f" p.{c['pagina']}" if c["pagina"] else "")
            outros = "; ".join(f"{o['normalizado']} ({o['pontuacao']})" for o in cands[1:])
            if c.get("nota"):
                val += f" – _{c['nota']}_"
            if not c.get("aplicar", True):
                val += " [só informativo]"
            out.append(f"| {campo} | **{val}** | {c['pontuacao']} | {org} | {outros} |")
    if diverg:
        out.append("\n## Divergências entre fontes\n")
        out += [f"- {d}" for d in diverg]
    if mapa:
        out.append("\n## Mapa de páginas (onde ler cada assunto)\n")
        for assunto, pags in mapa.items():
            if pags:
                out.append(f"- **{assunto}:** " + "; ".join(f"{a}" + (f" p.{p}" if p else "") + f" ({n})" for a, p, n in pags))
    out.append("\n## Todos os valores encontrados\n")
    rotulos = {**{c: r for c, (_, r) in PADROES.items()}, **ROTULOS_EXTRA}
    for campo, rot in rotulos.items():
        itens = achados.get(campo, [])
        if not itens:
            continue
        unicos = {}
        for i in itens:
            unicos.setdefault(i["valor"].lower(), i)
        out.append(f"\n### {rot} ({len(unicos)} valores distintos)\n")
        for i in list(unicos.values())[:40]:
            org = f"{i['arquivo']}" + (f", p. {i['pagina']}" if i["pagina"] else "")
            out.append(f"- **{i['valor']}** — _{org}_ — …{i['trecho']}…")
    return "\n".join(out) + "\n"


def _num(s):
    return float(s.replace(".", "").replace(",", "."))


def aplicar(cfg, sugestoes, minimo=5, margem=2):
    """Preenche no projeto.yaml só campos VAZIOS cujo 1º candidato tem pontuação >= minimo e vantagem >= margem."""
    ficha_p = cfg["dir"] / "projeto.yaml"
    f = yaml.safe_load(ficha_p.read_text(encoding="utf-8"))
    feitos = []

    def setar(caminho, valor, origem):
        alvo = f
        partes = caminho.split(".")
        for p in partes[:-1]:
            if not isinstance(alvo.get(p), dict):
                alvo[p] = {}
            alvo = alvo[p]
        if alvo.get(partes[-1]) in (None, ""):
            alvo[partes[-1]] = valor
            feitos.append((caminho, valor, origem))

    for campo, cands in sugestoes.items():
        if not cands:
            continue
        c = cands[0]
        if c.get("aplicar") is False:
            continue
        seg = cands[1]["pontuacao"] if len(cands) > 1 else 0
        if c["pontuacao"] < minimo or c["pontuacao"] - seg < margem:
            continue
        org = f"{c['arquivo']} p.{c['pagina']}"
        setar(campo, c["normalizado"], org)
        if c.get("ano") and campo.startswith("populacao.") and campo.endswith("_hab"):
            setar(campo.replace("_hab", "_ano"), c["ano"], org)
    if feitos:
        ficha_p.write_text(yaml.safe_dump(f, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
        log = cfg["dir"] / "dados" / "EXTRACAO_APLICADA.md"
        linhas = [f"- {c} = {v}  (fonte: {o})" for c, v, o in feitos]
        log.write_text("# Campos preenchidos automaticamente no projeto.yaml\n\nConferir na fonte indicada.\n\n"
                       + "\n".join(linhas) + "\n", encoding="utf-8")
    return feitos


def _ficha(cfg):
    """Ficha do projeto (projeto.yaml) ou {} se não houver projeto."""
    if not cfg:
        return {}
    p = cfg["dir"] / "projeto.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {} if p.exists() else {}


def _compor_manancial(diretos):
    """manancial.tipo ganha a profundidade do poço (ex.: 'subterrânea (poço profundo, 120 m)')."""
    prof = next((d for d in diretos if d["campo"] == "manancial.profundidade_m"), None)
    for d in diretos:
        if d["campo"] == "manancial.tipo" and d["normalizado"] == "subterrânea" and prof:
            d["normalizado"] = f"subterrânea (poço profundo, {prof['normalizado']} m de profundidade)"


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave", nargs="?")
    ap.add_argument("--arquivo", nargs="*")
    ap.add_argument("--sistema", choices=["SAA", "SES"], help="com --arquivo (sem projeto)")
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    cfg = projeto(a.chave) if a.chave else None
    if a.arquivo:
        arqs = [Path(x) for x in a.arquivo]
        titulo = ", ".join(x.name for x in arqs)
    elif cfg:
        arqs = sorted((cfg["dir"] / "extraido").glob("*.md"))
        titulo = f"{cfg['documento']} {cfg['sistema']} {cfg['municipio']}"
    else:
        ap.error("informe a chave do projeto ou --arquivo")
    sistema = a.sistema or (cfg["sistema"] if cfg else "SAA")
    from ferramentas.ingestao import memorial_diretos as md_dir
    achados = extrair(arqs)
    sug = classificar(achados, sistema)
    diretos = md_dir.extrair_diretos(arqs)
    _compor_manancial(diretos)
    for d in diretos:  # o achado direto passa à frente dos candidatos heurísticos do mesmo campo
        sug.setdefault(d["campo"], [])
        sug[d["campo"]] = [d] + sug[d["campo"]]
    for campo, lst in sug.items():  # dois achados diretos para o mesmo campo = ambíguo; aplicar não decide
        dir_c = [c for c in lst if c.get("pontuacao") == md_dir.PONTOS]
        if len(dir_c) > 1 and campo != "imoveis_terceiros":
            for c in dir_c:
                c["aplicar"] = False
                c["nota"] = (c.get("nota", "") + " [ambíguo: vários valores diretos]").strip()
    diverg = md_dir.divergencias(_ficha(cfg), diretos, arqs)
    md = relatorio(achados, titulo, sug, mapa_paginas(arqs), diverg)
    if cfg:
        (cfg["dir"] / "dados" / "EXTRACAO_MEMORIAL.md").write_text(md, encoding="utf-8")
        print(f"Relatório: {cfg['dir'] / 'dados' / 'EXTRACAO_MEMORIAL.md'}")
        if a.aplicar:
            for c, v, o in aplicar(cfg, sug):
                print(f"  preenchido {c} = {v} ({o})")
    print(md)


if __name__ == "__main__":
    main()
