/* Score (0–100) por conjunto/anúncio/público: helper compartilhado. Texto sempre via textContent/title. */
(function () {
  var TEXTO_LEGADO = 'Lançamento da Black usa códigos AD-XX##: o score por criativo ainda não cobre';
  var TEXTO_NAO_PONTUAVEL = 'Ainda não há respostas pontuáveis da pesquisa neste lançamento (ou a pesquisa é do Typeform antigo)';
  var TEXTO_ERRO = 'Não foi possível calcular agora';

  function brl(v) { return Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }); }

  function textoMotivo(item) {
    switch (item && item.motivo) {
      case 'sem_gasto': return 'Sem gasto de captação';
      case 'sem_leads': return 'Nenhum lead A ligado';
      case 'poucos_leads_a': return 'Pouco dado ainda (' + (item.leads_a || 0) + ' leads A)';
      case 'pre_quali': return 'Pré-quali: a régua é o custo por view (PQ-1)';
      default: return 'Sem dado de score';
    }
  }

  function vazio(td, texto) {
    td.textContent = '';
    var s = document.createElement('span');
    s.className = 'cs-vazio';
    s.textContent = '—';
    s.title = texto;
    td.appendChild(s);
  }

  function pintar(td, item) {
    if (!item || item.nota === null || item.nota === undefined) {
      vazio(td, textoMotivo(item));
      return;
    }
    var s = document.createElement('span');
    s.className = 'cs-nota' + (item.nota < 25 ? ' cs-ruim' : (item.nota > 75 ? ' cs-bom' : ''));
    s.textContent = String(item.nota);
    var custo = (item.custo_a === null || item.custo_a === undefined) ? '—' : brl(item.custo_a);
    s.title = 'custo por lead A ' + custo + ' · ' + (item.leads_a || 0) + ' leads A';
    td.textContent = '';
    td.appendChild(s);
  }

  function buscar(url) {
    return fetch(url, { credentials: 'same-origin' }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  function preencher(raiz, mapa) {
    mapa = mapa || {};
    raiz.querySelectorAll('td[data-score-chave]').forEach(function (td) {
      pintar(td, mapa[td.dataset.scoreChave]);
    });
  }

  function preencherNeutro(raiz, texto) {
    raiz.querySelectorAll('td[data-score-chave]').forEach(function (td) { vazio(td, texto); });
  }

  function textoNeutro(d, erro) {
    if (erro) return TEXTO_ERRO;
    return d && d.motivo === 'codigo_legado' ? TEXTO_LEGADO : TEXTO_NAO_PONTUAVEL;
  }

  window.BraboScore = { pintar: pintar, buscar: buscar, preencher: preencher, preencherNeutro: preencherNeutro, textoNeutro: textoNeutro, brl: brl };
})();
