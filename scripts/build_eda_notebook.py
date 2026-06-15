"""Build (do NOT execute) the narrated EDA notebook at notebooks/eda.ipynb.

This is a content-generation script (like generate_overview.py): it assembles a Jupyter notebook
with nbformat and writes it to disk WITHOUT running any cell. The author runs Restart & Run All and
strips outputs (nbstripout) afterwards, so this script never imports pandas/matplotlib itself — it
only emits source strings. That keeps the build step cheap and side-effect free.

Notebook design rules (mirrors the project's notebook conventions in CLAUDE.md):
  - Narrative markdown cells are PT-BR (this is the author's study "caderno"); code is English.
  - All heavy logic is IMPORTED from src/ — nothing from src.model is redefined here.
  - Imports live in the FIRST code cell only; seeds are fixed; one idea per cell.
  - The notebook must survive Restart & Run All with no hidden state.

Usage:
    uv run --extra notebook python scripts/build_eda_notebook.py
    # then render + strip outputs (the author's step, not this script's):
    uv run --extra notebook jupyter nbconvert --to notebook --execute --inplace notebooks/eda.ipynb
    uv run --extra notebook nbstripout notebooks/eda.ipynb
"""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

# Notebook target lives next to the other deliverables; the dir may not exist yet.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "eda.ipynb"


# ---------------------------------------------------------------------------
# Cell 0 — imports + seeds + config. The ONLY place imports/config live, so the
# notebook survives Restart & Run All with no hidden state (CLAUDE.md rule).
# ---------------------------------------------------------------------------
CELL_IMPORTS = """\
# Imports, seeds, and config — the ONLY setup cell. Everything below depends on this.
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Heavy logic is IMPORTED from src/, never redefined in the notebook.
from src.config import (
    CURATED_DIR,
    PRICE_WINSOR_LOWER_Q,
    PRICE_WINSOR_UPPER_Q,
)
from src.model.service import HostInput, fit_advisor, recommend

# Reproducibility: fix seeds so any sampling/jitter is deterministic across runs.
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

pd.set_option("display.max_columns", 40)
pd.set_option("display.width", 120)
plt.rcParams["figure.figsize"] = (9, 5)
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3
"""


# ---------------------------------------------------------------------------
# 1. Intro
# ---------------------------------------------------------------------------
MD_INTRO = """\
# Rio Airbnb Pricing Lab — EDA narrado

Este caderno é a narrativa de exploração (EDA) por trás do **advisor de posicionamento de preço**
para anfitriões de Airbnb no Rio de Janeiro. Ele acompanha — em ordem — como o mercado se parece,
por que o objetivo original mudou, e como a recomendação final é construída de forma **honesta**.

**Snapshot:** `2026-03-30` (Inside Airbnb, Rio de Janeiro), com **n = 39.816 anúncios**.
Grão da base de anúncios: **1 linha = 1 anúncio (listing)**.

**O pivô (importante).** O projeto começou mirando um **maximizador de RevPAN** (receita por
noite disponível). Esse objetivo se mostrou **não-identificável** com este snapshot único: a proxy
de ocupação é derivada de reviews, e RevPAN = preço × ocupação vira circular quando a ocupação não é
observada de forma independente do preço. Então o projeto **virou um advisor de posicionamento**:
em vez de prometer "o preço que maximiza receita", ele responde *"dado o seu anúncio, onde o seu
preço se posiciona frente aos comparáveis, e qual faixa é defensável?"* — sempre com uma **faixa**,
nunca um número único garantido.

Toda a lógica pesada (modelo hedônico, comparáveis, contexto sazonal, recomendação) vive em `src/`
e é **importada**, nunca reescrita aqui. Este caderno só carrega dados curados e conta a história.
"""

CELL_INTRO = """\
# Load the curated market (grain: 1 row = 1 listing). Heavy work stays in src/; we just read here.
listings = pd.read_parquet(CURATED_DIR / "listings.parquet")

print(f"listings: {listings.shape[0]:,} rows x {listings.shape[1]} cols")
print("snapshot under study: 2026-03-30")
print("\\nroom_type breakdown:")
print(listings["room_type"].value_counts())
"""


