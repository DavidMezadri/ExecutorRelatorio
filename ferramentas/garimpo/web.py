"""Acesso web comum aos garimpeiros: cabeçalhos de navegador, cache, correção de encoding, HTML -> texto."""
import hashlib
import re
import time
from pathlib import Path

import requests

from ferramentas.util import RAIZ

CACHE = RAIZ / "dados_comuns" / "cache" / "web"
NAVEGADOR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}
API = {"User-Agent": "ExecutorRelatorio/1.0 (relatorios ambientais)"}


def obter(url, params=None, json=False, cache_horas=24 * 7, timeout=90, cabecalhos=None, binario=False):
    """GET com cache em disco (padrão 7 dias). Retorna texto, bytes ou JSON."""
    chave = hashlib.md5((url + repr(sorted((params or {}).items()))).encode()).hexdigest()
    arq = CACHE / chave
    if arq.exists() and time.time() - arq.stat().st_mtime < cache_horas * 3600:
        dados = arq.read_bytes()
    else:
        cab = cabecalhos or (API if json else NAVEGADOR)
        try:
            r = requests.get(url, params=params, headers=cab, timeout=timeout)
        except requests.exceptions.SSLError:
            # alguns servidores públicos (IBGE, FUNAI) às vezes têm a cadeia de certificados incompleta;
            # para LEITURA de dado público refaz sem verificar e avisa.
            import urllib3
            urllib3.disable_warnings()
            print(f"  (aviso: certificado SSL inválido em {url.split('/')[2]}; leitura sem verificação)")
            r = requests.get(url, params=params, headers=cab, timeout=timeout, verify=False)
        r.raise_for_status()
        dados = r.content
        CACHE.mkdir(parents=True, exist_ok=True)
        arq.write_bytes(dados)
    if binario:
        return dados
    if json:
        import json as _j
        return _j.loads(dados)
    return decodificar(dados)


def decodificar(dados: bytes) -> str:
    m = re.search(rb'charset=["\']?([\w-]+)', dados[:3000], re.I)
    for enc in ([m.group(1).decode()] if m else []) + ["utf-8", "cp1252"]:
        try:
            return dados.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return dados.decode("utf-8", "replace")


def html_texto(html: str, remover_riscado=False) -> str:
    """HTML -> texto com quebras de parágrafo (remove script/style/nav).

    remover_riscado=True descarta <strike>/<s>/<del>: no Planalto, é a redação revogada que aparece
    antes da vigente – essencial para citar legislação corretamente.
    """
    h = re.sub(r"(?is)<(script|style|nav|header|footer|noscript)[^>]*>.*?</\1>", " ", html)
    if remover_riscado:
        h = _sem_riscado(h)
    h = re.sub(r"(?i)<sup>\s*o(s?)\s*</sup>", r"º\1", h)
    h = re.sub(r"(?i)<sup>\s*a(s?)\s*</sup>", r"ª\1", h)
    h = h.replace("\r", "")
    h = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h\d>|</li>|</tr>", "\n", h)
    h = re.sub(r"(?i)</?(td|th|table|tbody|thead|ul|ol|section|article|blockquote)\b[^>]*>", "\n", h)
    h = re.sub(r"<[^>]+>", "", h)  # tags de texto (span, a, b, font...) saem sem inserir espaço: não partem palavras
    import html as _h
    h = _h.unescape(h)
    h = re.sub(r"[ \t\xa0]+", " ", h)
    h = re.sub(r"\n\s*\n+", "\n\n", h)
    return h.strip()


def _sem_riscado(html: str) -> str:
    """Remove elementos riscados (<strike>, <s>, <del> ou style 'line-through'), preservando o texto seguinte."""
    import lxml.html
    raiz = lxml.html.fromstring(html)
    alvos = raiz.xpath("//strike | //s | //del | //*[contains(translate(@style, ' ', ''), 'line-through')]")
    for el in alvos:
        if el.getparent() is not None:
            el.drop_tree()  # drop_tree mantém o .tail (texto após o elemento)
    return lxml.html.tostring(raiz, encoding="unicode")


def titulo_html(html: str) -> str | None:
    for rx in (r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', r"<title[^>]*>(.*?)</title>"):
        m = re.search(rx, html, re.I | re.S)
        if m:
            import html as _h
            return re.sub(r"\s+", " ", _h.unescape(m.group(1))).strip()
    return None
