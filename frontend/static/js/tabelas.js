/* Extraído de frontend/templates/base.html em 21/09/2026.
   Carregado com <script> síncrono, na mesma ordem em que estava inline.
   Estes arquivos dependem dessa ordem (ex.: tema.js define bsThemeTokens,
   usado depois). Não adicionar defer/async sem revisar as dependências. */
/* exportação CSV de tabela e marcação da linha de total */

document.addEventListener("DOMContentLoaded", function() {
  // 1. Total rows
  document.querySelectorAll("table").forEach(function(table) {
    table.querySelectorAll("tbody tr").forEach(function(row) {
      if (!row.cells.length) return;
      var t = row.cells[0].innerText.toLowerCase();
      if (t.includes("total") || t.includes("média") || t.includes("consolidado")) {
        row.classList.add("total-row");
      }
    });
  });

  // 2. Sortable
  document.querySelectorAll("table").forEach(function(table) {
    var headers = table.querySelectorAll("thead th");
    if (!headers.length || table.closest("#bs-drawer")) return;
    var sortIdx = -1, sortDir = 1;
    headers.forEach(function(th, i) {
      th.classList.add("sortable-header");
      th.title = "Clique para ordenar";
      th.addEventListener("click", function() {
        var tbody = table.querySelector("tbody");
        if (!tbody) return;
        var rows = Array.from(tbody.rows);
        var totals = rows.filter(r => r.classList.contains("total-row"));
        var data   = rows.filter(r => !r.classList.contains("total-row"));
        sortDir = (sortIdx === i) ? -sortDir : -1;
        sortIdx = i;
        headers.forEach(h => { var s = h.querySelector(".sort-indicator"); if(s) s.remove(); });
        var ind = document.createElement("span");
        ind.className = "sort-indicator";
        ind.innerHTML = sortDir === 1 ? '<i class="ti ti-chevron-up"></i>' : '<i class="ti ti-chevron-down"></i>';
        th.appendChild(ind);
        data.sort(function(a, b) {
          var cA = a.cells[i], cB = b.cells[i];
          if (!cA || !cB) return 0;
          var vA = (cA.dataset.val || cA.innerText).replace(/[R$\s%]/g,"").replace(/\./g,"").replace(",",".");
          var vB = (cB.dataset.val || cB.innerText).replace(/[R$\s%]/g,"").replace(/\./g,"").replace(",",".");
          var nA = parseFloat(vA), nB = parseFloat(vB);
          if (!isNaN(nA) && !isNaN(nB)) return (nA - nB) * sortDir;
          return vA.localeCompare(vB) * sortDir;
        });
        tbody.innerHTML = "";
        data.forEach(r => tbody.appendChild(r));
        totals.forEach(r => tbody.appendChild(r));
      });
    });
  });

  // 3. Filter input + export CSV
  function csvCell(v) {
    v = String(v == null ? "" : v).replace(/\s+/g, " ").trim();
    if (/[;"\r\n]/.test(v)) v = '"' + v.replace(/"/g, '""') + '"';
    return v;
  }
  function tableTitle(table) {
    var sec = table.closest(".section, .dbf-section");
    var titleEl = sec && sec.querySelector(".section-title, .dbf-section-title");
    var text = (titleEl ? titleEl.innerText : document.title) || "tabela";
    var slug = text.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-+|-+$/g, "").toLowerCase();
    return (slug || "tabela").slice(0, 60);
  }
  function exportTableCsv(table) {
    var lines = [];
    var headCells = table.querySelectorAll("thead tr:last-child th, thead tr:last-child td");
    if (headCells.length) lines.push(Array.from(headCells).map(c => csvCell(c.innerText)).join(";"));
    var tbody = table.querySelector("tbody");
    Array.from(tbody.rows).forEach(function(r) {
      if (r.style.display === "none") return;
      lines.push(Array.from(r.cells).map(c => csvCell(c.innerText)).join(";"));
    });
    var blob = new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = tableTitle(table) + ".csv";
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  }
  document.querySelectorAll("table").forEach(function(table) {
    if (table.closest("#bs-drawer")) return;
    if (table.closest("[data-no-filter]")) return;
    var tbody = table.querySelector("tbody");
    if (!tbody) return;
    var dataRows = Array.from(tbody.rows).filter(r => !r.classList.contains("total-row"));
    if (dataRows.length <= 5) return;
    var wrap = document.createElement("div");
    wrap.className = "bs-table-filter-wrap bs-tf-collapsed";
    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "bs-table-filter-toggle";
    toggle.setAttribute("aria-label", "Filtrar tabela");
    toggle.innerHTML = '<i class="ti ti-search"></i>';
    var inp = document.createElement("input");
    inp.type = "text";
    inp.placeholder = "Filtrar tabela...";
    inp.className = "bs-table-filter";
    toggle.addEventListener("click", function() {
      wrap.classList.remove("bs-tf-collapsed");
      inp.focus();
    });
    inp.addEventListener("blur", function() {
      if (!inp.value) wrap.classList.add("bs-tf-collapsed");
    });
    inp.addEventListener("input", function() {
      var q = inp.value.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g,"");
      dataRows.forEach(function(row) {
        var t = row.innerText.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g,"");
        row.style.display = t.includes(q) ? "" : "none";
      });
    });
    var exportBtn = document.createElement("button");
    exportBtn.type = "button";
    exportBtn.className = "bs-table-export-btn";
    exportBtn.title = "Exportar CSV (respeita filtro e ordena\u00e7\u00e3o atuais)";
    exportBtn.innerHTML = '<i class="ti ti-download"></i>';
    exportBtn.addEventListener("click", function() { exportTableCsv(table); });
    wrap.appendChild(toggle); wrap.appendChild(inp); wrap.appendChild(exportBtn);
    var parent = table.parentElement;
    if (parent && parent.classList.contains("table-wrap")) {
      parent.parentElement.insertBefore(wrap, parent);
    } else {
      table.parentElement.insertBefore(wrap, table);
    }
  });
});
