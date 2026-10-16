"""Características das classes de solo (SiBCS) nas páginas da Embrapa – Ageitec, com referência ABNT e foto do perfil.

Uso:
    python -m ferramentas.garimpo.solos classe "Cambissolo Húmico Alumínico"     # mostra o que a página traz
    python -m ferramentas.garimpo.solos projeto <chave>                        # classes do mapa IBGE do projeto

Para cada classe do mapa pedológico do IBGE (ordem + subordem + grande grupo), abre a página da subordem na Ageitec
(Embrapa Solos – Sistema Brasileiro de Classificação de Solos), extrai: texto de caracterização, quadro do 3º nível
(grandes grupos: características e implicações de uso), autores, data de publicação e fotos do perfil
("Fonte: Acervo da Embrapa Solos"). É a mesma fonte usada no MODELO Palmeira (EMBRAPA, 2021).
Gera referencias/web/solos/<pagina>.md (texto para leitura) e, por projeto, dados/SOLOS_EMBRAPA.md +
dados/solos_embrapa.yaml (usado pelo redator em {{auto.pedologia}}), fotos em imagens/ e referências no catálogo.
"""
import argparse
import datetime as dt
import re
import shutil
import unicodedata

import yaml
from lxml import html

from ferramentas.util import console_utf8, projeto, slug, RAIZ
from ferramentas.garimpo import web, biblio

BASE = "https://www.embrapa.br/agencia-de-informacao-tecnologica/tematicas/solos-tropicais/sibcs/chave-do-sibcs"
PASTA = RAIZ / "referencias" / "web" / "solos"
CACHE_H = 24 * 90


def _norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"s\b", "", w) for w in re.split(r"[\s]+", s.replace("–", "-").strip()))


def _txt(e):
    return re.sub(r"\s+", " ", e.text_content()).strip()


def indice():
    """{nome normalizado: (nome, url)} de todas as ordens/subordens do menu da Ageitec."""
    d = html.fromstring(web.obter(f"{BASE}/cambissolos", cache_horas=CACHE_H))
    out = {}
    for a in d.xpath("//a[contains(@href,'chave-do-sibcs/')]"):
        nome, url = _txt(a), a.get("href").replace("/web/agencia", "/agencia")
        if nome and nome != "Chave do SiBCS":
            out[_norm(nome)] = (nome, url)
    return out


def localizar(classe_ibge):
    """'Cambissolo Húmico Alumínico' -> (nome da página, url, grande grupo 'Alumínico')."""
    nome = re.sub(r"^[A-Za-z]{1,6}\d*\s*-\s*", "", classe_ibge).strip()  # tira sigla do IBGE ("CHa - ")
    pal = nome.split()
    if not pal:
        return None
    idx = indice()
    sub = " ".join(pal[:2])
    ggrupo = pal[2] if len(pal) > 2 else None
    if _norm(sub) in idx:
        return (*idx[_norm(sub)], ggrupo)
    # subordem com hífen ("Vermelho-Amarelo") ou grafia diferente: tenta por prefixo
    for k, v in idx.items():
        if " " in k and _norm(sub).startswith(k.split()[0]) and k.split()[1][:5] == _norm(sub).split()[-1][:5]:
            return (*v, ggrupo)
    if _norm(pal[0]) in idx:  # só a ordem
        return (*idx[_norm(pal[0])], ggrupo)
    return None


BLOCO = {"p", "span", "td", "h4", "li"}


def _blocos(corpo):
    """Blocos de texto em ordem: p/span/td/li de nível mais alto (o texto da Ageitec mistura <p>, <span> soltos
    e legendas dentro de tabelas)."""
    for e in corpo.iter():
        if not isinstance(e.tag, str) or e.tag not in BLOCO:
            continue
        a, dentro = e.getparent(), False
        while a is not None and a is not corpo:
            if a.tag in BLOCO:
                dentro = True
                break
            a = a.getparent()
        if not dentro:
            yield e


