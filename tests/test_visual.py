"""Baseline visual — pega a regressão que nenhum outro teste daqui vê.

O smoke garante que a página responde 200 e devolve HTML. A caracterização
garante que os *dados* não mudaram. Nenhum dos dois percebe um stylesheet que
não carregou, um JS que quebrou no console ou um accordion que parou de montar
— a página continua 200, com os mesmos números, e crua na tela. Foi essa a
lacuna que a extração do CSS/JS do ``base.html`` (21/09/2026) expôs, e é o
pré-requisito de qualquer refatoração maior do frontend.

**Não compara pixel.** Segue o mesmo princípio de ``test_caracterizacao_*``: o
baseline versionado guarda uma impressão digital, não o conteúdo. Aqui a
impressão é o que o *browser calculou* — tokens de tema resolvidos, geometria
dos elementos de layout, contagem dos componentes que o JS monta, e o console
limpo. Comparar PNG entre máquinas é flaky por fonte, antialiasing e versão do
Chromium; comparar `getComputedStyle` não é.

Os screenshots são gravados assim mesmo, em ``_visual/`` (gitignored), porque
quando um teste falha a primeira pergunta é sempre "como ficou a tela?".

Uso::

    # gravar/atualizar (faça com tudo verde, ANTES de refatorar)
    ATUALIZAR_VISUAL=1 pytest tests/test_visual.py -m visual

    # verificar que nada mudou (depois de refatorar)
    pytest tests/test_visual.py -m visual

Precisa do banco real (``.env``) e do Chromium do Playwright; é excluído no CI
junto com os outros que dependem de infra.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

# Mesma trava do smoke: o aquecimento grava debriefing_snapshot no banco REAL, e
# o .env local aponta pra produção. Sem isto, rodar a suíte reescreve o snapshot
# de produção com números calculados pelo código do checkout.
os.environ["PRE_WARM_CACHE"] = "false"

BASELINE = RAIZ / "tests" / "baseline" / "visual.json"
SHOTS = RAIZ / "tests" / "baseline" / "_visual"
ATUALIZAR = os.environ.get("ATUALIZAR_VISUAL") == "1"

pytestmark = pytest.mark.visual


# ── O que conferir em cada página ─────────────────────────────────────────────
# Uma página por trilha do menu + as duas mais frágeis (debriefing, settings).
# Não é a lista das 32: o custo é ~8s por página e o valor marginal cai rápido —
# o que quebra o design system quebra em todas ao mesmo tempo.
PAGINAS = [
    ("index", "/"),
    ("captacao", "/captacao"),
    ("funil", "/funil"),
    ("criativos", "/criativos"),
    ("meta", "/meta"),
    ("google", "/google"),
    ("vendas", "/vendas"),
    ("leads", "/leads"),
    ("comparativo", "/comparativo"),
    ("calendario", "/calendario"),
    ("settings", "/settings"),
    ("debriefing", "/debriefing"),
]

# Tokens que todo tema precisa resolver. Se o CSS não carregar, voltam vazios —
# é o sinal mais barato de "a página está crua".
TOKENS = ["--bs-accent", "--bs-bg", "--bs-ink", "--bs-card", "--bs-border", "--bs-sidebar"]


@pytest.fixture(scope="session")
def servidor():
    """Sobe o app numa porta livre e derruba no fim.

    Precisa ser servidor de verdade, não TestClient: o TestClient devolve o HTML
    mas não executa JS, e é justamente o JS que este teste existe pra cobrir.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "frontend.app:app",
         "--host", "127.0.0.1", "--port", str(porta), "--log-level", "warning"],
        cwd=str(RAIZ),
        env={**os.environ, "PRE_WARM_CACHE": "false"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    base = f"http://127.0.0.1:{porta}"

    import urllib.error
    import urllib.request
    for _ in range(120):
        if proc.poll() is not None:
            bruto = proc.stderr.read() if proc.stderr else b""
            erro = (bruto or b"").decode("utf-8", "replace")[-2000:]
            pytest.skip(f"uvicorn morreu ao subir:\n{erro}")
        try:
            urllib.request.urlopen(f"{base}/login", timeout=1)
            break
        except urllib.error.HTTPError:
            break          # respondeu (3xx/4xx) — está de pé
        except Exception:
            time.sleep(0.25)
    else:
        proc.terminate()
        pytest.skip("uvicorn não respondeu a tempo")

    yield base
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def pagina_logada(servidor):
    """Uma aba já autenticada, com console e rede sob escuta."""
    playwright = pytest.importorskip("playwright.sync_api", reason="playwright não instalado")

    usuario = os.environ.get("BRABO_USER")
    senha = os.environ.get("BRABO_PASS")
    if not usuario or not senha:
        pytest.skip("BRABO_USER/BRABO_PASS ausentes no .env")

    with playwright.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"chromium indisponível ({e}); rode: playwright install chromium")
        pag = nav.new_context(viewport={"width": 1440, "height": 900}).new_page()

        registro: dict[str, list] = {"console": [], "rede": []}
        pag.on("console", lambda m: registro["console"].append(m.text)
               if m.type == "error" else None)
        pag.on("requestfailed", lambda r: registro["rede"].append(f"falhou {r.url}"))
        pag.on("response", lambda r: registro["rede"].append(f"HTTP {r.status} {r.url}")
               if r.status >= 400 else None)

        pag.goto(f"{servidor}/login", wait_until="load", timeout=120_000)
        pag.fill('input[type="email"], input[name="email"]', usuario)
        pag.fill('input[type="password"]', senha)
        pag.click('button[type="submit"]')
        # O submit redireciona pra "/", que também é página de dado — mesmo
        # motivo do _abrir(): esperar a rede aquietar aqui trava com cache frio.
        pag.wait_for_load_state("load", timeout=240_000)
        if "/login" in pag.url:
            nav.close()
            pytest.skip("login falhou — credenciais do .env não entraram")

        pag.registro = registro  # type: ignore[attr-defined]
        yield pag
        nav.close()


