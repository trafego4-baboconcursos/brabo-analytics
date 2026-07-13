import styles from "./page.module.css";

export default function Home() {
  return (
    <div className={styles.page}>
      <div className={styles.glow} />
      <header className={styles.nav}>
        <div className={styles.logoWrap}>
          <span className={styles.logoMark} />
          <div>
            <p className={styles.logoName}>LumenX Grid</p>
            <p className={styles.logoTag}>Energia solar + inteligencia operacional</p>
          </div>
        </div>
        <nav className={styles.navLinks}>
          <a href="#diferenciais">Diferenciais</a>
          <a href="#app">App</a>
          <a href="#beneficios">Beneficios</a>
          <a href="#prova">Prova</a>
        </nav>
        <button className={styles.navCta}>Solicitar diagnostico</button>
      </header>

      <main className={styles.main}>
        <section className={styles.hero}>
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}>Plataforma premium de energia inteligente</p>
            <h1>
              Energia solar com controle total, automacao e inteligencia de dados
            </h1>
            <p className={styles.subhead}>
              A LumenX Grid combina geracao solar com um sistema de gestao
              energetica que monitora cada circuito do imovel, em tempo real,
              com automacoes que reduzem custos e aumentam eficiencia.
            </p>
            <div className={styles.heroActions}>
              <button className={styles.primaryCta}>Agendar consultoria</button>
              <button className={styles.ghostCta}>Ver demonstracao do app</button>
            </div>
            <div className={styles.heroStats}>
              <div>
                <h3>32%</h3>
                <p>media de economia anual</p>
              </div>
              <div>
                <h3>120+ pontos</h3>
                <p>monitorados por unidade</p>
              </div>
              <div>
                <h3>24/7</h3>
                <p>alertas e automacoes</p>
              </div>
            </div>
          </div>
          <div className={styles.heroMockup}>
            <div className={styles.mockupTop}>
              <div>
                <p className={styles.mockupLabel}>Painel LumenX</p>
                <h4>Consumo total</h4>
                <p className={styles.mockupValue}>18.4 kWh</p>
              </div>
              <div className={styles.mockupChip}>Eficiencia +28%</div>
            </div>
            <div className={styles.mockupGrid}>
              <div className={styles.mockupCard}>
                <p>Iluminacao</p>
                <h5>1.2 kWh</h5>
                <span className={styles.statusGood}>Estavel</span>
              </div>
              <div className={styles.mockupCard}>
                <p>Climatizacao</p>
                <h5>6.8 kWh</h5>
                <span className={styles.statusWarn}>Alerta</span>
              </div>
              <div className={styles.mockupCard}>
                <p>Carregadores EV</p>
                <h5>4.3 kWh</h5>
                <span className={styles.statusGood}>Otimizado</span>
              </div>
            </div>
            <div className={styles.mockupFooter}>
              <p>Automacao ativa: modo pico solar</p>
              <button>Ver detalhes</button>
            </div>
          </div>
        </section>

        <section id="diferenciais" className={styles.section}>
          <div className={styles.sectionHeading}>
            <h2>Mais que energia solar: inteligencia por ponto de consumo</h2>
            <p>
              A plataforma cruza geracao, consumo e comportamento para otimizar
              cada ambiente e equipamento em tempo real.
            </p>
          </div>
          <div className={styles.cards}>
            <article className={styles.card}>
              <h3>Monitoramento cirurgico</h3>
              <p>Leitura de circuitos, equipamentos e cargas criticas.</p>
            </article>
            <article className={styles.card}>
              <h3>Gestao inteligente</h3>
              <p>Automacoes e metas que ajustam o consumo automaticamente.</p>
            </article>
            <article className={styles.card}>
              <h3>Alertas de desperdicio</h3>
              <p>Deteccao de anomalias e consumo fora do padrao.</p>
            </article>
            <article className={styles.card}>
              <h3>Visao em tempo real</h3>
              <p>Dashboards com dados ao vivo e previsoes de economia.</p>
            </article>
          </div>
        </section>

        <section className={styles.sectionAlt}>
          <div className={styles.sectionHeading}>
            <h2>Como funciona</h2>
            <p>
              Do sol ao dispositivo: um fluxo unico de dados, energia e
              inteligencia operacional.
            </p>
          </div>
          <ol className={styles.steps}>
            <li>
              <span>1</span>
              <div>
                <h3>Geracao solar otimizada</h3>
                <p>Dimensionamento premium e monitoramento da geracao.</p>
              </div>
            </li>
            <li>
              <span>2</span>
              <div>
                <h3>Leitura de circuitos</h3>
                <p>Sensorizacao de cada ambiente e equipamento critico.</p>
              </div>
            </li>
            <li>
              <span>3</span>
              <div>
                <h3>Painel inteligente</h3>
                <p>Dashboard unico com consumo, geracao e autonomia.</p>
              </div>
            </li>
            <li>
              <span>4</span>
              <div>
                <h3>Insights automaticos</h3>
                <p>Alertas de perdas e recomendacoes de economia.</p>
              </div>
            </li>
            <li>
              <span>5</span>
              <div>
                <h3>Otimizacao continua</h3>
                <p>Automacoes dinamicas com metas e previsoes.</p>
              </div>
            </li>
          </ol>
        </section>

        <section id="app" className={styles.section}>
          <div className={styles.split}>
            <div>
              <p className={styles.eyebrow}>App central de energia</p>
              <h2>Controle total na palma da mao</h2>
              <p>
                O aplicativo LumenX concentra consumo, eficiencia, alertas e
                automacoes em um unico painel intuitivo e elegante.
              </p>
              <div className={styles.featureGrid}>
                <div>
                  <h4>Dashboard total</h4>
                  <p>Consumo geral, geracao e autonomia em tempo real.</p>
                </div>
                <div>
                  <h4>Por comodo</h4>
                  <p>Mapa energetico dos ambientes da casa ou empresa.</p>
                </div>
                <div>
                  <h4>Por equipamento</h4>
                  <p>Detalhes de cada carga com previsao de custo.</p>
                </div>
                <div>
                  <h4>Automacoes inteligentes</h4>
                  <p>Rotinas e modos de economia personalizaveis.</p>
                </div>
                <div>
                  <h4>Alertas e anomalias</h4>
                  <p>Notificacoes proativas com acao imediata.</p>
                </div>
                <div>
                  <h4>Relatorios mensais</h4>
                  <p>Indicadores de eficiencia e metas de economia.</p>
                </div>
              </div>
            </div>
            <div className={styles.appStack}>
              <div className={styles.appCard}>
                <p className={styles.appTitle}>Tela inicial</p>
                <h3>Visao premium</h3>
                <p>Resumo da geracao e consumo com score energetico.</p>
              </div>
              <div className={styles.appCard}>
                <p className={styles.appTitle}>Ambientes</p>
                <h3>Mapa por comodo</h3>
                <p>Consumo por zona, com recomendacoes instantaneas.</p>
              </div>
              <div className={styles.appCard}>
                <p className={styles.appTitle}>Dispositivos</p>
                <h3>Controle remoto</h3>
                <p>Ative, pause e programe equipamentos criticos.</p>
              </div>
            </div>
          </div>
        </section>

        <section id="beneficios" className={styles.sectionAlt}>
          <div className={styles.sectionHeading}>
            <h2>Beneficios para o cliente</h2>
            <p>Economia real com visao profissional da energia do imovel.</p>
          </div>
          <div className={styles.benefits}>
            <div>
              <h4>Reducao de custos</h4>
              <p>Menos desperdicio e mais retorno do investimento solar.</p>
            </div>
            <div>
              <h4>Previsibilidade</h4>
              <p>Orcamento energetico com metas e alertas de desvios.</p>
            </div>
            <div>
              <h4>Controle total</h4>
              <p>Gestao detalhada por ambiente e dispositivo.</p>
            </div>
            <div>
              <h4>Conforto e seguranca</h4>
              <p>Automacoes inteligentes e monitoramento constante.</p>
            </div>
            <div>
              <h4>Sustentabilidade</h4>
              <p>Menos emissao e uso eficiente de energia limpa.</p>
            </div>
            <div>
              <h4>Valorizacao do imovel</h4>
              <p>Infraestrutura premium e tecnologia de ponta.</p>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <h2>Solucoes para diferentes publicos</h2>
            <p>
              Projetos personalizados para residencias, negocios e operacoes com
              alto consumo.
            </p>
          </div>
          <div className={styles.cards}>
            <article className={styles.card}>
              <h3>Residencias premium</h3>
              <p>Conforto, seguranca e economia com controle total.</p>
            </article>
            <article className={styles.card}>
              <h3>Condominios</h3>
              <p>Gestao centralizada, rateio inteligente e automacoes.</p>
            </article>
            <article className={styles.card}>
              <h3>Comercios</h3>
              <p>Reduza picos, ajuste horarios e controle equipamentos.</p>
            </article>
            <article className={styles.card}>
              <h3>Industrias leves</h3>
              <p>Monitoramento critico, previsoes e automacoes.</p>
            </article>
            <article className={styles.card}>
              <h3>Fazendas e rural</h3>
              <p>Controle remoto, bombas e maquinario inteligente.</p>
            </article>
            <article className={styles.card}>
              <h3>Corporate</h3>
              <p>Gestao energetica profissional com reports executivos.</p>
            </article>
          </div>
        </section>

        <section id="prova" className={styles.sectionAlt}>
          <div className={styles.sectionHeading}>
            <h2>Prova de valor e performance</h2>
            <p>Dados visuais que comprovam economia, controle e eficiencia.</p>
          </div>
          <div className={styles.proofGrid}>
            <div className={styles.proofCard}>
              <h3>Economia estimada</h3>
              <p className={styles.proofValue}>R$ 18.400 / ano</p>
              <p>Comparativo antes x depois em 12 meses.</p>
            </div>
            <div className={styles.proofCard}>
              <h3>Performance solar</h3>
              <p className={styles.proofValue}>+42% geracao liquida</p>
              <p>Otimizacao com smart routing de cargas.</p>
            </div>
            <div className={styles.proofCard}>
              <h3>Depoimentos</h3>
              <p>
                "Hoje vejo cada ponto da casa. A economia real e a sensacao de
                controle e total." - Cliente Alfa
              </p>
            </div>
          </div>
          <div className={styles.statsRow}>
            <div>
              <h4>98%</h4>
              <p>tempo de operacao estavel</p>
            </div>
            <div>
              <h4>65%</h4>
              <p>reducoes de pico em horario caro</p>
            </div>
            <div>
              <h4>3.1x</h4>
              <p>ROI medio em 36 meses</p>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <h2>Posicionamento e identidade da marca</h2>
            <p>
              Uma startup premium que entrega energia, dados e automacao em um
              unico ecossistema.
            </p>
          </div>
          <div className={styles.brandGrid}>
            <div className={styles.brandCard}>
              <h3>Nome e slogan</h3>
              <p>
                <strong>LumenX Grid</strong>
              </p>
              <p>Slogan: "Energia que pensa, controle que transforma"</p>
            </div>
            <div className={styles.brandCard}>
              <h3>Proposta de valor</h3>
              <p>
                Geracao solar integrada a uma plataforma de inteligencia
                energetica que monitora, controla e otimiza cada ponto de
                consumo do imovel.
              </p>
            </div>
            <div className={styles.brandCard}>
              <h3>Tom de voz</h3>
              <p>Confiante, tecnico, elegante e orientado a resultados.</p>
            </div>
            <div className={styles.brandCard}>
              <h3>Identidade visual</h3>
              <p>Premium, clean, futurista, com dashboards e grafos de energia.</p>
            </div>
            <div className={styles.brandCard}>
              <h3>Paleta de cores</h3>
              <div className={styles.palette}>
                <span className={styles.swatchSun} />
                <span className={styles.swatchAqua} />
                <span className={styles.swatchInk} />
                <span className={styles.swatchPaper} />
              </div>
              <p>Sun Gold, Aqua Tech, Ink Black, Paper White.</p>
            </div>
            <div className={styles.brandCard}>
              <h3>Tipografia</h3>
              <p>
                Headings com Space Grotesk e corpo em Sora para leitura
                executiva.
              </p>
            </div>
            <div className={styles.brandCard}>
              <h3>Estilo de imagens</h3>
              <p>
                Mockups de app, casas inteligentes, paines solares premium e
                visuais de dados.
              </p>
            </div>
            <div className={styles.brandCard}>
              <h3>Linguagem</h3>
              <p>Direta, objetiva, focada em economia, controle e confianca.</p>
            </div>
          </div>
        </section>

        <section className={styles.sectionAlt}>
          <div className={styles.sectionHeading}>
            <h2>Conceito completo do aplicativo</h2>
            <p>Experiencia simples, intuitiva e elegante.</p>
          </div>
          <div className={styles.appConcept}>
            <div>
              <h3>Tela inicial</h3>
              <p>Resumo da energia do dia, score e status dos sistemas.</p>
            </div>
            <div>
              <h3>Dashboard principal</h3>
              <p>Graficos de consumo, geracao e previsoes em tempo real.</p>
            </div>
            <div>
              <h3>Monitoramento por ambiente</h3>
              <p>Mapa da casa/empresa com consumo por zona.</p>
            </div>
            <div>
              <h3>Monitoramento por dispositivo</h3>
              <p>Detalhe de cargas, horarios e custo estimado.</p>
            </div>
            <div>
              <h3>Alertas</h3>
              <p>Deteccao de anomalias e consumo fora do padrao.</p>
            </div>
            <div>
              <h3>Automacoes</h3>
              <p>Rotinas, modos de economia e controle remoto.</p>
            </div>
            <div>
              <h3>Relatorios</h3>
              <p>Comparativos mensais, metas e eficiencia energetica.</p>
            </div>
            <div>
              <h3>Configuracoes</h3>
              <p>Perfis de uso, permissoes e integracoes inteligentes.</p>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <h2>Ideias de diferenciais competitivos</h2>
            <p>Onde a tecnologia entrega valor real e mensuravel.</p>
          </div>
          <div className={styles.cards}>
            <article className={styles.card}>
              <h3>IA de consumo preditivo</h3>
              <p>Previsao de picos e recomendacoes automaticas.</p>
            </article>
            <article className={styles.card}>
              <h3>Smart routing de carga</h3>
              <p>Prioriza equipamentos criticos e reduz desperdicios.</p>
            </article>
            <article className={styles.card}>
              <h3>Gemelo digital energetico</h3>
              <p>Simulacoes e cenarios para cada unidade.</p>
            </article>
            <article className={styles.card}>
              <h3>Relatorios executivos</h3>
              <p>KPIs financeiros, sustentabilidade e compliance.</p>
            </article>
          </div>
        </section>

        <section className={styles.sectionAlt}>
          <div className={styles.sectionHeading}>
            <h2>Tecnologia por tras da plataforma</h2>
            <p>Arquitetura robusta para dados e controle em tempo real.</p>
          </div>
          <div className={styles.techGrid}>
            <div>
              <h4>Edge controllers</h4>
              <p>Coleta local com latencia minima e redundancia.</p>
            </div>
            <div>
              <h4>Digital twin</h4>
              <p>Modelo energetico para simulacoes e previsoes.</p>
            </div>
            <div>
              <h4>Data lake energetico</h4>
              <p>Historico completo para insights e comparativos.</p>
            </div>
            <div>
              <h4>Automacao inteligente</h4>
              <p>Motor de regras + ML para economia automatizada.</p>
            </div>
          </div>
        </section>

        <section className={styles.finalCta}>
          <div>
            <h2>Pronto para transformar energia em inteligencia?</h2>
            <p>
              Solicite um diagnostico energetico ou agende uma consultoria para
              ver a LumenX em operacao.
            </p>
          </div>
          <div className={styles.finalActions}>
            <button className={styles.primaryCta}>Pedir demonstracao</button>
            <button className={styles.ghostCta}>Agendar consultoria</button>
          </div>
        </section>
      </main>
    </div>
  );
}
