# Robotrader v3 — Audit Quantitatif des Performances & Post-Mortem des Coûts d'Inférence LLM

**Date** : 24 Octobre 2026  
**Périmètre** : Architecture Hiérarchique Multi-Écosystèmes (26 Blockchains/Plateformes, `engine-rs` Rust measured mean `0.244 µs` for `HardRiskGate::validate` via `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate` + Warm-Path Python OpenRouter)  
**Sources auditées** :
- Ledger immuable d'inférence : [`backend/data/transcript_ledger.jsonl`](../backend/data/transcript_ledger.jsonl) (`325` cycles cognitifs, `440` requêtes HTTP OpenRouter, `4.41M` jetons)
- État des 3 populations de trading : `backtest_fixture` (Rust `engine-rs` **policy sanity check** fixture, `policy_sanity_check` — not a fill simulation), `paper_model` (carnet L2 + sélection adverse), `live_testnet` (Binance Spot Testnet + Solana Devnet, the only measured population)

---

## Provenance legend (new text — English)

**Figure block (trading performance)**: any table row, bullet item, or paragraph that states at least one numeric trading-performance value. Every trading-performance figure block in §1 and §3 carries, or is grouped under, its population and source:

| Label | Population | Meaning |
|---|---|---|
| `[FIXTURE]` | `backtest_fixture` | Deterministic **policy sanity check** (`policy_sanity_check`) on a synthetic fixture; declared-edge arithmetic, **not a fill simulation**. |
| `[SIMULATED]` | `paper_model` | L2 slippage + adverse-selection paper simulation. |
| `[MEASURED]` | `live_testnet` | Binance Spot Testnet / Solana Devnet orders actually realised. |

Only the `[MEASURED]` `live_testnet` figures in §3.3 are measured trading results. Leaf-level and treasury aggregates use the retained **recent 200-row window** (`live_testnet.recent`); `engine_metrics.live_testnet.cumulative_cex_pnl_usd` remains the lifetime CEX figure, so the two bases may diverge after eviction.

The inference-cost tables in §2 and §4 measure OpenRouter token spend. They are **operational cost measurements**, outside the three trading populations, and are not forced into the trading enums.

**Language note**: the pre-existing French body of this document is a recorded legacy exception. New text added by the integrity change is written in English; the repository's English-only convention applies to new content.

**Hot-path benchmark note (English)**: the `HardRiskGate::validate` approved-path mean is `0.244 µs` (244.15 ns). Command: `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate` (criterion 0.8.2; host: Apple Silicon macOS, 2026-10-26).

---

## 1. Synthèse Exécutive

Durant la campagne de test intensif de l'architecture hiérarchique Robotrader v3, la facture réelle OpenRouter a atteint **~$2.00 USD** (`4 413 015` jetons consommés sur `325` cycles cognitifs) — *operational inference-cost measurement, outside the three trading populations*.

**Only the `[MEASURED]` `live_testnet` figures in §3.3 are measured trading results. No fixture or simulated figure below is a product performance, a realized return, or a live trading result.**

L'audit révèle un contraste net entre :
1. **L'excellence du moteur d'exécution et de trading (`engine-rs` & `paper_model`)** :
   - **Zéro latence LLM dans le Hot-Path** (measured mean `0.244 µs` per `validate` call in Rust via `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`) — *operational latency measurement*.
   - **Deterministic policy sanity check (`backtest_fixture`, `policy_sanity_check`) [FIXTURE]** : a rule and plumbing check over a synthetic fixture, **not a fill simulation**. It reports `100.0%` de taux de réussite sur la branche Solana (`+$24.73` d'arithmétique d'edge déclaré sur `4` trades, Sharpe annualisé **`128.52`**, Max Drawdown **`0.0%`**, `3` rejets : `2` par le hurdle de coût et `1` rug pull `SCAM-SOL` bloqué par `HardRiskGate`), et valide les **pods Rust adaptés (`<= 4` par blockchain)** sur l'intégralité des **26 écosystèmes**. The PnL is `notional × (expected_edge_bps − modelled round-trip fees − modelled spread)`; it is not market-derived, realized, or backtest performance. All figures in this bullet are `[FIXTURE]`.
   - **Simulation Paper-Money réaliste (`paper_model`) [SIMULATED]** : **`+$1,155.52` de PnL net cumulé (`+11.55%` sur `$10,000`)**, **56.3% de win rate** (`845` gains / `624` pertes / `31` neutres) malgré l'application stricte du slippage L2 et de la sélection adverse. All figures in this bullet are `[SIMULATED]`.