# ---------------------------------------------------------------------------
# 2. Shape of the market: price distribution + occupancy proxy
# ---------------------------------------------------------------------------
MD_MARKET_SHAPE = """\
## 2. A forma do mercado: distribuição de preço e proxy de ocupação

Antes de qualquer modelo, olhamos a **forma do preço**. Preço de Airbnb é fortemente assimétrico à
direita (cauda longa de imóveis de luxo) e tem ruído de digitação nos extremos. Por isso reportamos
a distribuição **winsorizada a 1%/99%** (`PRICE_WINSOR_LOWER_Q` / `PRICE_WINSOR_UPPER_Q`): cortamos
os extremos só para *visualizar a massa central sem distorção*, não para apagar dados.

Números reais (verificados): **mediana = 500 BRL**, IQR **[330, 827]**.

**Grão explícito:** cada linha de `listings` é **1 anúncio**; cada linha de `occupancy` é **1 anúncio**
(proxy de ocupação estimada, derivada de reviews — não é booking observado). Essa proxy é a razão de
todo o cuidado de honestidade adiante.
"""

CELL_MARKET_SHAPE = """\
# Winsorize at 1/99 ONLY for the histogram view (config-driven), not to mutate the data.
lo, hi = listings["price"].quantile([PRICE_WINSOR_LOWER_Q, PRICE_WINSOR_UPPER_Q])
price_view = listings["price"].clip(lower=lo, upper=hi)

median_price = listings["price"].median()
q1, q3 = listings["price"].quantile([0.25, 0.75])
print(f"price BRL -> median {median_price:,.0f} | IQR [{q1:,.0f}, {q3:,.0f}]")
print(f"winsor clip window (1/99): [{lo:,.0f}, {hi:,.0f}] BRL")

fig, ax = plt.subplots()
ax.hist(price_view, bins=60, color="#2a6f97", edgecolor="white", linewidth=0.4)
ax.axvline(median_price, color="#d62828", linestyle="--", linewidth=1.5,
           label=f"mediana = {median_price:,.0f} BRL")
ax.set_title("Distribuicao de preco por noite (winsorizada 1/99) — n=39.816 anuncios")
ax.set_xlabel("Preco por noite (BRL)")
ax.set_ylabel("Numero de anuncios")
ax.legend()
plt.show()
"""

CELL_OCCUPANCY = """\
# Occupancy proxy (grain: 1 row = 1 listing). Reviews-driven ESTIMATE, not observed bookings.
occupancy = pd.read_parquet(CURATED_DIR / "occupancy.parquet")
print(f"occupancy: {occupancy.shape[0]:,} rows x {occupancy.shape[1]} cols (1 row = 1 listing)")
print(occupancy["occupancy_est"].describe()[["mean", "50%", "max"]])
print("\\nCAVEAT: occupancy_est is a reviews-based proxy capped at 0.70 — NOT measured occupancy.")
"""


# ---------------------------------------------------------------------------
# 3. Price map by neighbourhood
# ---------------------------------------------------------------------------
MD_NEIGHBOURHOOD = """\
## 3. Mapa de preço por bairro

O bairro é o eixo geográfico que mais move o preço no Rio. Abaixo, o **preço mediano** dos ~15
bairros com mais anúncios (mediana é robusta à cauda de luxo, ao contrário da média). Copacabana
domina o volume (12.455 anúncios), seguida de Ipanema, Barra da Tijuca, Centro, Recreio e Botafogo.
A leitura útil não é só "qual bairro é caro", mas **a dispersão entre bairros** — é isso que o
modelo hedônico vai capturar como efeito fixo de bairro.
"""

CELL_NEIGHBOURHOOD = """\
# Median price for the ~15 highest-volume neighbourhoods. Median resists the luxury tail.
top_n = 15
top_neigh = listings["neighbourhood"].value_counts().head(top_n).index
by_neigh = (
    listings[listings["neighbourhood"].isin(top_neigh)]
    .groupby("neighbourhood")["price"]
    .median()
    .sort_values()
)

fig, ax = plt.subplots(figsize=(9, 7))
ax.barh(by_neigh.index, by_neigh.values, color="#3a7d44", edgecolor="white", linewidth=0.4)
ax.set_title(f"Preco mediano por bairro — top {top_n} por volume de anuncios")
ax.set_xlabel("Preco mediano por noite (BRL)")
ax.set_ylabel("Bairro")
for y, v in enumerate(by_neigh.values):
    ax.text(v, y, f" {v:,.0f}", va="center", fontsize=8)
plt.show()
"""


