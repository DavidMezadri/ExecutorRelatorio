"""Geomorfologia do Paraná pelo Atlas Geomorfológico do Estado do Paraná (OKA-FIORI et al., 2006 – MINEROPAR/UFPR).

Uso:
    python -m ferramentas.garimpo.geomorfologia_pr ponto <lat> <lon>     # subunidade num ponto (teste)
    python -m ferramentas.garimpo.geomorfologia_pr projeto <chave>       # subunidade de cada unidade do projeto

O atlas (PDF público no site do IAT) descreve 50 subunidades morfoesculturais em 21 folhas 1:250.000. Não há
shapefile público, então a subunidade de cada unidade é obtida na própria carta do atlas:
  1. escolhe a folha pelas coordenadas (texto "latitudes ... e longitudes ..." de cada folha);
  2. renderiza a carta e a georreferencia pelos rótulos da grade UTM (SAD 69, meridiano central impresso);
  3. compara a cor (padrão de preenchimento) no ponto com as amostras da legenda -> código e nome da subunidade.
Do texto da folha extrai a descrição da subunidade (dissecação, declividades, gradiente, altitudes, formas de
topos, vertentes e vales, rochas) e, das páginas iniciais, o texto do planalto (unidade morfoescultural).
Gera dados/GEOMORFOLOGIA_PR.md e dados/geomorfologia_pr.yaml (usado pelo redator em {{auto.geomorfologia}}).
Conferir a subunidade na carta quando a unidade estiver perto de um limite (campo "confianca").
"""
import argparse
import re
from pathlib import Path

import numpy as np
import yaml

from ferramentas.util import console_utf8, projeto, RAIZ
from ferramentas.garimpo import web, biblio

URL = ("https://www.iat.pr.gov.br/sites/agua-terra/arquivos_restritos/files/documento/2020-04/"
       "atlas_geomorforlogico_parana_2006.pdf")
ARQ = RAIZ / "dados_comuns" / "cache" / "atlas_geomorfologico_pr_2006.pdf"
DPI = 150
CIT = "OKA-FIORI et al., 2006"
ABNT = ("OKA-FIORI, C. et al. Atlas geomorfológico do Estado do Paraná: escala base 1:250.000, modelos reduzidos "
        "1:500.000. Curitiba: Minerais do Paraná – MINEROPAR; Universidade Federal do Paraná, 2006. 63 p. "
        f"Disponível em: {URL}. Acesso em: {{acesso}}.")
# trecho do atlas sobre cada unidade morfoescultural: (início, fim) – o texto é diagramado em colunas e mistura
# geomorfologia com estratigrafia, por isso os limites são fixos
PLANALTOS = {
    "Primeiro Planalto Paranaense": ("A unidade morfológica denominada Primeiro Planalto Paranaense",
                                     "altitudes variando entre 400 e 1200 metros."),
    "Segundo Planalto Paranaense": ("A primeira está esculpida na faixa de rochas Paleozóicas", "560 metros s.n.m."),
    "Terceiro Planalto Paranaense": ("A Zona de Capeamento Areníto-Basáltico corresponde", "até o vale deste."),
    "Serra do Mar": ("A Serra do Mar configura-se", "termina o Planalto Atlântico."),
    "Planícies": ("As morfoesculturas Planícies Fluviais", "como é o caso das planícies fluviais."),
    "Planalto de Curitiba": ("No caso da morfoescultura do Planalto de Curitiba", "(Lima, Melo e Coimbra, 1991)."),
}


def _doc():
    import pymupdf
    if not ARQ.exists():
        ARQ.parent.mkdir(parents=True, exist_ok=True)
        ARQ.write_bytes(web.obter(URL, binario=True, cache_horas=24 * 365, timeout=300))
    return pymupdf.open(ARQ)


def _limpo(t):
    return re.sub(r"\s+", " ", re.sub(r"-\n(?=\w)", "", t)).strip()


