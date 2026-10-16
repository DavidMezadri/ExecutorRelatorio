"""Extração direta (por frase e por rótulo) de dados do memorial e dos carimbos/memoriais de legalização.

Complementa `memorial.py`: lá o valor é achado pela unidade e classificado pelo contexto; aqui cada campo da ficha tem
uma regra própria (frase típica dos memoriais Sanepar ou rótulo do carimbo), com pontuação alta. Também confere o
memorial contra o KMZ (divergências). Cada achado tem arquivo e página de origem.
"""
import re

NUM = r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)"
PONTOS = 10  # acima de qualquer candidato heurístico de memorial.py


def _num(s):
    return float(s.replace(".", "").replace(",", "."))


def _paginas(arq):
    """[(página, texto original, texto com espaços normalizados)] de um .md gerado por ingestao.pdf."""
    texto = arq.read_text(encoding="utf-8", errors="replace")
    partes = re.split(r"^## Página (\d+)\s*$", texto, flags=re.M)
    pags = [(None, texto)] if len(partes) == 1 else [(int(partes[k]), partes[k + 1]) for k in range(1, len(partes) - 1, 2)]
    out = []
    for pg, t in pags:
        sem_tabela = t.split("\n**Tabela")[0]  # as tabelas do extrator repetem o texto da página (com '|')
        t = sem_tabela if len(sem_tabela.strip()) > 200 else t
        out.append((pg, t, re.sub(r"\s+", " ", t)))
    return out


# (campo, regex sobre texto normalizado, conversão do grupo, unidade, nota, aplicar_na_ficha)
# Conversões: nome de função em CONV ou callable.
def _ls_de_m3h(m):
    return round(_num(m.group(1)) / 3.6, 2)


def _ano(m, i=1):
    return int(m.group(i))


REGRAS = [
    ("populacao.inicio_plano_ano", r"compreendido\s+de\s+((?:19|20)\d{2})\s+(?:at[ée]|a|[–-])\s+((?:19|20)\d{2})",
     lambda m: int(m.group(1)), None, "início do horizonte de projeto", True),
    ("populacao.final_plano_ano", r"compreendido\s+de\s+((?:19|20)\d{2})\s+(?:at[ée]|a|[–-])\s+((?:19|20)\d{2})",
     lambda m: int(m.group(2)), None, "fim do horizonte de projeto", True),
    ("horizonte_projeto_anos", r"horizonte\s+de\s+(?:projeto|plano)\s+de\s+(\d{1,2})\s+anos",
     lambda m: int(m.group(1)), "anos", "", True),
    ("populacao.final_plano_hab",
     r"popula[çc][ãa]o\s+(?:abastecida|atendida|beneficiada)?[^.]{0,60}?(?:ser[áa]|de|é de)\s+(?:de\s+)?(?:aproximadamente\s+)?"
     + NUM + r"\s+habitantes",
     lambda m: int(_num(m.group(1))), "hab", "população ao fim do plano", True),
    ("populacao.demanda_m3_dia", r"demanda\s+m[ée]dia\s+de\s+[áa]gua\s+ser[áa]\s+(?:de\s+)?(?:aproximadamente\s+)?" + NUM + r"\s*m[³3]/dia",
     lambda m: _num(m.group(1)), "m³/dia", "demanda média de água", True),
    ("eta.capacidade_nominal_ls", r"(?:dever[áa]\s+)?operar\s+normalmente\s+com\s+" + NUM + r"\s*m[³3]/h",
     _ls_de_m3h, "L/s", "vazão de operação normal (convertida de m³/h)", True),
    ("eta.capacidade_maxima_ls", r"vaz[ãa]o\s+de\s+produ[çc][ãa]o[^.]{0,50}?(?:de\s+)?at[ée]\s+" + NUM + r"\s*m[³3]/h",
     _ls_de_m3h, "L/s", "vazão de projeto do tratamento = capacidade testada do poço (convertida de m³/h)", True),
    ("eta.regime_operacao_h_dia", r"atendido\s+em\s+apenas\s+(\d{1,2})\s+horas\s+di[áa]rias",
     lambda m: int(m.group(1)), "h/dia", "operação prevista da elevatória (o poço foi testado em 20 h/dia)", True),
    ("manancial.profundidade_m", r"(\d{2,4})\s+metros\s+de\s+profundidade",
     lambda m: int(m.group(1)), "m", "profundidade do poço", False),
    ("manancial.tipo", r"(?:nova|uma)\s+capta[çc][ãa]o\s+(subterr[âa]nea|superficial)",
     lambda m: m.group(1).lower().replace("subterranea", "subterrânea"), None, "tipo de captação", True),
    ("manancial.nome", r"(CSB-?\d{2})\s*\(Po[çc]o\s*\d+\)",
     lambda m: f"Poço {m.group(1).upper()}", None, "identificação da captação", True),
    ("manancial.sia", r"\(SIA\s*(\d+)\)", lambda m: m.group(1), None, "código SIA da captação", False),
    ("eta.processo",
     r"utiliza[çc][ãa]o\s+de\s+([^.]{0,200}?(?:desinfec|clora[çc]|fluora[çc])[^.]{0,80})\.",
     lambda m: m.group(1).strip(), None, "produtos e etapas do tratamento", True),
    ("area.casa_quimica_m2", r"casa\s+de\s+qu[íi]mica[^.]{0,120}?" + NUM + r"\s*m²\s+de\s+[áa]rea\s+total",
     lambda m: _num(m.group(1)), "m²", "parcial: só a casa de química (área construída total depende das demais edificações)", False),
    ("manancial.bacia", r"bacia\s+hidrogr[áa]fica\s*(?::|d[oa])\s*(?:Bacia\s+)?(?:d[oa]\s+)?(Rio\s+[A-ZÀ-Ú][\wÀ-ú]+)",
     lambda m: f"Bacia do {m.group(1)}", None, "bacia hidrográfica", True),
]

