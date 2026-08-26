# 🆕 IMMUNED v3.5 - Changelog

## 🐛 Correções de extração + 🎯 Novo filtro de coorte (AIJ)

### 📌 Resumo das Mudanças

**Versão:** 3.5
**Data:** 26/08/2026
**Arquivo:** `app_immuned_v35.py`
**Gerado a partir da v3.4 via:** `patch_v34_to_v35.py`
**Testes:** `teste_v35.py` (45 asserções, todas passando)

Esta versão corrige três problemas de extração apontados em revisão — o mais
grave sendo a **negação não tratada**, que inflava sistematicamente as taxas de
uso atual — e adiciona a **exclusão de pacientes com AIJ** da coorte.

> ⚠️ **Impacto nos números:** por causa da correção da negação, as taxas de uso
> atual (biológicos e MTX) tendem a **cair** em relação à v3.4. Rerode a base e
> revalide as métricas antes de usar no artigo.

---

## 🎯 O Que Foi Corrigido

### 1. 🔴 Negação de uso não era tratada (crítico)

**Problema:** frases negadas eram lidas como uso ativo (`SIM`):

| Frase no prontuário | v3.4 (errado) | v3.5 (correto) |
|---|---|---|
| "não faz uso de adalimumabe" | SIM | NÃO |
| "não está em uso de tocilizumabe" | SIM | NÃO |
| "sem uso de metotrexato" | SIM | NÃO |
| "nega uso de …" | SIM / INDETERMINADO | NÃO |

O caso mais insidioso: `"em uso"` casava como *substring* dentro de `"sem uso"`.

**Correção:**
- Novo `NEGACAO_PATTERN`: detecta partícula de negação (`não`, `nunca`, `jamais`,
  `nega`, `sem`) imediatamente antes de um marcador de uso (janela de ~25 chars,
  até 2 palavras no meio).
- Nova lista `USO_NEGADO_PATTERNS` (uso explicitamente negativo).
- Nova ordem de varredura `STATUS_SCAN`: `NÃO` (negado) entra com **prioridade
  máxima (-1)**, vencendo `PRÉVIO` (0) e `SIM` (1) em empate de distância.
- Fronteira de palavra em `\bem\s+uso` para não disparar dentro de `"sem uso"`.

### 2. 🟠 Deduplicação apagava registros reais

**Problema:** `drop_duplicates(subset=['descricao'])` deduplicava só pelo texto.
Frases padronizadas ("Retorno em 3 meses.") apareciam em pacientes diferentes, e
a limpeza apagava silenciosamente um registro real.

**Correção:** chave de deduplicação passou a ser
`['paciente', 'tipo', 'data_hora', 'descricao']`.

### 3. 🟠 Vários biológicos ativos no mesmo registro

**Problema:** quando dois biológicos apareciam como `SIM` no mesmo registro, o
código fixava sempre `biologicos_em_uso[0]` (o primeiro da ordem de
configuração), escondendo o segundo antes de qualquer revisão.

**Correção:** 2+ biológicos ativos no mesmo registro são marcados como
`'MÚLTIPLO'`, com a lista completa preservada em `biologicos_atuais_lista` e a
contagem em `num_biologicos_atuais`. O caso fica visível na análise por biológico
em vez de mascarado.

### 4. ✨ Exclusão de coorte AIJ (novo)

**Motivação:** Artrite Idiopática Juvenil (AIJ) não é Artrite Reumatoide do
adulto e não deve compor a coorte.

**Comportamento:** pacientes com qualquer menção de AIJ — por texto (*artrite
idiopática / reumatoide / crônica juvenil*, siglas AIJ/ACJ/ARJ) **ou** por CID-10
(**M08**) — são removidos **inteiros** da coorte antes das análises. Um único
registro identificando o diagnóstico basta. A lista de excluídos fica disponível
para auditoria na tela.

Controlado pelo checkbox **"🎯 Filtros de coorte → Excluir pacientes com AIJ"**
(ligado por padrão) na aba *Configurar ETL*.

### 5. 🩹 Ajustes de tela

- Versão exibida no **cabeçalho** (`Immuned v3.5`) e no **rodapé** (antes o
  rodapé trazia `v3.4` fixo).