# ---------------------------------------------------------------------------
# 4. Seasonality
# ---------------------------------------------------------------------------
MD_SEASONALITY = """\
## 4. Sazonalidade: quando a demanda aperta

O calendário sazonal é **detrended por horizonte** (`calendar_seasonality_detrended.parquet`,
grão: **1 linha = 1 data**). A coluna `event_uplift` mede o quanto a indisponibilidade sobe acima da
linha de base esperada para aquele horizonte — um indicador de demanda, não um modulador de preço.

Dois cuidados não-negociáveis:

1. **`is_edge` filtrado.** Datas muito próximas do snapshot são artefatos (uplift espúrio de até
   +0,22) e são descartadas — exatamente como o `seasonal_context` em `src/` faz.
2. **Magnitudes são LIMITE INFERIOR.** Picos de horizonte longo (Réveillon, Carnaval) saturam no
   **teto 0,699**, então o prêmio real é *maior* do que o gráfico mostra. Um pull multi-snapshot
   no futuro de-saturaria isso (caminho para um modelo sazonal v2).

Os picos datados que importam: **Réveillon** (virada do ano) e **Carnaval**.
"""

CELL_SEASONALITY = """\
# Seasonality (grain: 1 row = 1 date). Filter is_edge artifacts exactly like src/ does.
detrended = pd.read_parquet(CURATED_DIR / "calendar_seasonality_detrended.parquet")
clean = detrended.loc[~detrended["is_edge"].fillna(False).astype(bool)].copy()
clean = clean.sort_values("date")
print(f"detrended calendar: {len(detrended)} dates | after is_edge filter: {len(clean)} dates")

# Mark the two dated peaks the demand context surfaces (Reveillon / Carnaval windows).
def _in_window(dates, lo, hi):
    md = dates.dt.month * 100 + dates.dt.day
    lo_ord, hi_ord = lo[0] * 100 + lo[1], hi[0] * 100 + hi[1]
    return (md >= lo_ord) | (md <= hi_ord) if lo[0] > hi[0] else (md >= lo_ord) & (md <= hi_ord)

reveillon = clean[_in_window(clean["date"], (12, 28), (1, 2))]
carnaval = clean[_in_window(clean["date"], (2, 6), (2, 12))]

fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(clean["date"], clean["event_uplift"], color="#5a189a", linewidth=1.0, label="event_uplift")
ax.axhline(0.699, color="#adb5bd", linestyle=":", linewidth=1.2, label="teto de saturacao 0.699")
ax.scatter(reveillon["date"], reveillon["event_uplift"], color="#d62828", s=28, zorder=5,
           label="Reveillon")
ax.scatter(carnaval["date"], carnaval["event_uplift"], color="#f77f00", s=28, zorder=5,
           label="Carnaval")
ax.set_title("Sazonalidade detrended — event_uplift e LIMITE INFERIOR (picos saturam em 0.699)")
ax.set_xlabel("Data")
ax.set_ylabel("event_uplift (limite inferior)")
ax.legend(loc="upper left", fontsize=8)
plt.show()
"""


# ---------------------------------------------------------------------------
# 5. Hedonic story
# ---------------------------------------------------------------------------
MD_HEDONIC = """\
## 5. A história hedônica: o que move o preço (e o que NÃO move)

Ajustamos o modelo hedônico **uma única vez** com `fit_advisor(listings)` (regressão sobre o log do
preço) e reusamos. Os coeficientes vivem em `advisor.coefs`; o R² ajustado vive em `advisor.adj_r2`.

Leitura: num modelo log-preço, um coeficiente de `+x` significa aproximadamente **+x·100%** no
preço. Os maiores drivers positivos são `bathrooms_num` (+0,142), `bedrooms` (+0,130) e
`accommodates` (+0,065); `no_review_history` (+0,300) reflete anúncios novos sem histórico.

**Destaque crítico de honestidade:** `host_is_superhost` tem coeficiente **NEGATIVO (-0,107)**.
Ou seja, no Rio deste snapshot, ser Superhost está associado a preços *menores* (provavelmente
porque Superhosts competem em ocupação, não em preço). Isso é um **caveat**, não uma alavanca: o
advisor **nunca** vende "vire Superhost para cobrar mais".

**adj_R² = 0,52**, reportado honestamente. O modelo explica ~metade da variância de preço — bom
para posicionar, **insuficiente** para prometer um preço exato. É por isso que a recomendação final
faz um **blend 50/50 entre modelo e mercado** (peers), em vez de confiar só no modelo.
"""