# Rótulos de memorial de legalização / carimbo (texto original, com quebras de linha)
UNICOS = {"autoria_projeto.projetista", "autoria_projeto.gerente_sanepar", "coordenadas.lat_lon_referencia",
          "coordenadas.utm_vertice_A1", "acessos_rodovia", "imoveis_terceiros_decreto"}  # vale a 1ª ocorrência
RX_INTERVENCAO = re.compile(r"Projeto/Unidade Construtiva:\s*(.+?)\s*Im[óo]vel:", re.S)
RX_MATRICULA =re.compile(r"Certid[ãa]o de Registro:\s*([\d.]+)\s*-\s*([^\n]+)")
RX_PROPRIETARIO = re.compile(r"Propriet[áa]rio:\s*(.+?)\s*Munic[íi]pio:", re.S)
RX_AREA_IMOVEL = re.compile(r"[ÁA]REA DE TERRAS MEDINDO\s+" + NUM + r"\s*m²", re.I)
RX_INCRA = re.compile(r"INCRA\s+([\d.]+-\d)")
RX_ATINGIMENTO = re.compile(r"[ÁA]rea de Atingimento(?:\s*\([^)]*\))?:\s*" + NUM + r"\s*m²", re.I)
RX_COMARCA = re.compile(r"Comarca:\s*([^\n]+?)\s*(?:\n|$)")
RX_ART = re.compile(r"ART\s*n[°ºo.]*\s*(\d{8,})", re.I)
RX_RT_LEGAL = re.compile(r"\n\s*([A-ZÀ-Ú][\wÀ-ú]+(?: [\wÀ-ú]+){1,4})\s*\n\s*CREA:\s*([^\n]+)\n\s*ART", re.I)
RX_LATLON = re.compile(r"(\d{1,2}°\s?\d{1,2}'\s?[\d.]+\"\s?S)\s*\n\s*(\d{1,2}°\s?\d{1,2}'\s?[\d.]+\"\s?W)")
RX_UTM = re.compile(r"E\s*=\s*([\d.]+,\d+)\s*m\s*e\s*N\s*=\s*([\d.]+,\d+)\s*m")
RX_DECRETO = re.compile(r"Decreto de Utilidade P[úu]blica,?\s*N[º°o.]*\s*([\d.]+)\s*de\s*(\d{2}/\d{2}/\d{4})", re.I)
RX_RODOVIA = re.compile(r"\n\s*((?:BR|PR)-\d{3})\s*\n")
RX_PROJETISTA = re.compile(r"RESP\. T[ÉE]CNICO DO PROJETO:\s*\n\s*([A-ZÀ-Ú][A-ZÀ-Ú ]{5,40})\n\s*CREA N°:")
RX_EMPRESA = re.compile(r"\n\s*([^\n]*(?:Engenharia|Consultoria)[^\n]*Ltda\.?)\s*\n", re.I)
RX_GERENTE = re.compile(r"GERENTE:\s*([A-ZÀ-Ú][A-ZÀ-Ú ]{4,40})\s*\n\s*CREA N°:\s*([\d.]+\s*-\s*D/PR)")
RX_CREA_PROJ = re.compile(r"\n\s*([\d]{2,3}\.\d{3}\s*-\s*D/PR)\s*\n")


