# Rio Airbnb Pricing Lab

[🇺🇸 English](README.md) · **🇧🇷 Português**

[![CI](https://github.com/Patrickfgf/rio-airbnb-pricing-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/Patrickfgf/rio-airbnb-pricing-lab/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-91%20passing-brightgreen.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-96%25-brightgreen.svg)](pyproject.toml)

Um **advisor honesto de posicionamento de preço** para anfitriões de Airbnb no Rio de Janeiro,
construído de ponta a ponta sobre os dados abertos do [Inside Airbnb](https://insideairbnb.com/).
Você descreve um anúncio; ele devolve uma **faixa** de preço — onde os comparáveis se posicionam e o
que o modelo hedônico espera — **nunca um número único garantido**.

> **A decisão mais importante: eu matei o meu próprio objetivo original.** O plano era um
> **maximizador de RevPAN** (receita por noite disponível). A EDA mostrou que ele era
> **não-identificável** com estes dados: a ocupação é estimada *a partir do volume de reviews*, o
> RevPAN é *preço × essa estimativa*, e um snapshot único não tem variação de preço dentro do mesmo
> anúncio para recuperar a curva de demanda. Otimizar isso produziria um número confiante e circular.
> Então fiz o **re-scope para posicionamento de preço** — e esse julgamento *é* o resultado mais
> importante aqui. Saber o que **não** modelar é metade do trabalho.

## Principais achados (39.816 anúncios reais, snapshot 2026-03-30)

- **Espaço físico define o preço, não o serviço.** Os maiores drivers são **banheiros (~+15%)** e
  **quartos (~+14%)**; o tipo de quarto puxa para baixo (**quarto privado ~−24%**, **quarto
  compartilhado ~−69%** vs. um imóvel inteiro).
- **Ser Superhost *não* é alavanca de preço.** O coeficiente é **negativo (~−10%)** — Superhosts
  ficam levemente *abaixo* de não-Superhosts comparáveis. O selo compra ocupação e reputação, não
  prêmio de preço. (A experiência real do autor como Superhost confirma isso de forma independente —
  veja a [validação ground-truth](docs/ground_truth_validation.md).)
- **A demanda tem data.** **Réveillon** e **Carnaval** são os picos datados; as magnitudes do
  calendário detrended são **limite inferior** (picos de horizonte longo saturam num teto).
- **O modelo é honesto sobre os limites.** **R² ajustado ≈ 0,52**, então cada recomendação faz um
  **blend 50/50 entre modelo e preços de comparáveis** — nenhum dos dois sozinho decide.

## O que este projeto demonstra

| Área | Neste repositório |
|---|---|
| **Engenharia de dados** | Pipeline idempotente `raw → curated` (download → DuckDB → Parquet) com manifesto `sha256`; o calendário de 13M linhas é agregado **no DuckDB**, nunca carregado inteiro no pandas. |
| **Modelagem estatística** | OLS hedônico com efeitos fixos de bairro, checagem de colinearidade (VIF), back-transform log→preço com **smearing de Duan**, e shrinkage empírico-Bayes para conjuntos pequenos de comparáveis. |
| **Honestidade científica** | Diagnostiquei um objetivo *não-identificável* e fiz re-scope; bloqueei vazamento de target; trouxe todo caveat (faixa, proxy, limite inferior) para a interface em vez de escondê-los. |
| **Engenharia de software** | 91 testes a ~96% de cobertura, CI em Python 3.11/3.12, contratos de schema com `pandera`, `src/` tipado e modular, UI fina com **zero lógica de negócio**. |
| **Entrega** | Dashboard Streamlit ao vivo, notebook de EDA narrado, relatório de decisão por persona, e deploy em um clique. |

## Honesto por construção

O ponto do projeto, garantido em código testado em `src/` (a UI não carrega lógica de negócio):

- Uma **faixa**, nunca um preço único garantido.
- Sem comparáveis → ele diz **"sem sinal comparável suficiente"**; **não** inventa uma posição no
  percentil 50.
- Ocupação é um **proxy baseado em reviews**, sinalizado em todo lugar — nunca vendido como noites
  reservadas.
- Bairros não vistos são **marcados** como estimativa baseline, não apresentados como precisos.

## Veja funcionando

- 🖥️ **Dashboard ao vivo:** _deploy pendente — cole aqui a URL do Streamlit Cloud após o deploy._
- 📓 **Notebook de EDA narrado:** [`notebooks/eda.ipynb`](notebooks/eda.ipynb) — forma do mercado →
  mapa de bairros → sazonalidade → drivers hedônicos → o re-scope. Outputs removidos para um diff
  limpo; rode localmente para ver as figuras.
- 📊 **Relatório de decisão (PT-BR):** [`reports/decision_report.md`](reports/decision_report.md) —
  posicionamento por persona para anfitriões do Rio.
- 📒 **Caderno de bordo (estudo PT-BR):** o [site vivo no GitHub Pages](https://patrickfgf.github.io/rio-airbnb-pricing-lab/)
  (arquitetura, ADRs, glossário, timeline de build — reconstruído do estado do repo pelo CI).

## Início rápido

```bash
uv sync                                              # deps do pipeline + modelo
uv run pytest                                        # 91 testes, ~96% de cobertura em src/

# O snapshot curado pequeno (2026-03-30) está commitado, então app/notebook rodam de imediato:
uv run streamlit run app/streamlit_app.py                    # o dashboard
uv run --extra notebook jupyter lab notebooks/eda.ipynb      # o notebook
```

Reconstruir os dados curados a partir do dump de origem (opcional):

```bash
uv run python -m src.pipeline
```

## Deploy

O dashboard é uma UI fina em [Streamlit](https://streamlit.io/); o snapshot curado commitado deixa
ele subir sem banco de dados. Para publicar no **Streamlit Community Cloud**:

1. Em [share.streamlit.io](https://share.streamlit.io/), **New app** → escolha este repo, branch
   `main`, arquivo principal `app/streamlit_app.py`.
2. Ele instala a partir do [`requirements.txt`](requirements.txt) e lê os `data/curated/*.parquet`
   commitados. Nenhum segredo necessário (a fonte de dados é pública).

## Estrutura do projeto

```
src/
  data/        baixa + ingere o dump do Inside Airbnb no DuckDB
  transform/   tabelas curadas (listings, sazonalidade, ocupação) — grão explícito + pandera
  model/       OLS hedônico, posicionamento por comparáveis, contexto de demanda, recommender, e a
               orquestração service.py que o app chama (input do host -> recomendação)
  pipeline.py  build idempotente raw -> curated, com manifesto sha256
app/           dashboard Streamlit (UI fina sobre src/model/service)
notebooks/     EDA narrado (eda.ipynb), gerado por scripts/build_eda_notebook.py
reports/       relatório de decisão (PT-BR)
docs/          validação ground-truth, spec de design & planos, caderno de bordo (GitHub Pages)
tests/         91 testes (pytest), gated no CI em Python 3.11/3.12
```

## Dados & proveniência

Inside Airbnb, Rio de Janeiro, snapshot **2026-03-30**. O pipeline da Fase 1 produz **39.816 anúncios
analisáveis** mais tabelas de sazonalidade e ocupação, com `sha256` por arquivo registrado em
`data/curated/manifest.json`. O dump cru e o calendário de 3,4M linhas **não** são commitados
(reconstruíveis); só as tabelas curadas pequenas que o app precisa são versionadas, para o deploy.

## Licença

[MIT](LICENSE).