def folhas(doc):
    """[{nome, pag_texto, pag_mapa, lat (min,max), lon (min,max)}] – coordenadas em graus (sul/oeste negativos)."""
    out = []
    for i in range(doc.page_count):
        t = _limpo(doc[i].get_text())
        m = re.search(r"FOLHA ([A-ZÁÉÍÓÚÂÊÔÃÕÇ ]+?) A folha", t)
        c = re.search(r"latitudes (\d+)º\s*(\d+)\s*’ e (\d+)º\s*(\d+)\s*’ sul e longitudes (\d+)º\s*(\d+)\s*’ e "
                      r"(\d+)º\s*(\d+)\s*’", t)
        if m and c:
            g = [int(x) for x in c.groups()]
            lat = sorted([-(g[0] + g[1] / 60), -(g[2] + g[3] / 60)])
            lon = sorted([-(g[4] + g[5] / 60), -(g[6] + g[7] / 60)])
            out.append({"nome": m.group(1).strip().title(), "pag_texto": i, "pag_mapa": i + 1, "lat": lat, "lon": lon})
    return out


def subunidades_da_folha(doc, f):
    """{código: {nome, unidade, texto}} a partir do texto da folha."""
    t = _limpo(doc[f["pag_texto"]].get_text())
    out = {}
    partes = re.split(r"(?=A sub-unidade morfoescultural número)", t)
    for p in partes[1:]:
        m = re.match(r"A sub-unidade morfoescultural número (\d\.\d\.\d+), denominada (.+?), (?:situada no|da unidade)", p)
        if not m:
            continue
        texto = re.sub(r"\s*sub-unidade morfoescultural \d\.\d\.\d+\s*", " ", p)
        texto = re.sub(r"\s+\d{1,2}\s*$", "", texto).strip()  # número de página no fim
        un = re.search(r"situada no ([A-ZÁÉÍÓÚ][\wÀ-ú ]+? Paranaense|Primeiro Planalto|Serra do Mar[\wÀ-ú ]*)", texto)
        out[m.group(1)] = {"nome": m.group(2).strip(), "unidade": un.group(1) if un else None, "texto": texto}
    return out


def texto_planalto(doc, unidade):
    """Trecho do atlas sobre a unidade morfoescultural (limites fixos em PLANALTOS)."""
    lim = next((v for k, v in PLANALTOS.items() if unidade and k.lower() in unidade.lower()), None)
    if not lim:
        return None
    t = _limpo(" ".join(doc[i].get_text() for i in range(10, 17)))
    a = t.find(lim[0])
    b = t.find(lim[1], a)
    if a < 0 or b < 0:
        return None
    trecho = t[a:b + len(lim[1])]
    # frases que dependem do parágrafo anterior do atlas
    return trecho.replace("A primeira está esculpida", "A Zona de Denudação Periférica está esculpida")


# ------------------------------------------------------------------ localização na carta
def _georef(pag, f, epsg):
    """(E, N) -> (x, y) em pixels pela moldura da carta: os cantos do retângulo da moldura são os cantos
    geográficos da folha (lat/lon do texto). Não usa os rótulos da grade UTM (em algumas folhas, como Campo
    Mourão, os rótulos de Norte estão deslocados ~100 km)."""
    import pymupdf
    from pyproj import Transformer
    esc = DPI / 72
    rets = []
    for d in pag.get_drawings():
        r = d["rect"] * pag.rotation_matrix
        if r.width * esc > 1500 and r.height * esc > 1000 and d.get("color") is not None:
            rets.append(r)
    if not rets:
        return None
    m = min(rets, key=lambda r: r.width * r.height)  # moldura do mapa (a maior é a borda da página)
    x0, y0, x1, y1 = (v * esc for v in (m.x0, m.y0, m.x1, m.y1))
    (la0, la1), (lo0, lo1) = f["lat"], f["lon"]
    tr = Transformer.from_crs(4326, epsg, always_xy=True)
    cantos = [((lo0, la1), (x0, y0)), ((lo1, la1), (x1, y0)), ((lo0, la0), (x0, y1)), ((lo1, la0), (x1, y1))]
    A = np.array([[*tr.transform(lo, la), 1.0] for (lo, la), _ in cantos])
    X = np.array([px for _, px in cantos])
    coef, *_ = np.linalg.lstsq(A, X, rcond=None)
    return lambda e, n: tuple(np.array([e, n, 1.0]) @ coef)