def _achado(campo, valor, arq, pg, trecho, nota="", aplicar=True, unidade=None, pontos=PONTOS):
    return {"campo": campo, "normalizado": valor, "unidade": unidade, "arquivo": arq.name, "pagina": pg,
            "valor": re.sub(r"\s+", " ", trecho).strip()[:140], "pontuacao": pontos, "ocorrencias": 1,
            "nota": nota, "aplicar": aplicar}


def extrair_diretos(arquivos):
    """Lista de achados diretos (um por campo/valor distinto; vale a 1ª ocorrência)."""
    achados, vistos, imoveis = [], set(), {}

    def add(a):
        k = (a["campo"], a["campo"] if a["campo"] in UNICOS else str(a["normalizado"]))
        if k not in vistos:
            vistos.add(k)
            achados.append(a)

    for arq in arquivos:
        for pg, orig, flat in _paginas(arq):
            for campo, rx, conv, un, nota, ap in REGRAS:
                for m in re.finditer(rx, flat, re.I):
                    trecho = f"{m.group(1)} m³/h" if un == "L/s" else m.group(0)
                    add(_achado(campo, conv(m), arq, pg, trecho, nota, ap, un))
            # legalização / carimbo: cada achado só vale se o rótulo existir na página
            if (m := RX_MATRICULA.search(orig)):
                # um imóvel por matrícula; cada memorial de legalização vira uma "intervenção" nele
                imovel = imoveis.setdefault(m.group(1), {"matricula": m.group(1), "cartorio": m.group(2).strip(),
                                                         "intervencoes": [], "_ref": (arq, pg, m.group(0))})
                for chave, rx in (("area_m2", RX_AREA_IMOVEL), ("incra", RX_INCRA), ("comarca", RX_COMARCA)):
                    if (x := rx.search(orig)) and chave not in imovel:
                        imovel[chave] = _num(x.group(1)) if chave.endswith("_m2") else x.group(1).strip()
                if (x := RX_PROPRIETARIO.search(orig)) and "proprietario" not in imovel:
                    imovel["proprietario"] = re.sub(r"\s+", " ", x.group(1)).strip()
                interv = {}
                if (x := RX_INTERVENCAO.search(orig)):
                    interv["descricao"] = re.sub(r"\s+", " ", x.group(1)).strip()
                if (x := RX_ATINGIMENTO.search(orig)):
                    interv["area_atingida_m2"] = _num(x.group(1))
                if (x := RX_ART.search(orig)):
                    interv["art_levantamento"] = x.group(1)
                if (x := RX_RT_LEGAL.search(orig)):
                    interv["responsavel_levantamento"] = f"{x.group(1).strip()} (CREA {x.group(2).strip()})"
                if interv.get("area_atingida_m2") and interv.get("area_atingida_m2") not in [
                        i.get("area_atingida_m2") for i in imovel["intervencoes"]]:
                    imovel["intervencoes"].append(interv)
            if (m := RX_LATLON.search(orig)):
                add(_achado("coordenadas.lat_lon_referencia", f"{m.group(1)} {m.group(2)}", arq, pg, m.group(0),
                            "SIRGAS 2000", False))
            if (m := RX_UTM.search(orig)):
                add(_achado("coordenadas.utm_vertice_A1", f"E={m.group(1)} N={m.group(2)}", arq, pg, m.group(0),
                            "SIRGAS 2000 / UTM 22S (MC 51°W); comparar com o KMZ", False))
            if (m := RX_DECRETO.search(orig)):
                add(_achado("imoveis_terceiros_decreto", f"Decreto de Utilidade Pública nº {m.group(1)} de {m.group(2)}",
                            arq, pg, m.group(0), "citado na planta de legalização", False))
            if (m := RX_RODOVIA.search(orig)):
                add(_achado("acessos_rodovia", m.group(1), arq, pg, m.group(0), "rodovia desenhada na planta", False))
            if (m := RX_PROJETISTA.search(orig)):
                crea = RX_CREA_PROJ.search(orig, m.end(), m.end() + 250)
                emp = RX_EMPRESA.search(orig)
                add(_achado("autoria_projeto.projetista",
                            f"{m.group(1).title()}" + (f" (CREA {crea.group(1)})" if crea else "")
                            + (f" – {emp.group(1).strip()}" if emp else ""), arq, pg, m.group(0),
                            "responsável técnico do PROJETO de engenharia (não é o RT do MCE)", False))
            if (m := RX_GERENTE.search(orig)):
                add(_achado("autoria_projeto.gerente_sanepar", f"{m.group(1).title()} (CREA {m.group(2)})", arq, pg,
                            m.group(0), "gerente Sanepar no carimbo", False))
    for imovel in imoveis.values():
        arq, pg, trecho = imovel.pop("_ref")
        achados.append(_achado("imoveis_terceiros", [imovel], arq, pg, trecho,
                               "imóvel afetado, dos memoriais de legalização", True))
    return achados


