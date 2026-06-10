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
        "desc": "Modelo hedônico interpretável + recomendador de preço/ocupação.",
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
        "Revenue Per Available Night = diária média × ocupação. Métrica-alvo do recomendador (fase 2).",
    ),
    (
        "ADR (duplo sentido)",
        "Aqui <strong>ADR</strong> = <em>Architecture Decision Record</em> (registro de decisão). No domínio hoteleiro, ADR = <em>Average Daily Rate</em> (diária média) — cuidado ao ler.",
    ),
]

# --------------------------------------------------------------------------- #
# Fase 1 — as 13 tasks. `key_file` (relativo à raiz) detecta conclusão sozinho.
# --------------------------------------------------------------------------- #
PHASE1_TASKS = [
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
    {"n": 13, "title": "Smoke run real (download real, checkpoint)", "key_file": None},
]

# --------------------------------------------------------------------------- #
# Fases futuras (resumo de roadmap)
# --------------------------------------------------------------------------- #
PHASES_FUTURE = [
    {
        "phase": "Fase 2 — Modelo & Recomendador",
        "summary": "Modelo hedônico interpretável (log-preço com efeitos fixos de bairro, statsmodels) + recomendador regras+estatística que devolve faixa de preço, ocupação esperada, RevPAN e top drivers. Inclui comparáveis e a curva preço×ocupação.",
    },
    {
        "phase": "Fase 3 — Entrega",
        "summary": "Notebook de EDA narrado, app Streamlit (UI fina sobre src/), validação contra ground-truth, README insight-first e relatório de decisão. Deploy no Streamlit Community Cloud.",
    },
]

# --------------------------------------------------------------------------- #
# Diário de bordo — registro incremental (entrada mais recente primeiro)
# --------------------------------------------------------------------------- #
DIARY = [
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
