"""Leitura de projetos AutoCAD (DXF; DWG via ODA File Converter) para quantitativos e geometria.

Uso:
    python -m ferramentas.ingestao.cad candoi                  # lê projetos/<chave>/cad/*.dxf|*.dwg
    python -m ferramentas.ingestao.cad --arquivo projeto.dxf [--epsg 31982]

Para cada desenho:
  - inventário por camada (layer): entidades, extensão total das linhas/polilinhas, blocos, textos
  - extensão por diâmetro: textos "DN 150", "DE160", "Ø200" são associados à linha mais próxima
  - blocos contados por nome (PV, registros, ventosas, hidrantes...)
  - georreferenciamento: se as coordenadas estão em UTM (SIRGAS 2000), exporta dados/cad_<nome>.gpkg e
    compara com as unidades do KMZ (deslocamento); senão avisa que o desenho está em coordenadas locais
Gera dados/CAD_<nome>.md e dados/cad_quantitativos.xlsx (abas por desenho) – usar com !quadro no texto.

DWG: instale o ODA File Converter (gratuito, opendesign.com) ou exporte do AutoCAD como DXF (Salvar como > DXF).
"""
import argparse
import glob
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

import pandas as pd

from ferramentas.util import console_utf8, projeto

RX_DN = re.compile(r"\b(?:DN|DE|Ø|Ф)\s?(\d{2,4})\b", re.I)
LINEARES = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "SPLINE"}


def oda_converter():
    for padrao in (r"C:\Program Files\ODA\ODAFileConverter*\ODAFileConverter.exe",
                   r"C:\Program Files (x86)\ODA\ODAFileConverter*\ODAFileConverter.exe"):
        achados = glob.glob(padrao)
        if achados:
            return achados[-1]
    return shutil.which("ODAFileConverter")


def dwg_para_dxf(dwg: Path) -> Path:
    exe = oda_converter()
    if not exe:
        raise SystemExit(f"{dwg.name}: é DWG e o ODA File Converter não está instalado. Instale-o (gratuito) ou exporte "
                         "do AutoCAD como DXF e coloque na mesma pasta.")
    saida = Path(tempfile.mkdtemp())
    subprocess.run([exe, str(dwg.parent), str(saida), "ACAD2018", "DXF", "0", "1", dwg.name], check=True)
    dxf = saida / (dwg.stem + ".dxf")
    if not dxf.exists():
        raise SystemExit(f"Conversão de {dwg.name} falhou.")
    return dxf


