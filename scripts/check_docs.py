# -*- coding: utf-8 -*-
"""
Valida a documentacao em docs/ e regera o mapa de roteamento do README.

    python scripts/check_docs.py                 # so valida (exit 1 se houver erro)
    python scripts/check_docs.py --atualizar-mapa  # valida e reescreve o mapa no README

Regras validadas:
  1. todo .md tem frontmatter com titulo/area/status/atualizado/responde
  2. 'area' e 'status' usam valores permitidos
  3. nome de arquivo e unico no vault (wikilink resolve por nome)
  4. todo [[wikilink]] aponta pra um doc existente
  5. todo doc e alcancavel a partir do docs/README.md (direto ou via indice)
"""
import io, os, re, sys

RAIZ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
AREAS = {"indice","sistema","negocio","operacao","performance","lancamento","projeto","analise","historico"}
STATUS = {"vigente","pendente","arquivado"}
OBRIGATORIOS = ("titulo","area","status","atualizado","responde")
MARCA_INI, MARCA_FIM = "<!-- MAPA:INICIO -->", "<!-- MAPA:FIM -->"
SUM_INI, SUM_FIM = "<!-- SUMARIO:INICIO -->", "<!-- SUMARIO:FIM -->"
LIMIAR_SUMARIO = 30 * 1024  # docs acima disso ganham sumario navegavel
RE_LINK = re.compile(r"\[\[([^\]\|]+)(?:\|[^\]]*)?\]\]")


def ler_docs():
    docs = {}
    for raiz, dirs, arqs in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in (".obsidian", "_templates", "_anexos")]
        for a in sorted(arqs):
            if not a.endswith(".md"):
                continue
            p = os.path.join(raiz, a)
            rel = os.path.relpath(p, RAIZ).replace(os.sep, "/")
            docs[rel] = {"nome": a[:-3], "texto": io.open(p, encoding="utf-8").read()}
    return docs


def parse_fm(texto):
    if not texto.startswith("---\n"):
        return None
    fim = texto.find("\n---\n", 4)
    if fim == -1:
        return None
    fm, chave = {}, None
    for linha in texto[4:fim].split("\n"):
        if linha.startswith("  - "):
            fm.setdefault(chave, []).append(linha[4:].strip().strip('"'))
        elif ":" in linha:
            k, v = linha.split(":", 1)
            chave = k.strip()
            v = v.strip().strip('"')
            fm[chave] = v if v else []
    return fm


def sem_codigo(texto):
    """Remove codigo (cercado e inline) — wikilink dentro de codigo nao e link."""
    texto = re.sub(r"```.*?```", "", texto, flags=re.DOTALL)
    return re.sub("`[^`" + chr(10) + "]*`", "", texto)


def validar(docs):
    erros = []
    porNome = {}
    for rel, d in docs.items():
        porNome.setdefault(d["nome"], []).append(rel)
        fm = parse_fm(d["texto"])
        d["fm"] = fm
        if fm is None:
            erros.append("%s: sem frontmatter" % rel)
            continue
        for campo in OBRIGATORIOS:
            if not fm.get(campo):
                erros.append("%s: frontmatter sem '%s'" % (rel, campo))
        if fm.get("area") not in AREAS:
            erros.append("%s: area invalida '%s'" % (rel, fm.get("area")))
        if fm.get("status") not in STATUS:
            erros.append("%s: status invalido '%s'" % (rel, fm.get("status")))

    for nome, rels in porNome.items():
        if len(rels) > 1:
            erros.append("nome duplicado '%s': %s" % (nome, ", ".join(rels)))

    validos = set(porNome) | {r[:-3] for r in docs}
    for rel, d in docs.items():
        for alvo in RE_LINK.findall(sem_codigo(d["texto"])):
            # [[DOC#secao]] aponta pra um cabecalho: so o DOC precisa existir.
            # [[#secao]] e ancora no proprio arquivo.
            arquivo = alvo.split("#")[0].strip()
            if not arquivo:
                continue
            if arquivo not in validos:
                erros.append("%s: wikilink quebrado [[%s]]" % (rel, alvo.strip()))

    # alcancabilidade a partir do README.
    # Só docs/sistema/ vai pro git; o resto do vault é local. Num clone sem o
    # vault completo não há README pra varrer, então a checagem é pulada em vez
    # de reprovar (evita quebrar CI por causa de arquivo que nao existe ali).
    if "README.md" not in docs:
        return erros
    alcancados, fila = set(), ["README.md"]
    while fila:
        atual = fila.pop()
        if atual in alcancados or atual not in docs:
            continue
        alcancados.add(atual)
        for alvo in RE_LINK.findall(sem_codigo(docs[atual]["texto"])):
            alvo = alvo.split("#")[0].strip()
            for rel in porNome.get(alvo, []):
                fila.append(rel)
    for rel in docs:
        if rel not in alcancados:
            erros.append("%s: nao e alcancavel a partir do README (linke num indice)" % rel)
    return erros