CELL_HEDONIC = """\
# Fit the hedonic model ONCE (fit_advisor) and reuse. adj_r2 and coefs come straight from src/.
advisor = fit_advisor(listings)
print(f"hedonic adj_R2 = {advisor.adj_r2:.2f} (~half the price variance — position, not predict)")

# Top drivers by absolute effect on log-price. Sign matters: superhost is NEGATIVE.
top_drivers = (
    advisor.coefs["effect"].astype(float)
    .reindex(advisor.coefs["effect"].astype(float).abs().sort_values(ascending=False).index)
    .head(12)
    .sort_values()
)

colors = ["#d62828" if v < 0 else "#2a6f97" for v in top_drivers.values]
fig, ax = plt.subplots(figsize=(9, 7))
ax.barh(top_drivers.index.astype(str), top_drivers.values, color=colors,
        edgecolor="white", linewidth=0.4)
ax.axvline(0, color="black", linewidth=0.8)
ax.set_title("Drivers hedonicos (efeito no log-preco) — vermelho = NEGATIVO")
ax.set_xlabel("Coeficiente (≈ variacao proporcional no preco)")
plt.show()

# Make the honesty point explicit in output, not just prose.
sh = advisor.coefs["effect"].astype(float)
if "host_is_superhost" in sh.index:
    coef = sh["host_is_superhost"]
    print(f"host_is_superhost coef = {coef:+.3f}  (NEGATIVE: caveat, not a lever)")
"""


# ---------------------------------------------------------------------------
# 6. The re-scope story (markdown only)
# ---------------------------------------------------------------------------
MD_RESCOPE = """\
## 6. Por que não um maximizador de RevPAN? (a história do re-scope)

O objetivo original era **maximizar RevPAN** = preço × ocupação. Três problemas tornaram esse alvo
**não-identificável** com este snapshot único:

1. **Ocupação ≈ reviews.** A proxy de ocupação é derivada do volume de reviews (modelo San
   Francisco do Inside Airbnb). Não é booking observado — é uma *estimativa* já correlacionada com
   popularidade e tempo de anúncio.
2. **Sem variação de preço observada.** Cada anúncio aparece com **um único preço** no snapshot.
   Sem variação de preço *dentro do mesmo anúncio*, não há como estimar a curva de demanda
   (elasticidade) que um maximizador de receita exigiria.
3. **Circularidade.** RevPAN = preço × ocupação, e a ocupação que temos é função de reviews, que por
   sua vez correlacionam com preço e maturidade. "Otimizar" RevPAN aqui seria otimizar um número que
   em parte já contém o próprio preço — um alvo que se morde.

Conclusão honesta: com **um snapshot e sem experimento de preço**, o melhor produto defensável não é
"o preço que maximiza receita", mas **"onde o seu preço se posiciona e qual faixa é defensável"**.
Daí o advisor de posicionamento. (Detalhe na memória do projeto: `phase2-positioning-advisor`.)
"""


# ---------------------------------------------------------------------------
# 7. Recommendation example
# ---------------------------------------------------------------------------
MD_RECOMMEND = """\
## 7. Exemplo de recomendação: uma persona de ponta a ponta

Agora juntamos tudo: para uma persona (**Copacabana, imóvel inteiro, 2 pessoas**), chamamos
`recommend(advisor, inp, detrended)` e mostramos o resultado **honesto**:

- uma **faixa** (`low`, `high`) em torno de uma âncora — nunca um número único garantido;
- o **posicionamento** frente aos peers (`position_label`, `price_percentile`);
- as **flags de honestidade** (`neighbourhood_in_model`, `has_peer_signal`);
- e os **caveats** explícitos (a proxy de ocupação é a estrela aqui).

Referência real para esta persona: âncora ≈ **482 BRL**, faixa **[360, 604]**, posição **"in line"**,
com **~1.882 peers** comparáveis.
"""

