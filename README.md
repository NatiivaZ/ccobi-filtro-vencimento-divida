# Acompanhamento — Comparação de bases por ano de vencimento (DIVIDA v2)

Aplicação **Streamlit** para **comparar duas versões de uma mesma base** (por exemplo, extração **antiga** vs **nova**) e medir **quantos autos “saíram” ou “entraram”** entre os conjuntos, **estratificando por ano de vencimento**.  
Inclui **histórico persistente** em **SQLite** e exportação de planilhas por execução.  
Projeto **CCOBI – SERASA**.

---

## Problema que resolve

Em ciclos regulares de atualização da base de **dívida ativa / vencimentos**, é comum precisar responder:

- Quantos registros **deixaram** de existir na base nova em relação à antiga?  
- Quantos **entraram**?  
- Como isso se distribui por **ano de vencimento**?

Este app automatiza o cálculo, gera **tabelas comparativas**, **gráficos** e **arquivos Excel** por ano, além de guardar um **histórico** consultável na própria interface.

---

## Funcionalidades principais

| Recurso | Descrição |
|---------|-----------|
| **Duas entradas** | Upload **base antiga** e **base nova** (`.xlsx`, `.xls`, `.csv`). |
| **Colunas configuráveis** | Identificador do auto (obrigatório), data de vencimento (obrigatório); opcionais: nº do processo, subtipo/modal, CPF/CNPJ. |
| **Deduplicação** | Por auto, **mantendo a data de vencimento mais antiga** quando há duplicatas. |
| **Ano de vencimento** | Deriva o ano a partir da coluna de vencimento (parse com `dayfirst`). |
| **Comparação** | Conjuntos por ano: autos que saíram, que entraram, totais agregados. |
| **Visualização** | Gráficos Plotly (barras/linhas conforme telas implementadas). |
| **Exportação** | Download de Excel na sessão + gravação em disco por “run”. |
| **Histórico** | SQLite (`historico_comparacoes.db`) + pasta `historico_exportacoes/<id>/` com `Comparacao.xlsx` e `Autos_vencimento_<ano>.xlsx`. |

---

## Requisitos

- **Python** 3.8+  

```bash
pip install -r requirements.txt
```

Pacotes: `streamlit`, `pandas`, `numpy`, `plotly`, `openpyxl`, `xlrd`.

---

## Como executar

```bash
cd "Sistema de filtro de vencimento DIVIDAv2"
pip install -r requirements.txt
streamlit run app_vencimentos.py
```

No Windows, use `iniciar_vencimentos.bat` se disponível.

A URL padrão do Streamlit será exibida no terminal (ex.: `http://localhost:8501`).

---

## Fluxo de uso (operador)

1. Abra o app e, na barra lateral, envie a planilha **base antiga** (período anterior) e a **base nova** (período atual).  
2. Confirme os nomes das colunas (valores padrão costumam ser `Identificador do Débito` e `Data do Vencimento`).  
3. Execute a análise.  
4. Interprete a tabela resumo (totais saíram/entraram) e os detalhes por ano.  
5. Faça **download** dos Excel gerados ou consulte o **histórico** de execuções anteriores (lista, metadados, opção de excluir registro do histórico conforme UI).

---

## Módulo `historico_db.py`

Responsável pela persistência:

- **`init_db()`** — cria tabela `comparacoes` se não existir.  
- **`save_run(...)`** — grava metadados, JSON auxiliar e arquivos em `historico_exportacoes/<uuid>/`.  
- **`list_runs()`** — lista execuções (mais recente primeiro).  
- **`get_run` / `excluir_run`** — recuperação e remoção de entradas.

Arquivos locais:

- `historico_comparacoes.db` — banco SQLite.  
- `historico_exportacoes/` — um subdiretório por execução com os XLSX exportados.

> **Git:** a pasta `historico_exportacoes/` e o `.db` costumam estar no **`.gitignore`** para não versionar dados reais. Após clonar, o histórico começa vazio até a primeira execução.

---

## Formato dos dados

- **CSV:** leitura com `encoding='utf-8'`, separador `;`, `decimal=','` (alinhado a exports brasileiros).  
- **Excel:** primeira linha como cabeçalho; linhas totalmente vazias são descartadas.

---

## Relação com o “Sistema de Comparação SERASA”

O repositório **Sistema de Comparação SERASA** contém `app.py` (cruzamento SERASA × Dívida Ativa) e um `app_vencimentos.py` para **uma** base.  
Este projeto (**DIVIDA v2**) aprofunda o cenário de **duas extrações temporais** da mesma linha de dados, com **histórico** e exports por ano — adequado a **acompanhamento evolutivo** da carteira.

---

## Estrutura de arquivos

| Arquivo | Função |
|---------|--------|
| `app_vencimentos.py` | Interface Streamlit + lógica de comparação |
| `historico_db.py` | SQLite + gravação de pastas de exportação |
| `requirements.txt` | Dependências |
| `iniciar_vencimentos.bat` | Atalho de execução |
| `historico_comparacoes.db` | Criado em runtime (não versionar com dados sensíveis) |
| `historico_exportacoes/` | Exports por execução (ignorado no Git) |

---

## Segurança

- Bases de dívida contêm **dados pessoais e financeiros**. Mantenha o repositório **privado** e restrinja cópias do `.db` e da pasta `historico_exportacoes`.  
- Em máquinas compartilhadas, proteja o diretório do projeto com permissões do sistema operacional.

---

## Solução de problemas

| Problema | Verificação |
|----------|-------------|
| Ano vazio ou estranho | Formato de data na coluna de vencimento; valores nulos. |
| Contagens inesperadas | Duplicatas de auto — conferir se a deduplicação “mais antiga” reflete a regra de negócio desejada. |
| Histórico não lista nada | Primeira execução ainda não salva; permissão de escrita na pasta do app. |
| Erro de CSV | Separador decimal/virgula vs ponto; tentar salvar como XLSX. |

---

## Contexto

Ferramenta de **acompanhamento** para gestão de carteira por **vencimento**, no âmbito **CCOBI – SERASA**.
