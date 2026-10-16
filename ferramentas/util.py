"""Utilitários comuns: caminhos, registro de projetos, console UTF-8."""
import sys
import unicodedata
import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
PROJETOS_DIR = RAIZ / "projetos"
REGISTRO = RAIZ / "projetos.yaml"


def console_utf8():
    """Evita erro de acentuação no console do Windows."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def _registro_completo() -> dict:
    with open(REGISTRO, encoding="utf-8") as f:
        return yaml.safe_load(f)


def carregar_registro() -> dict:
    return _registro_completo()["projetos"]


def corrigir_nome(texto: str) -> str:
    """Aplica `correcoes_nomes` de projetos.yaml (erros de digitação nas fontes)."""
    for errado, certo in (_registro_completo().get("correcoes_nomes") or {}).items():
        texto = texto.replace(errado, certo)
    return texto


def projeto(chave: str) -> dict:
    """Retorna a configuração do projeto, com caminhos já resolvidos."""
    reg = carregar_registro()
    if chave not in reg:
        raise SystemExit(f"Projeto '{chave}' não está em projetos.yaml. Disponíveis: {', '.join(reg)}")
    cfg = dict(reg[chave])
    cfg["chave"] = chave
    for k in ("pasta_fontes", "kmz"):
        if cfg.get(k):
            cfg[k] = (RAIZ / cfg[k]).resolve()
    cfg["dir"] = PROJETOS_DIR / chave
    # abrangência nacional: UF, empresa (empreendedor) e órgão licenciador configuráveis por projeto
    # (padrões = Sanepar/IAT-PR, dos primeiros projetos)
    from ferramentas.brasil import uf_do_codigo
    cfg["uf"] = (cfg.get("uf") or uf_do_codigo(cfg.get("cod_ibge")) or "PR").upper()
    cfg.setdefault("empreendedor", "sanepar")
    cfg.setdefault("orgao", "iat-pr")
    cfg["numero_projeto"] = cfg.get("numero_projeto") or cfg.get("projeto_sanepar")
    cfg["empresa"] = empresa(cfg["empreendedor"])
    cfg["orgao_info"] = orgao(cfg["orgao"])
    return cfg


def empresa(sigla: str) -> dict:
    """Dados do empreendedor (dados_comuns/empreendedores/<sigla>.yaml): razão social, CNPJ, equipe, padrão de plantas."""
    arq = RAIZ / "dados_comuns" / "empreendedores" / f"{sigla}.yaml"
    if not arq.exists():
        raise SystemExit(f"Empreendedor '{sigla}' sem cadastro em {arq} – copie sanepar.yaml como modelo e preencha.")
    dados = yaml.safe_load(arq.read_text(encoding="utf-8")) or {}
    dados.setdefault("sigla", sigla)
    return dados


def orgao(sigla: str) -> dict:
    """Órgão licenciador (modelos/orgaos/<sigla>/orgao.yaml): norma, termos de referência, estruturas e matrizes."""
    pasta = RAIZ / "modelos" / "orgaos" / sigla
    arq = pasta / "orgao.yaml"
    if not arq.exists():
        raise SystemExit(f"Órgão '{sigla}' sem cadastro em {arq} – crie a pasta com orgao.yaml, estruturas/ e matrizes/.")
    dados = yaml.safe_load(arq.read_text(encoding="utf-8")) or {}
    dados["pasta"] = pasta
    dados.setdefault("sigla_pasta", sigla)
    return dados


def salvar_yaml(dados, caminho: Path):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        yaml.safe_dump(dados, f, allow_unicode=True, sort_keys=False, width=120)