def _abrir(pag, url: str) -> None:
    """Navega de forma determinística.

    ``networkidle`` parece a escolha óbvia e não é: exige 500 ms sem nenhum
    request, o que uma página pesada com cache frio não alcança dentro de
    qualquer timeout razoável — o teste subiu um servidor novo, então o cache
    SEMPRE está frio aqui. ``load`` + uma espera curta cobre o que interessa
    (CSS aplicado e JS do accordion montado) sem depender da rede aquietar.
    """
    pag.goto(url, wait_until="load", timeout=240_000)
    pag.wait_for_timeout(1200)


def _impressao(pag) -> dict:
    """O que o browser calculou, reduzido a algo comparável e estável.

    **Contagem de componente não entra na comparação, e a lição custou um falso
    positivo no primeiro dia.** O baseline guardava "/calendario tem 64 pills";
    três lançamentos novos entraram no calendário e viraram 67, com o template
    intocado. Quase todo contador de página de dado é assim: as pills, as linhas
    de tabela e boa parte das seções saem de um ``{% for %}`` sobre o banco. Um
    teste que acusa dado novo como regressão é um teste que as pessoas aprendem
    a ignorar — o mesmo motivo pelo qual o baseline de caracterização tem a
    lista ``VOLATEIS``.

    Entra na comparação exata só o que **não pode** mudar com o dado: tokens
    resolvidos, geometria do layout, funções globais registradas, presença dos
    controles do accordion. Mais as *invariantes* — relações que valem seja qual
    for o volume: todo título de seção tem chevron (prova que ``secoes.js``
    percorreu a página inteira), toda tabela está dentro de ``.table-wrap``
    (prova que o markup seguiu o design system).

    Os contadores continuam sendo coletados e gravados, mas só para diagnóstico
    quando algo mais falhar; deles se compara a forma, nunca o valor.
    """
    return pag.evaluate(
        """(tokens) => {
        const css = getComputedStyle(document.documentElement);
        const geo = (sel) => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return [Math.round(r.width), Math.round(r.height)];
        };
        const n = (sel) => document.querySelectorAll(sel).length;
        return {
            tokens: Object.fromEntries(
                tokens.map(t => [t, css.getPropertyValue(t).trim()])),
            // layout: se o stylesheet não carregar, estes viram null ou 0
            geometria: {
                sidebar: geo('#bs-drawer'),
                main: geo('#bs-main'),
                topbar: geo('#bs-topbar'),
            },
            // Relações que valem com 1 linha de dado ou com 10 mil. São o
            // coração da comparação: se o JS não percorreu a página, ou se o
            // markup fugiu do design system, alguma delas vira false.
            invariantes: {
                todo_titulo_tem_chevron:
                    n('.section-title .ti-chevron-down, .dbf-section-title .ti-chevron-down')
                    === n('.section-title, .dbf-section-title'),
                toda_tabela_tem_wrap: n('.table-wrap table') === n('table'),
                tem_secoes: n('.section, .dbf-section') > 0,
                tem_nav: n('#bs-drawer a') > 0,
            },
            // Só diagnóstico: comparados pela forma (quais chaves existem),
            // nunca pelo valor — ver o docstring.
            contadores: {
                secoes: n('.section, .dbf-section'),
                titulos_secao: n('.section-title, .dbf-section-title'),
                tabelas: n('table'),
                kpis: n('.tp-kpi, .kpi-card, .dbf-kpi'),
                canvas: n('canvas'),
                pills: n('.bs-pill'),
                nav_links: n('#bs-drawer a'),
            },
            // controles do accordion só existem se secoes.js rodou
            controles_secao: {
                recolher: !!document.querySelector('.bs-sec-controls, .dbf-accordion-controls'),
                busca: !!document.querySelector('.bs-sec-search'),
            },
            // funções globais que cada arquivo de JS precisa ter registrado
            globais: ['bsSetTheme', 'bsMenuToggle', 'bsStartProgress', 'bsShortcuts',
                      'openVideoModalFromEl', 'lcOpen', 'bsPickerToggle', 'bsRunEtl']
                     .filter(f => typeof window[f] === 'function').sort(),
            body_data_page: document.body.getAttribute('data-page'),
        };
    }""",
        TOKENS,
    )