- Lista de pacientes excluídos por AIJ exibida com IDs limpos (sem `np.int64`).

---

## 🔧 Mudanças Técnicas

### Constantes e funções novas

| Item | Linha (aprox.) | Papel |
|---|---|---|
| `NEGACAO_PATTERN` | 421 | Regex de partícula de negação antes do marcador |
| `USO_NEGADO_PATTERNS` | 428 | Padrões de uso explicitamente negativo |
| `STATUS_SCAN` | 438 | Ordem de varredura NÃO(-1) < PRÉVIO(0) < SIM(1) |
| `AIJ_CID_PATTERN` | 319 | CID-10 M08.x |
| `AIJ_TEXTO_PATTERNS` | 320 | Termos de AIJ por texto |
| `registro_menciona_aij(text)` | 327 | True se o registro menciona AIJ (texto ou CID) |
| `APP_VERSION` | 1279 | Versão única, usada no cabeçalho e rodapé |

### Modificações no código existente

- **`extract_medicamento_status`**: laço de competição reescrito para usar
  `STATUS_SCAN` + checagem de negação por proximidade.
- **`extract_biologicos_detalhado`** (linhas ~759–798): novas colunas
  `num_biologicos_atuais` e `biologicos_atuais_lista`; ramo de 2+ ativos marca
  `'MÚLTIPLO'`.
- **`COLS_STATUS_EXTRA`**: inclui `num_biologicos_atuais` (propaga para `_t0`/`_t1`).
- **Pipeline (`main`)**: dedup por 4 colunas (linha ~1659) e nova **ETAPA 0.5**
  de exclusão de AIJ (linha ~1664); checkbox `excluir_aij` (linha ~1442).

### Colunas novas no `df_processed`

- `num_biologicos_atuais` — quantidade de biológicos ativos no registro.
- `biologicos_atuais_lista` — lista dos biológicos ativos (texto), quando ≥ 1.

---

## 📦 Compatibilidade

### ✅ Mantido compatível
- Estrutura de dados, abas e configurações de ETL preservadas.
- Colunas sem sufixo (`uso_biologico`, `{med}_status` etc.) continuam existindo.
- Opções de compatibilidade da v3.3 (`fallback_sim`, aliases estritos, janela)
  seguem disponíveis.

### 📊 Requisitos de dados (inalterados)
Colunas obrigatórias: `paciente`, `tipo`, `descricao`, `data_hora`.

### ⚠️ Mudança de resultado esperada
As taxas de uso atual mudam (para menos) em relação à v3.4 — isso é a **correção**
funcionando, não uma regressão. Documente o antes/depois ao atualizar o artigo.

---

## 🚀 Como Usar

### 1. Substituir / versionar o arquivo
```bash
# a v3.5 é gerada a partir da v3.4 pelo patch (reexecutável)
python3 patch_v34_to_v35.py    # -> app_immuned_v35.py
```

### 2. Rodar os testes
```bash
python3 teste_v35.py           # deve terminar em "TODOS OS TESTES PASSARAM"
```

### 3. Executar a aplicação
```bash
streamlit run app_immuned_v35.py
```

### 4. Deploy (Streamlit Cloud)
- Atualizar o **Main file path** para `app_immuned_v35.py`.
- `requirements.txt` deve fixar `pandas>=2.2.0,<3.0.0` (evita quebra no pandas 3.x).

---

## ✅ Checklist de Validação

- [x] Patch aplicado (12 substituições verificadas como ocorrência única)
- [x] `teste_v35.py` — 45 asserções passando (20 da v3.4 + 25 novas)
- [x] Negação testada (frases negadas → NÃO; positivas seguem SIM)
- [x] Dedup por paciente (frase igual de 2 pacientes não é apagada)
- [x] MÚLTIPLO em 2+ biológicos simultâneos
- [x] AIJ detectada por texto e por CID M08 (exclusão no nível paciente)
- [x] Versão no cabeçalho e rodapé
- [ ] Base real rerodada e taxas revalidadas para o artigo
- [ ] Entrypoint do Streamlit Cloud apontando para v3.5

---

**Versão 3.5 pronta para uso! 🎉**

*Desenvolvido com ❤️ para IMMUNED*
