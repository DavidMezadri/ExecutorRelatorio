"""Busca e baixa imagens com licença livre no Wikimedia Commons, registrando os créditos.

Uso:
    python -m ferramentas.imagens.web "Araucaria angustifolia" [-n 4] [--projeto candoi] [--so-listar]

Salva em projetos/<chave>/imagens/ (ou ./imagens) e acrescenta em CREDITOS.yaml: título, autor, licença,
URL e a string pronta para o campo fonte= da figura. Só aceita licenças livres (CC0, CC BY, CC BY-SA, domínio público).
"""
import argparse
import re
from pathlib import Path

import requests
import yaml

from ferramentas.util import console_utf8, projeto, slug

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "ExecutorRelatorio/1.0 (relatorios ambientais; contato via repositório)"}
LIVRES = ("cc0", "cc by", "cc-by", "public domain", "domínio público", "pd")


def _limpa_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def buscar(termo, n=4, largura=1600):
    params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": f"{termo} filetype:bitmap",
              "gsrnamespace": 6, "gsrlimit": n * 3, "prop": "imageinfo", "iiprop": "url|extmetadata|size",
              "iiurlwidth": largura}
    dados = requests.get(API, params=params, headers=UA, timeout=60).json()
    res = []
    for pag in sorted(dados.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)):
        info = (pag.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = _limpa_html(meta.get("LicenseShortName", {}).get("value", ""))
        if not any(l in lic.lower() for l in LIVRES):
            continue
        res.append({
            "titulo": pag["title"].replace("File:", ""),
            "autor": _limpa_html(meta.get("Artist", {}).get("value", "")) or "Desconhecido",
            "licenca": lic,
            "pagina": info.get("descriptionurl"),
            "url": info.get("thumburl") or info.get("url"),
            "descricao": _limpa_html(meta.get("ImageDescription", {}).get("value", ""))[:200],
        })
        if len(res) >= n:
            break
    return res


def baixar(itens, destino: Path):
    destino.mkdir(parents=True, exist_ok=True)
    cred_path = destino / "CREDITOS.yaml"
    creditos = yaml.safe_load(cred_path.read_text(encoding="utf-8")) if cred_path.exists() else {}
    for it in itens:
        ext = Path(it["url"].split("?")[0]).suffix.lower() or ".jpg"
        nome = slug(Path(it["titulo"]).stem)[:60] + ext
        (destino / nome).write_bytes(requests.get(it["url"], headers=UA, timeout=120).content)
        it["fonte"] = f"{it['autor']}, Wikimedia Commons ({it['licenca']})."
        creditos[nome] = it
        print(f"  {nome}  ->  fonte=\"{it['fonte']}\"")
    cred_path.write_text(yaml.safe_dump(creditos, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("termo")
    ap.add_argument("-n", type=int, default=4)
    ap.add_argument("--projeto")
    ap.add_argument("--so-listar", action="store_true")
    a = ap.parse_args()
    itens = buscar(a.termo, a.n)
    if not itens:
        print("Nenhuma imagem com licença livre encontrada.")
        return
    for it in itens:
        print(f"- {it['titulo']} | {it['autor']} | {it['licenca']}\n  {it['pagina']}")
    if not a.so_listar:
        destino = projeto(a.projeto)["dir"] / "imagens" if a.projeto else Path("imagens")
        baixar(itens, destino)
        print(f"Créditos em {destino / 'CREDITOS.yaml'}")


if __name__ == "__main__":
    main()
