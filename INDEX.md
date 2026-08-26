# 📚 IMMUNED — Índice de Documentação

Versão atual: **v3.5** · Arquivo principal: **`app_immuned_v35.py`**

---

## 🚀 Arquivos principais

| Arquivo | O que é |
|---|---|
| **`app_immuned_v35.py`** | Aplicação Streamlit — **este é o arquivo para executar e para o deploy** |
| `patch_v34_to_v35.py` | Gera a v3.5 a partir da v3.4 (reexecutável, 12 edições verificadas) |
| `teste_v35.py` | Suíte de testes (45 asserções, todas passando) |
| `extraction_module.py` | Funções auxiliares de extração |
| `requirements.txt` | Dependências (com `pandas>=2.2.0,<3.0.0`) |
| `LOGO.jpeg` | Logo (opcional; há fallback se ausente) |

Versões anteriores do app (`app_immuned_v34.py`, `v33`, `v32`) e `teste_v34.py`
ficam no repositório para referência/histórico.

---

## 📖 Documentação

| Documento | Conteúdo |
|---|---|
| [`README.md`](README.md) | Visão geral, instalação, estrutura de dados, casos de uso |
| [`CHANGELOG_v35.md`](CHANGELOG_v35.md) | **Mudanças da v3.5**: negação, dedup, MÚLTIPLO, AIJ |
| [`CHANGELOG_v32.md`](CHANGELOG_v32.md) | Histórico: Análise de Trocas de Medicamentos (v3.2) |
| [`GUIA_RAPIDO_v32.md`](GUIA_RAPIDO_v32.md) | Início rápido e casos de uso (base v3.2, ainda útil) |

---

## 🗺️ Histórico de versões (resumo)

- **v3.5 (atual)** — Correções de extração da revisão + limpeza de coorte:
  - 🔴 **Negação** tratada ("não/nega/sem uso" → não-ativo). Antes contava como
    uso atual e inflava as taxas.
  - 🟠 **Deduplicação** por `paciente+tipo+data+descrição` (não apaga registros
    reais).
  - 🟠 **Múltiplos biológicos** no mesmo registro → `MÚLTIPLO` (lista preservada).
  - ✨ **Exclusão de AIJ** (texto + CID-10 M08), no nível do paciente.
- **v3.4** — Aliases com fronteira de palavra; status por proximidade;
  categoria `INDETERMINADO`; base longitudinal com status `_t0`/`_t1`;
  ordenação cronológica antes das agregações.
- **v3.3** — Ajustes de extração/interface (base para a v3.4).
- **v3.2** — Análise de Trocas de Medicamentos (matriz de transição, taxa de
  abandono, motivos, sequências, eficácia pós-troca).
- **v3.1** — Interface IMMUNE; Fator Reumatoide; status SIM/PRÉVIO/NÃO; MTX
  detalhado; biológicos expandidos.

---

## ⚡ Começar em 3 passos

```bash
# 1. dependências (Python 3.9+)
pip install -r requirements.txt

# 2. testes
python3 teste_v35.py        # "TODOS OS TESTES PASSARAM"

# 3. executar
streamlit run app_immuned_v35.py
```

---

## 📊 Dados de entrada

Colunas obrigatórias: `paciente`, `tipo` (ANAMNESE/EVOLUCAO), `data_hora`,
`descricao`. Recomendadas: `idade`, `sexo`. Formatos: `.xlsx`, `.xls`, `.csv`.

---

## 🚢 Deploy (Streamlit Cloud)

- **Main file path:** `app_immuned_v35.py`
- Confira que o `requirements.txt` fixa `pandas>=2.2.0,<3.0.0` (o pandas 3.x
  quebra reduções numéricas no ambiente).

---

## ✅ Checklist de release v3.5

- [x] `teste_v35.py` — 45 asserções passando
- [x] Versão no cabeçalho e rodapé (`v3.5`)
- [x] `CHANGELOG_v35.md`, `README.md` e `INDEX.md` atualizados
- [ ] Base real rerodada e taxas revalidadas para o artigo
- [ ] Entrypoint do Streamlit Cloud apontando para `app_immuned_v35.py`

---

*Índice de Documentação — IMMUNED v3.5*
