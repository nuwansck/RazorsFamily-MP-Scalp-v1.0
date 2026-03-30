# RF MP Scalp v2.0 — Technical Specification & Operations Wiki

**Bot Name:** RF MP Scalp v2.0
**Instruments:** GBP/USD, EUR/USD, GBP/JPY, USD/JPY
**Exchange:** OANDA (practice & live)
**Deployment:** Railway (PaaS)
**Signal Timeframe:** M5 (5-minute candles)
**Cycle Interval:** Every 5 minutes
**Status:** Demo mode (`OANDA_DEMO=true`)

---

## 1. Purpose & Scope

RF MP Scalp v2.0 is a fully automated 5-minute scalping bot for four forex pairs.
It uses a three-layer signal engine (EMA crossover + ORB + CPR bias) scored 0–6/6,
with minimum thresholds per session. All configuration lives in `settings.json`.

---

## 2. Architecture Overview

```
scheduler.py  (APScheduler — every 5 min)
      |
      ├── run_bot_cycle()  ← called once per pair per cycle
      |       |
      |       ├── _guard_phase()    Market closed / dead zone / caps / news
      |       ├── _signal_phase()   SignalEngine.analyze() → score + direction
      |       └── _execution_phase() Margin check → spread check → place_order()
      |
      ├── send_daily_report()   04:00 SGT Mon–Fri
      ├── send_weekly_report()  Monday 08:15 SGT
      └── send_monthly_report() First Monday 08:00 SGT
```

---

## 3. Signal Engine

**File:** `signals.py` → `SignalEngine.analyze()`

Three components scored each M5 cycle:

### 3a. EMA Crossover (M5)
- EMA9 fresh cross above EMA21: **+3 pts** → `EMA Fresh Cross Up` (BUY)
- EMA9 fresh cross below EMA21: **+3 pts** → `EMA Fresh Cross Down` (SELL)
- EMA9 aligned above EMA21 (no fresh cross): **+1 pt** → `EMA Trend Up`
- EMA9 aligned below EMA21 (no fresh cross): **+1 pt** → `EMA Trend Down`

### 3b. ORB Confirmation (M15 first candle of session)
- Price beyond ORB and break is **fresh** (<60 min): **+2 pts**
- Price beyond ORB and break is **aging** (60–120 min): **+1 pt**
- ORB not formed or no break: **+0 pts**

### 3c. CPR Bias (Daily pivot)
- BUY signal and price above daily pivot: **+1 pt**
- SELL signal and price below daily pivot: **+1 pt**

**Max score: 6/6**

---

## 4. Session Schedule

All times SGT (UTC+8):

| Window | SGT | Score threshold | Trade cap |
|---|---|---|---|
| Dead zone | 04:00–07:59 | No trading | — |
| Tokyo | 08:00–15:59 | ≥ 5/6 | 10 |
| London | 16:00–20:59 | ≥ 4/6 | 10 |
| US | 21:00–23:59 | ≥ 4/6 | 10 |
| US continuation | 00:00–03:59 | ≥ 4/6 | 10 |

Market fully closed Saturday and Sunday. Monday opens at 08:00 SGT.

---

## 5. Position Sizing

Units are calculated from `position_usd` ÷ `sl_price_dist` per unit.
For JPY pairs, `pip_value_usd` corrects for the JPY denomination.

| Score | Position | Risk | Units (GBP/USD) | Units (GBP/JPY) |
|---|---|---|---|---|
| 4 | $20 partial | 1.0% of $2k | ~10,000 | ~8,500 |
| 5–6 | $30 full | 1.5% of $2k | ~15,000 | ~12,793 |

SL/TP per pair:

| Pair | SL | TP | RR | pip_value_usd |
|---|---|---|---|---|
| GBP/USD | 20p | 50p | 2.50× | 10.0 |
| EUR/USD | 20p | 38p | 1.90× | 10.0 |
| GBP/JPY | 35p | 88p | 2.51× | 6.7 |
| USD/JPY | 20p | 50p | 2.50× | 6.7 |

---

## 6. Risk Guards

Executed in order each cycle, early return on any failure:

1. **Market closed** — Saturday / Sunday / Monday pre-08:00
2. **Dead zone early exit** — 04:00–07:59 AND no open trades → zero API calls
3. **News block** — high-impact event within ±30 min
4. **News penalty** — medium event → −1 to score
5. **Loss cooldown** — consecutive losses → 30 min pause
6. **Friday cutoff** — after 23:00 SGT Friday
7. **Session check** — outside all active windows
8. **Daily loss cap** — 8 losing trades → pause until 08:00 SGT
9. **Session cap** — per-window trade limit reached
10. **Concurrent cap** — 1 trade per pair, 2 globally
11. **Margin guard** — units reduced if margin insufficient
12. **Min trade units** — reject if units < 1,000 after margin guard
13. **Spread guard** — skip if spread > limit for session

---

## 7. Telegram Alerts

All message cards defined in `telegram_templates.py`.

Alert suppression: WATCHING cards for score < `telegram_min_score_alert` (default 3) are silently skipped. Score 1–2 = noise; score 3+ sends.

### Report schedule

| Report | Time | Content |
|---|---|---|
| Daily | 04:00 SGT Mon–Fri | Session breakdown + day total + MTD |
| Weekly | Monday 08:15 SGT | Session + Pair + Setup bars |
| Monthly | First Monday 08:00 SGT | Full breakdown + verdict + recommendation |

---

## 8. Key Files

| File | Purpose |
|---|---|
| `scheduler.py` | Entry point — APScheduler, jobs, startup |
| `bot.py` | Per-pair cycle: guard → signal → execution |
| `signals.py` | EMA + ORB + CPR engine |
| `oanda_trader.py` | OANDA REST API wrapper |
| `telegram_templates.py` | All Telegram message cards |
| `reporting.py` | Daily / weekly / monthly report builders |
| `config_loader.py` | Settings loading + all defaults |
| `settings.json` | **Single source of truth for all config** |
| `database.py` | SQLite — cycle + signal + state logging |
| `reconcile_state.py` | Startup reconciliation of open trades |
| `news_filter.py` | Forex Factory news block/penalty |

---

## 9. Data Directory (`/data` on Railway volume)

| File | Purpose |
|---|---|
| `trade_history.json` | All trade records — open + closed |
| `settings.json` | Volume copy (overwritten from bundle on startup) |
| `runtime_state.json` | Last cycle status, balance |
| `ops_state_*.json` | Per-pair ops state (session, caps, alerts) |
| `score_cache_*.json` | Per-pair last signal dedup |
| `calendar_cache.json` | Cached Forex Factory events |
| `rf_scalp.db` | SQLite — cycle log, signal log |

---

## 10. Deployment

### Railway
1. Push folder to GitHub
2. New Railway project → Deploy from GitHub
3. Set environment variables (see below)
4. Add persistent volume mounted at `/data`
5. Railway builds and deploys automatically

### Environment Variables

| Variable | Required | Notes |
|---|---|---|
| `OANDA_API_KEY` | ✅ | Practice or live |
| `OANDA_ACCOUNT_ID` | ✅ | e.g. `101-003-XXXXXXX-001` |
| `OANDA_DEMO` | ✅ | `true` / `false` |
| `TELEGRAM_BOT_TOKEN` | ✅ | From @BotFather |
| `TELEGRAM_CHAT_ID` | ✅ | Your chat/channel ID |

---

## 11. Version History Summary

| Version | Key changes |
|---|---|
| v1.6.1 | Per-pair fixed pip SL/TP via `pair_sl_tp` |
| v1.7 | 1.5% risk sizing ($30/$20), JPY unit fix, min_trade_units |
| v1.7.1 | EUR/USD SL widened 15→20p (noise-stop fix) |
| v1.7.1b | Telegram alert suppression (score <3 silenced) |
| v1.8 | AtomicFX-style Telegram templates, dead zone API skip |
| v1.8.1 | EOD report 04:00 SGT, session breakdown, By Pair weekly |
| v1.9 | Correct session order in startup card |
| **v2.0** | **H1 trend filter (soft/strict mode), /export Telegram command** |