CELL_RECOMMEND = """\
# Run the SAME tested entry point the app uses. No business logic in the notebook.
persona = HostInput(
    neighbourhood="Copacabana",
    room_type="Entire home/apt",
    property_type="Entire rental unit",
    accommodates=2,
    bedrooms=1.0,
    bathrooms_num=1.0,
    min_nights=2,
    host_is_superhost=False,
    number_of_reviews=20,
    current_price=None,  # None -> percentile falls back to the estimate (honest, no fake anchor)
)
advice = recommend(advisor, persona, detrended)
rec = advice.recommendation

print("PERSONA: Copacabana | Entire home/apt | 2 pessoas")
print("-" * 60)
print(f"faixa recomendada : [{rec.low:,.0f}, {rec.high:,.0f}] BRL   (ancora {rec.anchor:,.0f})")
print(f"posicionamento    : {rec.position_label}  (percentil {rec.price_percentile:.0%})")
print(f"peers efetivos    : {advice.peer.n_effective:,}  | tier {advice.peer.tier_used}")
print()
print(f"bairro no modelo? : {advice.neighbourhood_in_model}")
print(f"sinal de peers?   : {advice.has_peer_signal}")
print(f"demanda           : {rec.demand_note}")
print("\\ncaveats:")
for c in rec.caveats:
    print(f"  - {c}")
"""

CELL_RECOMMEND_HONESTY = """\
# Honesty guardrails made executable: never invent a percentile, always flag a baseline estimate.
if not advice.has_peer_signal:
    print("Sem peers comparaveis suficientes — NAO mostrar um percentil falso de 0.5.")
else:
    print(f"OK: {advice.peer.n_effective:,} peers sustentam percentil {rec.price_percentile:.0%}.")

if not advice.neighbourhood_in_model:
    print("AVISO: bairro nao modelado individualmente — estimativa pela baseline.")
else:
    print("OK: bairro e um efeito fixo modelado (Copacabana).")
"""


# ---------------------------------------------------------------------------
# 8. Conclusion + honest limitations
# ---------------------------------------------------------------------------
MD_CONCLUSION = """\
## 8. Conclusão e limitações honestas

**O que o advisor faz bem:** posiciona um anúncio frente a comparáveis de forma transparente, com
uma faixa defensável, drivers explicáveis e flags de incerteza. O blend 50/50 modelo+mercado existe
exatamente porque nenhum dos dois isolado é decisivo (adj_R² = 0,52).

**Limitações que NÃO escondemos:**

- **Snapshot único (2026-03-30).** Sem série temporal, sem elasticidade de preço, sem RevPAN
  identificável — daí o re-scope para posicionamento.
- **Ocupação é proxy de reviews**, não booking observado. Toda leitura de demanda carrega esse
  caveat; a faixa é *posicionamento de preço*, não receita garantida.
- **Sazonalidade é limite inferior.** Réveillon e Carnaval saturam no teto 0,699; o prêmio real é
  maior. Multi-snapshot futuro de-satura.
- **Superhost é caveat, não alavanca.** Coeficiente negativo (-0,107); nunca vender "vire Superhost
  para cobrar mais".
- **adj_R² = 0,52.** Metade da variância fica de fora. O produto **nunca** promete um preço exato —
  sempre uma faixa, sempre com os caveats acima.

A honestidade não é um adendo deste projeto; é o ponto dele.
"""


def build_notebook() -> nbformat.NotebookNode:
    """Assemble the ordered cell list into an nbformat notebook (no execution)."""
    cells = [
        new_markdown_cell(MD_INTRO),
        new_code_cell(CELL_IMPORTS),
        new_code_cell(CELL_INTRO),
        new_markdown_cell(MD_MARKET_SHAPE),
        new_code_cell(CELL_MARKET_SHAPE),
        new_code_cell(CELL_OCCUPANCY),
        new_markdown_cell(MD_NEIGHBOURHOOD),
        new_code_cell(CELL_NEIGHBOURHOOD),
        new_markdown_cell(MD_SEASONALITY),
        new_code_cell(CELL_SEASONALITY),
        new_markdown_cell(MD_HEDONIC),
        new_code_cell(CELL_HEDONIC),
        new_markdown_cell(MD_RESCOPE),
        new_markdown_cell(MD_RECOMMEND),
        new_code_cell(CELL_RECOMMEND),
        new_code_cell(CELL_RECOMMEND_HONESTY),
        new_markdown_cell(MD_CONCLUSION),
    ]
    nb = new_notebook(cells=cells)
    nb.metadata.update(
        {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        }
    )
    return nb


def main() -> None:
    """Write the notebook to notebooks/eda.ipynb, creating the directory if absent."""
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    nb = build_notebook()
    nbformat.write(nb, NOTEBOOK_PATH)
    print(
        f"Wrote {NOTEBOOK_PATH} ({len(nb.cells)} cells). Not executed — run + strip outputs next."
    )


if __name__ == "__main__":
    main()
