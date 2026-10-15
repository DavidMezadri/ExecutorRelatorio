"""Transcrição local de áudios de campo (Whisper, offline) organizados por data.

Uso:
    python -m ferramentas.audio.transcrever candoi [--modelo small] [--refazer]
    python -m ferramentas.audio.transcrever candoi --observar [--intervalo 30]    # fica vigiando a pasta
    python -m ferramentas.audio.transcrever --arquivo gravacao.m4a                  # avulso, sem projeto

Coloque os áudios em projetos/<chave>/audios/AAAA-MM-DD/ (data da vistoria/reunião). Formatos de celular e
WhatsApp: m4a, mp3, ogg, opus, wav, aac, flac, mp4, webm, amr, 3gp.
Gera:
    audios/AAAA-MM-DD/<nome>.md     transcrição com marcação de tempo [mm:ss]
    extraido/transcricoes.md        todas as transcrições do projeto por data (fonte para a redação)

Modelos (baixados uma vez, ficam no cache): tiny, base, small (padrão: bom equilíbrio na CPU),
medium, large-v3 (mais preciso e mais lento). O vocabulário do projeto (unidades, município, termos de
saneamento) é passado ao modelo para acertar nomes técnicos.
"""
import argparse
import datetime as dt
import re
import time
from pathlib import Path

from ferramentas.util import console_utf8, projeto

EXTENSOES = {".m4a", ".mp3", ".ogg", ".opus", ".wav", ".aac", ".flac", ".mp4", ".webm", ".amr", ".3gp", ".wma"}
VOCAB = ("Sanepar, Biocerne, IAT, Instituto Água e Terra, MCE, PCA, ETA, ETE, EEE, EEB, adutora, AAB, AAT, "
         "reservatório, captação, outorga, APP, Área de Preservação Permanente, Reserva Legal, CAR, nascente, "
         "curso d'água, travessia, supressão de vegetação, Floresta Ombrófila Mista, araucária, erosão, "
         "desapropriação, servidão, emissário, interceptor, rede coletora, corpo receptor")
_MODELO = {}


def _modelo(nome):
    if nome not in _MODELO:
        from faster_whisper import WhisperModel
        print(f"Carregando modelo Whisper '{nome}' (na primeira vez é baixado)…", flush=True)
        _MODELO[nome] = WhisperModel(nome, device="cpu", compute_type="int8")
    return _MODELO[nome]


def _mmss(s):
    return f"{int(s // 60):02d}:{int(s % 60):02d}"


def _data_pasta(arq: Path):
    for parte in reversed(arq.parts):
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", parte)
        if m:
            return dt.date(*map(int, m.groups()))
    return dt.date.fromtimestamp(arq.stat().st_mtime)


def vocabulario(cfg=None):
    extra = []
    if cfg:
        extra.append(cfg["municipio"])
        u = cfg["dir"] / "dados" / "coordenadas.xlsx"
        if u.exists():
            import pandas as pd
            extra += sorted(set(pd.read_excel(u)["unidade"].astype(str)))
    return ", ".join(extra + [VOCAB])


def decodificar(arq: Path):
    """Áudio -> float32 mono 16 kHz (decodificação própria via PyAV: independe da versão usada pelo faster-whisper)."""
    import av
    import numpy as np
    partes = []
    with av.open(str(arq)) as cont:
        stream = next(s for s in cont.streams if s.type == "audio")
        reamostra = av.AudioResampler(format="s16", layout="mono", rate=16000)
        for pacote in cont.demux(stream):
            for quadro in pacote.decode():
                for q in reamostra.resample(quadro):
                    partes.append(q.to_ndarray().reshape(-1))
        for q in reamostra.resample(None):
            partes.append(q.to_ndarray().reshape(-1))
    if not partes:
        raise ValueError(f"sem áudio decodificável em {arq.name}")
    return np.concatenate(partes).astype(np.float32) / 32768.0