def divergencias(cfg, achados, arquivos):
    """Compara o memorial com o KMZ (ficha: unidades[].extensao_m / area_m2). Retorna lista de textos."""
    out = []
    unid = (cfg.get("unidades") or []) if isinstance(cfg, dict) else []
    kmz_lin = [u for u in unid if u.get("extensao_m")]
    for arq in arquivos:
        for pg, _, flat in _paginas(arq):
            for m in re.finditer(r"adutora[^.]{0,80}?(?:aproximadamente\s+)?" + NUM + r"\s*m\s+de\s+extens[ãa]o", flat, re.I):
                memorial = _num(m.group(1))
                for u in kmz_lin:
                    dif = abs(u["extensao_m"] - memorial) / memorial
                    if dif > 0.10:
                        out.append(f"Extensão da adutora: memorial {memorial:.0f} m ({arq.name} p.{pg}) × KMZ "
                                   f"{u['extensao_m']:.1f} m ('{u['nome']}') – diferença de {dif:.0%}. "
                                   "Conferir qual traçado vale (o KMZ pode incluir trecho a mais ou ser anterior ao projeto).")
    for arq in arquivos:
        flat = " ".join(f for _, _, f in _paginas(arq))
        if re.search(r"capta[çc][ãa]o\s+subterr[âa]nea", flat, re.I) and \
                re.search(r"p[áa]tio\s+da\s+capta[çc][ãa]o\s+superficial", flat, re.I):
            out.append(f"{arq.name}: descreve captação subterrânea (poço CSB-01), mas também cita 'pátio da captação "
                       "superficial' – provável erro de redação do projeto; usar 'subterrânea'.")
    return list(dict.fromkeys(out))
