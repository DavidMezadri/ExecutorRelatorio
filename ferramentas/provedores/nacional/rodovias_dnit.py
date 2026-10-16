"""Rodovias federais (DNIT – Sistema Nacional de Viação): trechos próximos com o tipo de superfície oficial."""
from ferramentas.garimpo import biblio
from ferramentas.provedores.comum import wfs, DNIT_WFS, lista

TEMA = "rodovias"
NOME = "DNIT – Sistema Nacional de Viação (SNV)"
UFS = None
BASES = ["DNIT", "SNV"]
SUPERFICIE = {"PAV": "pavimentada", "DUP": "pavimentada e duplicada", "EOD": "em obras de duplicação",
              "EOP": "em obras de pavimentação", "IMP": "implantada (não pavimentada)", "EOI": "em obras de implantação",
              "LEN": "leito natural", "PLA": "planejada", "TRV": "travessia"}
RAIO_KM = 15


def consultar(ctx):
    lons = [p[0] for pts in ctx["pontos"].values() for p in pts]
    lats = [p[1] for pts in ctx["pontos"].values() for p in pts]
    d = RAIO_KM / 111
    lon0, lat0 = sum(lons) / len(lons), sum(lats) / len(lats)
    fs = wfs(DNIT_WFS, "vgeo:vw_snv_rod", bbox=(lon0 - d, lat0 - d, lon0 + d, lat0 + d), n=500) or []
    if not fs:
        return None
    versao = max(f["properties"].get("Versao_SNV") or "" for f in fs)  # só a versão mais recente do SNV
    trechos = [f["properties"] for f in fs if f["properties"].get("Versao_SNV") == versao]
    por_br = {}
    for t in trechos:
        br = f"BR-{t.get('Codigo_BR')}"
        sup = SUPERFICIE.get(t.get("Superficie_Federal"), t.get("Superficie_Federal") or "superfície não informada")
        por_br.setdefault(br, set()).add(sup)
    ano = versao[:4] if versao[:4].isdigit() else "[20--]"
    cit = f"DNIT, {ano}"
    itens = [f"a {br} ({lista(sorted(s))})" for br, s in sorted(por_br.items())]
    par = (f"Segundo o Sistema Nacional de Viação (SNV, versão {versao}), mantido pelo Departamento Nacional de "
           f"Infraestrutura de Transportes, as rodovias federais num raio de aproximadamente {RAIO_KM} km do empreendimento são "
           f"{lista(itens)} ({cit}).")
    ref = biblio.registrar(f"dnit-snv-{versao}",
                           f"DNIT – DEPARTAMENTO NACIONAL DE INFRAESTRUTURA DE TRANSPORTES. Sistema Nacional de Viação – SNV, "
                           f"versão {versao}. Brasília, DF: DNIT, {ano}. Disponível em: https://servicos.dnit.gov.br/vgeo. "
                           f"Acesso em: {biblio.data_acesso()}.", "base", "https://servicos.dnit.gov.br/vgeo", cit)
    return {"paragrafos": [par], "por_unidade": {}, "refs": [ref],
            "resumo": [f"SNV {versao}: " + "; ".join(f"{b}: {', '.join(sorted(s))}" for b, s in por_br.items())],
            "rodovias": {b: sorted(s) for b, s in por_br.items()}}