def _carregar_baseline() -> dict:
    if BASELINE.exists():
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    return {}


_novo_baseline: dict = {}


@pytest.mark.parametrize("nome,rota", PAGINAS, ids=[p[0] for p in PAGINAS])
def test_pagina_nao_mudou_visualmente(pagina_logada, servidor, nome, rota):
    pag = pagina_logada
    # Zera antes de navegar: um request que só falha DEPOIS do teste anterior
    # terminar (ex.: abortado por timeout) cairia na conta da próxima página e
    # acusaria erro onde não há. Já aconteceu entre /comparativo e /calendario.
    pag.registro["console"].clear()
    pag.registro["rede"].clear()

    _abrir(pag, f"{servidor}{rota}")

    SHOTS.mkdir(parents=True, exist_ok=True)
    pag.screenshot(path=str(SHOTS / f"{nome}.png"))

    obtido = _impressao(pag)
    erros_js = list(pag.registro["console"])
    falhas_rede = [r for r in pag.registro["rede"] if "favicon" not in r]

    # Console e rede são absolutos: nunca podem regredir, nem com baseline novo.
    assert not erros_js, f"{rota} produziu erro de JS no console:\n" + "\n".join(erros_js[:5])
    assert not falhas_rede, f"{rota} teve request falhando:\n" + "\n".join(falhas_rede[:5])

    # O CSS carregou? Token vazio = página crua.
    vazios = [t for t, v in obtido["tokens"].items() if not v]
    assert not vazios, (
        f"{rota}: tokens sem valor {vazios} — algum stylesheet de "
        f"frontend/static/css/ não carregou"
    )

    if ATUALIZAR:
        _novo_baseline[nome] = obtido
        return

    baseline = _carregar_baseline()
    if nome not in baseline:
        pytest.skip(f"{nome} ainda não está no baseline visual (grave com ATUALIZAR_VISUAL=1)")

    esperado = baseline[nome]
    dica = (f"  screenshot: {SHOTS / f'{nome}.png'}\n"
            f"  contadores agora: {json.dumps(obtido['contadores'], ensure_ascii=False)}\n"
            f"  Se a mudança é intencional: "
            f"ATUALIZAR_VISUAL=1 pytest tests/test_visual.py -m visual")

    for secao in ("tokens", "geometria", "controles_secao", "globais",
                  "invariantes", "body_data_page"):
        assert obtido[secao] == esperado[secao], (
            f"{rota}: '{secao}' mudou.\n"
            f"  esperado: {json.dumps(esperado[secao], ensure_ascii=False)}\n"
            f"  obtido:   {json.dumps(obtido[secao], ensure_ascii=False)}\n" + dica
        )

    # Dos contadores só a forma: chave que some é componente que deixou de ser
    # coletado (bug do teste) ou seletor que mudou de nome (bug do CSS).
    assert sorted(obtido["contadores"]) == sorted(esperado["contadores"]), (
        f"{rota}: mudou o CONJUNTO de contadores (não o valor).\n" + dica
    )


@pytest.mark.parametrize("tema", ["a", "brabo", "b", "c", "d", "outatime",
                                  "predador", "spidey", "aranhaverso", "springfield"])