def ler_pagina(url):
    """Texto, quadro do 3º nível, autores, ano e figuras de uma página da Ageitec."""
    d = html.fromstring(web.obter(url, cache_horas=CACHE_H))
    titulo = next((_txt(h) for h in d.xpath("//h1") if "Ageitec" not in _txt(h)), "")
    corpo = next((c for c in d.xpath("//div[contains(@class,'embp-news-detailed')]") if "Autores" in _txt(c)), None)
    tudo = _txt(d)
    m = re.search(r"(?:migrado na íntegra em|Publicado em|Atualizado em):?\s*(\d{2})/(\d{2})/(\d{4})", tudo)
    ano = m.group(3) if m else None
    autores, intro, quadro3, figuras = [], [], {}, []
    if corpo is not None:
        ps = [t for t in (_txt(e) for e in _blocos(corpo)) if t]
        i = ps.index("Autores") + 1 if "Autores" in ps else 0
        while i < len(ps) and re.match(r"^[A-ZÁÉÍÓÚ][\wÀ-ú.' ]+ - [\wÀ-ú .()-]+$", ps[i]) and len(ps[i]) < 90:
            autores.append(ps[i].split(" - ")[0].strip())
            i += 1
        estado = "intro"
        pend = None
        for p in ps[i:]:
            if p.startswith("Figura"):
                mf = re.match(r"Figura\s*\d+\s*:\s*(.+?)\.?\s*(?:Fonte:\s*(.+))?$", p)
                if mf:
                    figuras.append({"legenda": mf.group(1).strip(), "fonte": (mf.group(2) or "").strip()})
                continue
            if p.startswith("Fonte:"):  # fonte da figura em bloco separado
                if figuras and not figuras[-1]["fonte"]:
                    figuras[-1]["fonte"] = p[6:].strip()
                continue
            if p.startswith("Foto:"):
                continue
            if p.startswith("Terceiro nível categórico"):
                estado = "pre3"
                continue
            if p.startswith("Quarto nível categórico"):
                break
            if estado == "intro":
                intro.append(re.sub(r"\s*\(Figuras? [\d ,e]+\)", "", p))
            elif estado == "pre3":
                if p in ("Terceiro nível", "Características"):
                    estado = "tab3"
                continue
            elif estado == "tab3":
                if p in ("Terceiro nível", "Características"):
                    continue
                if pend is None:
                    pend = p
                else:
                    quadro3[pend] = p
                    pend = None
        imgs = [im.get("src") for im in corpo.iter("img") if "/documents/" in (im.get("src") or "")]
        for f, src in zip(figuras, imgs):
            f["url"] = ("https://www.embrapa.br" + src) if src.startswith("/") else src
    # a página às vezes repete frases (blocos duplicados no HTML): mantém só a 1ª ocorrência de cada frase
    vistas, limpo = [], []
    for par in intro:
        novas = []
        for f in (f for f in re.split(r"(?<=[.!?])\s+", par) if f.strip()):
            pal = set(re.findall(r"\w{4,}", f.lower()))
            # repetida ou quase igual (mesma ideia reescrita, > 60% das palavras em comum)
            if any(pal and len(pal & v) / len(pal | v) > 0.6 for v in vistas):
                continue
            vistas.append(pal)
            novas.append(f)
        if novas:
            limpo.append(" ".join(novas))
    intro = limpo
    return {"titulo": titulo, "url": url, "autores": autores, "ano": ano, "intro": intro,
            "terceiro_nivel": quadro3, "figuras": figuras}


def abnt(p):
    autores = ", ".join(p["autores"])
    return (f"EMBRAPA. Empresa Brasileira de Pesquisa Agropecuária. {p['titulo']}. "
            + (f"Autores: {autores}. " if autores else "")
            + "In: Agência de Informação Tecnológica (Ageitec) – Solos Tropicais, Sistema Brasileiro de Classificação "
            f"de Solos (SiBCS). Brasília, DF: Embrapa, {p['ano'] or '[20--]'}{{letra}}. Disponível em: {p['url']}. "
            f"Acesso em: {biblio.data_acesso()}.")


