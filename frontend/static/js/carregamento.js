/* Extraído de frontend/templates/base.html em 21/09/2026.
   Carregado com <script> síncrono, na mesma ordem em que estava inline.
   Estes arquivos dependem dessa ordem (ex.: tema.js define bsThemeTokens,
   usado depois). Não adicionar defer/async sem revisar as dependências. */
/* frases de loading, barra de progresso, overlay de navegação */

// Nav loading indicator + top progress bar
(function() {
  var fill = document.getElementById('bs-topbar-fill');
  var overlay = document.getElementById('bs-loading-overlay');
  var _timer = null;

  /* ── Frases de pensadores enquanto carrega ──────────────────────────
     Só frases de atribuição consolidada (evita as "de internet"). A primeira
     aparece depois de ~400ms — navegação rápida não pisca frase — e troca a
     cada 7s enquanto a espera durar. */
  var BS_QUOTES = [
    ["Não é porque as coisas são difíceis que não ousamos; é porque não ousamos que elas são difíceis.", "Sêneca"],
    ["Nenhum vento é favorável para quem não sabe a que porto se dirige.", "Sêneca"],
    ["Somos o que fazemos repetidamente. A excelência, portanto, não é um ato, mas um hábito.", "Aristóteles"],
    ["A felicidade da sua vida depende da qualidade dos seus pensamentos.", "Marco Aurélio"],
    ["O que atrapalha o caminho torna-se o caminho.", "Marco Aurélio"],
    ["Não é o que acontece com você, mas como você reage, que importa.", "Epicteto"],
    ["Só sei que nada sei.", "Sócrates"],
    ["Uma vida sem reflexão não merece ser vivida.", "Sócrates"],
    ["O começo é a parte mais importante do trabalho.", "Platão"],
    ["Escolhe um trabalho de que gostes, e não terás que trabalhar nem um dia na tua vida.", "Confúcio"],
    ["Não importa quão devagar você vá, desde que não pare.", "Confúcio"],
    ["Uma viagem de mil milhas começa com um único passo.", "Lao Tsé"],
    ["Conhece o inimigo e conhece a ti mesmo; em cem batalhas, nunca correrás perigo.", "Sun Tzu"],
    ["A simplicidade é a sofisticação máxima.", "Leonardo da Vinci"],
    ["A imaginação é mais importante que o conhecimento.", "Albert Einstein"],
    ["No meio da dificuldade encontra-se a oportunidade.", "Albert Einstein"],
    ["Penso, logo existo.", "René Descartes"],
    ["Ousa saber.", "Immanuel Kant"],
    ["Quem tem um porquê para viver suporta quase qualquer como.", "Friedrich Nietzsche"],
    ["A dúvida é o princípio da sabedoria.", "Aristóteles"],
    ["O que não se pode medir não se pode melhorar.", "Peter Drucker"],
    ["A melhor maneira de prever o futuro é criá-lo.", "Peter Drucker"],
    ["A paciência é amarga, mas o seu fruto é doce.", "Jean-Jacques Rousseau"],
    ["O homem é a medida de todas as coisas.", "Protágoras"],
    ["Bem começado, metade feito.", "Aristóteles"],
    ["Feliz aquele que transfere o que sabe e aprende o que ensina.", "Cora Coralina"],
    ["Tudo vale a pena se a alma não é pequena.", "Fernando Pessoa"],
    ["Navegar é preciso; viver não é preciso.", "Fernando Pessoa"],
    ["O saber a gente aprende com os mestres e os livros. A sabedoria, se aprende é com a vida e com os humildes.", "Cora Coralina"],
    ["A leitura é para o intelecto o que o exercício é para o corpo.", "Joseph Addison"],
    ["Conhecimento é poder.", "Francis Bacon"],
    ["Quem não conhece a história está condenado a repeti-la.", "George Santayana"],
    ["A educação é a arma mais poderosa que você pode usar para mudar o mundo.", "Nelson Mandela"],
    ["Ensinar não é transferir conhecimento, mas criar as possibilidades para a sua própria produção.", "Paulo Freire"],
  ];
  // Easter egg: no tema "Outatime" (De Volta para o Futuro), as frases de
  // pensador viram falas do filme — trocam junto quando o tema muda
  // (bsSetTheme recarrega a página, então isso já pega o valor certo).
  var BF_QUOTES = [
    ["Estradas? Aonde vamos, não precisamos de estradas.", "Doc Brown, De Volta para o Futuro"],
    ["Grande Scott!", "Doc Brown, De Volta para o Futuro"],
    ["Se pudermos gerar 1,21 gigawatts de eletricidade...", "Doc Brown, De Volta para o Futuro"],
    ["O seu futuro ainda não foi escrito. O de ninguém foi. Faça dele um bom futuro.", "Doc Brown, De Volta para o Futuro"],
    ["Se você põe sua mente nisso, você pode realizar qualquer coisa.", "Doc Brown, De Volta para o Futuro"],
    ["Ninguém me chama de covarde.", "Marty McFly, De Volta para o Futuro"],
    ["Espera um pouco, Doc. Você está me dizendo que construiu uma máquina do tempo... com um DeLorean?", "Marty McFly, De Volta para o Futuro"],
    ["É isso aí, McFly, seu covarde.", "Biff Tannen, De Volta para o Futuro"],
    ["Isso é pesado.", "Marty McFly, De Volta para o Futuro"],
    ["Enquanto eu estiver aqui, sob nenhuma circunstância entre na casa dos seus pais.", "Doc Brown, De Volta para o Futuro"],
    ["Você é minha densidade... quer dizer, meu destino.", "George McFly, De Volta para o Futuro"],
    ["Faz que nem árvore e sai daqui.", "George McFly, De Volta para o Futuro"],
    ["Finalmente inventei uma coisa que funciona!", "Doc Brown, De Volta para o Futuro"],
    ["Do jeito que eu penso, se vai construir uma máquina do tempo dentro de um carro, por que não fazer com estilo?", "Doc Brown, De Volta para o Futuro"],
    ["Alô? Alô? Tem alguém aí? Pensa, McFly, pensa!", "Biff Tannen, De Volta para o Futuro"],
    ["Espera um instante, Doc. Você está dizendo que minha mãe está caidinha por mim?", "Marty McFly, De Volta para o Futuro"],
    ["Salvem a torre do relógio!", "De Volta para o Futuro"],
    ["Vinte e cinco anos atrás, quase morri por causa daquele maldito relógio.", "Doc Brown, De Volta para o Futuro"],
    ["Seus filhos, Marty! Precisa fazer alguma coisa com os seus filhos!", "Doc Brown, De Volta para o Futuro II"],
    ["Acho que vocês não estão prontos pra isso ainda. Mas os seus filhos vão adorar.", "Marty McFly, De Volta para o Futuro"],
  ];
  // Easter egg do tema "Predador" — mesma ideia do Outatime, filme diferente.
  var PD_QUOTES = [
    ["Se sangra, a gente pode matar.", "Dutch, Predador"],
    ["Vai pro helicóptero!", "Dutch, Predador"],
    ["Não tenho tempo pra sangrar.", "Blain, Predador"],
    ["Tem alguma coisa lá fora esperando por nós, e não é gente.", "Dutch, Predador"],
    ["O que diabos você é?", "Dutch, Predador"],
    ["Dillon, seu filho da mãe!", "Dutch, Predador"],
    ["Qualquer hora, qualquer lugar.", "Dutch e Dillon, Predador"],
    ["Fica aí!", "Dutch, Predador"],
    ["Anda logo, vamos embora daqui.", "Dutch, Predador"],
    ["Nós somos os caçadores, mas dessa vez fomos caçados.", "Dutch, Predador"],
  ];
  // Easter egg do tema "Amigão da Vizinhança" — não só do Homem-Aranha 2,
  // trilogia do Raimi + quadrinhos clássicos + Stan Lee + Aranhaverso.
  var SM_QUOTES = [
    ["Poderes grandes trazem grandes responsabilidades.", "Tio Ben, Homem-Aranha"],
    ["Seu amigo e vizinho, o Homem-Aranha.", "Slogan clássico dos quadrinhos"],
    ["Homem-Aranha: ameaça!", "J. Jonah Jameson, Homem-Aranha"],
    ["Fotos! Eu quero fotos do Homem-Aranha!", "J. Jonah Jameson, Homem-Aranha"],
    ["Vamos chamá-lo de... Homem-Aranha.", "J. Jonah Jameson batizando o herói, Homem-Aranha"],
    ["Existe um herói dentro de todos nós, que nos mantém honestos, nos dá força, nos torna nobres.", "Tia May, Homem-Aranha 2"],
    ["Às vezes temos que desistir de quem somos pra virar quem deveríamos ser.", "Tia May, Homem-Aranha 2"],
    ["A inteligência é um presente. Se usa pelo bem da humanidade.", "Otto Octavius, Homem-Aranha 2"],
    ["Nós não somos tão diferentes, você e eu.", "Duende Verde, Homem-Aranha"],
    ["Você é meu herói.", "Mary Jane Watson, Homem-Aranha"],
    ["Meu sentido aranha está formigando.", "Peter Parker"],
    ["Nunca foi fácil ser eu.", "Peter Parker"],
    ["Eu já fiz minha escolha. Eu sou o Homem-Aranha.", "Peter Parker, Homem-Aranha 2"],
    ["Excelsior!", "Stan Lee"],
    ["Qualquer um pode vestir a máscara. Você pode vestir a máscara.", "Homem-Aranha, No Aranhaverso"],
    ["Às vezes você tem que dar um salto de fé.", "Homem-Aranha, No Aranhaverso"],
    ["Faz o que pode um aranha fazer.", "Tema de abertura, desenho de 1967"],
    ["Todo mundo já pensou, em algum momento, o que faria se tivesse superpoderes.", "Peter Parker, narração, Homem-Aranha"],
    ["Nova York merece um herói de verdade.", "J. Jonah Jameson, Homem-Aranha"],
    ["Peter Parker, o fotógrafo mais azarado de Nova York.", "Apelido recorrente no Clarim Diário"],
  ];
  // Easter egg do tema "Aranhaverso" — Miles Morales e o multiverso
  // (Homem-Aranha no Aranhaverso + Através do Aranhaverso).
  var SV_QUOTES = [
    ["Qualquer um pode vestir a máscara.", "Miles Morales, Homem-Aranha no Aranhaverso"],
    ["Mais de um usa a máscara.", "Slogan oficial, Homem-Aranha no Aranhaverso"],
    ["Você pode ser mais de uma coisa.", "Rio Morales, Através do Aranhaverso"],
    ["Eu sou o Homem-Aranha. E vou ficar bem.", "Miles Morales, Homem-Aranha no Aranhaverso"],
    ["Isso é canon.", "Bordão recorrente, Através do Aranhaverso"],
    ["O cânone existe pra proteger todo mundo.", "Miguel O'Hara, Através do Aranhaverso"],
    ["Cada Aranha tem uma queda. Faz parte da história.", "Gwen Stacy, Através do Aranhaverso"],
    ["Isso é uma coisa de Homem-Aranha.", "Peter B. Parker, Homem-Aranha no Aranhaverso"],
    ["Às vezes você tem que dar um salto de fé.", "Miles Morales, Homem-Aranha no Aranhaverso"],
    ["Todo mundo que já usou a máscara teve um dia ruim.", "Peter B. Parker, Homem-Aranha no Aranhaverso"],
    ["Um bom Homem-Aranha guarda segredo de todo mundo. Um grande Homem-Aranha guarda segredo até de si mesmo.", "Miguel O'Hara, Através do Aranhaverso"],
    ["Bem-vindo ao clube.", "Bordão entre os Homens-Aranha do multiverso"],
    ["O multiverso é muito mais frágil do que você imagina.", "Miguel O'Hara, Através do Aranhaverso"],
    ["Eu sou a Gwen Stacy, também conhecida como Homem-Aranha.", "Gwen Stacy, se apresentando"],
    ["Poderes grandes trazem grandes responsabilidades — em qualquer universo.", "Narração, Homem-Aranha no Aranhaverso"],
    ["Um radioaranha te mordeu. Bem-vindo ao clube.", "Bordão de origem, Aranhaverso"],
  ];
  function activeQuotes() {
    var t = document.documentElement.getAttribute('data-bs-theme');
    if (t === 'outatime') return BF_QUOTES;
    if (t === 'predador') return PD_QUOTES;
    if (t === 'spidey') return SM_QUOTES;
    if (t === 'aranhaverso') return SV_QUOTES;
    return BS_QUOTES;
  }
  var quoteBox = document.getElementById('bs-loading-quote');
  var _qDelay = null, _qRotate = null, _qLast = -1;

  function bsQuoteShow() {
    var quotes = activeQuotes();
    if (!quoteBox || quotes.length === 0) return;
    var i;
    do { i = Math.floor(Math.random() * quotes.length); } while (i === _qLast && quotes.length > 1);
    _qLast = i;
    quoteBox.classList.remove('in');
    setTimeout(function() {
      quoteBox.querySelector('.q').textContent = quotes[i][0];
      quoteBox.querySelector('.a').textContent = quotes[i][1];
      quoteBox.classList.add('in');
    }, quoteBox.classList.contains('in') ? 300 : 0);
  }
  function bsQuoteStart() {
    bsQuoteStop();
    _qDelay = setTimeout(function() {
      bsQuoteShow();
      _qRotate = setInterval(bsQuoteShow, 7000);
    }, 400);
  }
  function bsQuoteStop() {
    clearTimeout(_qDelay); clearInterval(_qRotate);
    _qDelay = _qRotate = null;
    if (quoteBox) quoteBox.classList.remove('in');
  }

  function startProgress() {
    if (overlay) overlay.classList.add('show');
    bsQuoteStart();
    if (!fill) return;
    fill.style.transition = 'none';
    fill.style.width = '0%';
    requestAnimationFrame(function() {
      fill.style.transition = 'width 8s cubic-bezier(0.1,0.05,0,1)';
      fill.style.width = '85%';
    });
  }
  /* Exposto global — bsSoftNavigate (fora desta IIFE) precisa mostrar o
     overlay antes do fetch, não só em navegação normal via <a>. */
  window.bsStartProgress = startProgress;

  function finishProgress() {
    if (overlay) overlay.classList.remove('show');
    bsQuoteStop();
    if (!fill) return;
    fill.style.transition = 'width .2s ease';
    fill.style.width = '100%';
    clearTimeout(_timer);
    _timer = setTimeout(function() {
      fill.style.transition = 'opacity .3s ease';
      fill.style.opacity = '0';
      setTimeout(function() { fill.style.width='0%'; fill.style.opacity='1'; }, 350);
    }, 200);
  }

  document.querySelectorAll('.bs-nav-link:not(.disabled)').forEach(function(link) {
    link.addEventListener('click', function() {
      document.querySelectorAll('.bs-nav-link.loading').forEach(function(l) { l.classList.remove('loading'); });
      link.classList.add('loading');
      startProgress();
    });
  });

  // Links de conteúdo (fora da sidebar) que navegam para outra página desta aba
  document.querySelectorAll('a[href]:not(.bs-nav-link)').forEach(function(link) {
    if (link.target === '_blank') return;
    var href = link.getAttribute('href') || '';
    if (!href || href.charAt(0) === '#' || href.indexOf('javascript:') === 0 || href.indexOf('mailto:') === 0) return;
    link.addEventListener('click', function() { startProgress(); });
  });

  // Seletor de lançamento (troca via onchange -> window.location.href)
  document.querySelectorAll('.bs-camp-select').forEach(function(sel) {
    sel.addEventListener('change', function() { if (sel.value) startProgress(); });
  });

  // Forms que navegam via GET (ex: filtros)
  document.querySelectorAll('form').forEach(function(form) {
    if ((form.method || 'get').toLowerCase() !== 'get') return;
    form.addEventListener('submit', function() { startProgress(); });
  });

  window.addEventListener('pageshow', function() {
    document.querySelectorAll('.bs-nav-link.loading').forEach(function(l) { l.classList.remove('loading'); });
    finishProgress();
  });
})();
