"""Unidades do sistema a partir das plantas de projeto da Sanepar (código no nome do arquivo + título do carimbo).

Uso:
    python -m ferramentas.ingestao.unidades_sistema <chave>

As plantas da Sanepar seguem o padrão `NNN-SAA-XXXX-XXXX-PBHI-DE-0000<COD><NN><DESCRIÇÃO>-R0.pdf` (ex.: CSB01,
EET01, AAT01) e o carimbo traz o título da unidade ("CAPTAÇÃO SUBTERRÂNEA - CSB-01 / EEB-01"). Só entram unidades
com planta própria ou citadas no título de uma planta – códigos mencionados de passagem (unidades existentes,
outros sistemas) ficam fora. Nada é inventado: cada unidade traz a planta de onde saiu.

Gera em projetos/<chave>/dados/:
    unidades_sistema.yaml   lista usada no texto: {{unidades_sistema|lista}}
    UNIDADES_SISTEMA.md     quadro código / unidade / plantas (para conferência)
"""
import argparse
import re

import yaml

from ferramentas.util import console_utf8, projeto

# siglas de unidades usadas nos projetos da Sanepar (nome usado quando o carimbo não traz o título)
SIGLAS = {  # na ordem do fluxo (água: captação -> distribuição; esgoto: coleta -> lançamento)
    "CSB": "captação subterrânea", "CSP": "captação superficial", "CAP": "captação",
    "EEB": "estação elevatória de água bruta", "AAB": "adutora de água bruta",
    "ETA": "estação de tratamento de água", "SCF": "casa de química",
    "RAP": "reservatório apoiado", "REL": "reservatório elevado", "RSE": "reservatório semienterrado",
    "REN": "reservatório enterrado", "EET": "estação elevatória de água tratada", "BST": "booster",
    "AAT": "adutora de água tratada", "VRP": "válvula redutora de pressão", "RDA": "rede de distribuição de água",
    "RCE": "rede coletora de esgoto", "CTE": "coletor-tronco", "INT": "interceptor",
    "EEE": "estação elevatória de esgoto", "LRE": "linha de recalque de esgoto",
    "ETE": "estação de tratamento de esgoto", "EMI": "emissário", "EMF": "emissário final",
}
# códigos de arquivo que não são unidades (geral, sondagem, legalização...)
NAO_UNIDADE = {"GER", "PLA", "SON", "LEG"}

RE_ARQ = re.compile(r"-0000([A-Z]{3})(\d{2})[A-Z]", re.I)
RE_COD = r"[A-Z]{3}-\d{2}"
RE_TITULO = re.compile(r"HIDR[ÁA]ULICO\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ ]+?)\s+-\s+(" + RE_COD + r"(?:\s*/\s*" + RE_COD + r")*)")


def _frase(txt):
    return txt.strip().lower()


def levantar(dir_proj):
    unidades = {}  # código -> {nome, plantas}

    def anotar(cod, nome, planta, do_titulo=False):
        u = unidades.setdefault(cod, {"codigo": cod, "nome": nome, "plantas": [], "nome_do_carimbo": do_titulo})
        if do_titulo and not u["nome_do_carimbo"]:
            u["nome"], u["nome_do_carimbo"] = nome, True
        if planta not in u["plantas"]:
            u["plantas"].append(planta)

    for md in sorted((dir_proj / "extraido").glob("*.md")):
        m = RE_ARQ.search(md.stem)
        if not m or m.group(1).upper() in NAO_UNIDADE:
            texto_arq = None
        else:
            texto_arq = m
        texto = re.sub(r"\s+", " ", md.read_text(encoding="utf-8", errors="replace"))
        planta = md.stem.upper()
        # título do carimbo: "CAPTAÇÃO SUBTERRÂNEA - CSB-01 / EEB-01" (o 1º código recebe o título)
        for t in RE_TITULO.finditer(texto):
            codigos = re.findall(RE_COD, t.group(2))
            for i, cod in enumerate(codigos):
                sig = cod[:3]
                if i == 0 or sig not in SIGLAS:
                    nome = _frase(t.group(1)) if len(codigos) == 1 or sig not in SIGLAS else SIGLAS[sig]
                else:
                    nome = SIGLAS[sig]
                anotar(cod, nome, planta, do_titulo=(len(codigos) == 1 or sig not in SIGLAS))
        # código do nome do arquivo (planta própria da unidade)
        if texto_arq:
            sig, num = texto_arq.group(1).upper(), texto_arq.group(2)
            cod = f"{sig}-{num}"
            if cod not in unidades:
                anotar(cod, SIGLAS.get(sig, f"[A VERIFICAR: unidade {cod}]"), planta)
            elif planta not in unidades[cod]["plantas"]:
                unidades[cod]["plantas"].append(planta)
    ordem = list(SIGLAS)
    return sorted(unidades.values(), key=lambda u: (ordem.index(u["codigo"][:3]) if u["codigo"][:3] in ordem else 99, u["codigo"]))


def gerar(chave):
    cfg = projeto(chave)
    d = cfg["dir"]
    unidades = levantar(d)
    dados = d / "dados"
    dados.mkdir(parents=True, exist_ok=True)
    lista = [f"{u['nome']} ({u['codigo']})" for u in unidades]
    (dados / "unidades_sistema.yaml").write_text(
        "# Gerado por ferramentas.ingestao.unidades_sistema – plantas de projeto da Sanepar. {{unidades_sistema|lista}}\n"
        + yaml.safe_dump(lista or None, allow_unicode=True, sort_keys=False), encoding="utf-8")
    linhas = [f"# Unidades do sistema – plantas de projeto ({cfg['municipio']})\n",
              "Fonte: código no nome do arquivo e título do carimbo das plantas da Sanepar. Conferir antes de usar.\n",
              "| Código | Unidade | Plantas |", "|---|---|---|"]
    linhas += [f"| {u['codigo']} | {u['nome']} | {', '.join(u['plantas'])} |" for u in unidades]
    if not unidades:
        linhas.append("| – | nenhuma planta no padrão Sanepar em extraido/ | – |")
    (dados / "UNIDADES_SISTEMA.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return unidades


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    a = ap.parse_args()
    for u in gerar(a.chave):
        print(f"{u['codigo']:8} {u['nome']:45} {len(u['plantas'])} planta(s)")


if __name__ == "__main__":
    main()
