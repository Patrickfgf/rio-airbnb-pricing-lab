"""Curated content for the living project notebook (docs/index.html).

This is the ONE file to edit by hand to grow the notebook: project description,
architecture, stack rationale, ADRs (decision records), domain glossary, roadmap
and the running build log. All prose is PT-BR on purpose — this is a personal
study companion, not the public README.

Live facts (git timeline, file tree, task progress, stack versions) are NOT here:
they are extracted from the repository at generation time by generate_overview.py.

Light inline HTML (<code>, <strong>, <em>, <a>) is allowed in the text fields —
this content is fully trusted (we author it). Values coming from git are escaped
by the generator instead.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Identidade do projeto
# --------------------------------------------------------------------------- #
PROJECT = {
    "name": "Rio Airbnb Pricing Lab",
    "tagline": (
        "Laboratório de decisão de preços para anfitriões de Airbnb no Rio de "
        "Janeiro, construído sobre os dados abertos do Inside Airbnb."
    ),
    "problem": (
        "Um anfitrião no Rio não sabe <strong>por quanto</strong> alugar: preço "
        "alto derruba a ocupação, preço baixo queima receita. Não existe um número "
        "público confiável de ocupação por anúncio, e os dados crus do Inside "
        "Airbnb são sujos (preço como texto, booleanos <code>t/f</code>, colunas "
        "nulas). Falta uma ponte entre o dado bruto e uma <em>recomendação de "
        "preço defensável</em>."
    ),
    "goal": (
        "Um pipeline reprodutível e testado que transforma o dump do Inside "
        "Airbnb em tabelas <em>curated</em> tipadas, e — nas fases seguintes — "
        "num modelo de preço hedônico + recomendador que devolve faixa de preço "
        "sugerida, ocupação esperada e os principais drivers de valor."
    ),
}

# --------------------------------------------------------------------------- #
# Pipeline (estágios do fluxo de dados)
# --------------------------------------------------------------------------- #
PIPELINE = [
    {
        "stage": "dump",
        "label": "Inside Airbnb",
        "desc": "<code>listings.csv.gz</code> + <code>calendar.csv.gz</code> baixados via HTTP (snapshot resolvido em runtime).",
    },
    {
        "stage": "raw",
        "label": "DuckDB (raw)",
        "desc": "Camada bruta materializada no DuckDB — fiel ao dump, sem transformação.",
    },
    {
        "stage": "transform",
        "label": "src/transform",
        "desc": "Funções puras: limpeza de preço, parsing de campos, proxy de ocupação, features.",
    },
    {
        "stage": "curated",
        "label": "Parquet (curated)",
        "desc": "3 tabelas tipadas e validadas (pandera): listings, occupancy, calendar_seasonality.",
    },
    {
        "stage": "model",
        "label": "src/model (fase 2)",
        "desc": "Modelo hedônico interpretável (log-preço + efeitos fixos de bairro) + advisor de posicionamento: faixa sugerida e onde o anúncio cai vs. os pares. Ver ADR-08.",
    },
    {
        "stage": "app",
        "label": "Streamlit (fase 3)",
        "desc": "UI fina sobre src/ — o anfitrião insere o anúncio e recebe a recomendação.",
    },
]

# --------------------------------------------------------------------------- #
# Stack & ferramentas — cada uma com o PORQUÊ (o que defender numa conversa)
# --------------------------------------------------------------------------- #
STACK = [
    {
        "name": "uv",
        "role": "Ambiente + lockfile",
        "why": "Resolve e fixa dependências num <code>uv.lock</code> reproduzível; substitui pip+venv+pip-tools com ordens de magnitude mais rápido.",
    },
    {
        "name": "Python 3.11+",
        "role": "Linguagem",
        "why": "<code>tomllib</code> nativo, type hints modernas; <code>.python-version</code> fixa 3.12 no dev e o CI testa 3.11 e 3.12.",
    },
    {
        "name": "pandas 2.x",
        "role": "Tabular",
        "why": "Manipulação dos dados de tamanho médio (listings); ciente de copy-on-write para evitar mutações acidentais.",
    },
    {
        "name": "DuckDB",
        "role": "SQL analítico embarcado",
        "why": "Agrega o <code>calendar</code> (~13M linhas) em SQL out-of-core, sem carregar tudo na memória. Ver ADR-01.",
    },
    {
        "name": "pandera",
        "role": "Data contracts",
        "why": "Valida grão, tipos, ranges e unicidade das tabelas curated de forma declarativa — falha cedo se o dado quebrar o contrato.",
    },
    {
        "name": "numpy",
        "role": "Numérico",
        "why": "Base vetorizada para os cálculos de ocupação e features.",
    },
    {
        "name": "statsmodels",
        "role": "Modelo hedônico (OLS)",
        "why": "OLS de log-preço com efeitos fixos de bairro e <code>summary()</code> interpretável (coeficientes, p-valores, R² ajustado). Num modelo que precisa ser <em>defensável</em>, a interpretabilidade vale mais que 2 pontos de erro. Ver ADR-08.",
    },
    {
        "name": "scikit-learn",
        "role": "Pré-processo + baselines",
        "why": "<code>OneHotEncoder</code> para as categóricas e os baselines triviais (mediana global, mediana por bairro) que o hedônico <strong>tem</strong> que bater para se justificar.",
    },
    {
        "name": "requests",
        "role": "Download",
        "why": "Baixa o dump com headers anti-403; isolado em <code>src/data/download.py</code>.",
    },
    {
        "name": "pytest + pytest-cov",
        "role": "Testes",
        "why": "TDD por task; cobertura sobre <code>src</code> ligada por padrão no pyproject.",
    },
    {
        "name": "ruff",
        "role": "Lint + format",
        "why": "Um binário para lint e formatação; regras <code>E,F,I,UP,B,SIM</code>, linha 100.",
    },
    {
        "name": "GitHub Actions",
        "role": "CI + Pages",
        "why": "Roda Ruff + pytest na matriz 3.11/3.12 e publica este caderno no Pages.",
    },
    {
        "name": "git hook (post-commit)",
        "role": "Doc viva",
        "why": "Regenera este HTML a cada commit localmente — o caderno nunca fica desatualizado.",
    },
]

# --------------------------------------------------------------------------- #
# ADR — Architecture Decision Records (decisão + alternativa descartada + trade-off)
# --------------------------------------------------------------------------- #
ADRS = [
    {
        "id": "ADR-01",
        "title": "Agregar o calendar (~13M linhas) em DuckDB SQL, não em pandas",
        "status": "Aceita",
        "context": "O <code>calendar.csv.gz</code> tem ~365 dias × dezenas de milhares de anúncios ≈ 13M linhas. Carregar inteiro em pandas estoura memória e é lento.",
        "decision": "Agregar a sazonalidade (preço/disponibilidade por mês) com <strong>SQL no DuckDB</strong>, lendo o arquivo direto e materializando só o resultado agregado.",
        "alternative": "<code>pandas.read_csv</code> + <code>groupby</code> com o arquivo todo na RAM.",
        "tradeoff": "DuckDB é colunar e out-of-core: processa mais que a RAM e é rápido. O custo é mais uma engine no projeto. Mudaria se o calendar fosse pequeno (&lt;1M linhas), aí pandas bastaria.",
    },
    {
        "id": "ADR-02",
        "title": "Winsorizar preço em p01/p99 em vez de remover outliers",
        "status": "Aceita",
        "context": "Há anúncios com preço absurdo (R$1 de teste, R$50k de mansão) que distorcem médias e o modelo futuro.",
        "decision": "<strong>Winsorizar</strong>: limitar valores abaixo do quantil 1% e acima do 99% aos próprios quantis (constantes <code>PRICE_WINSOR_LOWER_Q/UPPER_Q</code>).",
        "alternative": "Remover as linhas fora do intervalo; ou usar apenas log do preço; ou um teto fixo.",
        "tradeoff": "Winsorize preserva a amostra (não perde linhas) e limita a influência dos extremos. Remover perderia dados; teto fixo seria arbitrário. Mudaria se os extremos fossem erros reais a descartar, não cauda legítima.",
    },
    {
        "id": "ADR-03",
        "title": "Estimar ocupação pelo modelo “San Francisco” (review-rate)",
        "status": "Aceita (a refinar ⭐)",
        "context": "O Inside Airbnb não publica ocupação real por anúncio — só o número de reviews. Precisamos de um proxy.",
        "decision": "Modelo San Francisco: <code>bookings ≈ reviews / review_rate(0.5)</code>, <code>noites ≈ bookings × avg_stay(4)</code>, com teto <code>max_occupancy(0.70)</code>; e <strong>blend 50/50</strong> com <code>estimated_occupancy_l365d</code> quando o dump traz esse campo.",
        "alternative": "Usar só <code>estimated_occupancy_l365d</code>, ou derivar de disponibilidade do calendar.",
        "tradeoff": "O review-rate é uma heurística consagrada (estilo AirDNA), mas enviesada (nem todo hóspede avalia). O blend reduz variância juntando duas fontes fracas. É o <strong>ponto que vale refinar</strong> com os dados reais (a baseline 50/50 mantém o pipeline verde).",
    },
    {
        "id": "ADR-04",
        "title": "Local-first com uv, DuckDB e pipeline idempotente",
        "status": "Aceita",
        "context": "Projeto de portfólio sem cloud fixa; precisa rodar na máquina de qualquer pessoa e ser reexecutável sem efeitos colaterais.",
        "decision": "Tudo local: <code>uv</code> para env/lock, DuckDB e Parquet em <code>data/</code>, pipeline <strong>idempotente</strong> (re-rodar = mesmo resultado), com um <code>manifest.json</code> versionado (snapshot_date + timestamp + sha256).",
        "alternative": "Pipeline em BigQuery/cloud; ou conda; ou orquestrador pesado (Airflow).",
        "tradeoff": "Local-first é grátis, reproduzível e simples de demonstrar. Não escala para TB nem agendamento — mas não é o caso. Mudaria com volume/orquestração recorrentes.",
    },
    {
        "id": "ADR-05",
        "title": "Validar as tabelas curated com contratos pandera",
        "status": "Aceita",
        "context": "Os dados vêm sujos e externos; sem validação, um schema quebrado vaza silenciosamente para o modelo.",
        "decision": "Definir <strong>schemas pandera</strong> para as 3 tabelas curated: não-nulo onde exigido, ranges plausíveis, unicidade da chave e <strong>grão</strong> explícito (1 linha = o quê).",
        "alternative": "<code>assert</code>s manuais espalhados, ou Great Expectations.",
        "tradeoff": "pandera é leve, declarativo e integra com pandas. GE é mais completo, porém pesado para o tamanho do projeto. Os asserts manuais não documentam o contrato.",
    },
    {
        "id": "ADR-06",
        "title": "Ancorar <code>/data/</code> no .gitignore para não esconder <code>src/data/</code>",
        "status": "Aceita",
        "context": "O padrão original <code>data/</code> (sem barra inicial) é “flutuante”: casa com <em>qualquer</em> diretório <code>data/</code> em qualquer profundidade — inclusive o pacote Python <code>src/data/</code>, que sumiria do git.",
        "decision": "Ancorar à raiz do repo: <code>/data/</code>. Assim ignora só os dados na raiz, não o código.",
        "alternative": "Manter flutuante e adicionar uma exceção <code>!src/data/</code>.",
        "tradeoff": "A âncora é mais clara e menos frágil que uma exceção. Princípio geral: padrões de gitignore para diretórios específicos devem ser ancorados. (Bug pego antes do primeiro commit de código.)",
    },
    {
        "id": "ADR-07",
        "title": "Este caderno é um artefato gerado (source ≠ artifact)",
        "status": "Aceita",
        "context": "O HTML muda a cada commit. Versioná-lo geraria diffs enormes e ruidosos a cada alteração.",
        "decision": "Versionar o <strong>gerador</strong> (<code>scripts/</code>) e o <strong>conteúdo curado</strong>; o <code>docs/index.html</code> é <strong>derivado</strong> — fica no <code>.gitignore</code> e é regenerado pelo hook <code>post-commit</code> e pelo CI (Pages).",
        "alternative": "Commitar o HTML junto com cada mudança.",
        "tradeoff": "Não commitar gerados mantém o histórico limpo e o repo enxuto; o preço é que um clone novo só tem o HTML após rodar o gerador (o hook resolve no 1º commit).",
    },
    {
        "id": "ADR-08",
        "title": "Re-escopo: de maximizador de RevPAN para <em>advisor de posicionamento</em>",
        "status": "Aceita (vira a Fase 2)",
        "context": "O plano original da Fase 2 era um recomendador que escolhe o preço que <strong>maximiza RevPAN</strong>. A EDA da Fase 2 (confirmada por 5 verificadores adversariais e reproduzida de forma determinística) mostrou que esse alvo é <strong>não-identificável</strong> neste snapshot: (1) <code>revenue ≈ price × occupancy</code> em <strong>73%</strong> das linhas → RevPAN é circular; (2) <code>corr(occupancy, reviews_ltm)=0,957</code> → a “ocupação” é uma estimativa de reviews, não reservas observadas, e 26% com zero reviews recebem ocupação 0; (3) controlando reviews, o β de preço→ocupação colapsa <strong>−0,086 → −0,008</strong> (90%) → não há curva de elasticidade para maximizar; (4) o preço é <strong>estático</strong> (o calendar não traz preço) → zero variação intra-anúncio.",
        "decision": "Abandonar o RevPAN-max e reposicionar a Fase 2 como um <strong>advisor de posicionamento de preço</strong>: dado um anúncio, dizer <em>onde</em> o preço cai em relação aos pares comparáveis e a uma estimativa hedônica, devolvendo uma <strong>faixa</strong> (não um ponto) e o caveat do proxy de ocupação. Honestidade &gt; falsa precisão.",
        "alternative": "Forçar o RevPAN-max mesmo assim (o ótimo interior cairia no teto de preço — “suba o preço para todo mundo”, um artefato, não um insight) ou buscar outro dataset com preço variável e reservas reais (fora do escopo de portfólio local-first).",
        "tradeoff": "O advisor entrega valor real e <em>defensável</em> com o dado que existe; abre mão da promessa (seseduzante, porém falsa) de um número “ótimo”. Mudaria se houvesse dados de reservas reais + variação de preço intra-anúncio.",
    },
    {
        "id": "ADR-09",
        "title": "Bloquear leakage e podar features antes do hedônico",
        "status": "Aceita",
        "context": "A matriz de features tem colunas que vazam o alvo ou desestabilizam os coeficientes: <code>estimated_occupancy/revenue_l365d</code> e <code>availability_365</code> são pós-tratamento; <code>beds</code> troca o sinal do coeficiente líquido (colinear com <code>accommodates</code>/<code>bedrooms</code>, e o VIF&lt;3 não pegou); o bairro tem 155 níveis (cauda rala).",
        "decision": "Alvo = <code>log(price)</code>. <strong>Dropar</strong> as colunas de leakage + 4 all-NULL + <code>beds</code>; colapsar <code>property_type</code> no top-8 e <code>room_type</code> Hotel(n=13)→Entire; <strong>poolar</strong> o efeito fixo de bairro (n&lt;30 → “Other”, 155→59 níveis). Guardrails: o hedônico tem que bater os baselines triviais.",
        "alternative": "Jogar tudo no modelo e confiar na regularização; ou usar o VIF como único juiz de colinearidade.",
        "tradeoff": "Podar à mão dá um modelo interpretável e estável (sinais de coeficiente que se sustentam) ao custo de algum trabalho manual e julgamento. O <code>superhost</code> ficou com coeficiente <strong>negativo</strong> — registrado como caveat, não vendido como alavanca de qualidade.",
    },
    {
        "id": "ADR-10",
        "title": "Comparáveis com <em>partial pooling</em> (shrinkage), sem corte rígido de k mínimo",
        "status": "Aceita",
        "context": "Posicionar um anúncio contra “pares” exige uma estatística de preço do grupo (bairro × tipo de quarto × faixa de capacidade). Grupos pequenos dão percentis instáveis; um corte rígido <code>k_min</code> cria um penhasco (abaixo dele, sem recomendação).",
        "decision": "<strong>Partial pooling</strong>: encolher (shrink) a estatística do grupo em direção ao pai (bairro, depois global) com peso proporcional ao tamanho da amostra — grupos grandes confiam em si, pequenos pegam emprestado força do pai. Sem penhasco de <code>k_min</code>.",
        "alternative": "Corte rígido <code>k_min</code> (descartar grupos pequenos) ou no-pooling (usar o grupo cru por menor que seja).",
        "tradeoff": "O shrinkage degrada suave em vez de quebrar, ao custo de um hiperparâmetro de força de pooling. É o padrão bayesiano/hierárquico clássico para “poucos dados por grupo”.",
    },
]

# --------------------------------------------------------------------------- #
# Glossário de domínio — os “pega-ratão” dos dados do Inside Airbnb
# --------------------------------------------------------------------------- #
GLOSSARY = [
    (
        "Inside Airbnb",
        "Projeto independente que publica snapshots abertos de <code>listings</code>, <code>calendar</code> e <code>reviews</code> por cidade.",
    ),
    (
        "snapshot_date",
        "Data do dump. Resolvida em runtime: testa datas candidatas e usa a primeira que responde HTTP 200.",
    ),
    (
        "grão (grain)",
        "O que 1 linha representa. <code>listings</code> = 1 anúncio; <code>calendar</code> = 1 (anúncio, dia); <code>seasonality</code> = 1 (anúncio, mês).",
    ),
    (
        "price (US-glyph)",
        'Preço vem como <em>texto</em> tipo <code>"$1,200.00"</code> — cifrão e vírgula de milhar — mas o valor é em <strong>BRL</strong>. Precisa virar float.',
    ),
    (
        "booleanos t/f",
        'Campos como <code>instant_bookable</code> chegam como <code>"t"</code>/<code>"f"</code>, não <code>true/false</code>.',
    ),
    (
        "host_*_rate",
        'Percentuais como <code>host_acceptance_rate</code> vêm como string <code>"95%"</code>.',
    ),
    (
        "bathrooms / bathrooms_text",
        '<code>bathrooms</code> numérico costuma vir vazio; o valor real está em <code>bathrooms_text</code> (ex.: <code>"1.5 baths"</code>).',
    ),
    (
        "neighbourhood_cleansed",
        "Bairro confiável. O <code>neighbourhood_group_cleansed</code> costuma ser todo nulo no Rio — não usar.",
    ),
    (
        "proxies de flexibilidade",
        "Sem <code>cancellation_policy</code> no dump, aproximamos flexibilidade por <code>instant_bookable</code> + <code>minimum_nights</code> + <code>host_response_time</code>/<code>acceptance_rate</code>.",
    ),
    (
        "winsorização",
        "Limitar valores extremos a um quantil (ex.: p01/p99) em vez de removê-los. Preserva a amostra.",
    ),
    (
        "occupancy proxy",
        "Estimativa de ocupação derivada de reviews (modelo San Francisco), já que o dado real não é público. Ver ADR-03.",
    ),
    (
        "idempotência",
        "Reexecutar o pipeline produz exatamente o mesmo resultado — sem duplicar nem acumular estado.",
    ),
    (
        "manifest.json",
        "Metadados versionados do snapshot processado: data, timestamp e <code>sha256</code> — rastreabilidade da origem.",
    ),
    (
        "curated",
        "Camada de dados limpa, tipada e validada, pronta para análise/modelo (em oposição à <em>raw</em>).",
    ),
    (
        "RevPAN",
        "Revenue Per Available Night = diária × ocupação. Era o alvo planejado da Fase 2, <strong>descartado</strong> por ser não-identificável neste snapshot (circular + ocupação é proxy de reviews). Ver ADR-08.",
    ),
    (
        "modelo hedônico",
        "Regressão que explica o preço pelos <em>atributos</em> do bem (quartos, capacidade, tipo, bairro). Cada coeficiente é o “preço implícito” de uma característica. Aqui: <code>log(price)</code> ~ features + efeitos fixos de bairro.",
    ),
    (
        "efeito fixo (FE) de bairro",
        "Um intercepto por bairro: absorve o nível de preço específico do local (Leblon ≠ Bangu) sem precisar de variáveis explícitas de localização. Bairros raros são poolados em “Other”.",
    ),
    (
        "partial pooling / shrinkage",
        "Estimar a estatística de um grupo pequeno <em>encolhendo-a</em> em direção ao grupo-pai, com peso pelo tamanho da amostra. Evita percentis instáveis sem descartar grupos pequenos. Ver ADR-10.",
    ),
    (
        "data leakage",
        "Quando uma feature carrega informação do alvo (ou do futuro) que não estaria disponível na hora de prever — infla a métrica e engana. Aqui: <code>estimated_occupancy/revenue_l365d</code>, <code>availability_365</code>.",
    ),
    (
        "identificabilidade",
        "Se os dados conseguem, em princípio, distinguir o efeito que você quer medir. RevPAN-max não é identificável aqui: sem variação de preço intra-anúncio e com ocupação ≈ reviews, não há curva de elasticidade a otimizar.",
    ),
    (
        "VIF",
        "Variance Inflation Factor: mede colinearidade de uma feature com as demais. VIF alto = coeficiente instável. Útil, mas não infalível — <code>beds</code> passou no VIF&lt;3 e mesmo assim trocava o sinal.",
    ),
    (
        "R² ajustado",
        "Fração da variância do (log-)preço explicada pelo modelo, penalizando nº de variáveis. O hedônico atingiu <strong>0,52</strong> e bateu a mediana por bairro (MAE 0,398 &lt; 0,511).",
    ),
    (
        "ADR (duplo sentido)",
        "Aqui <strong>ADR</strong> = <em>Architecture Decision Record</em> (registro de decisão). No domínio hoteleiro, ADR = <em>Average Daily Rate</em> (diária média) — cuidado ao ler.",
    ),
]

# --------------------------------------------------------------------------- #
# Roadmap por fase. Cada task tem `key_file` (relativo à raiz) que o gerador
# checa para marcar conclusão sozinho; tasks sem artefato de arquivo usam
# `done: True` explícito. `status` da fase: "done" | "current" | "todo".
# --------------------------------------------------------------------------- #
PHASES = [
    {
        "id": 1,
        "name": "Fase 1 — Fundação & pipeline de dados",
        "status": "done",
        "summary": (
            "Pipeline reprodutível e testado que transforma o dump cru do Inside "
            "Airbnb em 3 tabelas <em>curated</em> tipadas e validadas (pandera). "
            "Mergeada em <code>main</code> (PR #1)."
        ),
        "tasks": [
            {"n": 1, "title": "Scaffold uv + tooling (ruff, pytest)", "key_file": "pyproject.toml"},
            {
                "n": 2,
                "title": "CI — Ruff + pytest na matriz 3.11/3.12",
                "key_file": ".github/workflows/ci.yml",
            },
            {
                "n": 3,
                "title": 'Transform clean_price ("$1,200.00" → float)',
                "key_file": "src/transform/clean_price.py",
            },
            {
                "n": 4,
                "title": "Transform parse_fields (t/f, %, bathrooms_text)",
                "key_file": "src/transform/parse_fields.py",
            },
            {"n": 5, "title": "Fixtures de schema cru (conftest)", "key_file": "tests/conftest.py"},
            {
                "n": 6,
                "title": "Curated listings (raw → curated + winsorize)",
                "key_file": "src/transform/listings.py",
            },
            {
                "n": 7,
                "title": "Calendar seasonality (agregação DuckDB SQL)",
                "key_file": "src/transform/calendar.py",
            },
            {
                "n": 8,
                "title": "Occupancy estimation (modelo SF + blend) ⭐",
                "key_file": "src/transform/occupancy.py",
            },
            {"n": 9, "title": "Contratos pandera (3 tabelas)", "key_file": "src/schemas.py"},
            {
                "n": 10,
                "title": "Download (resolve snapshot + anti-403)",
                "key_file": "src/data/download.py",
            },
            {"n": 11, "title": "Ingest (csv.gz → DuckDB raw)", "key_file": "src/data/ingest.py"},
            {
                "n": 12,
                "title": "Pipeline (orquestra raw→curated + manifest)",
                "key_file": "src/pipeline.py",
            },
            {
                "n": 13,
                "title": "Smoke run real (download real, checkpoint)",
                "key_file": None,
                "done": True,
            },
        ],
    },
    {
        "id": 2,
        "name": "Fase 2 — Hedônico & advisor de posicionamento",
        "status": "done",
        "summary": (
            "Re-escopada do RevPAN-max (não-identificável, ADR-08) para um advisor "
            "de posicionamento. Modelo hedônico interpretável + comparáveis com "
            "shrinkage + recomendador de faixa. 70 testes, 95% cov, hedônico "
            "adjR²=0,52. Mergeada em <code>main</code> (PR #2)."
        ),
        "tasks": [
            {
                "n": 1,
                "title": "EDA + decisão de re-escopo (RevPAN não-identificável) ⭐",
                "key_file": None,
                "done": True,
            },
            {
                "n": 2,
                "title": "Matriz de features (log-preço, leakage bloqueado)",
                "key_file": "src/model/features.py",
            },
            {
                "n": 3,
                "title": "Hedônico OLS + FE de bairro + VIF + baselines",
                "key_file": "src/model/hedonic.py",
            },
            {
                "n": 4,
                "title": "Comparáveis (peer-price com partial pooling)",
                "key_file": "src/model/comparables.py",
            },
            {
                "n": 5,
                "title": "Contexto de demanda (sazonalidade, lower-bound)",
                "key_file": "src/model/demand_context.py",
            },
            {
                "n": 6,
                "title": "Validação honesta de ocupação (não “ground truth”)",
                "key_file": "src/model/validation.py",
            },
            {
                "n": 7,
                "title": "Recomendador de posicionamento (faixa + posição)",
                "key_file": "src/model/recommender.py",
            },
            {
                "n": 8,
                "title": "Smoke de integração nos 6 módulos (parquet real)",
                "key_file": None,
                "done": True,
            },
        ],
    },
    {
        "id": 3,
        "name": "Fase 3 — Entrega",
        "status": "current",
        "summary": (
            "Transformar pipeline + modelo nos entregáveis de portfólio: notebook "
            "EDA narrado, app Streamlit (UI fina sobre <code>src/</code>), validação "
            "contra ground-truth, README insight-first e relatório de decisão. "
            "Deploy no Streamlit Community Cloud."
        ),
        "tasks": [
            {
                "n": 1,
                "title": "predict() por-listing exposto no hedônico",
                "key_file": None,
                "done": True,
            },
            {
                "n": 2,
                "title": "Notebook EDA narrado (Restart & Run All limpo)",
                "key_file": "notebooks/eda.ipynb",
            },
            {
                "n": 3,
                "title": "App Streamlit — input + card de recomendação",
                "key_file": "app/streamlit_app.py",
            },
            {
                "n": 4,
                "title": "Validação ground-truth (narrativa do autor) ⭐",
                "key_file": "docs/ground_truth_validation.md",
            },
            {"n": 5, "title": "README insight-first (story + findings no topo)", "key_file": None},
            {
                "n": 6,
                "title": "Relatório de decisão (1–2 págs, por persona)",
                "key_file": "reports/decision_report.md",
            },
            {"n": 7, "title": "Deploy Streamlit Cloud + link no README", "key_file": None},
        ],
    },
]

# --------------------------------------------------------------------------- #
# Diário de bordo — registro incremental (entrada mais recente primeiro)
# --------------------------------------------------------------------------- #
DIARY = [
    {
        "date": "2026-06-14",
        "title": "Fase 3 começa: predict() por-anúncio fecha o contrato log↔preço",
        "body": (
            "Primeiro tijolo da Fase 3 e o único achado da auditoria que tocava "
            "modelagem: o hedônico ajusta <code>log(price)</code>, mas o app precisa "
            "de reais. <code>exp(média do log)</code> recupera a mediana, não a "
            "média — subestima por <code>exp(σ²/2)</code> (desigualdade de Jensen). "
            "Exponho <code>FittedHedonic.predict_price()</code> que devolve um ponto "
            "em <strong>espaço de preço</strong>, corrigido pelo <strong>estimador "
            "de smearing de Duan</strong> (<code>mean(exp(resíduos))</code>) — não "
            "-paramétrico, sem assumir resíduos normais (preço de aluguel é "
            "assimétrico). Testes provam que ele bate a média condicional real "
            "(dentro de 10%), tolera bairro não-visto (FE zera) e alimenta o "
            "<code>recommend_price</code> em reais — sem mistura de unidades. "
            "Descartei a fórmula normal <code>exp(σ̂²/2)</code>: mais simples, "
            "porém assume normalidade. 86 testes verdes."
        ),
    },
    {
        "date": "2026-06-14",
        "title": "Auditoria adversarial da Fase 2 + blindagem de robustez",
        "body": (
            "Antes de construir a Fase 3 em cima do modelo, rodei uma auditoria "
            "multi-dimensão (12 agentes: estatística, dados/pandas, qualidade, "
            "testes) com verificação adversarial — cada achado HIGH/CRITICAL "
            "submetido a um cético que tenta refutá-lo. Resultado tranquilizador: "
            "<strong>nenhum bug ativo</strong>; os 3 “confirmados” foram rebaixados "
            "para MEDIUM/LOW. O tema real: o código não se defendia contra os tipos "
            "e entradas <em>reais</em>. Blindei: <code>is_edge</code> nullable "
            "<code>boolean</code> (mesma classe do gotcha de ExtensionType), faixas "
            "e tamanhos nas fronteiras (<code>validation</code> exige len igual; "
            "<code>recommend_price</code> valida entradas), <code>cv=None</code> "
            "quando a fatia tem 1 linha, falha-alto se uma coluna numérica é toda "
            "NULL, e — no espírito do módulo — honestidade: cap-hit agora reportado "
            "no proxy <em>e</em> no benchmark, e a correlação vira "
            "<code>None</code> (não um NaN disfarçado de número) no cohort de "
            "ocupação estrutural-zero. Policy do recomendador saiu de literais "
            "inline para constantes em <code>config</code>. <strong>70 → 83 "
            "testes</strong>, ruff limpo. O único achado que toca modelagem — o "
            "hedônico prevê em <code>log(price)</code> e o recomendador espera "
            "reais — fica para a Fase 3 (o <code>predict()</code> exponencia com "
            "correção de smearing de Duan)."
        ),
    },
    {
        "date": "2026-06-12",
        "title": "Fase 2 entregue: advisor de posicionamento (PR #2 mergeado)",
        "body": (
            "Implementados e mergeados os 6 módulos de <code>src/model/</code>: "
            "<code>features</code> (curated→X, alvo <code>log(price)</code>, leakage "
            "bloqueado), <code>hedonic</code> (OLS + efeitos fixos de bairro + VIF + "
            "baselines triviais), <code>comparables</code> (percentil de preço dos "
            "pares com <em>partial pooling</em>), <code>demand_context</code> "
            "(sazonalidade, lower-bound), <code>validation</code> (concordância "
            "honesta de ocupação) e <code>recommender</code> (faixa + posição). "
            "<strong>70 testes, 95% cobertura, ruff limpo.</strong> O smoke de "
            "integração nos 6 módulos sobre o parquet real deu hedônico "
            "<strong>adjR²=0,52</strong>, batendo a mediana por bairro "
            "(MAE 0,398 &lt; 0,511) — e pegou dois bugs que os testes unitários "
            "com dtype numpy não viam: ExtensionType <code>boolean</code> que "
            "<code>pd.to_numeric</code> não converte, e uma feature de bairro com "
            "nome hardcoded no OneHotEncoder. Lição: sempre smoke-compor no dado real."
        ),
    },
    {
        "date": "2026-06-12",
        "title": "A virada: por que abandonei o maximizador de RevPAN",
        "body": (
            "A Fase 2 ia ser um recomendador que escolhe o preço que maximiza "
            "RevPAN. A EDA matou a ideia — e foi a melhor coisa que aconteceu no "
            "projeto. Quatro evidências (reproduzidas de forma determinística e "
            "checadas por 5 verificadores adversariais): receita = preço × ocupação "
            "em 73% das linhas (circular); ocupação tem <code>corr=0,957</code> com "
            "reviews (é proxy, não reserva observada); controlando reviews, o efeito "
            "preço→ocupação some (−0,086 → −0,008); e o preço é estático (sem "
            "variação intra-anúncio). Sem curva de elasticidade, não há o que "
            "maximizar. Re-escopei para um <strong>advisor de posicionamento</strong> "
            "honesto (faixa + caveat), registrado no ADR-08. Honestidade &gt; falsa "
            "precisão — e é uma história melhor de portfólio."
        ),
    },
    {
        "date": "2026-06-11",
        "title": "Fase 1 fechada e mergeada (PR #1)",
        "body": (
            "Pipeline raw→curated completo e testado entrou em <code>main</code>: "
            "download (resolve snapshot + anti-403), ingest para DuckDB, transforms "
            "puros, contratos pandera nas 3 tabelas e orquestração idempotente com "
            "<code>manifest.json</code> (snapshot + sha256). Smoke real: "
            "<strong>39.816 anúncios analisáveis</strong> + tabela de sazonalidade "
            "anúncio × mês × dia-da-semana, com a tendência de horizonte removida."
        ),
    },
    {
        "date": "2026-06-10",
        "title": "Scaffold commitado + caderno de bordo vivo",
        "body": (
            "Primeiro commit de código: scaffold uv (<code>pyproject.toml</code>, "
            "<code>uv.lock</code>, pacote <code>src/</code>, config tipada). Pego um "
            "bug de gitignore antes de commitar — <code>data/</code> flutuante "
            "escondia <code>src/data/</code> (ADR-06). Criado este caderno: gerador "
            "Python + conteúdo curado, HTML regenerado por hook post-commit (ADR-07)."
        ),
    },
    {
        "date": "2026-06-08",
        "title": "Design spec + planos das 3 fases aprovados",
        "body": (
            "Aprovado o business plan e a spec de design. Escritos os planos das "
            "fases 1–3 (a fase 1 detalhada em 13 tasks TDD; fases 2 e 3 em outline "
            "a expandir nos respectivos checkpoints)."
        ),
    },
]
