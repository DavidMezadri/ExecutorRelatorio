"""Provedores de informação temática por localização – nacionais (todo o Brasil) + complementos estaduais.

Uso:
    python -m ferramentas.provedores <chave> [--temas hidrologia,geologia]

Cada provedor é um módulo em nacional/ ou estadual/ com:
    TEMA      'hidrologia' | 'geologia' | 'hidrogeologia' | 'geomorfologia' | 'rodovias' | ...
    NOME      nome curto da fonte (aparece no relatório)
    UFS       None = nacional; {"PR"} = só projetos nessas UFs
    BASES     palavras que identificam a base na legenda/fonte de um mapa (ex.: ["ANA"], ["SGB", "CPRM"])
    consultar(ctx) -> dict | None   com:
        paragrafos  lista de parágrafos prontos, com citação (AUTOR, ano) – números só se publicados pela fonte
        por_unidade {nome da unidade: atributos}  (conferência)
        refs        chaves do catálogo de referências usadas (biblio.registrar)
        resumo      linhas para dados/PROVEDORES.md
Ordem no texto: nacionais primeiro, depois os estaduais da UF do projeto. Para incluir um estado: novo módulo em
estadual/ com UFS={"XX"} e acrescentar em ESTADUAIS. Para outro tema nacional: módulo em nacional/ e NACIONAIS.
"""
import argparse
import importlib
import traceback

import yaml

from ferramentas.util import console_utf8, projeto, corrigir_nome

NACIONAIS = ["hidrografia_ana", "geologia_sgb", "hidrogeologia_sgb", "rodovias_dnit"]
ESTADUAIS = ["pr_aguas", "pr_geomorfologia"]


def modulos():
    out = []
    for nome in NACIONAIS:
        out.append(importlib.import_module(f"ferramentas.provedores.nacional.{nome}"))
    for nome in ESTADUAIS:
        out.append(importlib.import_module(f"ferramentas.provedores.estadual.{nome}"))
    return out


def contexto(cfg):
    from ferramentas.geo.tematico import unidades
    u, epsg = unidades(cfg)
    u["nome"] = u["nome"].map(corrigir_nome)
    uw = u.to_crs(4326)
    pontos = {}
    for (_, r), (_, rw) in zip(u.iterrows(), uw.iterrows()):
        g = rw.geometry
        pts = [g.interpolate(t, normalized=True) for t in (0, .5, 1)] if g.geom_type.endswith("LineString") else [g.centroid]
        pontos[r["nome"]] = [(p.x, p.y) for p in pts]
    return {"cfg": cfg, "uf": cfg["uf"], "unidades": u, "unidades_wgs": uw, "epsg": epsg, "pontos": pontos}


def consultar(cfg, temas=None, salvar=True):
    """{tema: [resultado, ...]} – nacionais primeiro, depois estaduais que cobrem a UF."""
    ctx = contexto(cfg)
    res = {}
    for m in modulos():
        temas_m = getattr(m, "TEMAS", None) or [m.TEMA]
        if temas and not set(temas_m) & set(temas):
            continue
        if m.UFS and cfg["uf"] not in m.UFS:
            continue
        try:
            r = m.consultar(ctx)
        except Exception as e:
            traceback.print_exc(limit=1)
            print(f"  (provedor {m.NOME} indisponível: {e.__class__.__name__})")
            r = None
        if not r:
            continue
        # provedor de vários temas devolve {tema: resultado}
        por_tema = r if hasattr(m, "TEMAS") else {m.TEMA: r}
        for tema, x in por_tema.items():
            if temas and tema not in temas:
                continue
            x.update({"provedor": m.NOME, "abrangencia": "nacional" if not m.UFS else "/".join(sorted(m.UFS)),
                      "bases": m.BASES})
            res.setdefault(tema, []).append(x)
    # referências de todos os provedores entram na lista do projeto (seção Referências automática)
    from ferramentas.garimpo import biblio
    chaves = list(dict.fromkeys(k for lst in res.values() for r in lst for k in r.get("refs", []) if k))
    if chaves:
        biblio.usar(cfg["chave"], chaves)
    if salvar:
        d = cfg["dir"] / "dados"
        (d / "provedores.yaml").write_text(yaml.safe_dump(res, allow_unicode=True, sort_keys=False), encoding="utf-8")
        md = [f"# Provedores temáticos – {cfg['municipio']}/{cfg['uf']}", ""]
        for tema, lst in res.items():
            md.append(f"## {tema}")
            for r in lst:
                md += ["", f"### {r['provedor']} ({r['abrangencia']})", ""] + [f"- {x}" for x in r.get("resumo", [])]
                md += ["", *r.get("paragrafos", [])]
            md.append("")
        (d / "PROVEDORES.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return res


def paragrafos(res, tema, bases=None):
    """Parágrafos do tema; com `bases` (fonte do mapa do Felipe), prefere o provedor da mesma base."""
    lst = res.get(tema) or []
    if bases:
        alvo = [r for r in lst if any(b.lower() in " ".join(bases).lower() for b in r.get("bases", []))]
        lst = alvo + [r for r in lst if r not in alvo]
    cobertos = {c for r in lst for c in r.get("cobre", [])}
    out = []
    for r in lst:
        out += r.get("paragrafos", [])
        # parágrafos opcionais (ex.: unidade hidrográfica da ANA) saem quando um provedor estadual cobre o assunto
        out += [p for k, p in (r.get("opcionais") or {}).items() if k not in cobertos]
    return out


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    ap.add_argument("--temas", help="lista separada por vírgula")
    a = ap.parse_args()
    cfg = projeto(a.chave)
    consultar(cfg, a.temas.split(",") if a.temas else None)
    print((cfg["dir"] / "dados" / "PROVEDORES.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
