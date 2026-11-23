# scripts/figma — produção de arte para o Figma

Ferramentas que já deram certo em criativos reais. O passo a passo, as armadilhas e o porquê de cada
escolha estão em `docs/performance/playbooks/FIGMA_PRODUCAO_DE_ARTE.md` — leia lá antes de usar.

Dependências fora do `requirements.txt` (só para produção de arte, nunca no servidor):
`pip install vtracer opencv-python-headless scikit-image scipy pillow av`

| script | faz |
|---|---|
| `separar_secoes_painel.js` | (rodar via `use_figma`) quebra a captura de uma tela do painel em uma Section por bloco, com Atual × Proposta lado a lado. Trocar `__PAGE__`/`__ROOT__` |
| `vetorizar_png.py` | PNG → SVG fiel em camadas de cor (VTracer + cor-chave magenta + recorte pela silhueta). Ferramenta geral |
| `recortar_folha_ia.py` | recorta poses/objetos de uma folha em grade gerada por IA: fundo = branco ligado à borda da folha, cada pedaço vai para a célula do seu centro, borda suave, amplia com nitidez. `recortar_folha_ia.py folha.png cols rows prefixo escala [itens_com_furo]` |
| `recortar_pessoa_grabcut.py` | recorta pessoa de foto/arte com fundo transparente (GrabCut, sem rembg); marca rosto e áreas de texto por cima como fundo |
| `vetorizar_traco.py` | desenho de traço → linhas **abertas** em SVG, para animar com `PATH_TRIM_END` no Figma |
| `caixas/1_texto_e_fonte.py` | acha as linhas de texto de selos/caixas, escolhe a fonte mais parecida (só fontes que o Figma tem), apaga o texto do PNG |
| `caixas/2_logo_oficial.py` | acha o logo (ex. INSS) na arte, mede escala/rotação contra o componente vetorial oficial e apaga o logo do fundo |
| `caixas/3_medir_formas.py`, `4_medir_resto.py` | mede cartão/faixa (retângulo, raio do canto, cor, borda), forma com aba, área do emoji; separa o que ainda vai pro VTracer |
| `animar_card_raster.py` | anima card "chapado" fora do Figma (digitação dos pixels originais + cursor) → MP4 |
| `datilografia.py` + `texto_card.py` | máquina de escrever real em MP4, texto redesenhado com PIL nas posições do Figma |
| `compor_video_gemini.py` | encaixa vídeo gerado no Gemini dentro do card (borda esfumada, tom, áudio) com PyAV |
| `mapa_sp_svg.py` | mapa do estado de SP em traço + pinos, em SVG |

Os scripts de `caixas/` foram escritos para as 8 caixas do INSS (PI-NOV-26): esperam
`PASTA/caixas/orig/c1..c8.png`, fontes do Google Fonts em `PASTA/fonts/` e gravam em `PASTA/caixas/editavel/`.
Para outra arte, ajuste o dicionário `BOXES` (texto de cada linha) no topo do `1_texto_e_fonte.py`.
