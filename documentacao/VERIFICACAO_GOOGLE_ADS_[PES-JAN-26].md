# VERIFICAÇÃO FINAL: DADOS GOOGLE ADS [PES-JAN-26]

## ✅ CONFIRMADO

### Google Ads Investment [PES-JAN-26]

| Métrica | Valor |
| :--- | :--- |
| **Total Gasto (Custo)** | **R$ 270.755,22** ✅ VERIFICADO |
| **Conversões Reportadas** | **16.779** |
| **CPA Médio** | **R$ 16,14** |
| **Período** | 23/12/2025 - 22/01/2026 |
| **Campanhas** | **31 campanhas** (todas com [PES-JAN-26]) |

---

## Fonte dos Dados

**Arquivo:** `Gads---Anunciante-Campanhas-23-de-dez-de-2025-21-de-jan-de-2026.csv`

**Linha de Total:**
```
Total: Campanhas, --,--,--,--,BRL,--,,--,--,"0,04","5,20",52.058.218,
11.265.723,"21,64%","0,02","270755,22","16.779,00","16,14","0,00",...
```

**Conversão do valor:** 270755,22 (formatação brasileira com vírgula) = **R$ 270.755,22**

---

## Verificação de Integridade

### ✅ Todas as 31 campanhas têm [PES-JAN-26]

```
Linha 5-35: Campanhas individuais
├─ 31 campanhas com [PES-JAN-26] na nomenclatura ✅
├─ Todas com Status "Pausada", "Ativada" ou "recently_completed"
└─ Período: 23/12/2025 - 21/01/2026

Linha 36: Total: Campanhas
└─ Custo: "270755,22" (soma de todas acima)

Linha 37: Total: Conta
└─ Custo: "903194,17" (inclui OUTRAS campanhas, períodos diferentes)
```

### ⚠️ Total: Conta é DIFERENTE (R$ 903.194,17)

**Explicação:**
- `Total: Campanhas` = Apenas [PES-JAN-26] = **R$ 270.755,22** ✅
- `Total: Conta` = Todas as campanhas da conta Google = **R$ 903.194,17** (em outro período/data)
- Não devemos usar Total: Conta (inclui campanhas fora do escopo)

---

## Resumo da Campanha [PES-JAN-26]

| Tipo | Campanhas | Gasto |
| :--- | ---: | ---: |
| Pré-qualificação Vídeo | 4 | R$ 34.193,25 |
| Captação Escrevente (Geração) | 23 | R$ 212.935,07 |
| Remarketing (RMK Aulas) | 4 | R$ 23.626,90 |
| **TOTAL** | **31** | **R$ 270.755,22** |

---

## Conclusão

✅ **Google Ads [PES-JAN-26] investimento: R$ 270.755,22 CORRETO**
✅ **Conversões: 16.779 CORRETO**
✅ **CPA: R$ 16,14 CORRETO**

Todos os valores estão validados e prontos para análise final.
