# Phase 3 — Delivery (EDA · Dashboard · Validation · README) — Plan Outline

> ⚠️ **SUPERSEDED (2026-06-14)** by `2026-06-14-phase3-delivery.md`. This outline predates the
> Phase-2 re-scope and still assumes a RevPAN-maximizer ("RevPAN frontier", "expected RevPAN"),
> which Phase 2 dropped as unidentifiable. Kept for history only — follow the new plan.

> **STATUS: OUTLINE.** Expanded into a full step-by-step plan **at the Phase-3 checkpoint**, once
> the model + recommender (Phase 2) exist and the real findings are known. The narrative
> deliverables (insight-first README, decision report, ground-truth validation) are written
> *from actual results* — drafting their prose now would be fiction.
>
> **For agentic workers (after expansion):** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Turn the tested pipeline + model into the portfolio deliverables: a narrated EDA notebook, a live Streamlit dashboard with the recommender, the ground-truth validation section, an insight-first README, and a 1–2 page decision report.

**Architecture:** The Streamlit app is a **thin UI** over `src/transform` + `src/model` — zero business logic in the app layer (spec §4 contract). The notebook is exploration/narrative only; any reusable logic already lives in `src/`. Honesty is built into the UI: the recommender shows a *range* + the occupancy-proxy caveat.

**Tech Stack (additions):** Streamlit + Plotly (interactive dashboard) · matplotlib/seaborn (notebook figures) · jupyter/nbconvert (rendered notebook) · Streamlit Community Cloud (public deploy, like the Eldorado project).

---

## File Structure (planned)

```
app/streamlit_app.py            # thin UI: filters + recommender + honesty caveats
app/components/                  # small render helpers (charts, recommendation card)
notebooks/eda.ipynb             # narrated EDA (Restart & Run All clean, seeds fixed)
reports/decision_report.md      # 1-2 pages: per-persona actionable translations
README.md                       # rewritten insight-first (story + findings on top)
.streamlit/config.toml          # theme
requirements-app.txt            # OR streamlit deploy deps pinned for the cloud
docs/ground_truth_validation.md # author playbook vs Rio data drivers (spec §7)
```

---

## Task Skeleton (to be expanded with full steps at checkpoint)

1. **EDA notebook** — narrative: market shape, neighbourhood price map, seasonality curve (Réveillon/Carnaval spikes), hedonic coefficient story, RevPAN frontier. Enforce Restart & Run All clean, seeds fixed, no hidden state, outputs stripped before commit (nbstripout). Heavy logic imported from `src/`, not redefined.
2. **Streamlit app — inputs** — host input form (neighbourhood, room_type, capacity, superhost, flexibility proxies, season). Wires to `src/model/recommender`.
3. **Streamlit app — output card** — suggested price *range*, expected occupancy, expected RevPAN, top drivers, and the **occupancy-proxy caveat** rendered inline (no false precision — spec §6).
4. **Streamlit app — explore tab** — filterable market views (Plotly): price by neighbourhood, seasonality, occupancy benchmark (own proxy vs `estimated_occupancy_l365d` when present).
5. **Ground-truth validation** (spec §7) ⭐ **AUTHOR NARRATIVE** — confront the author's real Superhost playbook (fast response, flexible policy, own photos, seasonal pricing) with the drivers that emerge from Rio data; framed honestly (operated market was Pirenópolis-GO, so it's *transferable principles vs Rio market*, not "my own data").
6. **Insight-first README** — story + key findings on top, "how to run" below; badges (CI, license); link to live dashboard + rendered notebook (nbviewer).
7. **Decision report** — per-persona ("if you host in Copacabana, do X"), 1–2 pages.
8. **Deploy** — Streamlit Community Cloud; verify the live app loads and the recommender works end-to-end; add the link to README.
9. **Final pass** — full test suite + Ruff green; notebook Restart & Run All; visual check of the deployed app.

---

## Open questions to resolve at checkpoint

- **Deploy data strategy:** Streamlit Cloud has no persistent disk — either run the pipeline at app startup (slow cold start) or commit a small pre-computed curated parquet (e.g. listings + seasonality, no 13M-row calendar) as a release artifact. Decide based on curated file sizes from Phase 1.
- **Notebook output policy:** nbstripout vs jupytext paired script (keep git clean).
- **README findings:** written from the actual top drivers + RevPAN numbers produced in Phase 2.

## Spec coverage targeted by Phase 3
§5 (recommender UI + honesty) · §7 (ground-truth validation) · §8 (all deliverables: README, notebook, live dashboard, decision report) · §10 (proxy caveat surfaced in UI/README).
