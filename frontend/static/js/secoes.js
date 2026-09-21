/* Extraído de frontend/templates/base.html em 21/09/2026.
   Carregado com <script> síncrono, na mesma ordem em que estava inline.
   Estes arquivos dependem dessa ordem (ex.: tema.js define bsThemeTokens,
   usado depois). Não adicionar defer/async sem revisar as dependências. */
/* accordion, ordem/visibilidade, visualizações salvas, busca */

/* ── Accordion de seções (.section / .section-title) ──────────────────
   Generalizado pra qualquer página que já usa o bloco .section/.section-
   title do design system — não precisa mudar nada no template da página.
   Além de recolher/expandir, dá pra arrastar a ordem, ocultar seções e
   salvar tudo isso como uma "visualização" nomeada (igual o gerenciador
   de colunas do Google Ads). Tudo persiste por página em localStorage —
   é por navegador, não sincroniza entre pessoas/dispositivos. ── */
(function () {
  var SKIP_PAGES = ['settings', 'login', 'invite', 'index'];
  // Vinha interpolado por Jinja quando este bloco era inline no base.html.
  // Agora chega pelo data-page do <body> (setado la, tambem por Jinja).
  var PAGE = document.body.getAttribute('data-page') || 'page';
  if (SKIP_PAGES.indexOf(PAGE) !== -1) return;
  // Modo apresentação/PDF (debriefing ?modo=slides) monta os slides
  // clonando as seções originais — não mexe nelas antes, senão o
  // chevron/tag/etc. vazam pro clone exportado.
  if (document.documentElement.classList.contains('bs-slides')) return;

  function load(key, fallback) {
    try { var v = JSON.parse(localStorage.getItem(key)); return (v === null || v === undefined) ? fallback : v; }
    catch (e) { return fallback; }
  }
  function save(key, val) { try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) {} }
  function esc(s) { return String(s).replace(/</g, '&lt;'); }
  // minúscula sem acento — usada tanto pra key da seção quanto pra busca
  // ("captação" tem que achar digitando "captacao").
  function norm(s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }

  // Tags de etapa — detectadas por palavra-chave no título da seção. Sem
  // match, fica em branco (o usuário atribui manualmente no painel).
  var TAG_DEFS = [
    { name: 'Pré-Quali',       kw: ['pré-qual', 'pre-qual', 'prequal'],                       bg: '#cffafe', fg: '#0e7490' },
    { name: 'Captação',        kw: ['captação', 'captacao'],                                  bg: '#dbeafe', fg: '#1d4ed8' },
    { name: 'Remarketing',     kw: ['remarketing'],                                           bg: '#fee2e2', fg: '#dc2626' },
    { name: 'WhatsApp',        kw: ['whatsapp', 'grupo'],                                     bg: '#dcfce7', fg: '#16a34a' },
    { name: 'Active Campaign', kw: ['active campaign'],                                       bg: '#ede9fe', fg: '#7c3aed' },
    { name: 'Vendas',          kw: ['venda', 'pagamento', 'faturamento', 'matrícul', 'matricul'], bg: '#fef3c7', fg: '#92400e' },
    { name: 'Pesquisa',        kw: ['pesquisa', 'sorteio'],                                   bg: '#fce7f3', fg: '#be185d' },
  ];
  function detectTag(label) {
    var l = label.toLowerCase();
    for (var i = 0; i < TAG_DEFS.length; i++) {
      for (var j = 0; j < TAG_DEFS[i].kw.length; j++) {
        if (l.indexOf(TAG_DEFS[i].kw[j]) !== -1) return TAG_DEFS[i].name;
      }
    }
    return '';
  }
  function tagColors(name) {
    var found = TAG_DEFS.filter(function (t) { return t.name.toLowerCase() === String(name).toLowerCase(); })[0];
    return found ? { bg: found.bg, fg: found.fg } : { bg: '#f3f4f6', fg: '#4b5563' };
  }

  function initAccordion() {
    // .dbf-section/.dbf-section-title é o padrão mais antigo do Debriefing —
    // reconhecido junto do genérico .section/.section-title, sem precisar
    // renomear nada lá (evita quebrar o modo apresentação/PDF, que depende
    // desses nomes de classe pra clonar as seções em slides).
    var allSections = Array.prototype.slice.call(document.querySelectorAll('.section, .dbf-section'))
      .filter(function (s) { return s.querySelector(':scope > .section-title, :scope > .dbf-section-title'); });
    if (allSections.length < 2) return; // 0 ou 1 seção: nada pra organizar

    // key derivada do TÍTULO (slug), não da posição. Era 'section-<idx>' até
    // 17/09/26, quando as visualizações passaram a ser compartilhadas no banco:
    // índice quebra em silêncio assim que alguém insere uma seção no meio do
    // template — a "Padrão" da equipe passaria a apontar pra seção errada, sem
    // erro nenhum. Estado antigo continua sendo lido via legacyKey.
    function slugKey(s) {
      return norm(s).replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 48);
    }
    var usadas = {};
    var meta = allSections.map(function (section, idx) {
      var title = section.querySelector(':scope > .section-title, :scope > .dbf-section-title');
      var label = title.textContent.trim();
      // data-tag no título força a etapa sem depender de palavra-chave no
      // texto — necessário pras seções que tiraram "Captação"/"Pré-
      // Qualificação" do nome (pedido do usuário 16/09/26: a palavra sai
      // do título, mas a tag continua aparecendo).
      var forcedTag = title.getAttribute('data-tag');
      // A chave sai do título SEM as badges de lançamento. Três seções
      // (Resumo Executivo, Detalhamento de Tráfego, Detalhamento por Dia)
      // carregam o código do lançamento no título, então usar o texto inteiro
      // gerava chave diferente por lançamento — "resumo-executivo-pes-set-26-
      // pes-mai-26" num, "resumo-executivo-pes-mai-26-pes-mar-26" noutro. A
      // visualização salva num lançamento não reconhecia essas seções em
      // outro e jogava as três pro fim da página; parecia que tinham sumido
      // (relatado 21/09/26). A badge segue no `label`, que é o que aparece
      // na lista de Seções.
      var semBadge = title.cloneNode(true);
      Array.prototype.forEach.call(semBadge.querySelectorAll('.dbf-launch-badge'),
                                   function (b) { b.parentNode.removeChild(b); });
      var labelEstavel = semBadge.textContent.trim();
      var base = title.getAttribute('data-sec-key') || slugKey(labelEstavel) || 'secao';
      var key = base;
      for (var n = 2; usadas[key]; n++) key = base + '-' + n;   // títulos repetidos
      usadas[key] = true;
      return { el: section, title: title, key: key, legacyKey: 'section-' + idx,
               legacySlug: slugKey(label),
               label: label, autoTag: forcedTag || detectTag(label) };
    });
    var byKey = {};    meta.forEach(function (m) { byKey[m.key] = m; });
    var deLegacy = {}; meta.forEach(function (m) {
      deLegacy[m.legacyKey] = m.key;
      // chave antiga (com a badge) do lançamento aberto agora
      if (m.legacySlug && m.legacySlug !== m.key) deLegacy[m.legacySlug] = m.key;
    });
    var defaultOrder = meta.map(function (m) { return m.key; });

    // Traduz um estado salvo (banco ou localStorage) pras keys de hoje e
    // garante as quatro partes — view antiga não tinha `customs`.
    function migrarKeys(est) {
      est = est || {};
      // View salva antes de 21/09/26 guarda a chave COM o código do
      // lançamento. Tirar o código na marra recupera essas views em qualquer
      // lançamento — sem isso, quem já tinha visualização continuaria vendo as
      // três seções irem pro fim da página.
      function semLancamento(x) {
        return x.replace(/-(?:pbb|pes|pi)-[a-z]{3}-\d{2}/g, '')
                .replace(/-bv-\d{2}/g, '')
                .replace(/-+/g, '-').replace(/^-+|-+$/g, '');
      }
      function k(x) {
        if (byKey[x]) return x;
        if (deLegacy[x]) return deLegacy[x];
        var limpo = semLancamento(x);
        return byKey[limpo] ? limpo : x;
      }
      function obj(o) {
        var out = {};
        Object.keys(o || {}).forEach(function (x) { out[k(x)] = o[x]; });
        return out;
      }
      return {
        order:     (est.order && est.order.length ? est.order : defaultOrder).map(k),
        hidden:    obj(est.hidden),
        collapsed: obj(est.collapsed),
        customs:   obj(est.customs),
      };
    }

    // só reordena o DOM se todas as seções tiverem o mesmo elemento pai —
    // layout fora do padrão não é mexido, só perde a reordenação.
    var container = meta[0].el.parentNode;
    var sameParent = meta.every(function (m) { return m.el.parentNode === container; });

    var collapsedKey   = 'bs-collapsed-sections:' + PAGE;
    var stateKey       = 'bs-section-state:' + PAGE;
    var customKey      = 'bs-section-custom:' + PAGE;
    var legacyViewsKey = 'bs-saved-views:' + PAGE;   // visualizações de antes do banco
    var migradasKey    = 'bs-views-migradas:' + PAGE;

    // O estado "de trabalho" (o que você está vendo agora) continua no
    // localStorage — arrastar uma seção não vai bater no banco a cada gesto.
    // O que vai pro banco são as visualizações NOMEADAS, em /api/section-views:
    // as pessoais seguem você entre navegadores, e a da equipe marcada como
    // padrão é a que todo mundo abre na primeira visita.
    var salvoLocal = load(stateKey, {});
    var temEstadoLocal = !!(salvoLocal && salvoLocal.order);
    var inicial = migrarKeys({
      order: salvoLocal.order, hidden: salvoLocal.hidden,
      collapsed: load(collapsedKey, {}), customs: load(customKey, {}),
    });
    var working  = { order: inicial.order, hidden: inicial.hidden };
    var collapsed = inicial.collapsed;
    var customs   = inicial.customs;  // { key: { tag?: string, name?: string } } — só overrides manuais
    var views = [];          // do banco: [{id, nome, escopo, is_padrao, estado, …}]
    var podeGlobal = false;  // admin/analista
    var bancoOk = false;     // migration 010 rodou e a API respondeu

    function getLabel(key) { var c = customs[key]; return (c && c.name) ? c.name : (byKey[key] ? byKey[key].label : ''); }
    function getTag(key) { var c = customs[key]; if (c && c.tag !== undefined) return c.tag; return byKey[key] ? byKey[key].autoTag : ''; }
    function applyCustom(key) {
      var m = byKey[key]; if (!m || !m.override) return;  // título ainda não remontado
      var custom = customs[key] || {};
      if (custom.name) { m.override.textContent = custom.name; m.override.style.display = ''; m.orig.style.display = 'none'; }
      else { m.override.style.display = 'none'; m.orig.style.display = ''; }
      var tag = getTag(key);
      if (tag) {
        var c = tagColors(tag);
        m.tagBadge.textContent = tag;
        m.tagBadge.style.cssText = 'background:' + c.bg + ';color:' + c.fg + ';display:inline-flex';
      } else {
        m.tagBadge.style.display = 'none';
      }
      if (m.badges) updateBadgesVisibility(m);
    }
    function saveCustom(key, patch) {
      var c = Object.assign({}, customs[key] || {}, patch);
      Object.keys(c).forEach(function (k) { if (c[k] === undefined || c[k] === '') delete c[k]; });
      if (Object.keys(c).length) customs[key] = c; else delete customs[key];
      save(customKey, customs);
      applyCustom(key);
    }

    // Aplica um estado inteiro — ordem, ocultas, recolhidas E os apelidos/tags.
    // Os customs viajam junto desde 17/09/26: uma visualização que renomeia
    // seções mas não leva os nomes não é a mesma visualização.
    function applyState(est) {
      est = migrarKeys(est);
      working   = { order: est.order.slice(), hidden: Object.assign({}, est.hidden) };
      collapsed = Object.assign({}, est.collapsed);
      customs   = Object.assign({}, est.customs);
      if (sameParent) {
        working.order.forEach(function (key) { if (byKey[key]) container.appendChild(byKey[key].el); });
        // seção nova na página (não existia quando a view foi salva) vai pro final.
        meta.forEach(function (m) { if (working.order.indexOf(m.key) === -1) container.appendChild(m.el); });
      }
      meta.forEach(function (m, idx) {
        var isCollapsed = (m.key in collapsed) ? collapsed[m.key] : (idx !== 0);
        m.el.classList.toggle('collapsed', isCollapsed);
        m.el.classList.toggle('bs-hidden-section', !!working.hidden[m.key]);
        applyCustom(m.key);
      });
      save(stateKey, working);
      save(collapsedKey, collapsed);
      save(customKey, customs);
      renderSecPanel();
      renderViewsPanel();
    }

    // Retrato do que está na tela — é isso que vai pro banco ao salvar.
    function estadoAtual() {
      return {
        order:     working.order.slice(),
        hidden:    Object.assign({}, working.hidden),
        collapsed: Object.assign({}, collapsed),
        customs:   JSON.parse(JSON.stringify(customs)),
      };
    }

    function updateBadgesVisibility(m) {
      var hasExtra = Array.prototype.some.call(m.badges.children, function (c) { return c !== m.tagBadge; });
      m.badges.style.display = (hasExtra || m.tagBadge.style.display !== 'none') ? '' : 'none';
    }

    // Reagrupa o conteúdo original do título num wrapper: o ícone (sempre o
    // 1º filho, se houver) fica sozinho, fora do texto — maior, alinhado ao
    // centro das duas linhas de baixo (.bs-sec-body). Texto vira a linha 1;
    // qualquer badge que já viesse solta no título (ex.: .dbf-launch-badge)
    // e a tag automática descem pra .bs-sec-badges, linha 2 — permite trocar
    // o texto por nome customizado sem perder a marcação original. Sem essa
    // separação, título+badges brigavam pelo mesmo flex-wrap e quebravam de
    // qualquer jeito no celular, cada badge numa linha (achado 16/09/26).
    // Clique no título recolhe/expande.
    meta.forEach(function (m) {
      var iconEl = (m.title.firstElementChild && m.title.firstElementChild.tagName === 'I')
        ? m.title.firstElementChild : null;
      if (iconEl) m.title.removeChild(iconEl);

      var orig = document.createElement('span');
      orig.className = 'bs-sec-orig';
      var badges = document.createElement('div');
      badges.className = 'bs-sec-badges';
      // tag de etapa vem primeiro (pedido do usuário 16/09/26: "etapa -
      // plataforma - lançamento - lançamento anterior") — criada e
      // inserida ANTES do while, que só faz appendChild (sempre no fim),
      // então qualquer badge que já viesse solta no título (plataforma,
      // lançamento atual/anterior — nessa ordem, é como cada template já
      // as escreve) entra depois dela, na ordem certa.
      var tagBadge = document.createElement('span');
      tagBadge.className = 'bs-sec-tag';
      tagBadge.style.display = 'none';
      badges.appendChild(tagBadge);
      while (m.title.firstChild) {
        var node = m.title.firstChild;
        m.title.removeChild(node);
        (node.nodeType === 1 ? badges : orig).appendChild(node);
      }

      var override = document.createElement('span');
      override.className = 'bs-sec-label-override';
      override.style.display = 'none';

      var body = document.createElement('div');
      body.className = 'bs-sec-body';
      body.appendChild(orig);
      body.appendChild(override);
      body.appendChild(badges);

      if (iconEl) m.title.appendChild(iconEl);
      m.title.appendChild(body);
      var chev = document.createElement('i');
      chev.className = 'ti ti-chevron-down bs-chevron';
      m.title.appendChild(chev);

      m.orig = orig; m.override = override; m.tagBadge = tagBadge; m.badges = badges;
      updateBadgesVisibility(m);
      m.title.addEventListener('click', function () {
        m.el.classList.toggle('collapsed');
        collapsed[m.key] = m.el.classList.contains('collapsed');
        save(collapsedKey, collapsed);
      });
      applyCustom(m.key);
    });

    applyState(estadoAtual());

    // ── Barra de controles (Recolher/Expandir + busca + dropdown Seções) ─
    var controls = document.createElement('div');
    controls.className = 'bs-accordion-controls';
    controls.innerHTML =
      '<button type="button" data-act="collapse"><i class="ti ti-arrows-minimize"></i> Recolher</button>' +
      '<button type="button" data-act="expand"><i class="ti ti-arrows-maximize"></i> Expandir</button>' +
      '<div class="bs-launch-picker" id="bs-sec-picker">' +
        '<button type="button" class="bs-sec-picker-btn" onclick="bsPickerToggle(this)">' +
          '<i class="ti ti-layout-list"></i> Seções<i class="ti ti-chevron-down bs-launch-picker-chevron"></i>' +
        '</button>' +
        '<div class="bs-launch-picker-menu bs-sec-menu">' +
          '<div class="bs-launch-picker-group bs-sec-list-head">' +
            '<span>Ordem e visibilidade</span>' +
            '<span class="bs-sec-bulk">' +
              '<button type="button" data-bulk="show">Marcar todas</button>' +
              '<button type="button" data-bulk="hide">Desmarcar todas</button>' +
            '</span>' +
          '</div>' +
          '<div class="bs-sec-list" id="bs-sec-list"></div>' +
          '<div class="bs-sec-sep"></div>' +
          '<div class="bs-launch-picker-group">Visualizações salvas</div>' +
          '<div class="bs-view-list" id="bs-view-list"></div>' +
          '<div class="bs-view-save-row">' +
            '<input type="text" id="bs-view-name" placeholder="Nome da visualização..." maxlength="40">' +
            '<select id="bs-view-scope" title="Quem enxerga esta visualização" style="display:none">' +
              '<option value="user">Minha</option>' +
              '<option value="global">Da equipe</option>' +
            '</select>' +
            '<button type="button" id="bs-view-save" title="Salvar visualização atual"><i class="ti ti-plus"></i></button>' +
          '</div>' +
          '<div class="bs-view-hint" id="bs-view-hint"></div>' +
        '</div>' +
      '</div>' +
      '<div class="bs-sec-search">' +
        '<i class="ti ti-search"></i>' +
        '<input type="text" id="bs-sec-search-input" placeholder="Buscar seção..." autocomplete="off" spellcheck="false">' +
        '<button type="button" class="bs-sec-search-clear" title="Limpar busca (Esc)"><i class="ti ti-x"></i></button>' +
      '</div>' +
      '<span class="bs-sec-search-info" id="bs-sec-search-info"></span>';
    // Se a página já tem uma barra própria de controles (ex.: o botão "Gerar
    // PDF" do debriefing, em .dbf-accordion-controls), entra nela — na mesma
    // linha, à esquerda — em vez de criar uma segunda linha abaixo.
    var ownControls = document.querySelector('.dbf-accordion-controls');
    if (ownControls) {
      ownControls.insertBefore(controls, ownControls.firstChild);
    } else {
      var firstEl = sameParent ? byKey[working.order[0]].el : meta[0].el;
      firstEl.parentNode.insertBefore(controls, firstEl);
    }

    controls.querySelector('[data-act="collapse"]').addEventListener('click', function () { setAllCollapsed(true); });
    controls.querySelector('[data-act="expand"]').addEventListener('click', function () { setAllCollapsed(false); });
    function setAllCollapsed(v) {
      meta.forEach(function (m) { m.el.classList.toggle('collapsed', v); collapsed[m.key] = v; });
      save(collapsedKey, collapsed);
    }
    controls.querySelectorAll('[data-bulk]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var hide = btn.dataset.bulk === 'hide';
        working.order.forEach(function (key) {
          if (hide) working.hidden[key] = true; else delete working.hidden[key];
          if (byKey[key]) byKey[key].el.classList.toggle('bs-hidden-section', hide);
        });
        save(stateKey, working);
        renderSecPanel();
      });
    });

    // ── Lista de seções: arrastar pra reordenar, checkbox pra ocultar ─
    var dragKey = null;
    function renderSecPanel() {
      var list = document.getElementById('bs-sec-list');
      if (!list) return;
      list.innerHTML = '';
      working.order.forEach(function (key) {
        var m = byKey[key];
        // seção sem dado pro lançamento some do DOM depois (carregamento
        // progressivo do debriefing) — não listar fantasma no painel.
        if (!m || !m.el.isConnected) return;
        var row = document.createElement('div');
        row.className = 'bs-sec-row' + (working.hidden[key] ? ' is-hidden' : '');
        row.draggable = true;
        var tag = getTag(key);
        var tc = tagColors(tag || '—');
        row.innerHTML =
          '<i class="ti ti-grip-vertical bs-sec-drag"></i>' +
          '<input type="checkbox" ' + (working.hidden[key] ? '' : 'checked') + '>' +
          '<span class="lbl">' + esc(getLabel(key)) + '</span>' +
          '<span class="bs-sec-row-tag" data-act="tag" style="background:' + tc.bg + ';color:' + tc.fg + '">' +
            esc(tag || '+ tag') + '</span>' +
          '<button type="button" class="bs-sec-row-btn" data-act="rename" title="Renomear seção"><i class="ti ti-pencil"></i></button>';
        row.querySelector('input').addEventListener('change', function (e) {
          if (e.target.checked) delete working.hidden[key]; else working.hidden[key] = true;
          m.el.classList.toggle('bs-hidden-section', !e.target.checked);
          row.classList.toggle('is-hidden', !e.target.checked);
          save(stateKey, working);
        });
        row.querySelector('[data-act="tag"]').addEventListener('click', function (e) {
          e.stopPropagation();
          var val = prompt('Tag da seção — sugestões: Pré-Quali, Captação, Remarketing, WhatsApp, Active Campaign, Vendas.\nDeixe vazio pra remover a tag.', getTag(key));
          if (val === null) return;
          saveCustom(key, { tag: val.trim() });
          renderSecPanel();
        });
        row.querySelector('[data-act="rename"]').addEventListener('click', function (e) {
          e.stopPropagation();
          var val = prompt('Novo nome pra essa seção — deixe vazio pra voltar ao original ("' + m.label + '"):', (customs[key] && customs[key].name) || '');
          if (val === null) return;
          saveCustom(key, { name: val.trim() });
          renderSecPanel();
        });
        row.addEventListener('dragstart', function () { dragKey = key; row.classList.add('dragging'); });
        row.addEventListener('dragend', function () {
          row.classList.remove('dragging');
          dragKey = null;
          list.querySelectorAll('.bs-sec-row').forEach(function (r) { r.classList.remove('drag-over'); });
        });
        row.addEventListener('dragover', function (e) {
          e.preventDefault();
          if (dragKey && key !== dragKey) row.classList.add('drag-over');
        });
        row.addEventListener('dragleave', function () { row.classList.remove('drag-over'); });
        row.addEventListener('drop', function (e) {
          e.preventDefault();
          row.classList.remove('drag-over');
          if (!dragKey || dragKey === key) return;
          var order = working.order.slice();
          var from = order.indexOf(dragKey), to = order.indexOf(key);
          order.splice(from, 1);
          order.splice(to, 0, dragKey);
          working.order = order;
          if (sameParent) order.forEach(function (k) { if (byKey[k]) container.appendChild(byKey[k].el); });
          save(stateKey, working);
          renderSecPanel();
        });
        list.appendChild(row);
      });
    }

    // ── Visualizações: banco (equipe + pessoais), com queda pro local ─
    function api(url, opts) {
      return fetch(url, Object.assign({ credentials: 'same-origin' }, opts || {}))
        .then(function (r) {
          return r.json().catch(function () { return {}; }).then(function (j) {
            if (!r.ok || j.ok === false) throw new Error(j.error || ('HTTP ' + r.status));
            return j;
          });
        });
    }
    function apiPost(url, body) {
      return api(url, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
      });
    }
    function hint(msg, erro) {
      var el = document.getElementById('bs-view-hint');
      if (!el) return;
      el.textContent = msg || '';
      el.classList.toggle('is-err', !!erro);
      el.classList.toggle('is-on', !!msg);
    }

    function carregarViews(primeiraVez) {
      return api('/api/section-views?pagina=' + encodeURIComponent(PAGE))
        .then(function (j) {
          bancoOk = !!j.disponivel;
          podeGlobal = !!j.pode_global;
          views = j.views || [];
          var sel = document.getElementById('bs-view-scope');
          if (sel) sel.style.display = (bancoOk && podeGlobal) ? '' : 'none';
          if (!bancoOk) {
            hint('Salvando só neste navegador — a tabela section_views ainda não existe no banco.');
            return;
          }
          // Primeira visita nesta página (sem estado local): já abre na padrão
          // da equipe — é exatamente para isso que ela existe.
          var padrao = views.filter(function (v) { return v.is_padrao; })[0];
          if (primeiraVez && !temEstadoLocal && padrao) applyState(padrao.estado);
          return migrarViewsLegadas();
        })
        .catch(function () { bancoOk = false; })
        .then(function () { renderViewsPanel(); });
    }

    // O que já estava salvo no localStorage vira visualização pessoal no
    // banco, uma vez só: ninguém perde o que tinha antes de 17/09/26.
    function migrarViewsLegadas() {
      if (!bancoOk || load(migradasKey, false)) return;
      var legado = load(legacyViewsKey, {});
      var nomes = Object.keys(legado);
      if (!nomes.length) { save(migradasKey, true); return; }
      return nomes.reduce(function (p, nome) {
        return p.then(function () {
          return apiPost('/api/section-views', {
            pagina: PAGE, escopo: 'user', nome: nome, estado: migrarKeys(legado[nome]),
          }).catch(function () {});
        });
      }, Promise.resolve()).then(function () {
        save(migradasKey, true);
        return api('/api/section-views?pagina=' + encodeURIComponent(PAGE))
          .then(function (j) { views = j.views || []; })
          .catch(function () {});
      });
    }

    function renderViewsPanel() {
      var list = document.getElementById('bs-view-list');
      if (!list) return;
      list.innerHTML = '';

      // Linha fixa: volta pra ordem crua do template, sem apelido nem oculta.
      // Continua existindo mesmo quando a equipe define outra padrão — é a
      // saída de emergência de quem herdou uma ordem que não serve.
      var zerar = document.createElement('div');
      zerar.className = 'bs-view-item';
      zerar.innerHTML = '<i class="ti ti-restore"></i><span class="name">Ordem original do sistema</span>';
      zerar.addEventListener('click', function () {
        applyState({ order: defaultOrder, hidden: {}, collapsed: {}, customs: {} });
        hint('Voltou para a ordem original.');
      });
      list.appendChild(zerar);

      if (!bancoOk) { renderViewsLocais(list); return; }

      views.forEach(function (v) {
        var global = v.escopo === 'global';
        var podeEditar = global ? podeGlobal : true;
        var item = document.createElement('div');
        item.className = 'bs-view-item';
        item.innerHTML =
          '<i class="ti ' + (v.is_padrao ? 'ti-star-filled bs-view-star' : (global ? 'ti-users' : 'ti-bookmark')) + '"></i>' +
          '<span class="name">' + esc(v.nome) + '</span>' +
          (v.is_padrao ? '<span class="bs-view-badge">padrão</span>'
                       : (global ? '<span class="bs-view-badge equipe">equipe</span>' : '')) +
          '<span class="bs-view-acts">' +
            (podeGlobal && global && !v.is_padrao
              ? '<i class="ti ti-star" data-act="padrao" title="Tornar a padrão da página"></i>' : '') +
            (podeEditar ? '<i class="ti ti-device-floppy" data-act="salvar" title="Salvar a tela atual por cima desta"></i>' +
                          '<i class="ti ti-pencil" data-act="renomear" title="Renomear"></i>' +
                          '<i class="ti ti-x" data-act="excluir" title="Excluir"></i>' : '') +
          '</span>';
        item.addEventListener('click', function (e) {
          var alvo = e.target.closest('[data-act]');
          if (!alvo) { applyState(v.estado); hint('Aplicada: ' + v.nome); return; }
          e.stopPropagation();
          var act = alvo.getAttribute('data-act');
          var falhou = function (err) { hint(err.message, true); };
          if (act === 'padrao') {
            apiPost('/api/section-views/' + v.id + '/padrao', {})
              .then(function () { hint('"' + v.nome + '" agora é a padrão da página.'); return carregarViews(false); })
              .catch(falhou);
          } else if (act === 'salvar') {
            if (!confirm('Salvar a tela atual (ordem, ocultas, apelidos e tags) por cima de "' + v.nome + '"?')) return;
            apiPost('/api/section-views', { pagina: PAGE, escopo: v.escopo, nome: v.nome, estado: estadoAtual() })
              .then(function () { hint('"' + v.nome + '" atualizada.'); return carregarViews(false); })
              .catch(falhou);
          } else if (act === 'renomear') {
            var novo = prompt('Novo nome para a visualização:', v.nome);
            if (novo === null) return;
            apiPost('/api/section-views/' + v.id + '/rename', { nome: novo })
              .then(function () { hint('Renomeada.'); return carregarViews(false); })
              .catch(falhou);
          } else if (act === 'excluir') {
            if (!confirm('Excluir a visualização "' + v.nome + '"?' + (global ? '\nEla some para todo mundo.' : ''))) return;
            api('/api/section-views/' + v.id, { method: 'DELETE' })
              .then(function () { hint('Excluída.'); return carregarViews(false); })
              .catch(falhou);
          }
        });
        list.appendChild(item);
      });
    }

    // Sem banco (migration 010 ainda não rodou) o painel continua funcionando
    // como antes, só que local — não vale travar a página por causa disso.
    function renderViewsLocais(list) {
      var locais = load(legacyViewsKey, {});
      Object.keys(locais).sort().forEach(function (nome) {
        var item = document.createElement('div');
        item.className = 'bs-view-item';
        item.innerHTML =
          '<i class="ti ti-bookmark"></i><span class="name">' + esc(nome) + '</span>' +
          '<span class="bs-view-acts">' +
            '<i class="ti ti-device-floppy" data-act="salvar" title="Salvar a tela atual por cima desta"></i>' +
            '<i class="ti ti-x" data-act="excluir" title="Excluir"></i>' +
          '</span>';
        item.addEventListener('click', function (e) {
          var alvo = e.target.closest('[data-act]');
          if (!alvo) { applyState(locais[nome]); return; }
          e.stopPropagation();
          if (alvo.getAttribute('data-act') === 'salvar') locais[nome] = estadoAtual();
          else if (!confirm('Excluir a visualização "' + nome + '"?')) return;
          else delete locais[nome];
          save(legacyViewsKey, locais);
          renderViewsPanel();
        });
        list.appendChild(item);
      });
    }

    function salvarNova() {
      var input = document.getElementById('bs-view-name');
      var nome = input.value.trim();
      if (!nome) { hint('Dê um nome à visualização.', true); return; }
      if (!bancoOk) {
        var locais = load(legacyViewsKey, {});
        locais[nome] = estadoAtual();
        save(legacyViewsKey, locais);
        input.value = '';
        renderViewsPanel();
        return;
      }
      var sel = document.getElementById('bs-view-scope');
      var escopo = (sel && sel.style.display !== 'none') ? sel.value : 'user';
      var jaExiste = views.some(function (v) { return v.escopo === escopo && norm(v.nome) === norm(nome); });
      if (jaExiste && !confirm('Já existe "' + nome + '" nesse escopo. Salvar por cima?')) return;
      apiPost('/api/section-views', { pagina: PAGE, escopo: escopo, nome: nome, estado: estadoAtual() })
        .then(function () { input.value = ''; hint('Salva: ' + nome); return carregarViews(false); })
        .catch(function (err) { hint(err.message, true); });
    }
    document.getElementById('bs-view-save').addEventListener('click', salvarNova);
    document.getElementById('bs-view-name').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') salvarNova();
    });

    // ── Busca de seções ──────────────────────────────────────────────
    // Filtra a página: fica só o que casa, o resto some. Título e tag vêm
    // primeiro; o conteúdo só entra quando NENHUM título casa — senão
    // procurar "vendas" traria meia página só porque a palavra aparece
    // solta numa tabela.
    var buscaAtiva = false, colapsoAntesDaBusca = null, textoCache = {}, cacheSujo = true, buscaTimer = null;

    function aplicarBusca(termo) {
      termo = norm(termo).trim();
      var info = document.getElementById('bs-sec-search-info');
      var caixa = document.querySelector('.bs-sec-search');
      if (caixa) caixa.classList.toggle('has-value', !!termo);

      if (!termo) {
        if (buscaAtiva) {
          meta.forEach(function (m) { m.el.classList.remove('bs-search-off', 'bs-search-hit'); });
          if (colapsoAntesDaBusca) {
            collapsed = Object.assign({}, colapsoAntesDaBusca);
            meta.forEach(function (m, idx) {
              var c = (m.key in collapsed) ? collapsed[m.key] : (idx !== 0);
              m.el.classList.toggle('collapsed', c);
            });
            save(collapsedKey, collapsed);
          }
          colapsoAntesDaBusca = null;
          buscaAtiva = false;
        }
        if (info) { info.textContent = ''; info.classList.remove('is-on'); }
        return;
      }

      var vivas = meta.filter(function (m) { return m.el.isConnected; });
      var achados = vivas.filter(function (m) {
        return norm(getLabel(m.key)).indexOf(termo) !== -1
            || norm(m.label).indexOf(termo) !== -1
            || norm(getTag(m.key)).indexOf(termo) !== -1;
      });
      var porConteudo = false;
      if (!achados.length) {
        // recalcula o texto só quando precisa (e quando alguma seção lazy
        // chegou depois) — textContent da página inteira não é de graça.
        var novo = {};
        vivas.forEach(function (m) {
          novo[m.key] = (!cacheSujo && textoCache[m.key] !== undefined) ? textoCache[m.key] : norm(m.el.textContent);
        });
        textoCache = novo;
        cacheSujo = false;
        achados = vivas.filter(function (m) { return textoCache[m.key].indexOf(termo) !== -1; });
        porConteudo = achados.length > 0;
      }

      if (!buscaAtiva) { colapsoAntesDaBusca = Object.assign({}, collapsed); buscaAtiva = true; }
      var achadas = {}; achados.forEach(function (m) { achadas[m.key] = true; });
      meta.forEach(function (m) {
        var hit = !!achadas[m.key];
        m.el.classList.toggle('bs-search-off', !hit);
        m.el.classList.toggle('bs-search-hit', hit);   // vence o "ocultar" do painel
        if (hit) m.el.classList.remove('collapsed');   // já abre no resultado
      });
      if (info) {
        info.classList.add('is-on');
        info.textContent = achados.length
          ? (achados.length === 1 ? '1 seção' : achados.length + ' seções') + (porConteudo ? ' (no conteúdo)' : '')
          : 'nada encontrado';
      }
    }
    function agendarBusca() {
      clearTimeout(buscaTimer);
      buscaTimer = setTimeout(function () {
        var input = document.getElementById('bs-sec-search-input');
        aplicarBusca(input ? input.value : '');
      }, 140);
    }
    var buscaInput = document.getElementById('bs-sec-search-input');
    buscaInput.addEventListener('input', agendarBusca);
    buscaInput.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { buscaInput.value = ''; aplicarBusca(''); buscaInput.blur(); }
    });
    controls.querySelector('.bs-sec-search-clear').addEventListener('click', function () {
      buscaInput.value = '';
      aplicarBusca('');
      buscaInput.focus();
    });
    // Seção que chega depois (carregamento progressivo do debriefing) tem que
    // entrar no resultado da busca que já está na tela.
    if (typeof MutationObserver !== 'undefined') {
      new MutationObserver(function () {
        cacheSujo = true;
        if (buscaAtiva) agendarBusca();
      }).observe(container, { childList: true, subtree: true });
    }

    // primeira renderização dos painéis (applyState() já tentou antes de
    // #bs-sec-list/#bs-view-list existirem no DOM — refaz agora que existem).
    renderSecPanel();
    renderViewsPanel();
    carregarViews(true);
  }
  if (document.readyState !== 'loading') initAccordion();
  else document.addEventListener('DOMContentLoaded', initAccordion);
})();
