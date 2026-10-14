"""Cria os textos-base (Markdown) de um documento a partir da estrutura padrão.

Uso:
    python -m ferramentas.docx.esqueleto candoi [--forcar]

Copia modelos/estruturas/<documento>_<sistema>/*.md para projetos/<chave>/texto/, preenchendo as
tabelas que dependem das unidades do projeto.yaml. Não sobrescreve arquivos existentes sem --forcar.
"""
import argparse

import yaml

from ferramentas.util import console_utf8, projeto, RAIZ

ROMANOS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV"]


def _caracteristica(u: dict) -> str:
    partes = []
    if u.get("extensao_m"):
        partes.append(f"Extensão aproximada de {u['extensao_m']:,.0f} m".replace(",", "."))
    if u.get("area_m2"):
        partes.append(f"Área aproximada de {u['area_m2']:,.0f} m²".replace(",", "."))
    partes.append(u.get("descricao") or "[A VERIFICAR: características – vazão, Hm, potência, volume, material, diâmetro]")
    return "; ".join(partes)


def preencher(texto: str, ficha: dict) -> str:
    unidades = ficha.get("unidades") or []
    linhas = "\n".join(f"| {u['nome']} | {_caracteristica(u)} |" for u in unidades) or \
        "| [A VERIFICAR: unidade] | [A VERIFICAR: características] |"
    anexos = "\n".join(f"| {u['nome']} | Anexo {ROMANOS[i]} |" for i, u in enumerate(unidades))
    titulos = []
    for i, u in enumerate(unidades):
        titulos.append(f"# ANEXO {ROMANOS[i]} – {u['nome'].upper()} {{-}}\n\n"
                       f"<!-- Inserir a planta com: !pdf[](anexos/arquivo.pdf){{paginas=1}} -->\n"
                       f"[A VERIFICAR: inserir planta/projeto da unidade em PDF]\n\n\\newpage\n")
    titulos.append(f"# ANEXO {ROMANOS[len(unidades)]} – ART {{-}}\n\n[A VERIFICAR: inserir ART do responsável técnico]\n")
    return (texto.replace("<<UNIDADES_LINHAS>>", linhas)
                 .replace("<<ANEXOS_LINHAS>>", anexos)
                 .replace("<<ANEXOS_TITULOS>>", "\n".join(titulos)))


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    ap.add_argument("--forcar", action="store_true", help="sobrescreve textos existentes")
    a = ap.parse_args()

    cfg = projeto(a.chave)
    estrutura = RAIZ / "modelos" / "estruturas" / f"{cfg['documento']}_{cfg['sistema']}".lower()
    if not estrutura.exists():
        disp = ", ".join(p.name for p in (RAIZ / "modelos" / "estruturas").iterdir())
        raise SystemExit(f"Estrutura {estrutura.name} ainda não existe. Disponíveis: {disp}")
    ficha_path = cfg["dir"] / "projeto.yaml"
    if not ficha_path.exists():
        raise SystemExit(f"Rode antes: python -m ferramentas.iniciar_projeto {a.chave}")
    ficha = yaml.safe_load(ficha_path.read_text(encoding="utf-8"))

    destino = cfg["dir"] / "texto"
    destino.mkdir(parents=True, exist_ok=True)
    for src in sorted(estrutura.glob("*.md")):
        dst = destino / src.name
        if dst.exists() and not a.forcar:
            print(f"  mantido  {dst.name}")
            continue
        dst.write_text(preencher(src.read_text(encoding="utf-8"), ficha), encoding="utf-8")
        print(f"  criado   {dst.name}")
    print(f"Textos em {destino}")


if __name__ == "__main__":
    main()