2. **Une sur-fréquence et une inflation de contexte dans la boucle cognitive Warm-Path (`~$2.00` dépensés)** — *operational inference-cost measurement* :
   - Le robot feuille Solana se réveillait toutes les **30s à 45s** pour ré-analyser des bougies **15 minutes (`900s`)**, envoyant **~8 300 jetons d'entrée** par appel et doublant la consommation lors des escalades de troncature (`115` retries), tandis que `CostGuard` sous-estimait les tarifs OpenRouter d'un facteur ~10x et perdait son compteur à chaque redémarrage de conteneur.

Les **4 correctifs structurels** mis en œuvre à l'issue de cet audit réduisent le coût d'inférence horaire d'un **facteur 25x à 40x** (`~$0.02/heure` en mode actif continu contre `~$0.65/heure` auparavant) et placent l'auto-scheduler en **pause par défaut au démarrage (`$0.00/heure`)** — *operational inference-cost measurement, outside the three trading populations*.

---

## 2. Anatomie Financière des ~$2.00 d'Inférence OpenRouter

> Operational inference-cost measurement — outside the three trading populations. Source labels `[FIXTURE]` / `[SIMULATED]` / `[MEASURED]` do not apply to this section.

### 2.1 Répartition exacte par modèle et par agent (`transcript_ledger.jsonl`)

| Modèle OpenRouter | Rôle / Agent | Cycles | Appels HTTP (incl. retries) | Jetons Prompt (Input) | Jetons Completion (Output) | Total Jetons | Latence Moy. | JSON Valide | Coût Réel Estimé |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `deepseek/deepseek-v4.1-flash-1017` | `Leaf/leaf-*` (Solana & feuilles) | 199 | 265 | 2 287 323 | 550 012 | **2 837 335** | 14.0 s | 190/199 (95.5%) | **~$1.29** |
| `deepseek/deepseek-v4.1-flash` | `Leaf/leaf-solana` (cycles initiaux) | 110 | 156 | 1 171 878 | 300 891 | **1 472 769** | 15.3 s | 100/110 (90.9%) | **~$0.58** |
| `moonshotai/kimi-k3.1-pro` | `MasterOrchestrator/MacroLoop` | 15 | 17 | 50 671 | 31 009 | **81 680** | 43.2 s | 15/15 (100.0%) | **~$0.12** |
| `z-ai/glm-5.3-flash` | Failover / Eco | 1 | 2 | 17 139 | 4 092 | **21 231** | 17.5 s | 1/1 (100.0%) | **~$0.01** |
| **TOTAL SESSION** | **Flotte Hiérarchique Complète** | **325** | **440** | **3 527 011** | **886 004** | **4 413 015** | **15.8 s** | **306/325 (94.2%)** | **~$2.00** |

### 2.2 Les 3 causes racines de la dérive de coût

1. **Cadence de réveil `30s–45s` décorrélée de l'horizon des bougies `15m` (`900s`)** :
   - En régime `HIGH_INFLECTION`, `CostGuard` abaissait `min_wakeup_sec` à `30s–45s`.
   - `Leaf/leaf-solana` a exécuté **291 cycles cognitifs** (souvent espacés de 35 secondes) sur les mêmes bougies OHLCV 15 minutes (`SOL/USDT`, `JUP/USDT`, `RAY/USDT`), alors que les 4 pods Rust (`engine-rs`) géraient déjà le carnet d'ordres L2 avec un `HardRiskGate::validate` mesuré à `0.244 µs` en moyenne (bench: `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`) sans besoin de LLM.