def gerar_mapa(docs):
    grupos = {}
    for rel, d in sorted(docs.items()):
        fm = d.get("fm") or {}
        if fm.get("status") == "arquivado" or fm.get("area") == "indice":
            continue
        for r in fm.get("responde", []):
            grupos.setdefault(r, []).append(d["nome"])
    linhas = [MARCA_INI,
              "",
              "> Gerado por `scripts/check_docs.py --atualizar-mapa`. Nao editar a mao.",
              "",
              "| se a pergunta e... | abra |",
              "|---|---|"]
    for pergunta in sorted(grupos):
        alvos = " · ".join("[[%s]]" % n for n in sorted(set(grupos[pergunta])))
        linhas.append("| %s | %s |" % (pergunta, alvos))
    linhas += ["", MARCA_FIM]
    return "\n".join(linhas)



def gerar_sumario(d):
    """Sumario clicavel dos itens de um doc grande.

    Um diario de lancamento chega a 215 KB / 130 itens: ler o arquivo inteiro
    pra achar um item custa caro (pessoa rola, agente gasta contexto). O sumario
    lista o que existe; depois le-se so a secao desejada.
    """
    nome = d["nome"]
    linhas = []
    for linha in d["texto"].split(chr(10)):
        if linha.startswith("### "):
            titulo = linha[4:].strip()
            if any(c in titulo for c in ("|", "#", "[", "]")):
                linhas.append("- " + titulo)
            else:
                linhas.append("- [[%s#%s|%s]]" % (nome, titulo, titulo))
        elif linha.startswith("## "):
            linhas.append("")
            linhas.append("**" + linha[3:].strip() + "**")
            linhas.append("")
    itens = sum(1 for l in linhas if l.startswith("- "))
    if not itens:
        return None
    # tudo dentro do callout (prefixo "> ") pra ele recolher de verdade:
    # sem isso a lista fica sempre aberta e empurra o conteudo pra baixo.
    corpo = ["> " + l if l else ">" for l in linhas]
    cabeca = [SUM_INI, "",
              "> [!abstract]- Sumario - %d itens (gerado por `scripts/check_docs.py --atualizar-mapa`)" % itens,
              ">"]
    return chr(10).join(cabeca + corpo + ["", SUM_FIM])


def aplicar_sumarios(docs):
    tocados = []
    for rel, d in sorted(docs.items()):
        if len(d["texto"].encode("utf-8")) < LIMIAR_SUMARIO:
            continue
        novo = gerar_sumario(d)
        if not novo:
            continue
        s = d["texto"]
        if SUM_INI in s and SUM_FIM in s:
            ini = s.index(SUM_INI)
            fim = s.index(SUM_FIM) + len(SUM_FIM)
            s = s[:ini] + novo + s[fim:]
        else:
            pos = s.find(chr(10) + "# ")
            if pos == -1:
                continue
            fim_h1 = s.index(chr(10), pos + 1)
            s = s[:fim_h1 + 1] + chr(10) + novo + chr(10) + s[fim_h1 + 1:]
        io.open(os.path.join(RAIZ, rel), "w", encoding="utf-8", newline="").write(s)
        d["texto"] = s
        tocados.append(rel)
    return tocados

def main():
    docs = ler_docs()
    erros = validar(docs)

    if "--atualizar-mapa" in sys.argv:
        tocados = aplicar_sumarios(docs)
        if tocados:
            print("sumario gerado em: " + ", ".join(tocados))
        p = os.path.join(RAIZ, "README.md")
        novo = gerar_mapa(docs)
        if not os.path.exists(p):
            print("docs/README.md ausente (vault local nao presente) - mapa nao gerado")
            s = None
        else:
            s = io.open(p, encoding="utf-8").read()
        if s is not None and MARCA_INI in s and MARCA_FIM in s:
            ini = s.index(MARCA_INI)
            fim = s.index(MARCA_FIM) + len(MARCA_FIM)
            s = s[:ini] + novo + s[fim:]
            io.open(p, "w", encoding="utf-8", newline="").write(s)
            print("mapa atualizado em docs/README.md")
        elif s is not None:
            print("AVISO: marcadores %s / %s nao encontrados no README" % (MARCA_INI, MARCA_FIM))

    print("%d documentos verificados" % len(docs))
    if erros:
        print("\n%d problema(s):" % len(erros))
        for e in erros:
            print("  -", e)
        return 1
    print("tudo certo: frontmatter, nomes unicos, links e alcancabilidade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
