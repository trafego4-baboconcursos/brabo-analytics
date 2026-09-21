/* Extraído de frontend/templates/base.html em 21/09/2026.
   Carregado com <script> síncrono, na mesma ordem em que estava inline.
   Estes arquivos dependem dessa ordem (ex.: tema.js define bsThemeTokens,
   usado depois). Não adicionar defer/async sem revisar as dependências. */
/* wizard de configuração de lançamento */

(function(){
  var _code = "";
  var _step = 1;
  var _debounceTimer = null;

  window.lcOpen = function(code) {
    _code = code;
    _step = 1;
    document.getElementById("lc-title").textContent = code;
    document.getElementById("lc-overlay").style.display = "flex";
    // Reseta
    document.getElementById("lc-outras-list").innerHTML = "";
    document.getElementById("lc-product-list").innerHTML = "";
    document.getElementById("lc-tmb-list").innerHTML = "";
    document.getElementById("lc-yt-list").innerHTML = "";
    lcPopulateEtapas([]);
    document.getElementById("lc-outras-body").classList.remove("open");
    document.getElementById("lc-outras-toggle").classList.remove("open");
    document.getElementById("lc-meta-menu").innerHTML = "";
    document.getElementById("lc-google-menu").innerHTML = "";
    lcAccChange("meta"); lcAccChange("google");
    document.querySelectorAll(".lc-input").forEach(function(el){ el.value = ""; });
    document.querySelectorAll(".lc-camp-badge[id]").forEach(function(b){ b.textContent = "— campanhas"; });
    lcRenderStep();
    // Carrega config existente + contas de anúncio disponíveis (Meta/Google, ao vivo via API)
    fetch("/api/launch-config/" + encodeURIComponent(code))
      .then(function(r){ return r.json(); })
      .then(function(data){
        lcRenderAccountOptions("meta", data.meta_accounts || []);
        lcRenderAccountOptions("google", data.google_accounts || []);
        lcPopulate(data.config || {});
      })
      .catch(function(){});
  };

  window.lcClose = function() {
    document.getElementById("lc-overlay").style.display = "none";
  };

  function lcRenderAccountOptions(platform, accounts) {
    var menu = document.getElementById("lc-" + platform + "-menu");
    var checkedBefore = new Set(Array.from(menu.querySelectorAll("input:checked")).map(function(cb){ return cb.value; }));
    menu.innerHTML = "";
    if (!accounts.length) {
      menu.innerHTML = '<div style="padding:8px;font-size:12px;color:var(--bs-ink-muted)">Nenhuma conta encontrada — verifique as credenciais no .env</div>';
      return;
    }
    accounts.forEach(function(acc){
      var label = document.createElement("label");
      label.className = "lc-acc-option";
      label.innerHTML =
        '<input type="checkbox" value="' + acc.id + '" onchange="lcAccChange(\'' + platform + '\')">' +
        '<div><div class="lc-acc-option-name">' + acc.name + '</div><div class="lc-acc-option-id">' + acc.id + '</div></div>';
      if (checkedBefore.has(acc.id)) label.querySelector("input").checked = true;
      menu.appendChild(label);
    });
    lcAccChange(platform);
  }

  window.lcRefreshAccounts = function(btn) {
    var original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="ti ti-loader-2"></i> Atualizando...';
    fetch("/api/ad-accounts/refresh", { method: "POST" })
      .then(function(r){ return r.json(); })
      .then(function(data){
        lcRenderAccountOptions("meta", data.meta_accounts || []);
        lcRenderAccountOptions("google", data.google_accounts || []);
      })
      .catch(function(){ alert("Erro ao atualizar contas de anúncio."); })
      .finally(function(){ btn.disabled = false; btn.innerHTML = original; });
  };

  function lcRenderStep() {
    [1,2,3,4,5,6].forEach(function(s){
      var step = document.getElementById("lc-step-" + s);
      var pane = document.getElementById("lc-pane-" + s);
      step.className = "lc-step" + (s === _step ? " active" : s < _step ? " done" : "");
      pane.style.display = s === _step ? "" : "none";
    });
    [1,2,3,4,5].forEach(function(i){
      var line = document.getElementById("lc-line-" + i);
      line.className = "lc-step-line" + (i < _step ? " done" : "");
    });
    document.getElementById("lc-btn-prev").style.display = _step > 1 ? "" : "none";
    document.getElementById("lc-btn-next").style.display = _step < 6 ? "" : "none";
    document.getElementById("lc-btn-save").style.display = _step === 6 ? "" : "none";
  }

  window.lcNext = function() {
    if (_step < 6) { _step++; lcRenderStep(); document.getElementById("lc-body").scrollTop = 0; }
  };
  window.lcPrev = function() {
    if (_step > 1) { _step--; lcRenderStep(); document.getElementById("lc-body").scrollTop = 0; }
  };

  function lcPopulate(cfg) {
    function setVal(id, val){ var el = document.getElementById(id); if(el && val !== undefined && val !== null) el.value = val; }
    
    setVal("lc_pre_quali_start_date",  cfg.pre_quali_start_date || "");
    setVal("lc_pre_quali_end_date",    cfg.pre_quali_end_date   || "");
    setVal("lc_meta_leads_pre_quali",  cfg.meta_leads_pre_quali || "");
    setVal("lc_meta_investimento_pre_quali", cfg.meta_investimento_pre_quali || "");

    setVal("lc_captacao_start_date",  cfg.captacao_start_date || "");
    setVal("lc_captacao_end_date",    cfg.captacao_end_date   || "");
    setVal("lc_meta_leads",           cfg.meta_leads          || "");
    setVal("lc_meta_investimento",    cfg.meta_investimento_captacao || "");
    setVal("lc_filtro_lancamento",    cfg.filtro_lancamento   || "");
    setVal("lc_filtro_captacao",      cfg.filtro_captacao     || "");
    setVal("lc_filtro_pre_quali",     cfg.filtro_pre_quali    || "");
    setVal("lc_filtro_quente",        cfg.filtro_quente       || "");
    setVal("lc_filtro_quente_scope",  cfg.filtro_quente_scope || "campanhas");
    setVal("lc_filtro_frio",          cfg.filtro_frio         || "");
    setVal("lc_filtro_frio_scope",    cfg.filtro_frio_scope   || "campanhas");
    setVal("lc_carrinho_start_date",  cfg.carrinho_start_date || "");
    setVal("lc_carrinho_end_date",    cfg.carrinho_end_date   || "");
    setVal("lc_abertura_oficial_carrinho", cfg.abertura_oficial_carrinho || "");
    setVal("lc_depoimento_start_date", cfg.depoimento_start_date || "");
    setVal("lc_depoimento_end_date",   cfg.depoimento_end_date   || "");
    setVal("lc_aulas_start_date",      cfg.aulas_start_date      || "");
    setVal("lc_aulas_end_date",        cfg.aulas_end_date        || "");
    setVal("lc_drive_folder_url",     cfg.drive_folder_url    || "");

    setVal("lc_produto_nome",           cfg.produto_nome            || "");
    setVal("lc_produto_preco_vista",    cfg.produto_preco_vista     || "");
    setVal("lc_oferta_parcela_cartao",  cfg.oferta_parcela_cartao   || "");
    setVal("lc_oferta_parcela_boleto",  cfg.oferta_parcela_boleto   || "");
    setVal("lc_meta_faturamento",       cfg.meta_faturamento        || "");

    var metaIds = cfg.meta_ad_account_ids || [];
    document.querySelectorAll("#lc-meta-menu input[type=checkbox]").forEach(function(cb){
      cb.checked = metaIds.indexOf(cb.value) >= 0;
    });
    lcAccChange("meta");

    var googleIds = cfg.google_ad_account_ids || [];
    document.querySelectorAll("#lc-google-menu input[type=checkbox]").forEach(function(cb){
      cb.checked = googleIds.indexOf(cb.value) >= 0;
    });
    lcAccChange("google");

    var products = cfg.hotmart_produto_ids || [];
    var list = document.getElementById("lc-product-list");
    list.innerHTML = "";
    products.forEach(function(p){ lcAddProductItem(p); });

    var tmbProducts = cfg.tmb_produto_ids || [];
    var tmbList = document.getElementById("lc-tmb-list");
    tmbList.innerHTML = "";
    tmbProducts.forEach(function(p){ lcAddTmbItem(p); });

    var outras = cfg.outras_temperaturas || [];
    document.getElementById("lc-outras-list").innerHTML = "";
    outras.forEach(function(o){ lcAddOutraItem(o.termo || "", o.scope || "campanhas"); });

    var ytAulas = cfg.youtube_aulas || [];
    document.getElementById("lc-yt-list").innerHTML = "";
    ytAulas.forEach(function(a){ lcAddYtAulaItem(a.id || "", a.label || ""); });

    lcPopulateEtapas(cfg.etapas || []);
    lcSyncAllLinkedEtapas();

    lcUpdateBadge("lc_filtro_lancamento", "lc-badge-lancamento");
    lcUpdateBadge("lc_filtro_captacao",   "lc-badge-captacao");
    lcUpdateBadge("lc_filtro_pre_quali",  "lc-badge-pre-quali");
  }

  window.lcToggleDD = function(platform) {
    var trigger = document.querySelector("#lc-" + platform + "-dd .lc-acc-trigger");
    var menu    = document.getElementById("lc-" + platform + "-menu");
    var open    = menu.classList.contains("open");
    document.querySelectorAll(".lc-acc-menu").forEach(function(m){ m.classList.remove("open"); });
    document.querySelectorAll(".lc-acc-trigger").forEach(function(t){ t.classList.remove("open"); });
    if (!open) { menu.classList.add("open"); trigger.classList.add("open"); }
  };

  document.addEventListener("click", function(e){
    if (!e.target.closest(".lc-acc-dropdown")) {
      document.querySelectorAll(".lc-acc-menu").forEach(function(m){ m.classList.remove("open"); });
      document.querySelectorAll(".lc-acc-trigger").forEach(function(t){ t.classList.remove("open"); });
    }
  });

  window.lcAccChange = function(platform) {
    var checked = Array.from(document.querySelectorAll("#lc-" + platform + "-menu input[type=checkbox]:checked"));
    var count   = checked.length;
    document.getElementById("lc-" + platform + "-acc-count").textContent = count + " selecionada(s)";
    document.getElementById("lc-" + platform + "-trigger-txt").textContent =
      count === 0 ? "Selecionar contas" : count + " conta(s) selecionada(s)";
  };

  function lcUpdateBadge(inputId, badgeId) {
    var term  = (document.getElementById(inputId)||{}).value || "";
    var badge = document.getElementById(badgeId);
    if (!term || !_code) { if(badge) badge.textContent = "— campanhas"; return; }
    fetch("/api/campaign-count?launch_code=" + encodeURIComponent(_code) + "&term=" + encodeURIComponent(term))
      .then(function(r){ return r.json(); })
      .then(function(d){ if(badge) badge.textContent = d.matched + " de " + d.total + " campanhas"; })
      .catch(function(){ if(badge) badge.textContent = "— campanhas"; });
  }

  window.lcDebouncedCount = function(input, badgeId) {
    clearTimeout(_debounceTimer);
    _debounceTimer = setTimeout(function(){ lcUpdateBadge(input.id, badgeId); }, 600);
  };

  window.lcRefreshCount = function() {
    lcUpdateBadge("lc_filtro_lancamento", "lc-badge-lancamento");
    lcUpdateBadge("lc_filtro_captacao",   "lc-badge-captacao");
    lcUpdateBadge("lc_filtro_pre_quali",  "lc-badge-pre-quali");
  };

  window.lcToggleOutras = function() {
    document.getElementById("lc-outras-toggle").classList.toggle("open");
    document.getElementById("lc-outras-body").classList.toggle("open");
  };

  window.lcAddOutra = function() { lcAddOutraItem("", "campanhas"); };

  function lcAddOutraItem(termo, scope) {
    var container = document.getElementById("lc-outras-list");
    var row = document.createElement("div");
    row.className = "lc-temp-row";
    row.innerHTML =
      '<input class="lc-input lc-outra-termo" type="text" placeholder="Ex: morno" value="' + (termo||"") + '">' +
      '<div class="lc-scope-wrap">em' +
        '<select class="lc-scope-select lc-outra-scope">' +
          '<option value="campanhas"' + (scope==="campanhas"?" selected":"") + '>Campanhas</option>' +
          '<option value="conjuntos"' + (scope==="conjuntos"?" selected":"") + '>Conjuntos de Anúncios</option>' +
          '<option value="anuncios"'  + (scope==="anuncios" ?" selected":"") + '>Anúncios</option>' +
        '</select>' +
      '</div>' +
      '<button type="button" onclick="this.closest(\'.lc-temp-row\').remove()" ' +
        'style="border:none;background:none;cursor:pointer;color:var(--bs-ink-muted);font-size:16px;' +
        'display:flex;align-items:center;padding:4px;border-radius:6px">' +
        '<i class="ti ti-x"></i></button>';
    container.appendChild(row);
  }

  window.lcAddProduct = function() {
    var inp = document.getElementById("lc-new-product");
    var val = (inp.value || "").trim();
    if (!val) return;
    lcAddProductItem(val);
    inp.value = "";
  };

  function lcAddProductItem(val) {
    var list = document.getElementById("lc-product-list");
    var row  = document.createElement("div");
    row.className = "lc-product-row";
    row.innerHTML =
      '<input class="lc-input lc-product-id" type="text" value="' + val + '" readonly>' +
      '<button type="button" class="lc-icon-btn" onclick="this.closest(\'.lc-product-row\').remove()" title="Remover">' +
        '<i class="ti ti-x"></i>' +
      '</button>';
    list.appendChild(row);
  }

  window.lcAddTmb = function() {
    var inp = document.getElementById("lc-new-tmb");
    var val = (inp.value || "").trim();
    if (!val) return;
    lcAddTmbItem(val);
    inp.value = "";
  };

  function lcAddTmbItem(val) {
    var list = document.getElementById("lc-tmb-list");
    var row  = document.createElement("div");
    row.className = "lc-product-row";
    row.innerHTML =
      '<input class="lc-input lc-tmb-id" type="text" value="' + val + '" readonly>' +
      '<button type="button" class="lc-icon-btn" onclick="this.closest(\'.lc-product-row\').remove()" title="Remover">' +
        '<i class="ti ti-x"></i>' +
      '</button>';
    list.appendChild(row);
  }

  window.lcAddYtAula = function() {
    var idInp    = document.getElementById("lc-yt-new-id");
    var lblInp   = document.getElementById("lc-yt-new-label");
    var vid = (idInp.value || "").trim();
    var lbl = (lblInp.value || "").trim();
    if (!vid) return;
    lcAddYtAulaItem(vid, lbl);
    idInp.value = ""; lblInp.value = "";
    idInp.focus();
  };

  function lcAddYtAulaItem(vid, lbl) {
    var list = document.getElementById("lc-yt-list");
    var row  = document.createElement("div");
    row.className = "lc-product-row";
    row.style.cssText = "display:flex;gap:6px;margin-bottom:6px;align-items:center";
    row.innerHTML =
      '<input class="lc-input lc-yt-id" type="text" value="' + vid + '" placeholder="ID" style="flex:1;font-family:monospace">' +
      '<input class="lc-input lc-yt-label" type="text" value="' + (lbl || "") + '" placeholder="Título" style="flex:2">' +
      '<button type="button" class="lc-icon-btn" onclick="this.closest(\'.lc-product-row\').remove()" title="Remover">' +
        '<i class="ti ti-x"></i>' +
      '</button>';
    list.appendChild(row);
  }

  document.addEventListener("DOMContentLoaded", function(){
    var newProd = document.getElementById("lc-new-product");
    if (newProd) newProd.addEventListener("keydown", function(e){
      if (e.key === "Enter") { e.preventDefault(); lcAddProduct(); }
    });
    var newTmb = document.getElementById("lc-new-tmb");
    if (newTmb) newTmb.addEventListener("keydown", function(e){
      if (e.key === "Enter") { e.preventDefault(); lcAddTmb(); }
    });
  });

  var LC_ETAPAS_VERBA_DEFAULT = [
    { key: "pre_qualificacao", nome: "Pré-Qualificação" },
    { key: "captacao",         nome: "Captação" },
  ];
  // Os nomes aqui são chave de verdade, não rótulo: o /debriefing e o /verba
  // casam a etapa pelo nome exato (ex.: `nome == "WhatsApp"` em
  // routes/analytics.py). Renomear uma destas zera o previsto da seção
  // correspondente sem erro nenhum.
  var LC_ETAPAS_EVENTO_DEFAULT = [
    { key: "lembrete",         nome: "Lembrete" },
    { key: "depoimento",       nome: "Depoimento" },
    { key: "aulas",            nome: "Aulas no Ar" },
    { key: "replay",           nome: "Replay" },
    { key: "matriculas",       nome: "Matrículas Abertas" },
    { key: "whatsapp",         nome: "WhatsApp" },
  ];

  function lcEtapaId(key, suffix) { return "lc_etapa_" + key + "_" + suffix; }

  function lcSlugify(nome) {
    return (nome || "etapa").toLowerCase()
      .normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "etapa";
  }

  function lcUniqueEtapaKey(nome) {
    var base = lcSlugify(nome);
    var key = base;
    var i = 2;
    while (document.getElementById(lcEtapaId(key, "start"))) {
      key = base + "_" + i;
      i++;
    }
    return key;
  }

  function lcCreateEtapaBlock(containerId, key, nome, removable, linked) {
    var container = document.getElementById(containerId);
    var block = document.createElement("div");
    block.className = "lc-section";
    block.dataset.etapaKey = key;
    block.dataset.etapaNome = nome;
    var linkedAttr = linked ? ' disabled title="Editado no passo Pré-Qualificação/Captação, não aqui — evita os dois campos divergirem"' : '';
    block.innerHTML =
      '<div class="lc-section-title" style="display:flex;align-items:center;justify-content:space-between">' +
        '<span>' + nome + '</span>' +
        (removable
          ? '<button type="button" class="lc-icon-btn" onclick="this.closest(\'.lc-section\').remove()" title="Remover etapa"><i class="ti ti-x"></i></button>'
          : '') +
      '</div>' +
      (linked ? '<div class="note info" style="font-size:11px;padding:6px 10px;margin-bottom:8px">Datas e orçamento vêm do passo "' + nome + '" — mudam automaticamente se você editar lá.</div>' : '') +
      '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">' +
        '<div class="lc-field" style="flex:1;min-width:140px"><label>Início</label>' +
          '<input type="date" class="lc-input" id="' + lcEtapaId(key,"start") + '"' + linkedAttr + '></div>' +
        '<div class="lc-field" style="flex:1;min-width:140px"><label>Fim</label>' +
          '<input type="date" class="lc-input" id="' + lcEtapaId(key,"end") + '"' + linkedAttr + '></div>' +
        '<div class="lc-field" style="flex:1;min-width:140px"><label>Total planejado (R$)</label>' +
          '<input type="number" step="0.01" min="0" class="lc-input" id="' + lcEtapaId(key,"total") + '"' + linkedAttr + '></div>' +
      '</div>' +
      '<label style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--bs-muted);margin-bottom:8px">' +
        '<input type="checkbox" id="' + lcEtapaId(key,"personalizada") + '" onchange="lcToggleEtapaCurva(\'' + key + '\')">' +
        'Distribuição personalizada por dia (padrão: uniforme, dividido igualmente pelos dias do período)' +
      '</label>' +
      '<div id="' + lcEtapaId(key,"curva-wrap") + '" style="display:none;margin-bottom:10px">' +
        '<button type="button" class="lc-add-btn" style="margin-bottom:6px" onclick="lcGerarCurvaEtapa(\'' + key + '\')">Gerar dias do período</button>' +
        '<div id="' + lcEtapaId(key,"curva") + '" style="display:flex;flex-wrap:wrap;gap:6px"></div>' +
        '<div style="font-size:12px;color:var(--bs-muted);margin-top:4px">Soma: <span id="' + lcEtapaId(key,"curva-soma") + '">0</span>%</div>' +
      '</div>' +
      '<div class="lc-section-title" style="font-size:12px;margin-top:4px">Buckets (plataforma / temperatura / aula / manual)</div>' +
      '<div id="' + lcEtapaId(key,"buckets") + '"></div>' +
      '<div class="lc-product-add" style="margin-top:6px">' +
        '<input class="lc-input" type="text" id="' + lcEtapaId(key,"new-bucket-nome") + '" placeholder="Nome do bucket (ex: FB Quente, Aula 2, WhatsApp)" style="flex:2">' +
        '<button type="button" class="lc-add-btn" onclick="lcAddEtapaBucket(\'' + key + '\')" title="Adicionar bucket"><i class="ti ti-plus"></i></button>' +
      '</div>' +
      '<div style="font-size:12px;color:var(--bs-muted);margin-top:4px">Soma dos buckets: <span id="' + lcEtapaId(key,"bucket-soma") + '">0</span>%</div>';
    container.appendChild(block);
    var curvaDiv = block.querySelector("#" + lcEtapaId(key,"curva"));
    curvaDiv.addEventListener("input", function(){ lcUpdateCurvaSoma(key); });
    var bucketsDiv = block.querySelector("#" + lcEtapaId(key,"buckets"));
    bucketsDiv.addEventListener("input", function(){ lcUpdateBucketSoma(key); });
    return block;
  }

  window.lcAddEtapaEvento = function() {
    var inp = document.getElementById("lc-new-etapa-evento-nome");
    var nome = (inp.value || "").trim();
    if (!nome) return;
    var key = lcUniqueEtapaKey(nome);
    lcCreateEtapaBlock("lc-etapas-evento-container", key, nome, true);
    inp.value = "";
  };

  window.lcToggleEtapaCurva = function(key) {
    var checked = document.getElementById(lcEtapaId(key,"personalizada")).checked;
    document.getElementById(lcEtapaId(key,"curva-wrap")).style.display = checked ? "" : "none";
  };

  function lcDateRangeDays(startStr, endStr) {
    if (!startStr || !endStr) return 0;
    var start = new Date(startStr + "T00:00:00");
    var end   = new Date(endStr + "T00:00:00");
    var diff  = Math.round((end - start) / 86400000) + 1;
    return diff > 0 ? diff : 0;
  }

  window.lcGerarCurvaEtapa = function(key) {
    var start = document.getElementById(lcEtapaId(key,"start")).value;
    var end   = document.getElementById(lcEtapaId(key,"end")).value;
    var n = lcDateRangeDays(start, end);
    var curvaDiv = document.getElementById(lcEtapaId(key,"curva"));
    curvaDiv.innerHTML = "";
    if (!n) return;
    var pct = (100 / n);
    for (var i = 1; i <= n; i++) {
      var wrap = document.createElement("div");
      wrap.style.cssText = "display:flex;flex-direction:column;align-items:center;width:56px";
      wrap.innerHTML =
        '<label style="font-size:10px;color:var(--bs-muted)">D' + i + '</label>' +
        '<input type="number" step="0.01" class="lc-input lc-curva-pct" value="' + pct.toFixed(2) + '" style="width:100%;padding:4px;font-size:12px">';
      curvaDiv.appendChild(wrap);
    }
    lcUpdateCurvaSoma(key);
  };

  function lcUpdateCurvaSoma(key) {
    var vals = Array.from(document.querySelectorAll("#" + lcEtapaId(key,"curva") + " .lc-curva-pct")).map(function(i){ return parseFloat(i.value) || 0; });
    var soma = vals.reduce(function(a,b){ return a+b; }, 0);
    var span = document.getElementById(lcEtapaId(key,"curva-soma"));
    if (span) {
      span.textContent = soma.toFixed(1);
      span.style.color = Math.abs(soma - 100) > 0.5 ? "var(--bs-danger)" : "var(--bs-success)";
    }
  }

  window.lcAddEtapaBucket = function(key) {
    var inp = document.getElementById(lcEtapaId(key,"new-bucket-nome"));
    var nome = (inp.value || "").trim();
    if (!nome) return;
    lcAddEtapaBucketRow(key, { nome: nome, pct: 0, tipo: "campanha", plataforma: "meta" });
    inp.value = "";
    lcUpdateBucketSoma(key);
  };

  function lcAddEtapaBucketRow(key, bucket) {
    var list = document.getElementById(lcEtapaId(key,"buckets"));
    var row = document.createElement("div");
    row.className = "lc-product-row lc-bucket-row";
    row.style.cssText = "display:flex;gap:6px;margin-bottom:6px;align-items:center;flex-wrap:wrap";
    var tipo = bucket.tipo || "campanha";
    var plataforma = bucket.plataforma || "meta";
    row.innerHTML =
      '<input class="lc-input lc-bucket-nome" type="text" value="' + (bucket.nome||"") + '" placeholder="Nome" style="flex:2;min-width:110px">' +
      '<input class="lc-input lc-bucket-pct" type="number" step="0.01" min="0" max="100" value="' + (bucket.pct||0) + '" placeholder="%" style="width:70px">' +
      '<select class="lc-input lc-bucket-tipo" style="width:110px" onchange="var r=this.closest(\'.lc-bucket-row\'),v=this.value===\'campanha\'?\'\':\'none\';r.querySelector(\'.lc-bucket-plataforma\').style.display=v;r.querySelector(\'.lc-bucket-conta\').style.display=v">' +
        '<option value="campanha"' + (tipo==="campanha"?" selected":"") + '>Campanha</option>' +
        '<option value="manual"'   + (tipo==="manual"  ?" selected":"") + '>Manual</option>' +
      '</select>' +
      '<select class="lc-input lc-bucket-plataforma" style="width:100px;' + (tipo==="campanha"?"":"display:none") + '">' +
        '<option value="meta"'   + (plataforma==="meta"  ?" selected":"") + '>Meta</option>' +
        '<option value="google"' + (plataforma==="google"?" selected":"") + '>Google</option>' +
        '<option value="tiktok"' + (plataforma==="tiktok"?" selected":"") + '>TikTok</option>' +
        '<option value="outro"'  + (plataforma==="outro" ?" selected":"") + '>Outro</option>' +
      '</select>' +
      // Conta de anúncio (opcional): quando preenchida, o realizado do bucket é
      // lido pelo gasto DAQUELA conta, não pela temperatura no nome. É o que
      // permite acompanhar verba por expert num lançamento multiproduto.
      '<input class="lc-input lc-bucket-conta" type="text" value="' + (bucket.conta||"") + '" placeholder="Conta (opcional)" title="ID da conta de anúncio: act_… no Meta, o customer id no Google. Preenchido, mede o gasto por conta em vez da temperatura." style="width:150px;' + (tipo==="campanha"?"":"display:none") + '">' +
      '<button type="button" class="lc-icon-btn" onclick="this.closest(\'.lc-bucket-row\').remove()" title="Remover">' +
        '<i class="ti ti-x"></i>' +
      '</button>';
    list.appendChild(row);
  }

  function lcUpdateBucketSoma(key) {
    var vals = Array.from(document.querySelectorAll("#" + lcEtapaId(key,"buckets") + " .lc-bucket-pct")).map(function(i){ return parseFloat(i.value) || 0; });
    var soma = vals.reduce(function(a,b){ return a+b; }, 0);
    var span = document.getElementById(lcEtapaId(key,"bucket-soma"));
    if (span) {
      span.textContent = soma.toFixed(1);
      span.style.color = Math.abs(soma - 100) > 0.5 ? "var(--bs-danger)" : "var(--bs-success)";
    }
  }

  function lcFillEtapaBlock(block, cfg) {
    var key = block.dataset.etapaKey;
    document.getElementById(lcEtapaId(key,"start")).value = cfg.start_date || "";
    document.getElementById(lcEtapaId(key,"end")).value   = cfg.end_date   || "";
    document.getElementById(lcEtapaId(key,"total")).value = cfg.total != null ? cfg.total : "";
    var personalizada = cfg.distribuicao === "personalizada";
    document.getElementById(lcEtapaId(key,"personalizada")).checked = personalizada;
    document.getElementById(lcEtapaId(key,"curva-wrap")).style.display = personalizada ? "" : "none";
    var curvaDiv = document.getElementById(lcEtapaId(key,"curva"));
    curvaDiv.innerHTML = "";
    if (personalizada && Array.isArray(cfg.curva_pct)) {
      cfg.curva_pct.forEach(function(pct, i){
        var wrap = document.createElement("div");
        wrap.style.cssText = "display:flex;flex-direction:column;align-items:center;width:56px";
        wrap.innerHTML =
          '<label style="font-size:10px;color:var(--bs-muted)">D' + (i+1) + '</label>' +
          '<input type="number" step="0.01" class="lc-input lc-curva-pct" value="' + pct + '" style="width:100%;padding:4px;font-size:12px">';
        curvaDiv.appendChild(wrap);
      });
    }
    lcUpdateCurvaSoma(key);
    var bucketsDiv = document.getElementById(lcEtapaId(key,"buckets"));
    bucketsDiv.innerHTML = "";
    (cfg.buckets || []).forEach(function(b){ lcAddEtapaBucketRow(key, b); });
    lcUpdateBucketSoma(key);
  }

  // Fonte única: Pré-Qualificação/Captação têm data+orçamento definidos nos
  // passos 1/2 (lc_pre_quali_*/lc_captacao_*/lc_meta_investimento*). O bloco
  // de Verba desses dois NÃO tem input próprio (ver linkedAttr em
  // lcCreateEtapaBlock) — só espelha esses campos, pra nunca mais divergir
  // como aconteceu com PES-SET-26 (data de Pré-Quali e orçamento de Captação
  // ficaram desatualizados no bloco de Verba porque eram editáveis à parte).
  var LC_ETAPA_VERBA_LINKED_SOURCE = {
    pre_qualificacao: { start: "lc_pre_quali_start_date", end: "lc_pre_quali_end_date", total: "lc_meta_investimento_pre_quali" },
    captacao:         { start: "lc_captacao_start_date",  end: "lc_captacao_end_date",  total: "lc_meta_investimento" },
  };

  function lcSyncLinkedEtapa(key) {
    var src = LC_ETAPA_VERBA_LINKED_SOURCE[key];
    if (!src) return;
    var startEl = document.getElementById(lcEtapaId(key, "start"));
    var endEl   = document.getElementById(lcEtapaId(key, "end"));
    var totalEl = document.getElementById(lcEtapaId(key, "total"));
    if (!startEl) return; // bloco ainda não renderizado (ex: no step 1 antes de abrir o step 6)
    var srcStart = document.getElementById(src.start);
    var srcEnd   = document.getElementById(src.end);
    var srcTotal = document.getElementById(src.total);
    startEl.value = srcStart ? srcStart.value : "";
    endEl.value   = srcEnd   ? srcEnd.value   : "";
    totalEl.value = srcTotal ? srcTotal.value : "";
  }

  function lcSyncAllLinkedEtapas() {
    Object.keys(LC_ETAPA_VERBA_LINKED_SOURCE).forEach(lcSyncLinkedEtapa);
  }

  // Liga a sincronização assim que o usuário edita o passo 1/2 — o card na
  // Verba já reflete na hora, sem precisar trocar de step e voltar.
  (function () {
    Object.keys(LC_ETAPA_VERBA_LINKED_SOURCE).forEach(function (key) {
      var src = LC_ETAPA_VERBA_LINKED_SOURCE[key];
      [src.start, src.end, src.total].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.addEventListener("input", function () { lcSyncLinkedEtapa(key); });
      });
    });
  })();

  function lcPopulateEtapas(etapas) {
    etapas = etapas || [];
    var verbaNomes = { "Pré-Qualificação": "pre_qualificacao", "Captação": "captacao" };

    var verbaContainer = document.getElementById("lc-etapas-container");
    verbaContainer.innerHTML = "";
    LC_ETAPAS_VERBA_DEFAULT.forEach(function(et){
      lcCreateEtapaBlock("lc-etapas-container", et.key, et.nome, false, true);
    });

    // As padrão entram SEMPRE, mesmo quando o lançamento já tem etapas salvas.
    // Antes, config existente caía no else e só renderizava o que estava no
    // banco — uma etapa padrão nova (o "WhatsApp") nunca aparecia em lançamento
    // antigo, e o previsto dela ficava zerado pra sempre no /debriefing.
    // Efeito colateral aceito: etapa padrão removida à mão volta na próxima
    // abertura, com total 0 (previsto "—") até alguém preencher.
    var eventoContainer = document.getElementById("lc-etapas-evento-container");
    eventoContainer.innerHTML = "";
    LC_ETAPAS_EVENTO_DEFAULT.forEach(function(et){
      lcCreateEtapaBlock("lc-etapas-evento-container", et.key, et.nome, true);
    });
    etapas.filter(function(e){
      return !verbaNomes[e.nome]
          && !LC_ETAPAS_EVENTO_DEFAULT.some(function(d){ return d.nome === e.nome; });
    }).forEach(function(e){
      lcCreateEtapaBlock("lc-etapas-evento-container", lcUniqueEtapaKey(e.nome), e.nome, true);
    });

    Array.from(verbaContainer.children).concat(Array.from(eventoContainer.children)).forEach(function(block){
      var nome = block.dataset.etapaNome;
      var cfg = etapas.filter(function(e){ return e.nome === nome; })[0] || {};
      lcFillEtapaBlock(block, cfg);
    });
  }

  function lcCollectEtapasFromContainer(containerId) {
    return Array.from(document.querySelectorAll("#" + containerId + " > .lc-section")).map(function(block){
      var key = block.dataset.etapaKey;
      var nome = block.dataset.etapaNome;
      var personalizada = document.getElementById(lcEtapaId(key,"personalizada")).checked;
      var curvaPct = personalizada
        ? Array.from(document.querySelectorAll("#" + lcEtapaId(key,"curva") + " .lc-curva-pct")).map(function(i){ return parseFloat(i.value) || 0; })
        : [];
      var buckets = Array.from(document.querySelectorAll("#" + lcEtapaId(key,"buckets") + " .lc-bucket-row")).map(function(row){
        var tipo = row.querySelector(".lc-bucket-tipo").value;
        return {
          nome: row.querySelector(".lc-bucket-nome").value.trim(),
          pct: parseFloat(row.querySelector(".lc-bucket-pct").value) || 0,
          tipo: tipo,
          plataforma: tipo === "campanha" ? row.querySelector(".lc-bucket-plataforma").value : null,
          conta: tipo === "campanha" ? (row.querySelector(".lc-bucket-conta").value || "").trim() : "",
        };
      }).filter(function(b){ return b.nome; });
      return {
        nome: nome,
        start_date: document.getElementById(lcEtapaId(key,"start")).value || null,
        end_date: document.getElementById(lcEtapaId(key,"end")).value || null,
        total: parseFloat(document.getElementById(lcEtapaId(key,"total")).value) || 0,
        distribuicao: personalizada ? "personalizada" : "uniforme",
        curva_pct: curvaPct,
        buckets: buckets,
      };
    });
  }

  function lcCollectEtapas() {
    return lcCollectEtapasFromContainer("lc-etapas-container").concat(lcCollectEtapasFromContainer("lc-etapas-evento-container"));
  }

  // Num <input type=number>, texto que o navegador não consegue parsear (um
  // "540.000" digitado no teclado brasileiro, por exemplo) some: `.value`
  // devolve "" e fica indistinguível de campo apagado. O resultado era gravar
  // NULL em silêncio com o botão dizendo "✓ Salvo!". `validity.badInput` é o
  // único lugar onde esse estado ainda é visível, e só aqui no navegador —
  // o servidor nunca chega a ver o que a pessoa digitou.
  function lcCamposNumericosInvalidos() {
    return Array.from(document.querySelectorAll("#lc-modal input[type=number]"))
      .filter(function(el){ return el.validity && el.validity.badInput; })
      .map(function(el){
        var campo = el.closest(".lc-field") || el.closest(".lc-section");
        var lbl = campo && campo.querySelector(".lc-label, .lc-section-title");
        return (lbl ? lbl.textContent : el.id).trim();
      });
  }

  window.lcSave = function() {
    var btn = document.getElementById("lc-btn-save");

    var invalidos = lcCamposNumericosInvalidos();
    if (invalidos.length) {
      alert("Número inválido em: " + invalidos.join(", ") +
            "\n\nUse só dígitos, sem ponto de milhar (540000, não 540.000). " +
            "Para centavos, use ponto decimal (997.50).");
      return;
    }

    btn.textContent = "Salvando...";
    btn.disabled = true;

    var metaIds   = Array.from(document.querySelectorAll("#lc-meta-menu input[type=checkbox]:checked")).map(function(cb){ return cb.value; });
    var googleIds = Array.from(document.querySelectorAll("#lc-google-menu input[type=checkbox]:checked")).map(function(cb){ return cb.value; });
    var productIds = Array.from(document.querySelectorAll(".lc-product-id")).map(function(i){ return i.value.trim(); }).filter(Boolean);
    var tmbIds = Array.from(document.querySelectorAll(".lc-tmb-id")).map(function(i){ return i.value.trim(); }).filter(Boolean);
    var outras = Array.from(document.querySelectorAll("#lc-outras-list .lc-temp-row")).map(function(row){
      return { termo: row.querySelector(".lc-outra-termo").value.trim(), scope: row.querySelector(".lc-outra-scope").value };
    }).filter(function(o){ return o.termo; });

    function v(id){ var el = document.getElementById(id); return el ? el.value : ""; }

    var payload = {
      
      pre_quali_start_date:       v("lc_pre_quali_start_date"),
      pre_quali_end_date:         v("lc_pre_quali_end_date"),
      meta_leads_pre_quali:       v("lc_meta_leads_pre_quali"),
      meta_investimento_pre_quali:v("lc_meta_investimento_pre_quali"),
      captacao_start_date:        v("lc_captacao_start_date"),
      captacao_end_date:          v("lc_captacao_end_date"),
      meta_leads:                 v("lc_meta_leads"),
      meta_investimento_captacao: v("lc_meta_investimento"),
      meta_ad_account_ids:        metaIds,
      google_ad_account_ids:      googleIds,
      filtro_lancamento:          v("lc_filtro_lancamento"),
      filtro_captacao:            v("lc_filtro_captacao"),
      filtro_pre_quali:           v("lc_filtro_pre_quali"),
      filtro_quente:              v("lc_filtro_quente"),
      filtro_quente_scope:        v("lc_filtro_quente_scope"),
      filtro_frio:                v("lc_filtro_frio"),
      filtro_frio_scope:          v("lc_filtro_frio_scope"),
      outras_temperaturas:        outras,
      carrinho_start_date:        v("lc_carrinho_start_date"),
      carrinho_end_date:          v("lc_carrinho_end_date"),
      abertura_oficial_carrinho:  v("lc_abertura_oficial_carrinho"),
      depoimento_start_date:      v("lc_depoimento_start_date"),
      depoimento_end_date:        v("lc_depoimento_end_date"),
      aulas_start_date:           v("lc_aulas_start_date"),
      aulas_end_date:             v("lc_aulas_end_date"),
      hotmart_produto_ids:        productIds,
      tmb_produto_ids:            tmbIds,
      drive_folder_url:           v("lc_drive_folder_url"),
      produto_nome:               v("lc_produto_nome"),
      produto_preco_vista:        v("lc_produto_preco_vista"),
      oferta_parcela_cartao:      v("lc_oferta_parcela_cartao"),
      oferta_parcela_boleto:      v("lc_oferta_parcela_boleto"),
      meta_faturamento:           v("lc_meta_faturamento"),
      youtube_aulas:              Array.from(document.querySelectorAll("#lc-yt-list .lc-product-row")).map(function(row){
        return {
          id:    (row.querySelector(".lc-yt-id")    || {}).value || "",
          label: (row.querySelector(".lc-yt-label") || {}).value || "",
        };
      }).filter(function(a){ return a.id; }),
      etapas: lcCollectEtapas(),
    };

    fetch("/api/launch-config/" + encodeURIComponent(_code), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    })
    .then(function(r){ return r.json(); })
    .then(function(data){
      // O motivo vem do servidor (número inválido, sem permissão): sem isso
      // todo erro virava o mesmo "Erro ao salvar" e o valor sumia sem explicação.
      if (!data.ok && data.error) alert(data.error);
      btn.textContent = data.ok ? "✓ Salvo!" : "Erro ao salvar";
      btn.style.background = data.ok ? "var(--bs-success)" : "var(--bs-danger)";
      setTimeout(function(){
        btn.textContent = "Salvar";
        btn.style.background = "";
        btn.disabled = false;
        if (data.ok) lcClose();
      }, 1400);
    })
    .catch(function(){
      btn.textContent = "Erro";
      btn.style.background = "var(--bs-danger)";
      btn.disabled = false;
    });
  };

})();
