"""Dossiê padrão da localidade: mesmas informações, mesmas fontes, para todo município.

Uso:
    python -m ferramentas.dossie.gerar candoi [--so socioeconomia,clima] [--raio-entorno 500]

Blocos (ordem fixa): socioeconomia (IBGE), saneamento (Censo 2022: água, esgoto, lixo), clima (NASA POWER +
Köppen), acesso (OSRM até Curitiba + rodovias do OpenStreetMap), entorno (OSM por unidade + CNES),
territórios (FUNAI, UCs) e consultas manuais (IPHAN, INCRA, Plano Diretor, PMSB, CAR).
Gera:
    dados/DOSSIE.md     leitura para a redação (cada bloco com as fontes a citar)
    dados/dossie.yaml   valores para o texto: {{dossie.acesso.distancia_capital_km}}, {{dossie.saneamento.esgoto_rede_pct}}...
e registra as referências no catálogo do projeto (seção Referências automática).
Requer iniciar_projeto (unidades); territórios usa dados/oficiais (fontes.oficiais) quando existir.
"""
import argparse
import datetime as dt
import json
import traceback

import yaml

from ferramentas.util import console_utf8, projeto
from ferramentas.dossie.coletores import COLETORES
from ferramentas.garimpo import biblio


def contexto(cfg):
    from ferramentas.fontes import ibge
    from ferramentas.geo.tematico import unidades
    u, _ = unidades(cfg)
    uw = u.to_crs("EPSG:4326")
    c = uw.geometry.union_all().centroid
    cod = cfg.get("cod_ibge") or ibge.buscar(cfg["municipio"], cfg["uf"])["id"]
    return {"cfg": cfg, "cod": int(cod), "unidades_utm": u, "unidades_wgs": uw, "centro": (c.x, c.y)}


def gerar(cfg, so=None, raio_entorno=500):
    d = cfg["dir"] / "dados"
    yml = d / "dossie.yaml"
    anterior = yaml.safe_load(yml.read_text(encoding="utf-8")) if yml.exists() else {}
    ctx = contexto(cfg)
    blocos, pendencias, fontes = {}, [], []
    for nome, fn in COLETORES.items():
        if so and nome not in so:
            continue
        print(f"  {nome} …", flush=True)
        try:
            r = fn(ctx, raio_entorno) if nome == "entorno" else fn(ctx)
            blocos[nome] = r
            pendencias += r.get("pendencias", [])
            fontes += r.get("fontes", [])
        except Exception as e:
            traceback.print_exc(limit=1)
            blocos[nome] = {"titulo": nome, "dados": None, "linhas": [f"- Coleta falhou ({e.__class__.__name__}): rodar de novo mais tarde"],
                            "fontes": []}
            pendencias.append(f"Bloco '{nome}' sem dados – repetir: python -m ferramentas.dossie.gerar {cfg['chave']} --so {nome}")
    biblio.usar(cfg["chave"], [f for f in fontes if f])

    dados = {**(anterior or {}), **{k: v["dados"] for k, v in blocos.items() if v.get("dados") is not None}}
    dados["_gerado_em"] = str(dt.date.today())
    yml.write_text(yaml.safe_dump(json.loads(json.dumps(dados, default=str)), allow_unicode=True, sort_keys=False, width=200),
                   encoding="utf-8")

    # cada bloco fica em dados/dossie/<bloco>.md; o DOSSIE.md é remontado com todos (rodar --so não apaga os demais)
    cat = biblio.catalogo()
    pasta = d / "dossie"
    pasta.mkdir(exist_ok=True)
    for nome, b in blocos.items():
        if b.get("dados") is None and (pasta / f"{nome}.md").exists():
            continue  # coleta falhou: mantém a versão anterior do bloco
        sec = [f"## {b['titulo']}\n", f"*Coletado em {dt.date.today():%d/%m/%Y}*\n"] + b["linhas"]
        cits = [cat[f]["citacao"] for f in b.get("fontes", []) if f in cat and cat[f].get("citacao")]
        if cits:
            sec.append(f"\n*Citar como:* {'; '.join(dict.fromkeys(cits))}")
        if b.get("pendencias"):
            sec.append("\n*Ressalvas:*\n" + "\n".join(f"- {p}" for p in b["pendencias"]))
        (pasta / f"{nome}.md").write_text("\n".join(sec) + "\n", encoding="utf-8")
    md = [f"# Dossiê da localidade – {cfg['municipio']}/{cfg['uf']} ({cfg['documento']} {cfg['sistema']})\n",
          "Gerado por `ferramentas.dossie.gerar` (blocos padrão, iguais para todo município). Valores disponíveis no "
          "texto como `{{dossie.<bloco>.<campo>}}` (ver dados/dossie.yaml).\n"]
    for nome in COLETORES:
        arq = pasta / f"{nome}.md"
        md.append("\n" + (arq.read_text(encoding="utf-8") if arq.exists() else
                          f"## {nome}\n\n- [A VERIFICAR: bloco ainda não coletado – python -m ferramentas.dossie.gerar "
                          f"{cfg['chave']} --so {nome}]\n"))
    falhas = [p for p in pendencias if p.startswith("Bloco")]
    if falhas:
        md.append("\n## Coletas a repetir\n" + "\n".join(f"- {p}" for p in falhas))
    (d / "DOSSIE.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return d / "DOSSIE.md"


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave")
    ap.add_argument("--so", help="blocos separados por vírgula")
    ap.add_argument("--raio-entorno", type=int, default=500)
    a = ap.parse_args()
    cfg = projeto(a.chave)
    arq = gerar(cfg, a.so.split(",") if a.so else None, a.raio_entorno)
    print(arq.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