def test_tema_troca_os_tokens(pagina_logada, servidor, tema):
    """Cada tema precisa resolver todos os tokens e produzir um conjunto próprio.

    Cobre `temas.css` + `tema.js` juntos: um tema que não existir mais no CSS
    passa a devolver os tokens do tema padrão, e é isso que se detecta aqui.
    """
    pag = pagina_logada
    if "/captacao" not in pag.url:
        _abrir(pag, f"{servidor}/captacao")

    pag.evaluate("(t) => window.bsSetTheme(t)", tema)
    pag.wait_for_timeout(300)
    lidos = pag.evaluate(
        "(tokens) => { const c = getComputedStyle(document.documentElement);"
        " return Object.fromEntries(tokens.map(t => [t, c.getPropertyValue(t).trim()])); }",
        TOKENS,
    )
    vazios = [t for t, v in lidos.items() if not v]
    assert not vazios, f"tema '{tema}': tokens sem valor {vazios}"

    if ATUALIZAR:
        _novo_baseline.setdefault("_temas", {})[tema] = lidos
        return

    baseline = _carregar_baseline().get("_temas", {})
    if tema not in baseline:
        pytest.skip(f"tema '{tema}' ainda não está no baseline")
    assert lidos == baseline[tema], (
        f"tema '{tema}' mudou de tokens.\n"
        f"  esperado: {baseline[tema]}\n  obtido:   {lidos}"
    )
    # volta pro padrão pra não vazar tema pro próximo teste
    pag.evaluate("() => window.bsSetTheme('a')")


def test_accordion_responde(pagina_logada, servidor):
    """Recolher/Expandir e a busca precisam mexer no DOM — cobre `secoes.js`."""
    pag = pagina_logada
    _abrir(pag, f"{servidor}/captacao")

    total = pag.evaluate("document.querySelectorAll('.section').length")
    if total == 0:
        pytest.skip("/captacao sem seções — nada a exercitar")

    # Pelo data-act, nunca pelo texto: a sidebar tem um "Recolher menu" que casa
    # com /Recolher/i e não mexe em seção nenhuma — procurar por texto clica nele
    # e o teste acusa um bug de accordion que não existe.
    clique = """(act) => {
        const b = document.querySelector(`[data-act="${act}"]`);
        if (b) b.click();
        return !!b;
    }"""
    assert pag.evaluate(clique, "collapse"), "botão [data-act=collapse] não encontrado"
    pag.wait_for_timeout(500)
    assert pag.evaluate("document.querySelectorAll('.section.collapsed').length") == total, (
        "'Recolher' não recolheu todas as seções"
    )

    assert pag.evaluate(clique, "expand"), "botão [data-act=expand] não encontrado"
    pag.wait_for_timeout(500)
    assert pag.evaluate("document.querySelectorAll('.section.collapsed').length") == 0, (
        "'Expandir' não expandiu todas as seções"
    )

    campo = pag.query_selector('.bs-sec-search input, input[placeholder*="Buscar"]')
    if campo:
        campo.fill("zzzznaoexiste")
        pag.wait_for_timeout(600)
        visiveis = pag.evaluate(
            "[...document.querySelectorAll('.section')].filter(s => s.offsetParent !== null).length")
        assert visiveis == 0, f"busca sem resultado deixou {visiveis} seções na tela"
        campo.fill("")
        pag.wait_for_timeout(400)


def test_wizard_abre(pagina_logada, servidor):
    """`lcOpen` precisa montar o modal — cobre `wizard-lancamento.js` + seu CSS."""
    pag = pagina_logada
    _abrir(pag, f"{servidor}/captacao")

    codigo = pag.evaluate("""() => {
        const el = document.querySelector('.bs-launch-picker-item, [data-launch-code]');
        return el ? (el.getAttribute('data-launch-code') || el.textContent.trim()) : null;
    }""")
    if not codigo:
        pytest.skip("nenhum lançamento na barra lateral pra abrir o wizard")

    pag.evaluate("(c) => window.lcOpen(c)", codigo)
    pag.wait_for_timeout(1800)
    display = pag.evaluate("""() => {
        const o = document.getElementById('lc-overlay');
        return o ? getComputedStyle(o).display : 'ausente';
    }""")
    assert display not in ("ausente", "none"), f"wizard não abriu (display={display})"
    pag.evaluate("() => window.lcClose && window.lcClose()")


@pytest.fixture(scope="session", autouse=True)
def _gravar_baseline_no_fim():
    yield
    if ATUALIZAR and _novo_baseline:
        atual = _carregar_baseline()
        atual.update(_novo_baseline)
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(atual, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"\nbaseline visual gravado: {BASELINE} ({len(atual)} entradas)")