def _pontos(e):
    t = e.dxftype()
    if t == "LINE":
        return [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
    if t == "LWPOLYLINE":
        return [(p[0], p[1]) for p in e.get_points("xy")]
    if t == "POLYLINE":
        return [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
    if t in ("ARC", "SPLINE"):
        try:
            return [(p.x, p.y) for p in e.flattening(0.5)]
        except Exception:
            return []
    return []


def _texto(e):
    if e.dxftype() == "TEXT":
        return e.dxf.text, (e.dxf.insert.x, e.dxf.insert.y)
    if e.dxftype() == "MTEXT":
        return e.plain_text(), (e.dxf.insert.x, e.dxf.insert.y)
    return None, None


def eh_utm(x, y):
    return 100_000 <= x <= 900_000 and 6_000_000 <= y <= 10_000_000


def ler(dxf: Path):
    import ezdxf
    from shapely.geometry import LineString, Point
    doc = ezdxf.readfile(str(dxf))
    msp = doc.modelspace()
    unidade = {0: "sem unidade", 1: "polegadas", 2: "pés", 4: "mm", 5: "cm", 6: "m"}.get(doc.header.get("$INSUNITS", 0), "?")
    linhas, textos, blocos = [], [], defaultdict(int)
    camadas = defaultdict(lambda: {"entidades": 0, "extensao": 0.0, "blocos": 0, "textos": 0})
    for e in msp:
        cam = e.dxf.layer
        camadas[cam]["entidades"] += 1
        t = e.dxftype()
        if t in LINEARES:
            pts = _pontos(e)
            if len(pts) >= 2:
                g = LineString(pts)
                linhas.append({"camada": cam, "geom": g})
                camadas[cam]["extensao"] += g.length
        elif t in ("TEXT", "MTEXT"):
            txt, pos = _texto(e)
            if txt and txt.strip():
                textos.append({"camada": cam, "texto": " ".join(txt.split()), "pos": Point(pos)})
                camadas[cam]["textos"] += 1
        elif t == "INSERT":
            blocos[e.dxf.name] += 1
            camadas[cam]["blocos"] += 1
    # diâmetro por linha: texto "DN xxx" mais próximo (até 30 unidades do desenho)
    dn_txt = [(int(m.group(1)), t["pos"]) for t in textos for m in [RX_DN.search(t["texto"])] if m]
    por_dn = defaultdict(float)
    for l in linhas:
        if dn_txt:
            dn, pos = min(dn_txt, key=lambda d: d[1].distance(l["geom"]))
            if pos.distance(l["geom"]) <= 30:
                l["dn"] = dn
                por_dn[dn] += l["geom"].length
    xs = [c for l in linhas for c in l["geom"].bounds[::2]]
    ys = [c for l in linhas for c in l["geom"].bounds[1::2]]
    bbox = (min(xs), min(ys), max(xs), max(ys)) if xs else None
    georef = bool(bbox and eh_utm(bbox[0], bbox[1]) and eh_utm(bbox[2], bbox[3]))
    return {"arquivo": dxf.name, "unidade": unidade, "camadas": dict(camadas), "linhas": linhas, "textos": textos,
            "blocos": dict(blocos), "por_dn": dict(por_dn), "bbox": bbox, "georef": georef}


def exportar_gpkg(r, destino: Path, epsg: str):
    import geopandas as gpd
    g = gpd.GeoDataFrame([{"camada": l["camada"], "dn": l.get("dn"), "extensao_m": round(l["geom"].length, 2)}
                          for l in r["linhas"]], geometry=[l["geom"] for l in r["linhas"]], crs=epsg)
    g.to_file(destino, driver="GPKG")
    return g


def comparar_kmz(cfg, g):
    import geopandas as gpd
    u = cfg["dir"] / "dados" / "unidades.gpkg"
    if not u.exists() or g.empty:
        return None
    un = gpd.read_file(u).to_crs(g.crs)
    dist = un.geometry.union_all().distance(g.geometry.union_all())
    return round(dist, 1)


def relatorio(r, comparacao=None) -> str:
    br = lambda v, c=0: f"{v:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    out = [f"# Projeto AutoCAD – {r['arquivo']}\n",
           f"- Unidade do desenho: {r['unidade']}",
           f"- Georreferenciado em UTM: {'sim' if r['georef'] else 'NÃO (coordenadas locais)'}"]
    if r["bbox"]:
        out.append(f"- Extensão do desenho: E {br(r['bbox'][0])}–{br(r['bbox'][2])}; N {br(r['bbox'][1])}–{br(r['bbox'][3])}")
    if comparacao is not None:
        out.append(f"- Distância entre o desenho e as unidades do KMZ: {br(comparacao, 1)} m "
                   f"({'coerente' if comparacao < 50 else 'VERIFICAR: desenho e KMZ não coincidem'})")
    out.append("\n## Camadas\n\n| Camada | Entidades | Extensão | Blocos | Textos |\n|---|---|---|---|---|")
    for c, v in sorted(r["camadas"].items(), key=lambda x: -x[1]["extensao"]):
        out.append(f"| {c} | {v['entidades']} | {br(v['extensao'], 1)} | {v['blocos']} | {v['textos']} |")
    if r["por_dn"]:
        out.append("\n## Extensão por diâmetro (texto DN mais próximo de cada linha)\n\n| Diâmetro | Extensão |\n|---|---|")
        out += [f"| DN {dn} | {br(ext, 1)} |" for dn, ext in sorted(r["por_dn"].items())]
    if r["blocos"]:
        out.append("\n## Blocos (símbolos)\n\n| Bloco | Quantidade |\n|---|---|")
        out += [f"| {b} | {n} |" for b, n in sorted(r["blocos"].items(), key=lambda x: -x[1])]
    rel = sorted({t["texto"] for t in r["textos"] if re.search(r"ETE|ETA|EEE|EEB|EET|RAP|REL|PV|captação|reservat|adutora|emiss|interceptor|DN|Rio|Rua", t["texto"], re.I)})
    if rel:
        out.append("\n## Textos relevantes do desenho\n")
        out += [f"- {t}" for t in rel[:80]]
    return "\n".join(out) + "\n"


def processar(arquivos, cfg=None, epsg=None):
    resultados = []
    planilhas = {}
    for arq in arquivos:
        dxf = dwg_para_dxf(arq) if arq.suffix.lower() == ".dwg" else arq
        r = ler(dxf)
        r["arquivo"] = arq.name
        comp = None
        if r["georef"] and (cfg or epsg):
            from ferramentas.geo.coordenadas import fuso_utm
            if not epsg and cfg:
                import geopandas as gpd
                u = gpd.read_file(cfg["dir"] / "dados" / "unidades.gpkg").to_crs("EPSG:4674")
                c = u.geometry.union_all().centroid
                epsg = fuso_utm(c.x, c.y)
            if cfg:
                g = exportar_gpkg(r, cfg["dir"] / "dados" / f"cad_{arq.stem}.gpkg", epsg)
                comp = comparar_kmz(cfg, g)
        md = relatorio(r, comp)
        resultados.append((arq, md))
        planilhas[arq.stem[:28]] = pd.DataFrame(
            [{"camada": c, "extensao": round(v["extensao"], 2), "entidades": v["entidades"], "blocos": v["blocos"]}
             for c, v in r["camadas"].items()] +
            [{"camada": f"DN {dn}", "extensao": round(e, 2), "entidades": None, "blocos": None} for dn, e in sorted(r["por_dn"].items())])
    return resultados, planilhas


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave", nargs="?")
    ap.add_argument("--arquivo", nargs="*")
    ap.add_argument("--epsg")
    a = ap.parse_args()
    cfg = projeto(a.chave) if a.chave else None
    if a.arquivo:
        arqs = [Path(x) for x in a.arquivo]
    elif cfg:
        pasta = cfg["dir"] / "cad"
        pasta.mkdir(exist_ok=True)
        arqs = sorted(p for p in pasta.iterdir() if p.suffix.lower() in (".dxf", ".dwg"))
        if not arqs:
            raise SystemExit(f"Coloque os arquivos .dxf/.dwg em {pasta}")
    else:
        ap.error("informe a chave do projeto ou --arquivo")
    resultados, planilhas = processar(arqs, cfg, a.epsg)
    for arq, md in resultados:
        if cfg:
            (cfg["dir"] / "dados" / f"CAD_{arq.stem}.md").write_text(md, encoding="utf-8")
        print(md)
    if cfg and planilhas:
        with pd.ExcelWriter(cfg["dir"] / "dados" / "cad_quantitativos.xlsx") as w:
            for nome, df in planilhas.items():
                df.to_excel(w, sheet_name=nome, index=False)
        print(f"Quantitativos: {cfg['dir'] / 'dados' / 'cad_quantitativos.xlsx'}")


if __name__ == "__main__":
    main()