def _salvar_leitura(p):
    PASTA.mkdir(parents=True, exist_ok=True)
    md = [f"# {p['titulo']}", "", f"Fonte: {p['url']}", f"Autores: {', '.join(p['autores'])}", f"Ano: {p['ano']}", ""]
    md += p["intro"] + ["", "## Terceiro nível (grandes grupos)", ""]
    md += [f"- **{k}**: {v}" for k, v in p["terceiro_nivel"].items()]
    md += ["", "## Figuras", ""] + [f"- {f['legenda']} (Fonte: {f['fonte']}) {f.get('url', '')}" for f in p["figuras"]]
    (PASTA / f"{slug(p['titulo'])}.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def _grande_grupo(quadro, gg):
    if not gg:
        return None, None
    alvo = _norm(gg)
    for k, v in quadro.items():  # 1º nome exato (Alumínico != Aluminoférrico), depois prefixo
        if _norm(k) == alvo:
            return k, v
    for k, v in quadro.items():
        if _norm(k).startswith(alvo[:7]) or alvo.startswith(_norm(k)[:7]):
            return k, v
    return None, None


def para_projeto(chave, classes):
    """classes: nomes do mapa IBGE (na ordem de importância). Registra referências (com letra a, b... para o mesmo
    ano) e copia a 1ª foto de cada página para imagens/. Retorna lista de dicts para o redator."""
    cfg = projeto(chave)
    vistos, saida = {}, []
    for cl in classes:
        loc = localizar(cl)
        if not loc:
            saida.append({"classe": cl, "encontrada": False})
            continue
        nome_pag, url, gg = loc
        if url not in vistos:
            p = ler_pagina(url)
            _salvar_leitura(p)
            vistos[url] = p
        p = vistos[url]
        k3, d3 = _grande_grupo(p["terceiro_nivel"], gg)
        saida.append({"classe": cl, "encontrada": True, "pagina": p["titulo"], "url": url, "ano": p["ano"],
                      "intro": p["intro"], "grande_grupo": k3, "grande_grupo_desc": d3, "figuras": p["figuras"]})
    # letras para várias páginas da Embrapa no mesmo ano (ABNT: 2021a, 2021b...)
    por_ano = {}
    for s in saida:
        if s.get("encontrada"):
            por_ano.setdefault(s["ano"], [])
            if s["url"] not in por_ano[s["ano"]]:
                por_ano[s["ano"]].append(s["url"])
    chaves = []
    for s in saida:
        if not s.get("encontrada"):
            continue
        urls = por_ano[s["ano"]]
        letra = "abcdefghij"[urls.index(s["url"])] if len(urls) > 1 else ""
        ano = s["ano"] or "[20--]"
        s["citacao"] = f"EMBRAPA, {ano}{letra}"
        ref_chave = f"{chave}-embrapa-sibcs-{slug(s['pagina'])}"  # por projeto: a letra depende das outras páginas
        biblio.registrar(ref_chave, abnt(vistos[s["url"]]).replace("{letra}", letra), "web", s["url"], s["citacao"])
        chaves.append(ref_chave)
        # foto do perfil (1ª figura da página)
        if s["figuras"] and s["figuras"][0].get("url"):
            dest = cfg["dir"] / "imagens" / f"solo_{slug(s['pagina'])}.jpg"
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    dest.write_bytes(web.obter(s["figuras"][0]["url"], binario=True, cache_horas=CACHE_H))
                except Exception as e:
                    print(f"  (foto não baixada: {e.__class__.__name__})")
            if dest.exists():
                s["foto"] = f"imagens/{dest.name}"
                s["foto_legenda"] = s["figuras"][0]["legenda"]
                s["foto_fonte"] = f"{s['figuras'][0]['fonte']} ({s['citacao']})."
    biblio.usar(chave, list(dict.fromkeys(chaves)))
    d = cfg["dir"] / "dados"
    (d / "solos_embrapa.yaml").write_text(yaml.safe_dump({"gerado_em": str(dt.date.today()), "classes": saida},
                                                         allow_unicode=True, sort_keys=False), encoding="utf-8")
    md = [f"# Classes de solo – Embrapa/Ageitec (SiBCS) – {cfg['municipio']}", ""]
    for s in saida:
        if not s.get("encontrada"):
            md += [f"## {s['classe']}", "", "- Página não encontrada na Ageitec: descrever com outra fonte.", ""]
            continue
        md += [f"## {s['classe']} -> {s['pagina']} ({s['citacao']})", "", f"{s['url']}", ""] + s["intro"]
        if s["grande_grupo"]:
            md += ["", f"**3º nível – {s['grande_grupo']}**: {s['grande_grupo_desc']}"]
        if s.get("foto"):
            md += ["", f"Foto: {s['foto']} – {s['foto_legenda']} (Fonte: {s['foto_fonte']})"]
        md.append("")
    (d / "SOLOS_EMBRAPA.md").write_text("\n".join(md), encoding="utf-8")
    return saida


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classe"); c.add_argument("nome")
    pj = sub.add_parser("projeto"); pj.add_argument("chave")
    a = ap.parse_args()
    if a.cmd == "classe":
        loc = localizar(a.nome)
        if not loc:
            print("Classe não encontrada na Ageitec")
            return
        p = ler_pagina(loc[1])
        print(f"{p['titulo']} ({p['ano']}) – {', '.join(p['autores'])}\n{p['url']}\n")
        print("\n\n".join(p["intro"]))
        k, v = _grande_grupo(p["terceiro_nivel"], loc[2])
        if k:
            print(f"\n3º nível – {k}: {v}")
        print("\nFiguras:", *[f"- {f['legenda']} ({f['fonte']})" for f in p["figuras"]], sep="\n")
    else:
        from ferramentas.redacao.redator import Redator
        r = Redator(projeto(a.chave))
        classes = [c for c, pct in (r.ponderado("solos") or {}).items() if pct >= 1 and not c.lower().startswith("área urbana")]
        for s in para_projeto(a.chave, classes):
            print(f"{s['classe']}: " + (f"{s['pagina']} ({s['citacao']}), 3º nível: {s['grande_grupo']}"
                                        if s.get("encontrada") else "NÃO encontrada"))


if __name__ == "__main__":
    main()