def transcrever(arq: Path, modelo="small", prompt=None) -> Path:
    segs, info = _modelo(modelo).transcribe(decodificar(arq), language="pt", vad_filter=True, beam_size=5,
                                            initial_prompt=prompt, condition_on_previous_text=True)
    linhas = [f"[{_mmss(s.start)}] {s.text.strip()}" for s in segs]
    data = _data_pasta(arq)
    md = arq.with_suffix(".md")
    md.write_text(
        f"# Transcrição – {arq.name}\n\n"
        f"- Data: {data:%d/%m/%Y}\n- Duração: {_mmss(info.duration)}\n- Modelo: Whisper {modelo} (local)\n"
        f"- Confiança do idioma ({info.language}): {info.language_probability:.0%}\n\n"
        "> Transcrição automática: conferir nomes próprios, números e medidas antes de usar no relatório.\n\n"
        + "\n".join(linhas) + "\n", encoding="utf-8")
    return md


def pendentes(pasta: Path, refazer=False):
    for a in sorted(p for p in pasta.rglob("*") if p.suffix.lower() in EXTENSOES):
        md = a.with_suffix(".md")
        if refazer or not md.exists() or md.stat().st_mtime < a.stat().st_mtime:
            yield a


def consolidar(cfg) -> Path:
    pasta = cfg["dir"] / "audios"
    mds = sorted(pasta.rglob("*.md"), key=lambda p: (_data_pasta(p), p.name))
    out = [f"# Transcrições de áudio – {cfg['documento']} {cfg['sistema']} {cfg['municipio']}\n",
           "Fonte para a redação: informação de campo/reunião. Citar como \"informação obtida em vistoria de campo "
           "realizada em DD/MM/AAAA\" (ou reunião). Conferir nomes e números com a equipe.\n"]
    data_atual = None
    for md in mds:
        d = _data_pasta(md)
        if d != data_atual:
            out.append(f"\n## {d:%d/%m/%Y}\n")
            data_atual = d
        corpo = md.read_text(encoding="utf-8").split("\n\n", 3)[-1]
        out.append(f"### {md.relative_to(pasta).as_posix()}\n\n{corpo.strip()}\n")
    destino = cfg["dir"] / "extraido" / "transcricoes.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(out) + "\n", encoding="utf-8")
    return destino


def processar(cfg, modelo, refazer=False):
    pasta = cfg["dir"] / "audios"
    pasta.mkdir(parents=True, exist_ok=True)
    feitos = 0
    prompt = vocabulario(cfg)
    for a in pendentes(pasta, refazer):
        t0 = time.time()
        print(f"  transcrevendo {a.relative_to(pasta)} …", flush=True)
        md = transcrever(a, modelo, prompt)
        print(f"  ok -> {md.name} ({time.time() - t0:.0f}s)", flush=True)
        feitos += 1
    if feitos or refazer:
        print(f"Consolidado: {consolidar(cfg)}")
    return feitos


def main():
    console_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chave", nargs="?")
    ap.add_argument("--arquivo")
    ap.add_argument("--modelo", default="small", choices=["tiny", "base", "small", "medium", "large-v3"])
    ap.add_argument("--refazer", action="store_true")
    ap.add_argument("--observar", action="store_true")
    ap.add_argument("--intervalo", type=int, default=30)
    a = ap.parse_args()
    if a.arquivo:
        print(transcrever(Path(a.arquivo), a.modelo, vocabulario()).read_text(encoding="utf-8"))
        return
    if not a.chave:
        ap.error("informe a chave do projeto ou --arquivo")
    cfg = projeto(a.chave)
    print(f"Pasta de áudios: {cfg['dir'] / 'audios'} (subpastas AAAA-MM-DD)")
    n = processar(cfg, a.modelo, a.refazer)
    if not a.observar:
        print(f"{n} áudio(s) transcrito(s).")
        return
    print(f"Observando a pasta a cada {a.intervalo}s (Ctrl+C para sair)…")
    try:
        while True:
            time.sleep(a.intervalo)
            processar(cfg, a.modelo)
    except KeyboardInterrupt:
        print("Encerrado.")


if __name__ == "__main__":
    main()