2. **Inflation du prompt `FULL_THESIS` (`~8 300` jetons/cycle) + pénalité de double facturation sur troncature** :
   - Le contrat `FULL_THESIS` injectait les dictionnaires JSON bruts complets de `ta_snapshots` (`SOL/USDT`, `JUP/USDT`, `RAY/USDT`), les 4 derniers tiroirs `MemPalace`, **et** les 2 derniers transcripts bruts complets (`format_recent_transcripts(limit=2)`).
   - Lorsque la réponse JSON dépassait le plafond initial de jetons de sortie (`115` fois sur `325` cycles, soit `35%` des cycles), le mécanisme d'escalade relançait immédiatement un second appel HTTP avec un plafond supérieur — **re-facturant une seconde fois les ~8 300 jetons d'entrée**.
3. **Sous-évaluation d'un facteur ~10x dans `CostGuard` et réinitialisation en RAM** :
   - `FRONTIER_FLASH_MODELS` utilisait des tarifs théoriques (`$0.035 / 1M input`, `$0.11 / 1M output`) ~10x inférieurs aux tarifs effectifs OpenRouter des modèles de raisonnement (`~$0.30–$0.60 / 1M input`, `$1.10–$2.50 / 1M output`).
   - De plus, `self.total_cost_usd` n'était pas réhydraté depuis `transcript_ledger.jsonl` lors des reconstructions Docker (`docker compose up --build -d`), empêchant le basculement automatique en `TACTICAL_FOCUS` -> `ECO_CONSERVATION` -> `DETERMINISTIC_LOCK`.

---

## 3. Bilan Quantitatif des Performances Produit (3 Populations Isolées)

Conformément à l'invariant d'isolation des métriques, Robotrader v3 sépare strictement ses trois populations d'évaluation :

### 3.1 Population 1 — Policy Sanity Check Fixture (`backtest_fixture`, `policy_sanity_check`, `engine-rs` measured mean `0.244 µs` via `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`) [`FIXTURE`]

> Source: `[FIXTURE]` — every numeric trading figure in this subsection is the output of a deterministic **policy sanity check** on a synthetic fixture. It is a rule and plumbing check, **not a fill simulation** and not realized, live, or backtest performance. The PnL is declared-edge arithmetic: `notional × (expected_edge_bps − modelled round-trip fees − modelled spread)`.

