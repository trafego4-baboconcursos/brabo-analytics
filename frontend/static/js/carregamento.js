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
     Só frases com fonte primária conferida (obra, carta, discurso ou entrevista);
     redação popular que não é do autor sai. Conferência de 12/11/26. A primeira
     aparece depois de ~400ms — navegação rápida não pisca frase — e troca a
     cada 7s enquanto a espera durar.
     [frase, autor, slug do retrato]. O retrato fica em
     static/img/pensadores/<slug>.webp (gerado por scripts/gerar_retratos_pensadores.py,
     que tem a descrição visual de cada slug). Bíblicas: texto da NVI 1993/2000 (a do Bible Gateway, NVI-PT), autor
     com livro e versículo. */
  var BS_QUOTES = [
    // filósofos
    ["Não é porque as coisas são difíceis que não ousamos; é porque não ousamos que elas são difíceis.", "Sêneca", "seneca"],
    ["Nenhum vento é favorável para quem não sabe a que porto se dirige.", "Sêneca", "seneca"],
    ["Enquanto adiamos, a vida passa.", "Sêneca", "seneca"],
    ["Tornamo-nos justos praticando atos justos, moderados praticando atos moderados, corajosos praticando atos corajosos.", "Aristóteles", "aristoteles"],
    ["Todos os homens, por natureza, desejam saber.", "Aristóteles", "aristoteles"],
    ["Bem começado, metade feito.", "Aristóteles", "aristoteles"],
    ["A alma se tinge dos seus pensamentos.", "Marco Aurélio", "marco-aurelio"],
    ["O que atrapalha o caminho torna-se o caminho.", "Marco Aurélio", "marco-aurelio"],
    ["Não perca mais tempo discutindo como deve ser um homem bom. Seja um.", "Marco Aurélio", "marco-aurelio"],
    ["Não são as coisas que perturbam os homens, mas as opiniões que eles têm sobre elas.", "Epicteto", "epicteto"],
    ["Primeiro diga a si mesmo o que você quer ser; depois faça o que tem de fazer.", "Epicteto", "epicteto"],
    ["Só sei que nada sei.", "Sócrates", "socrates"],
    ["Uma vida sem reflexão não merece ser vivida.", "Sócrates", "socrates"],
    ["O começo é a parte mais importante do trabalho.", "Platão", "platao"],
    ["O homem é a medida de todas as coisas.", "Protágoras", "protagoras"],
    ["Ninguém entra duas vezes no mesmo rio.", "Heráclito", "heraclito"],
    ["Não estrague o que você tem desejando o que não tem; lembre-se de que o que tem agora já esteve entre as coisas que você só desejava.", "Epicuro", "epicuro"],
    ["A gratidão não é só a maior das virtudes, mas a mãe de todas as outras.", "Cícero", "cicero"],
    ["Errar e não se corrigir: isso, sim, é errar.", "Confúcio", "confucio"],
    ["Quando sabes, admitir que sabes; quando não sabes, admitir que não sabes: isso é saber.", "Confúcio", "confucio"],
    ["Uma viagem de mil milhas começa com um único passo.", "Lao Tsé", "lao-tse"],
    ["Conhece o inimigo e conhece a ti mesmo; em cem batalhas, nunca correrás perigo.", "Sun Tzu", "sun-tzu"],
    ["A palavra é metade de quem fala, metade de quem ouve.", "Michel de Montaigne", "montaigne"],
    ["O coração tem razões que a própria razão desconhece.", "Blaise Pascal", "pascal"],
    ["Penso, logo existo.", "René Descartes", "descartes"],
    ["Tudo o que é excelente é tão difícil quanto raro.", "Baruch Spinoza", "spinoza"],
    ["O ótimo é inimigo do bom.", "Voltaire", "voltaire"],
    ["Viver não é respirar, é agir.", "Jean-Jacques Rousseau", "rousseau"],
    ["Ousa saber.", "Immanuel Kant", "kant"],
    ["A vida só pode ser compreendida olhando-se para trás, mas só pode ser vivida olhando-se para a frente.", "Søren Kierkegaard", "kierkegaard"],
    ["O talento acerta um alvo que ninguém mais consegue acertar; o gênio acerta um alvo que ninguém mais consegue ver.", "Arthur Schopenhauer", "schopenhauer"],
    ["Quem tem um porquê para viver suporta quase qualquer como.", "Friedrich Nietzsche", "nietzsche"],
    ["No mundo moderno, os estúpidos têm certeza de tudo, e os inteligentes estão cheios de dúvida.", "Bertrand Russell", "bertrand-russell"],
    ["Os limites da minha linguagem significam os limites do meu mundo.", "Ludwig Wittgenstein", "wittgenstein"],
    // grandes pensadores
    ["Assim como o ferro enferruja sem uso e a água apodrece ou congela no frio, o intelecto se estraga se não for exercitado.", "Leonardo da Vinci", "leonardo-da-vinci"],
    ["Nossas dúvidas são traidoras e nos fazem perder o bem que poderíamos conquistar, por medo de tentar.", "William Shakespeare", "shakespeare"],
    ["Conhecimento é poder.", "Francis Bacon", "francis-bacon"],
    ["A leitura é para o intelecto o que o exercício é para o corpo.", "Joseph Addison", "joseph-addison"],
    ["Bem feito é melhor do que bem dito.", "Benjamin Franklin", "benjamin-franklin"],
    ["Saber não basta; é preciso aplicar. Querer não basta; é preciso fazer.", "Johann Wolfgang von Goethe", "goethe"],
    ["Aqueles que não conseguem lembrar o passado estão condenados a repeti-lo.", "George Santayana", "santayana"],
    ["A força não vem da capacidade física. Vem de uma vontade indomável.", "Mahatma Gandhi", "gandhi"],
    ["Nunca ceda — nunca, nunca, nunca, nunca.", "Winston Churchill", "churchill"],
    ["Sozinhos, podemos tão pouco; juntos, podemos tanto.", "Helen Keller", "helen-keller"],
    ["Tudo pode ser tirado de uma pessoa, menos a última das liberdades humanas: escolher a própria atitude diante de qualquer circunstância.", "Viktor Frankl", "viktor-frankl"],
    ["Se não puder voar, corra; se não puder correr, ande; se não puder andar, rasteje; mas, faça o que fizer, continue em frente.", "Martin Luther King Jr.", "martin-luther-king"],
    ["A educação é a arma mais poderosa que você pode usar para mudar o mundo.", "Nelson Mandela", "mandela"],
    ["Não há nada tão inútil quanto fazer com grande eficiência aquilo que nem deveria ser feito.", "Peter Drucker", "drucker"],
    ["Só existe uma definição válida para o propósito de uma empresa: criar um cliente.", "Peter Drucker", "drucker"],
    ["A única maneira de fazer um grande trabalho é amar o que você faz.", "Steve Jobs", "steve-jobs"],
    ["Tudo vale a pena se a alma não é pequena.", "Fernando Pessoa", "fernando-pessoa"],
    ["Eu sou do tamanho do que vejo e não do tamanho da minha altura.", "Fernando Pessoa (Alberto Caeiro)", "fernando-pessoa"],
    ["Feliz aquele que transfere o que sabe e aprende o que ensina.", "Cora Coralina", "cora-coralina"],
    ["Removi pedras, quebrei arestas da vida e plantei roseiras.", "Cora Coralina", "cora-coralina"],
    ["No meio do caminho tinha uma pedra.", "Carlos Drummond de Andrade", "drummond"],
    ["O correr da vida embrulha tudo, a vida é assim: esquenta e esfria, aperta e daí afrouxa, sossega e depois desinquieta. O que ela quer da gente é coragem.", "Guimarães Rosa", "guimaraes-rosa"],
    ["Liberdade é pouco. O que eu desejo ainda não tem nome.", "Clarice Lispector", "clarice-lispector"],
    ["Os otimistas são ingênuos, e os pessimistas, amargos. Eu me considero um realista esperançoso.", "Ariano Suassuna", "suassuna"],
    ["Somei mais fracassos que vitórias em minhas lutas. Horrível seria ter ficado ao lado dos que nos venceram.", "Darcy Ribeiro", "darcy-ribeiro"],
    ["Ensinar não é transferir conhecimento, mas criar as possibilidades para a sua própria produção.", "Paulo Freire", "paulo-freire"],
    // bíblicos (NVI 1993/2000)
    ["Consagre ao Senhor tudo o que você faz, e os seus planos serão bem-sucedidos.", "Salomão · Provérbios 16:3", "salomao"],
    ["Observe a formiga, preguiçoso, reflita nos caminhos dela e seja sábio!", "Salomão · Provérbios 6:6", "salomao"],
    ["Assim como o ferro afia o ferro, o homem afia o seu companheiro.", "Salomão · Provérbios 27:17", "salomao"],
    ["Para tudo há uma ocasião certa; há um tempo certo para cada propósito debaixo do céu.", "O Mestre · Eclesiastes 3:1", "salomao"],
    ["O Senhor é o meu pastor; de nada terei falta.", "Davi · Salmos 23:1", "davi"],
    ["O Senhor é a minha luz e a minha salvação; de quem terei temor?", "Davi · Salmos 27:1", "davi"],
    ["Ensina-nos a contar os nossos dias para que o nosso coração alcance sabedoria.", "Moisés · Salmos 90:12", "moises"],
    ["Seja forte e corajoso! Não se apavore, nem desanime, pois o Senhor, o seu Deus, estará com você por onde você andar.", "Josué 1:9", "josue"],
    ["Mas aqueles que esperam no Senhor renovam as suas forças. Voam alto como águias; correm e não ficam exaustos, andam e não se cansam.", "Isaías 40:31", "isaias"],
    ["Porque sou eu que conheço os planos que tenho para vocês, diz o Senhor, planos de fazê-los prosperar e não de lhes causar dano, planos de dar-lhes esperança e um futuro.", "Jeremias 29:11", "jeremias"],
    ["Peçam, e lhes será dado; busquem, e encontrarão; batam, e a porta lhes será aberta.", "Jesus · Mateus 7:7", "jesus"],
    ["Portanto, não se preocupem com o amanhã, pois o amanhã trará as suas próprias preocupações. Basta a cada dia o seu próprio mal.", "Jesus · Mateus 6:34", "jesus"],
    ["Tudo posso naquele que me fortalece.", "Paulo · Filipenses 4:13", "paulo"],
    ["Combati o bom combate, terminei a corrida, guardei a fé.", "Paulo · 2 Timóteo 4:7", "paulo"],
    ["E não nos cansemos de fazer o bem, pois no tempo próprio colheremos, se não desanimarmos.", "Paulo · Gálatas 6:9", "paulo"],
    ["Assim, permanecem agora estes três: a fé, a esperança e o amor. O maior deles, porém, é o amor.", "Paulo · 1 Coríntios 13:13", "paulo"],
    ["Se algum de vocês tem falta de sabedoria, peça-a a Deus, que a todos dá livremente, de boa vontade; e lhe será concedida.", "Tiago 1:5", "tiago"],
    ["Lancem sobre ele toda a sua ansiedade, porque ele tem cuidado de vocês.", "Pedro · 1 Pedro 5:7", "pedro"],
    // cientistas
    ["Deem-me um ponto de apoio e eu moverei a Terra.", "Arquimedes", "arquimedes"],
    ["Se eu vi mais longe, foi por estar sobre ombros de gigantes.", "Isaac Newton", "newton"],
    ["Nada se cria, nem nas operações da arte nem nas da natureza; há apenas mudanças e modificações.", "Antoine Lavoisier", "lavoisier"],
    ["Nada é bom demais para ser verdade, se for coerente com as leis da natureza.", "Michael Faraday", "faraday"],
    ["No campo da observação, o acaso favorece apenas as mentes preparadas.", "Louis Pasteur", "pasteur"],
    ["Um homem que ousa desperdiçar uma hora de tempo não descobriu o valor da vida.", "Charles Darwin", "darwin"],
    ["Gênio é um por cento de inspiração e noventa e nove por cento de transpiração.", "Thomas Edison", "edison"],
    ["Não esmorecer para não desmerecer.", "Oswaldo Cruz", "oswaldo-cruz"],
    ["A vida não é fácil para nenhum de nós. Mas e daí? Precisamos ter perseverança e, acima de tudo, confiança em nós mesmos.", "Marie Curie", "marie-curie"],
    ["A imaginação é mais importante que o conhecimento.", "Albert Einstein", "einstein"],
    ["O importante é não parar de questionar.", "Albert Einstein", "einstein"],
    ["A vida é como andar de bicicleta: para manter o equilíbrio, é preciso continuar em movimento.", "Albert Einstein", "einstein"],
    ["No drama da existência, nós mesmos somos ao mesmo tempo atores e espectadores.", "Niels Bohr", "niels-bohr"],
    ["A penicilina começou como uma observação casual. Meu único mérito foi não desprezar a observação e segui-la como bacteriologista.", "Alexander Fleming", "fleming"],
    ["Só podemos enxergar um pouco à frente, mas podemos ver muito do que ainda precisa ser feito.", "Alan Turing", "turing"],
    ["A melhor maneira de ter uma boa ideia é ter muitas ideias.", "Linus Pauling", "linus-pauling"],
    ["A ciência e a vida cotidiana não podem e não devem ser separadas.", "Rosalind Franklin", "rosalind-franklin"],
    ["O primeiro princípio é que você não deve enganar a si mesmo — e você é a pessoa mais fácil de enganar.", "Richard Feynman", "feynman"],
    ["O que eu não consigo criar, eu não entendo.", "Richard Feynman", "feynman"],
    ["Afirmações extraordinárias exigem evidências extraordinárias.", "Carl Sagan", "carl-sagan"],
    ["Por mais difícil que a vida pareça, sempre há algo que você pode fazer e em que pode ter sucesso.", "Stephen Hawking", "hawking"],
    ["Cada um de nós faz diferença todos os dias. E temos escolha: que tipo de diferença queremos fazer?", "Jane Goodall", "jane-goodall"],
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
  // Easter egg do tema "Diretiva Primária" — RoboCop (1987).
  var RC_QUOTES = [
    ["Vivo ou morto, você vem comigo.", "RoboCop, RoboCop (1987)"],
    ["Servir à confiança pública. Proteger os inocentes. Cumprir a lei.", "Diretivas primárias, RoboCop (1987)"],
    ["Sua vez, verme.", "RoboCop, RoboCop (1987)"],
    ["Obrigado pela cooperação. Boa noite.", "RoboCop, RoboCop (1987)"],
    ["Por favor, largue a arma. Você tem 20 segundos para obedecer.", "ED-209, RoboCop (1987)"],
    ["Eu compraria isso por um dólar!", "Bixby Snyder, RoboCop (1987)"],
    ["Tenho certeza de que é só uma falha. Um contratempo temporário.", "Dick Jones, RoboCop (1987)"],
    ["A Velha Detroit tem um câncer. Esse câncer é o crime.", "Reunião da diretoria da OCP, RoboCop (1987)"],
    ["Murphy, é você.", "Anne Lewis, RoboCop (1987)"],
    ["Bela pontaria, filho. Qual é o seu nome? — Murphy.", "Presidente da OCP e RoboCop, RoboCop (1987)"],
    ["Diretiva 4: confidencial.", "Visor do RoboCop, RoboCop (1987)"],
    ["Você sabe voar, Bobby?", "Clarence Boddicker, RoboCop (1987)"],
  ];
  // Temas de Natal. "Esta Casa É Minha" — Esqueceram de Mim (1990).
  var KV_QUOTES = [
    ["Feliz Natal, seu animal imundo!", "Johnny, em “Anjos com Almas Imundas” — Esqueceram de Mim (1990)"],
    ["Fique com o troco, seu animal imundo.", "Johnny, em “Anjos com Almas Imundas” — Esqueceram de Mim (1990)"],
    ["Esta é a minha casa. Eu tenho que defendê-la.", "Kevin McCallister, Esqueceram de Mim (1990)"],
    ["Eu fiz a minha família desaparecer!", "Kevin McCallister, Esqueceram de Mim (1990)"],
    ["Eu não tenho mais medo!", "Kevin McCallister, Esqueceram de Mim (1990)"],
    ["Estou comendo besteira e vendo porcaria! É melhor vocês virem me impedir!", "Kevin McCallister, Esqueceram de Mim (1990)"],
    ["Se você vir o Papai Noel, diga que, em vez de presentes, este ano eu só quero a minha família de volta.", "Kevin McCallister, Esqueceram de Mim (1990)"],
    ["Kevin, você é o que os franceses chamam de les incompétents.", "Linnie McCallister, Esqueceram de Mim (1990)"],
    ["Kevin!", "Kate McCallister, Esqueceram de Mim (1990)"],
    ["Nós somos os Bandidos Molhados.", "Marv, Esqueceram de Mim (1990)"],
  ];
  // "Quemlândia" — O Grinch (livro do Dr. Seuss, 1957, e filme de 2000).
  var GR_QUOTES = [
    ["O Grinch odiava o Natal! A temporada de Natal inteira! Por favor, não pergunte por quê. Ninguém sabe bem o motivo.", "Como o Grinch Roubou o Natal, Dr. Seuss"],
    ["Cada Quem lá embaixo, em Quemlândia, gostava muito do Natal… mas o Grinch, que morava ao norte de Quemlândia, não!", "Como o Grinch Roubou o Natal, Dr. Seuss"],
    ["O Natal veio! Veio sem fitas! Veio sem etiquetas! Veio sem pacotes, caixas ou sacolas!", "Como o Grinch Roubou o Natal, Dr. Seuss"],
    ["Talvez o Natal não venha de uma loja. Talvez o Natal… signifique um pouquinho mais!", "O Grinch, Como o Grinch Roubou o Natal (Dr. Seuss)"],
    ["E dizem, em Quemlândia, que o pequeno coração do Grinch cresceu três tamanhos naquele dia.", "Como o Grinch Roubou o Natal, Dr. Seuss"],
    ["4h: chafurdar na autopiedade. 4h30: encarar o abismo. 5h: resolver a fome no mundo, não contar a ninguém.", "A agenda do Grinch, O Grinch (2000)"],
    ["Onde está você, Natal?", "Cindy Lou Quem, O Grinch (2000)"],
  ];
  function activeQuotes() {
    var t = document.documentElement.getAttribute('data-bs-theme');
    if (t === 'kevin') return KV_QUOTES;
    if (t === 'grinch') return GR_QUOTES;
    if (t === 'diretiva') return RC_QUOTES;
    if (t === 'outatime') return BF_QUOTES;
    if (t === 'predador') return PD_QUOTES;
    if (t === 'spidey') return SM_QUOTES;
    if (t === 'aranhaverso') return SV_QUOTES;
    return BS_QUOTES;
  }
  var quoteBox = document.getElementById('bs-loading-quote');
  var _qDelay = null, _qRotate = null, _qLast = -1, _qNext = -1;

  /* Retrato do autor dentro do anel (só nas frases com slug — as dos temas
     de filme não têm, e esses temas escondem o anel). A cor do tema vem de
     um overlay em CSS. Sem imagem (404/erro), cai nas iniciais. */
  var fotoBox = overlay ? overlay.querySelector('.bs-loading-foto') : null;
  var fotoImg = fotoBox ? fotoBox.querySelector('img') : null;
  var fotoIni = fotoBox ? fotoBox.querySelector('.bs-loading-ini') : null;
  var FOTO_BASE = (overlay && overlay.getAttribute('data-fotos')) || '/static/img/pensadores/';
  function fotoUrl(slug) { return FOTO_BASE + slug + '.webp'; }
  function iniciais(autor) {
    var nome = autor.split(' · ')[0].replace(/[^\p{L}\s]/gu, ' ').trim().split(/\s+/);
    var ini = nome[0].charAt(0) + (nome.length > 1 ? nome[nome.length - 1].charAt(0) : '');
    return ini.toUpperCase();
  }
  if (fotoImg) {
    fotoImg.addEventListener('error', function() { fotoBox.classList.add('sem-foto'); });
    fotoImg.addEventListener('load', function() { fotoBox.classList.remove('sem-foto'); });
  }
  function sorteia(quotes, evita) {
    var i;
    do { i = Math.floor(Math.random() * quotes.length); } while (i === evita && quotes.length > 1);
    return i;
  }
  function preload(q) { if (q && q[2]) { var im = new Image(); im.src = fotoUrl(q[2]); } }

  function bsQuoteShow() {
    var quotes = activeQuotes();
    if (!quoteBox || quotes.length === 0) return;
    var i = (_qNext >= 0 && _qNext < quotes.length && _qNext !== _qLast) ? _qNext : sorteia(quotes, _qLast);
    _qLast = i;
    _qNext = sorteia(quotes, i);
    preload(quotes[_qNext]);   // a próxima foto já chega em cache antes da troca
    quoteBox.classList.remove('in');
    if (fotoBox) fotoBox.classList.remove('in');
    setTimeout(function() {
      var q = quotes[i];
      quoteBox.querySelector('.q').textContent = q[0];
      quoteBox.querySelector('.a').textContent = q[1];
      quoteBox.classList.add('in');
      if (fotoBox && q[2]) {
        fotoIni.textContent = iniciais(q[1]);
        fotoBox.classList.remove('sem-foto');
        fotoImg.src = fotoUrl(q[2]);
        fotoBox.classList.add('in');
      }
    }, quoteBox.classList.contains('in') ? 300 : 0);
  }
  function bsQuoteStart() {
    bsQuoteStop();
    // já sorteia a primeira e baixa a foto nos ~400ms antes de ela aparecer
    var quotes = activeQuotes();
    if (quotes.length && _qNext < 0) { _qNext = sorteia(quotes, _qLast); preload(quotes[_qNext]); }
    _qDelay = setTimeout(function() {
      bsQuoteShow();
      _qRotate = setInterval(bsQuoteShow, 7000);
    }, 400);
  }
  function bsQuoteStop() {
    clearTimeout(_qDelay); clearInterval(_qRotate);
    _qDelay = _qRotate = null;
    if (quoteBox) quoteBox.classList.remove('in');
    if (fotoBox) fotoBox.classList.remove('in');
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