def _dominante(px):
    """Cor de fundo dominante (sem branco dos padrões pontilhados, preto de texto/traços e azul da hidrografia)."""
    if not len(px):
        return None
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    ok = (px.max(axis=1) > 45) & (px.min(axis=1) < 225) & ~((b > r + 40) & (b > g + 10))
    px = px[ok]
    if len(px) < 8:
        return None
    q = (px // 24).astype(int)
    chaves, cont = np.unique(q[:, 0] * 10000 + q[:, 1] * 100 + q[:, 2], return_counts=True)
    alvo = chaves[cont.argmax()]
    sel = px[(q[:, 0] * 10000 + q[:, 1] * 100 + q[:, 2]) == alvo]
    return sel.mean(axis=0)


def _legenda(pag, img):
    """{código: cor média (RGB) da amostra da legenda} – o código é escrito sobre a amostra de cor."""
    import pymupdf
    esc = DPI / 72
    palavras = [(w, pymupdf.Rect(w[:4]) * pag.rotation_matrix) for w in pag.get_text("words")]
    ref = next((r for w, r in palavras if w[4].startswith("Sub-unidades")), None)
    out = {}
    for w, r in palavras:
        if not re.fullmatch(r"\d\.\d\.\d{1,2}", w[4]) or ref is None or r.y0 < ref.y0 or r.x0 < ref.x0 - 20:
            continue
        x0, y0, x1, y1 = [int(v * esc) for v in (r.x0, r.y0, r.x1, r.y1)]
        caixa = img[max(0, y0 - 3):y1 + 3, max(0, x0 - 6):x1 + 6].reshape(-1, 3).astype(float)
        cor = _dominante(caixa)
        if cor is not None:
            out[w[4]] = cor
    return out


def _amostra(img, x, y, raio=6):
    """Cor média da janela, sem traços pretos e hidrografia (azul); None se for fundo branco (fora do estado)."""
    jan = img[max(0, int(y) - raio):int(y) + raio + 1, max(0, int(x) - raio):int(x) + raio + 1].reshape(-1, 3).astype(float)
    if not len(jan):
        return None
    r, g, b = jan[:, 0], jan[:, 1], jan[:, 2]
    ok = (jan.max(axis=1) > 45) & ~((b > r + 40) & (b > g + 10))
    if ok.sum() < len(jan) * 0.4:
        return None
    return _dominante(jan)


def _classificar(img, x, y, leg):
    """Vota entre janelas em volta do ponto (borda de polígono, rio ou limite estadual não decidem sozinhos)."""
    from collections import Counter
    votos, gaps = Counter(), {}
    for dx in (-18, -9, 0, 9, 18):
        for dy in (-18, -9, 0, 9, 18):
            cor = _amostra(img, x + dx, y + dy)
            if cor is None:
                continue
            dist = sorted((float(np.linalg.norm(cor - c)), cod) for cod, c in leg.items())
            peso = 3 if (dx, dy) == (0, 0) else 2 if abs(dx) + abs(dy) <= 9 else 1
            votos[dist[0][1]] += peso
            gaps.setdefault(dist[0][1], []).append((dist[1][0] if len(dist) > 1 else 999) - dist[0][0])
    if not votos:
        return None, None
    (cod, v1), *resto = votos.most_common()
    v2 = resto[0][1] if resto else 0
    total = sum(votos.values())
    conf = "alta" if v1 / total >= 0.75 else "média" if v1 / total >= 0.5 else "baixa – conferir na carta"
    return cod, conf


def localizar(doc, lat, lon, cache=None):
    """(folha, código, confiança) da subunidade num ponto (lat/lon WGS84)."""
    from pyproj import Transformer
    f = next((f for f in folhas(doc) if f["lat"][0] <= lat <= f["lat"][1] and f["lon"][0] <= lon <= f["lon"][1]), None)
    if not f:
        return None, None, None
    pag = doc[f["pag_mapa"]]
    mer = re.search(r"Meridiano (\d+)º", pag.get_text())
    zona = int((180 - int(mer.group(1))) / 6) + 1 if mer else int((lon + 180) / 6) + 1
    epsg = 29170 + zona  # SAD 69 / UTM zona S (sistema das cartas)
    e, n = Transformer.from_crs(4326, epsg, always_xy=True).transform(lon, lat)
    chave = f["pag_mapa"]
    if cache is not None and chave in cache:
        img, geo, leg = cache[chave]
    else:
        pix = pag.get_pixmap(dpi=DPI)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
        geo, leg = _georef(pag, f, epsg), None
        leg = _legenda(pag, img)
        if cache is not None:
            cache[chave] = (img, geo, leg)
    if not geo or not leg:
        return f, None, None
    cod, confianca = _classificar(img, *geo(e, n), leg)
    return f, cod, confianca


# ------------------------------------------------------------------ projeto
def para_projeto(chave):
    from ferramentas.geo.tematico import unidades
    cfg = projeto(chave)
    u, _ = unidades(cfg)
    uw = u.to_crs(4326)
    doc = _doc()
    cache, res = {}, {}
    for (_, row), (_, roww) in zip(u.iterrows(), uw.iterrows()):
        g = roww.geometry
        pts = [g.centroid] if not g.geom_type.endswith("LineString") else [g.interpolate(t, normalized=True) for t in (0, .5, 1)]
        achados = []
        for p in pts:
            f, cod, conf = localizar(doc, p.y, p.x, cache)
            if cod:
                achados.append((cod, conf, f))
        if not achados:
            res[row["nome"]] = None
            continue
        cod = max({a[0] for a in achados}, key=lambda c: sum(a[0] == c for a in achados))
        conf = next(a[1] for a in achados if a[0] == cod)
        f = next(a[2] for a in achados if a[0] == cod)
        res[row["nome"]] = {"codigo": cod, "folha": f["nome"], "confianca": conf,
                            "outras": sorted({a[0] for a in achados} - {cod})}
    subs = {}
    for nome, r in res.items():
        if not r:
            continue
        f = next(x for x in folhas(doc) if x["nome"] == r["folha"])
        d = subunidades_da_folha(doc, f).get(r["codigo"], {})
        subs.setdefault(r["codigo"], {"codigo": r["codigo"], "nome": d.get("nome"), "unidade": d.get("unidade"),
                                      "folha": r["folha"], "texto": d.get("texto"), "unidades_projeto": []})
        subs[r["codigo"]]["unidades_projeto"].append(nome)
    planaltos = {}
    for s in subs.values():
        if s["unidade"] and s["unidade"] not in planaltos:
            planaltos[s["unidade"]] = texto_planalto(doc, s["unidade"])
    biblio.usar(chave, [biblio.registrar("oka-fiori-2006", ABNT.format(acesso=biblio.data_acesso()), "base", URL, CIT)])
    d = cfg["dir"] / "dados"
    dados = {"fonte": CIT, "por_unidade": res, "subunidades": list(subs.values()), "planaltos": planaltos}
    (d / "geomorfologia_pr.yaml").write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=False), encoding="utf-8")
    md = [f"# Geomorfologia – Atlas Geomorfológico do Paraná ({CIT}) – {cfg['municipio']}", ""]
    for nome, r in res.items():
        md.append(f"- {nome}: " + (f"{r['codigo']} (folha {r['folha']}; confiança {r['confianca']}"
                                   + (f"; traçado também em {', '.join(r['outras'])}" if r["outras"] else "") + ")"
                                   if r else "fora das folhas do atlas / não identificado"))
    for s in subs.values():
        md += ["", f"## {s['codigo']} – {s['nome']} ({s['unidade']})", "", s["texto"] or ""]
    for un, tx in planaltos.items():
        md += ["", f"## {un}", "", tx or ""]
    (d / "GEOMORFOLOGIA_PR.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return dados


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ponto"); p.add_argument("lat", type=float); p.add_argument("lon", type=float)
    pj = sub.add_parser("projeto"); pj.add_argument("chave")
    a = ap.parse_args()
    if a.cmd == "ponto":
        doc = _doc()
        f, cod, conf = localizar(doc, a.lat, a.lon)
        print(f"Folha: {f['nome'] if f else '-'} | subunidade: {cod} | confiança: {conf}")
        if f and cod:
            s = subunidades_da_folha(doc, f).get(cod, {})
            print(s.get("nome"), "-", s.get("unidade"))
            print(s.get("texto"))
    else:
        r = para_projeto(a.chave)
        for nome, x in r["por_unidade"].items():
            print(nome, "->", x)
        print("-> dados/GEOMORFOLOGIA_PR.md")


if __name__ == "__main__":
    main()
