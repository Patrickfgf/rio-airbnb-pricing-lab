# Rio Airbnb Pricing Lab — Design Spec

> **Codinome interno:** "Maré" · **Autor:** Patrick Fernandes Godinho Filho · **Data:** 2026-06-08
> **Tipo:** Projeto de portfólio — Data Analytics (case "que move decisão")
> **Status:** Design aprovado, aguardando plano de implementação.

---

## 1. Problema e objetivo

Um host de Airbnb no Rio de Janeiro toma, repetidamente, **a decisão mais cara da operação: quanto cobrar por noite, em cada data.** Cobrar caro demais → diária vazia. Cobrar barato demais → lotado, mas deixando dinheiro na mesa. A maioria decide no feeling.

Este projeto entrega uma **análise + ferramenta de decisão de pricing** sobre dados reais e abertos do mercado carioca, capaz de recomendar uma faixa de preço por **bairro × tipo de imóvel × época do ano**, com a ocupação e a receita esperadas — e de explicar *por que*.

**Por que este projeto existe (contexto de portfólio):** diferenciar o portfólio do autor. Hoje seus projetos de DS reais são datasets de brinquedo (Titanic, Kaggle); o projeto-âncora (pipeline Eldorado) prova Engenharia de Dados. Falta um **case de Analytics que demonstre julgamento de negócio** — tirar decisão de dado, não só treinar modelo. EDA pura de Airbnb é commodity (já há várias públicas); o diferencial aqui é (a) um **produto de decisão**, não só gráficos, e (b) **validação contra ground truth** de quem operou um anúncio Top 10% global.

## 2. Pergunta central e métrica

> *"Para um host no Rio, qual preço maximiza a receita esperada (RevPAN) em cada combinação de bairro × tipo de imóvel × época do ano — e quais atributos do anúncio movem essa fronteira?"*

**Métrica-alvo: RevPAN (Revenue per Available Night) = preço × ocupação.**
Razão: nem preço sozinho (caro e vazio não paga conta) nem ocupação sozinha (lotado e barato também não) capturam o objetivo do host. RevPAN é o trade-off que importa.

Sub-perguntas:
1. **Sazonalidade** — como preço e ocupação variam por mês e dia da semana? (Réveillon, Carnaval, alta/baixa.)
2. **Hedônico** — quanto cada atributo (bairro, Superhost, política de cancelamento, nº de quartos, capacidade) adiciona a preço e ocupação?
3. **Fronteira preço×ocupação** — onde está o preço que maximiza RevPAN, dado o conjunto de comparáveis?

## 3. Fonte de dados

**Inside Airbnb — Rio de Janeiro** (dados abertos, sem PII → sem questão de LGPD; contraste limpo com o Eldorado, que rodou dados sintéticos).

Cobertura confirmada na fonte (jun/2026):
- `listings.csv.gz` — ~35.847 anúncios, 106 variáveis (preço, tipo, bairro, amenidades, política, Superhost, reviews, scores…).
- `calendar.csv.gz` — preço e disponibilidade **diários** para ~12 meses à frente (insumo de sazonalidade e do proxy de ocupação).
- `reviews.csv.gz` — data de cada review (proxy de ritmo de reservas).

Snapshot único (o dump datado mais recente). A data do dump é registrada e versionada para reprodutibilidade.

## 4. Arquitetura

Unidades pequenas, com propósito único e testáveis isoladamente (mesmo padrão do pipeline Eldorado).

```
data/                 ingestão: baixa o dump do Inside Airbnb Rio → DuckDB (raw)
src/transform/        funções puras: limpeza de preço ("$1,200.00"→float), parsing de
                      calendar, cálculo do proxy de ocupação, feature engineering
src/model/            modelo hedônico (regressão log-preço) + lógica do recomendador
notebooks/eda.ipynb   narrativa exploratória (Restart & Run All limpo, seeds fixas)
app/streamlit_app.py  dashboard + recomendador (UI fina sobre src/)
tests/                pytest sobre transform e model
.github/workflows/    CI: Ruff + pytest (matriz de versões de Python)
```

**Fluxo de dados:**
`dump Inside Airbnb` → `DuckDB raw` → `src/transform (pandas/DuckDB)` → `tabelas curated` → consumidores: (a) `notebooks/eda.ipynb`, (b) `src/model` hedônico, (c) recomendador → `app/streamlit_app.py`.

Camadas explícitas **raw → curated** (reconstruíveis a partir do dump). Pipeline idempotente: re-rodar produz o mesmo resultado.

### Contratos entre unidades (o que cada uma faz / depende)
- `transform`: recebe DataFrames raw, devolve DataFrames curated tipados. Não conhece UI nem modelo.
- `model`: recebe curated, devolve coeficientes hedônicos e a função recomendadora. Não conhece UI.
- `app`: só orquestra `transform`/`model` e renderiza. Sem lógica de negócio embutida.