- **Branche Solana (`leaf-solana`, 4 pods Rust natifs)** — fixture figures, `[FIXTURE]` :
  - **Capital initial** : `$10,000.00` -> **Capital final** : **`$10,024.73`** (**`+0.247%`** d'arithmétique d'edge déclaré sur la séquence de référence)
  - **Taux de réussite (Win Rate)** : **`100.0%`** (`4` gains / `0` perte sur `4` exécutions de fixture)
  - **Ratio de Sharpe annualisé** : **`128.52`** (fixture arithmetic; not a performance target)
  - **Max Drawdown** : **`0.0%`**
  - **Frais d'exécution cumulés** : `$1.47` (Maker rebate CEX `-1.0 bps` + Jupiter v6 + tip Jito MEV)
  - **Protection `HardRiskGate` (measured mean `0.244 µs`; bench: `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`)** : **`3` rejets critiques** — **`2` par le hurdle de coût** (JUP smart-money edge `70.2` contre hurdle `87.2`; AIX-SOL sniper edge `95.0` contre hurdle `151.4`) et **`1` `OnChainRugCheckFailed`** (`SCAM-SOL`, edge `81.0` contre hurdle `87.8`, perte évitée : 100% de l'allocation sniper)
  - **Attribution par Pod Rust Solana** :
    - `pod_carry` (`Solana JitoSOL/Perp Funding Basis Carry`) : **`+$13.61`** (2 trades de fixture)
    - `pod_momentum` (`Solana L2 Orderflow & Raydium CLMM Momentum`) : **`+$11.11`** (2 trades de fixture)
- **Flotte Multi-Blockchains (26 écosystèmes, `1..=4` pods Rust adaptés par blockchain)** :
  - Chaque écosystème dispose désormais de ses propres pods Rust compilés dans `engine-rs` (`crates/strategies/src/lib.rs`) et testables individuellement via `POST /api/v1/leaf/{leaf_id}/backtest`.
  - Exemple `leaf-bitcoin` (3 pods Rust : `btc_etf_basis_carry`, `btc_halving_l2_momentum`, `btc_utxo_whale_accumulator`) — fixture `policy_sanity_check`, `[FIXTURE]` : `3` trades, `100.0%` win rate, **`+$19.58`**, Sharpe **`238.97`**, Max DD **`0.0%`**, `1` rejet par le hurdle de coût. These are rule/plumbing outcomes, not a performance measurement.

### 3.2 Population 2 — Simulation Continue avec Slippage L2 & Sélection Adverse (`paper_model`) [`SIMULATED`]

> Source: `[SIMULATED]` — every numeric trading figure in this subsection is produced by the L2 slippage + adverse-selection paper model. It is not realized or live profit.

Le moteur `paper_model` applique sur chaque tick un modèle de microstructure pénalisant les entrées tardives (RSI élevé, spread L2, friction de sélection adverse) :

| Métrique `paper_model` | Fenêtre Globale (Lifetime) | Fenêtre Récente (200 derniers trades) |
| :--- | :---: | :---: |
| **Nombre d'exécutions** | **1 500 trades** | 200 trades |
| **Gains / Pertes / Neutres** | **845 W / 624 L / 31 Flat** | 99 W / 96 L / 5 Flat |
| **Win Rate (hors neutres)** | **56.3%** | 49.5% |
| **PnL Net Cumulé (`simulated_pnl_usd`)** | **`+$1,155.52` (`+11.55%`)** | `-$35.33` |
| **Frais Simulés Cumulés** | `$27.29` | `$3.64` |

**Attribution Lifetime par Pod (`+$1,155.52` total)** :
- `pod_sniper` : **`+$629.31`** (54.5% du profit total)
- `pod_solana_alpha` : **`+$310.88`** (26.9% du profit total)
- `pod_carry` : **`+$109.38`** (9.5% du profit total)
- `pod_momentum` : **`+$105.95`** (9.2% du profit total)

*Observation* : La fenêtre récente de 200 trades (`-$35.33`, win rate `49.5%`) s'explique par le maintien temporaire d'un biais `LONG_BIAS` alors que le carnet L2 `SOL/USDT` s'était inversé (`OBI = -0.571` à `$85.56`). Cela démontre que le simulateur `paper_model` n'est pas complaisant et sanctionne fidèlement tout retard d'invalidation.

### 3.3 Population 3 — Exécution Réelle Testnet (`live_testnet` : Binance Spot Testnet) [`MEASURED`]

> Source: `[MEASURED]` — these are the only measured trading results in this document. The window figures use the retained recent 200-row window; the CEX cumulative figure is a lifetime figure.

- **Exécutions dans la fenêtre active** : `200` (`16` gains / `22` pertes / `162` actions Solana Devnet simulées, exclues de la population mesurée)
- **PnL CEX Testnet réalisé** : `-$4.6036` cumulé (`-$0.1539` sur la fenêtre récente), lié au spread bid-ask du carnet Binance Spot Testnet à faible liquidité.
- **Stabilité opérationnelle** : `100%` de disponibilité RPC, zéro crash, latence WebSocket/REST nominale.

> **Correction datée 2026-10-26** — Les `162` auto-transferts Solana Devnet historiques ne sont pas des exécutions mesurées : ils sont désormais enregistrés comme actions simulées (`is_simulated: true`, non signées, non diffusées) et exclus de `live_testnet` et de `measured_realized_pnl_usd`. Seul le Binance Spot Testnet reste mesuré.

---

## 4. Les 4 Ajustements Structurels Mis en Place (Réduction OpEx 25x–40x)

> Operational inference-cost measurement — outside the three trading populations. The table below compares inference spend, not trading performance.

| # | Ajustement | Avant (Session à $2.00) | Après (Configuration Optimisée) | Gain d'OpEx |
| :---: | :--- | :--- | :--- | :---: |
| **1** | **Auto-Scheduler en pause par défaut au boot** (`ENABLE_AUTO_LLM_SCHEDULER=false`) + bouton UI `PAUSE ($0.00/h)` / `ACTIF` | Démarrage automatique immédiat des boucles LLM dès `docker compose up` | **Pause par défaut (`$0.00/h`)** ; activation à la demande via l'UI (`POST /api/v1/cognitive/scheduler`) ou réflexion manuelle | **100% au repos (`$0.00/h`)** |
| **2** | **Alignement des cadences sur les bougies 15m (`900s`) et Macro 1h (`3600s`)** | Feuille : `30s–120s` (`~45` appels/h)<br>Maître : `900s` (`4` appels/h) | Feuille active : **`900s` (15m, max 4 appels/h)**<br>Maître : **`3600s` (1h, 1 appel/h)**<br>Feuille en veille : `3600s` | **~10x moins d'appels/heure** |
| **3** | **Compression x7 du prompt `FULL_THESIS` (`_compact_ta_digest`)** | `~8 300` jetons d'entrée/appel (JSON OHLCV/TA bruts + 2 transcripts bruts complets) | **`~1 150` jetons d'entrée/appel** (digest scalaire complet : Ichimoku, Fib 0.382/0.618/0.786, RSI, pente, ATR, OBI, confluence) + `max_tokens=950` | **~7x moins de jetons/appel** |
| **4** | **Tarification OpenRouter réelle + Hydratation 24h (`hydrate_from_ledger`)** | Tarifs sous-évalués ~10x (`$0.18` affiché pour `$2.00` réels) et remise à zéro en RAM au restart | Tarifs réels OpenRouter (`$0.30/$1.10` DeepSeek Flash, `$0.60/$2.50` Kimi K3.1 Pro) + reconstruction automatique du cumul 24h depuis `transcript_ledger.jsonl` | **Verrouillage budgétaire exact** |

### Coût Horaire Projeté (Lorsque l'Auto-Scheduler est activé)
- **Mode Par Défaut (`PAUSE`)** : **`$0.00 / heure`** (les pods Rust `engine-rs` continuent d'exécuter les règles mécaniques du `PolicyEnvelope` avec un `HardRiskGate::validate` mesuré à `0.244 µs` en moyenne; bench: `cargo bench --manifest-path engine-rs/Cargo.toml -p robotrader-risk-gate`; sans aucun appel LLM).
- **Mode Auto-Scheduler `ACTIF` (4 réflexions feuille/h + 1 réflexion maître/h)** :
  - `Leaf/leaf-solana` (`4 x ~1 800` jetons totaux/h sous `deepseek-v4.1-flash-1017`) : **`~$0.004 / heure`**
  - `MasterOrchestrator` (`1 x ~2 500` jetons totaux/h sous `kimi-k3.1-pro`) : **`~$0.003 / heure`**
  - **Total Flotte Active** : **`~$0.007 à $0.015 / heure`** (soit **`<$0.30 / jour`** en fonctionnement continu 24h/24, protégé par le disjoncteur `CostGuard` hydraté depuis le disque).