## 5. O recomendador (núcleo do produto)

**Input do host:** bairro, tipo de imóvel, nº de quartos, capacidade, é Superhost?, política de cancelamento, datas/temporada.

**Output:** faixa de preço sugerida (não um número mágico) · ocupação esperada nessa faixa · RevPAN esperado · **os top drivers** que mais pesaram na recomendação.

**Método — regras + estatística interpretável, por escolha consciente** (mesma decisão "regras vs ML" defendida no Eldorado):
1. **Comparáveis de mercado** — peers no mesmo bairro × tipo × época (distribuição de preço dos similares).
2. **Ajuste hedônico** — corrige a faixa pelos atributos específicos do anúncio (Superhost, política, capacidade) via coeficientes do modelo.
3. **Curva preço×ocupação** — estima ocupação como função do preço relativo ao mercado comparável; aponta o preço que maximiza RevPAN.

**Honestidade embutida na UI:** mostra intervalo + a ressalva do proxy de ocupação. Sem precisão falsa.

## 6. Rigor metodológico (blindagem contra leitura sênior)

- **Proxy de ocupação:** disponibilidade do Inside Airbnb ≠ reserva real (bloqueado ≠ reservado). Mitigação: cross-check com ritmo de reviews ("San Francisco model": reviews × taxa de review × estadia média) e **documentação explícita da limitação**.
- **Modelo hedônico:** variável dependente em log-preço; efeitos fixos de bairro; checagem de multicolinearidade (VIF); coeficientes lidos como **associação, não causa**.
- **Vieses declarados:** survivorship (só anúncios ativos no snapshot); viés do snapshot único (sem histórico longitudinal); outliers de preço tratados por winsorize/clip com limiar documentado.
- **Reprodutibilidade:** seeds fixas (`np.random.seed`, `random_state`); dump datado e versionado; notebook roda de cima a baixo sem estado oculto.

## 7. Validação contra ground truth (diferencial único, não copiável)

Seção dedicada (README + notebook) confrontando o **playbook real de Superhost do autor** (resposta rápida, política flexível, fotos próprias, precificação sazonal) com os drivers que emergem dos dados do Rio: os atributos que ele priorizou na prática aparecem como movedores de ocupação/receita?

**Enquadramento honesto:** o mercado operado foi Pirenópolis-GO, não Rio. Logo, a validação é de **princípios transferíveis de hosting contra o mercado do Rio** — não "meus próprios dados". Isso converte um exercício de dados em prova de julgamento de negócio.

## 8. Entregáveis (padrão de qualidade "DNA Eldorado")

- Repositório público **MIT**, README **insight-first** (história + principais achados no topo, antes do "como rodar").
- **Notebook de EDA** narrada e renderizada (nbviewer).
- **Dashboard Streamlit ao vivo** (deploy público, como o Eldorado), com filtros + o recomendador.
- **Relatório de decisão** (1–2 páginas): traduções acionáveis por persona ("se você é host em Copacabana, faça X").
- **pytest** sobre `transform`/`model` + **GitHub Actions** (Ruff + testes).

## 9. Escopo

**Dentro:** Rio de Janeiro; snapshot único do dump mais recente; recomendador por regras + hedônico; dashboard; validação contra ground truth.

**Fora (vira "Trabalho futuro" no README):** múltiplas cidades; ingestão recorrente/streaming; ML pesado (XGBoost/forecasting de demanda); autenticação/multiusuário.

**Prazo estimado:** ~1,5–2 semanas em operação solo com IA.

## 10. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Proxy de ocupação engana | Cross-check por reviews + limitação documentada na UI e no README |
| Parecer "mais uma EDA de Airbnb" | Produto de decisão (recomendador) + validação ground-truth como espinha |
| Escopo inflar (virar mini-Eldorado) | Não-escopo explícito; snapshot único; regras > ML |
| Link de dump do Inside Airbnb mudar/cair | Script de ingestão parametrizado por URL/data; dump versionado localmente |

## 11. Onde o julgamento de domínio do autor entra no código

Pontos em que a decisão é do autor (host), não do assistente — a serem implementados por ele (5–10 linhas), no estilo aprendizado:
- **Fórmula do proxy de ocupação** (como traduzir disponibilidade + reviews em ocupação estimada).
- **Lógica de escolha do preço ótimo** no recomendador (como ponderar a curva preço×ocupação para maximizar RevPAN).

## 12. Stack

Python (pandas, numpy, scikit-learn/statsmodels para o hedônico, matplotlib/seaborn) · DuckDB (SQL analítico, camadas raw→curated) · Streamlit + Plotly (dashboard) · pytest · Ruff · GitHub Actions. Reusa a stack já provada no Eldorado.
