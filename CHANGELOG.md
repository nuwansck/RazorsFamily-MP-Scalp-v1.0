# RF Scalp Bot — Changelog

---

## v1.7.1 patch — Telegram Alert Suppression

### 🔇 Feature — Suppress Low-Score WATCHING Alerts (`bot.py`, `settings.json`)

**Problem:** Every 5-minute cycle sends up to 4 Telegram messages (one per pair)
even when score is 1 or 2/6 — well below any tradeable threshold. With 4 pairs
and a 5-minute cycle, a quiet session generates 48+ useless notifications per hour.

**Fix:** New setting `telegram_min_score_alert` (default: `3`).
WATCHING alerts are silently suppressed if `score < telegram_min_score_alert`.

What is suppressed:
- Score 1/6 WATCHING cards ← always noise, never actionable
- Score 2/6 WATCHING cards ← never actionable (threshold is 4)

What always fires regardless of score:
- Score 3/6 WATCHING (one step below threshold — worth knowing)
- Trade opened / trade closed / TP / SL
- Order failed / margin protection / position size errors
- Session cap hit / daily loss cap hit
- News filter blocks
- Daily / weekly / monthly reports
- OANDA login failures

| Key | Default | Effect |
|---|---|---|
| `telegram_min_score_alert` | `3` | Suppress WATCHING for score < 3. Set `0` to restore all alerts. |

---

## v1.7.1 — 2026-03-28

### 🔴 Fix — EUR/USD SL Widened 15p → 20p (`settings.json`)

**Problem:** EUR/USD was being stopped out on M5 noise. All 3 EUR/USD losses hit
at almost exactly −21 pips — just beyond the 15-pip SL plus spread. The SL was
sitting inside normal M5 candle noise for this pair.

**Evidence from live trades:**
- Trade #1:  EUR/USD BUY → −20.9 pips → SL hit
- Trade #5:  EUR/USD BUY → −20.7 pips → SL hit
- Trade #10: EUR/USD BUY → −21.1 pips → SL hit

All three losses were caused by normal M5 fluctuation, not genuine direction
reversals. The 15-pip SL was simply too tight for EUR/USD.

**Fix:** EUR/USD `sl_pips` widened from **15 → 20** to match GBP/USD.
TP remains at 38 pips. RR adjusts from 2.53× to 1.90×.

| | Before | After |
|---|---|---|
| EUR/USD SL | 15p | **20p** |
| EUR/USD TP | 38p | 38p (unchanged) |
| EUR/USD RR | 2.53× | 1.90× |
| BE win rate | 28% | **35%** |
| Units (full $30) | ~20,000 | **~15,000** |
| $/pip | $2.00 | **$1.50** |
| SL risk | $30 | $30 (unchanged) |

Note: widening SL reduces unit count proportionally (position_usd stays $30),
so risk per trade is identical — only the pip target moves.

All other pairs unchanged. JPY pairs running with correct sizing from v1.7.

---

## v1.7.0 — 2026-03-27

### 🔴 Fix — STOP_LOSS_ON_FILL_LOSS on JPY Pairs (`signals.py`, `bot.py`)

**Root cause:** `sl_usd_rec` was being used for two conflicting purposes:
1. Unit sizing: `units = position_usd / sl_usd_rec` — correct when sl_usd_rec is $ risk per unit
2. Price placement: `sl_price = entry - sl_usd_rec` — correct only when sl_usd_rec is a price distance

For USD-quoted pairs (GBP/USD, EUR/USD) these are identical because `pip_size = pip_usd_unit`.
For JPY pairs they differ completely:
- `sl_usd_rec` for USD/JPY (fixed_pips mode) = 20 × (6.7/100,000) = **0.00134** ($ per unit)
- Correct price distance for 20 pips = 20 × 0.01 = **0.200**

`compute_sl_tp_prices` was placing SL at 159.937 − 0.00134 = 159.9357 — essentially AT the
entry price, causing OANDA to reject with `STOP_LOSS_ON_FILL_LOSS`.

**Fix:** `signals.py` fixed_pips block now stores two separate values:
- `levels["sl_usd_rec"]` — dollar risk per unit, used for unit sizing (unchanged)
- `levels["sl_price_dist"]` = sl_pips × pip_size — price distance, used for SL/TP placement

`compute_sl_usd` and `compute_tp_usd` in `bot.py` now check `sl_price_dist` / `tp_price_dist`
first, falling back to `sl_usd_rec` for pct_based mode (backward compatible).

---

### 🔴 Fix — Margin Guard Reducing to Micro-Units (`bot.py`, `settings.json`)

**Problem:** The margin guard was reducing USD/JPY from 14,925 units to 143 units because
`apply_margin_guard` uses `entry_price` (159.937) in its denominator — correct for EUR/USD
but inflates the calculation for USD/JPY. The resulting 143-unit order then failed with
`STOP_LOSS_ON_FILL_LOSS` (compounded by Bug 1 above).

**Fix:** Added `min_trade_units` setting. If the margin guard reduces units below this
threshold, the trade is rejected cleanly with a Telegram alert instead of sending a
near-worthless micro-order to OANDA.

| Key | Default | Description |
|---|---|---|
| `min_trade_units` | `1000` | Minimum units after margin adjustment. If guard reduces below this, trade is skipped and logged. |

---


### 🟢 Position Sizing — Professional 1.5% Risk Model (`settings.json`, `bot.py`, `signals.py`)

**Problem with previous sizing:** `position_full_usd: 100` meant the bot risked $100
per trade — 5% of a $2,000 account. Eight consecutive losses (the daily cap) would
wipe 40% of the account. That is too aggressive for a demo bot still being validated.

**Fix:** Switched to the professional standard of 1.5% risk per trade for full-size
signals and 1.0% for partial signals. All three places that hold these defaults are
updated so the values are fully centralised to `settings.json`.

| Setting | Old | New | Effect on $2,000 account |
|---|---|---|---|
| `position_full_usd` | 100 | **30** | ~15,000 units GBP/USD, risk $30/trade (1.5%) |
| `position_partial_usd` | 66 | **20** | ~10,000 units GBP/USD, risk $20/trade (1.0%) |
| `max_total_open_trades` | 2 | **2** | Hard cap: 2 trades open across all pairs |
| `max_concurrent_trades` | 1 | **1** | Per-pair cap: 1 trade per instrument |

**Effective unit sizes at 1.5% risk (pair-specific SL from v1.6.1):**

| Pair | Units | $/pip | SL risk | TP reward | % account |
|---|---|---|---|---|---|
| GBP/USD | ~15,000 | $1.50 | $30 (20p) | $75 (50p) | 1.5% |
| EUR/USD | ~20,000 | $2.00 | $30 (15p) | $76 (38p) | 1.5% |
| GBP/JPY | ~11,000 | $0.86 | $30 (35p) | $76 (88p) | 1.5% |
| USD/JPY | ~22,000 | $1.50 | $30 (20p) | $75 (50p) | 1.5% |

**Worst-case daily loss (8 SLs at full size):** $240 = 12% of account.
Previously this was $400 = 20%.

**EV at various win rates (GBP/USD, SL 20p, TP 50p):**

| Win Rate | EV/trade | Monthly (20 trades) |
|---|---|---|
| 30% | +$1.50 | +$30 |
| 40% | +$12.00 | +$240 |
| 50% | +$22.50 | +$450 |

**Concurrency — centrally controlled via `settings.json`:**
- `max_total_open_trades: 2` — broker-verified hard cap across all 4 pairs combined
- `max_concurrent_trades: 1` — per-pair cap (1 trade per instrument at a time)
- Both values read exclusively from `settings.json` with no hardcoded overrides

---

### 🔴 Fix — JPY Pair Unit Sizing (`signals.py`, `settings.json`)

**Problem:** GBP/JPY and USD/JPY were being sized using `position_usd / sl_price_distance`
where `sl_price_distance` is in JPY (e.g. 0.35 for 35 pips at pip_size=0.01), not USD.
This produced absurdly small positions — GBP/JPY: ~86 units, USD/JPY: ~150 units —
making those trades meaningless to overall P&L.

**Fix:** Added `pip_value_usd` to each entry in `pair_sl_tp`. This is the dollar value
of 1 pip for 1 standard lot (100,000 units). The SL distance is now calculated as:

```
sl_usd_rec = sl_pips * (pip_value_usd / 100_000)
units      = position_usd / sl_usd_rec
```

For USD pairs `pip_value_usd = 10.0`, giving `sl_usd_rec = sl_pips * 0.0001` — identical
to the old `pip_size` calculation. For JPY pairs `pip_value_usd = 6.7` (at ~150 USD/JPY),
giving correctly sized positions of ~8,500–12,800 units.

**Update `pip_value_usd` for JPY pairs** if USD/JPY moves more than 10 points from 150.
Formula: `pip_value_usd = 1000 / current_USDJPY_rate`.

---

## v1.6.1 — 2026-03-27

### 🟢 Feature — Per-Pair Fixed SL/TP Pips (`signals.py`, `settings.json`)

**Problem with the old approach:** SL and TP were calculated as a percentage of
entry price (`sl_pct = 0.20%`). This worked reasonably well but produced TP targets
of 68–98 pips that required 75–100% of the entire daily range to be travelled in one
direction — rarely achievable on a single M5 trade.

**Fix:** Added a `pair_sl_tp` block in `settings.json` that sets fixed pip values
per instrument. When present, these override the percentage calculation entirely.
The fallback to `sl_pct` / `rr_multiple` remains for any pair not in the dict.

**Why these pip values:**
- SL sized at 5× the typical M5 candle body for each pair — enough buffer to avoid
  noise-triggered stops while still being tight enough to define risk cleanly.
- TP set so the target is 58–68% of the average daily range — realistic for a single
  London or US session move rather than asking for the whole day.

| Pair | Old SL | Old TP | New SL | New TP | TP % ADR |
|---|---|---|---|---|---|
| GBP/USD | ~27p | ~68p | **20p** | **50p** | 62% |
| EUR/USD | ~23p | ~58p | **15p** | **38p** | 58% |
| GBP/JPY | ~39p | ~98p | **35p** | **88p** | 68% |
| USD/JPY | ~30p | ~75p | **20p** | **50p** | 67% |

All pairs maintain 2.5× gross RR and ~28–29% break-even win rate — the edge is
unchanged. The difference is the TP is now within a realistic single-session move.

**New `settings.json` block:**
```json
"pair_sl_tp": {
  "GBP_USD": {"sl_pips": 20, "tp_pips": 50},
  "EUR_USD": {"sl_pips": 15, "tp_pips": 38},
  "GBP_JPY": {"sl_pips": 35, "tp_pips": 88},
  "USD_JPY": {"sl_pips": 20, "tp_pips": 50}
}
```

To revert to percentage mode for any pair, remove its entry from `pair_sl_tp`.
To disable fixed pips entirely, set `"pair_sl_tp": {}`.

---

## v1.3.0 — 2026-03-26

### 🔴 Fix — WATCHING Card Showed Wrong Session Threshold (`bot.py`, `telegram_templates.py`)

**Problem:** The signal WATCHING card displayed `Score: 2/6 (threshold 5)` even
during London session (which uses threshold 4). The `_send_signal_update` closure
was defined before `_thr` was computed, so it fell back to reading the global
`signal_threshold: 4` setting instead of the session-resolved value. During Tokyo
this happened to show `5` (Tokyo's threshold), but during London it showed `4` only
by coincidence. Any session with a non-default threshold would display incorrectly.

**Fix:** `_thr` is now computed immediately after `cpr_w` — before the closure is
defined — and passed explicitly into both `_signal_payload()` and `msg_signal_update()`.
The WATCHING card will always show the threshold that is actually in effect for the
current session.

---

### 🟢 Feature — WATCHING Card Redesigned (`telegram_templates.py`)

The WATCHING card has been redesigned to match a cleaner info-card format (matching
Image 4 from user feedback), replacing the old one-liner format:

**Before:**
```
🇬🇧 LONDON [GBP/USD]
📊 BUY  Score 2/6  👀 WATCHING
Reason:  R:R 1:2.5
Next cycle in 5 min
```

**After:**
```
🇬🇧 LONDON [GBP/USD] | Watching

Bias:    BUY
Score:   2/6  (threshold 4)
Setup:   EMA Trend Up
CPR:     0.48% width
ORB:     89min (aging)

Next cycle in 5 min
```

Changes:
- `| Watching` suffix on the banner line instead of an inline icon
- `Score` shows the actual session threshold in parentheses
- `Setup` line shows the detected setup name (EMA Fresh Cross Up, EMA Trend Down, etc.)
- `ORB` status line shows age and freshness label (`fresh` / `aging` / `stale`)
- News penalty still shown when active
- Three new params added to `msg_signal_update`: `signal_threshold`, `setup`, `orb_age_min`, `orb_formed`

---

### 🟢 Feature — TP2 Reference Level in Trade Opened Alert (`telegram_templates.py`, `bot.py`, `settings.json`)

The trade opened Telegram alert now shows a TP2 reference level alongside the bot's
TP1 target. TP2 is a display-only reference — no second order is placed.

**Trade opened alert now shows:**
```
SL:   1.33749  (-0.00268 move)
TP1:  1.34687  (+0.00670 move)  ← bot target
TP2:  1.35018  (+0.01005 move)  ← 3.0×RR ref
```

TP2 is calculated as `entry ± (sl_distance × tp2_rr_reference)`. The multiplier
defaults to `3.0` and is fully configurable:

| Key | Default | Description |
|-----|---------|-------------|
| `tp2_rr_reference` | `3.0` | R:R multiplier for the TP2 reference level displayed in trade alerts. Set to `0` to hide. |

---

### 🟢 Feature — Instant SL Flag in Daily Report (`reporting.py`, `telegram_templates.py`)

The daily performance report now flags trades that hit their stop loss within
5 minutes of being opened — a signal that the entry caught a bad fill or an
immediate reversal.

**Daily report now includes (when applicable):**
```
  ⚡ Instant SL: 1 trade(s) closed ≤5 min
```

Detection: any losing trade where `closed_at_sgt - timestamp_sgt ≤ 5 minutes`.
The count is added to the `day_stats` dict as `instant_sl_count` and displayed
only when > 0, so clean days are unaffected.

---



### 🔴 Fix — Startup Telegram Still Showed Old Session Schedule (`telegram_templates.py`, `scheduler.py`)

**Problem:** The `msg_startup` function had its session schedule hardcoded with the
v1.1 layout (dead zone 01:00–15:59, no Tokyo). The v1.2.0 trading logic was fully
correct — sessions, thresholds, and ORBs all worked — but the startup Telegram
message displayed stale information on every deploy, making it impossible to visually
confirm the Tokyo session was active.

**Root cause:** `msg_startup()` accepted only `max_trades_london`, `max_trades_us`,
and `max_losing_day`. It had no parameters for Tokyo hours, dead zone bounds, US
session bounds, or the global trade cap. The session schedule rows were hardcoded
strings rather than being built from settings.

**Fix:** `msg_startup()` signature extended with 11 new parameters covering all
configurable session bounds. The startup Telegram now shows:

```
Session schedule (SGT)
  🗽 00:00–03:59  US cont.     cap 10
  💤 04:00–07:59  Dead zone
  🗼 08:00–15:59  Tokyo        cap 10
  🇬🇧 16:00–20:59  London       cap 10
  🗽 21:00–23:59  US session   cap 10

Window:    16:00 → 03:59 SGT (Tokyo + London + US)
Global open cap: 2 trades across all pairs
```

All values are read from `settings.json` at startup — changing session hours or
caps in settings will automatically update the Telegram message on next deploy.

The `scheduler.py` call site updated to pass all 11 new parameters.

**Also fixed in this patch:**
- `msg_session_open()`: Tokyo window now shows `🗼` banner instead of `🗽`
- `msg_session_cap()`: both `session_name` and `next_session` now correctly resolve
  to `🗼` for Tokyo rather than defaulting to the US `🗽` icon

---



### 🟢 Feature — Tokyo/Asian Session Added (`bot.py`, `signals.py`, `settings.json`)

**Rationale:** With Gold removed and four Forex pairs active, the Asian session is
genuinely relevant — especially for the two JPY pairs (USD_JPY, GBP_JPY) whose
daily range is heavily influenced by the Tokyo open. Running only London + US left
7.5 hours of tradeable market (08:00–15:59 SGT) completely idle.

**What changed:**
- `"Tokyo Window"` (08:00–15:59 SGT by default) added as a full trading session in
  `_build_sessions()` and `_get_active_session()`.
- The dead zone shrinks from **01:00–15:59** to just **04:00–07:59** — the genuine
  gap between the early US continuation window and the Tokyo open.
- Tokyo ORB (Opening Range Breakout) now has its own cache key per instrument,
  keyed to the Tokyo open hour. Each pair maintains a separate ORB independently.
- `session_thresholds.Tokyo` defaults to **5/6** (vs 4/6 for London/US). This is
  intentionally stricter: EUR/USD and GBP/USD are less liquid in Asia, so a higher
  score requirement acts as a natural filter. Lower to 4 in settings if you want
  parity.
- `max_trades_tokyo: 10` added (per-pair cap, same as London/US).
- Tokyo spread limits inherited from London defaults per pair (tighter than US).
- `SESSION_BANNERS` updated with `"Tokyo": "🗼 TOKYO"` for Telegram alerts.

**New settings keys:**

| Key | Default | Description |
|-----|---------|-------------|
| `tokyo_session_start_hour` | `8` | Tokyo window open (SGT) |
| `tokyo_session_end_hour` | `15` | Tokyo window close (SGT, inclusive) |
| `max_trades_tokyo` | `10` | Per-pair trade cap for Tokyo session |
| `dead_zone_start_hour` | `4` | Updated from 1 → 4 (pre-Tokyo gap only) |
| `dead_zone_end_hour` | `7` | Updated from 15 → 7 |
| `session_thresholds.Tokyo` | `5` | Added to session_thresholds dict |

All keys auto-populate with safe defaults on first load — no manual edit required
on existing deployments.

---

### 🟢 Feature — Global Concurrent Trade Cap (`bot.py`, `settings.json`)

**Rationale:** With 4 pairs running independently, the bot could theoretically hold
4 simultaneous positions (one per pair). That represents $400 of notional risk on a
$2,000 demo account — 20% exposure at once. A global broker-level cap provides an
additional safety layer independent of per-pair limits.

**What changed:**
- New `max_total_open_trades` setting (default **2**). After the per-pair
  `max_concurrent_trades` check passes, the guard calls `trader.get_open_trades()`
  — with no instrument filter — to get the true total across all pairs at the broker.
  If that total is ≥ `max_total_open_trades`, the cycle skips without opening a new
  position and sends a Telegram alert (deduplicated via `send_once_per_state`).
- Set to `0` to disable (per-pair limits only).
- Appears in DB cycle summary as stage `"global_trade_cap"`.

**New settings key:**

| Key | Default | Description |
|-----|---------|-------------|
| `max_total_open_trades` | `2` | Max simultaneous open trades across all pairs. 0 = disabled. |

---

### 🟡 Clean-up — Dynamic Session Hours in Telegram Session-Open Banner (`bot.py`)

The "session open" Telegram notification previously used a hard-coded `_hours_map`
string (`"21:00–00:59"` / `"16:00–20:59"`). This is now built dynamically from the
settings keys so the displayed times always match what the bot actually uses, and
Tokyo is correctly included.

---



### 🔴 Fix — `bot_name` Not Updated for v1.1 (`settings.json`)

**Problem:** `version.py` was correctly bumped to `1.1.0` but `bot_name` in
`settings.json` was left as `"RF Scalp v1.0 Multipair"`. Because `config_loader`
always overwrites the Railway volume with the bundled `settings.json` on every
startup, the old name propagated into every log cycle header and every Telegram
alert, making it impossible to tell at a glance which version was running.

**Fix:** `bot_name` updated to `"RF Scalp v1.1 Multipair"` in both `settings.json`
and `settings.json.example`.

---

### 🔴 Fix — Dead Variable and Incorrect Session Bounds in `_get_active_session` (`signals.py`)

**Problem:** The v1.1 refactor of `_get_active_session` read `us_session_end_hour`
from settings into `us_e` but never applied it — the condition remained
`h >= us_h or h == 0`. Two consequences:

1. The US late-night window was not capped at `us_session_end_hour` (23 by default).
   Any hour ≥ 21 would match, including hours that should fall outside the window if
   the end hour is configured lower.
2. The US early-morning window matched only `h == 0` (midnight), ignoring
   `us_session_early_end_hour` (default 3). Hours 01:00–03:00 were silently excluded
   from ORB session detection in `signals.py`, while `_build_sessions` in `bot.py`
   correctly included them.

**Fix:** `_get_active_session` now uses explicit bounded ranges for both US windows:

```python
if us_h  <= h <= us_e:   return "US"   # late window:  21–23
if 0     <= h <= us_e2:  return "US"   # early window: 00–03
```

All three configurable hours (`us_session_end_hour`, `us_session_early_end_hour`)
are now active. Default values preserve v1.0 behaviour exactly.

---



### 🔴 Fix — Calendar Refresh Interval Setting Was Silently Ignored (`settings.json`, `calendar_fetcher.py`)

**Problem:** `settings.json` defined `"calendar_refresh_interval_min"` but
`calendar_fetcher.py` read `"calendar_fetch_interval_min"` — a key name mismatch
that meant the configured interval was never picked up. The code always fell back
to the hardcoded default of 60 minutes regardless of what was set.

**Fix:** The key in `settings.json` (and `settings.json.example`) has been renamed
to `"calendar_fetch_interval_min"` to match what the code reads. The default in
`config_loader.py` is unchanged (60 min).

---

### 🔴 Fix — Trade History Pruning Ignored `db_retention_days` Setting (`bot.py`)

**Problem:** `prune_old_trades()` used a module-level constant `HISTORY_DAYS = 90`
that was never read from settings. Changing `db_retention_days` in `settings.json`
correctly drove the database cleanup job, but the JSON trade history was always
pruned at 90 days regardless.

**Fix:** `HISTORY_DAYS` constant removed. `prune_old_trades()` now accepts a
`settings` dict and reads `db_retention_days` from it at call time. The `_guard_phase`
call site passes `settings` through.

---

### 🟡 Clean-up — `atomic_json_write()` Alias Removed (`bot.py`)

`atomic_json_write()` was a single-line wrapper around `save_json()` that added no
logic and was used inconsistently alongside direct `save_json()` calls in the same
file. Both call sites (`save_signal_cache`, `save_ops_state`) now call `save_json()`
directly. The alias function has been removed.

---

### 🟡 Clean-up — Signal Check Display Label Aligned to `signal_threshold` (`bot.py`)

`_build_signal_checks()` displayed `"Score >= 3"` on Telegram signal cards, but
the actual entry threshold is `signal_threshold` from settings (default 4). The
label now reads `"Score >= {signal_threshold}"` and reflects whatever is configured.

---

### 🟡 Clean-up — XAU/Gold Dead Code Removed (`oanda_trader.py`)

Gold (XAU_USD) was removed from the bot in v1.0. Five `XAU_USD` conditional
branches remained in `get_instrument_specs()` — including a read of the nonexistent
`xau_margin_rate_override` key. All gold-specific code has been removed. The unused
`load_settings` import in `oanda_trader.py` has also been dropped.

---

### 🟡 Clean-up — Log File Renamed (`logging_utils.py`)

The rotating log file was still named `cpr_gold_bot.log` — the last trace of the
original CPR Gold Bot product name anywhere in the active codebase. Renamed to
`rf_scalp_bot.log`.

---

### 🟢 Enhancement — Session Window Hours Parameterised (`bot.py`, `signals.py`, `settings.json`)

Trading session windows (London 16:00–20:59 SGT, US 21:00–23:59 + 00:00–03:59 SGT)
and the dead-zone range were previously hard-coded in `SESSIONS` (bot.py) and
`ORB_SESSIONS` (signals.py). They are now fully configurable via `settings.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `london_session_start_hour` | `16` | London window open (SGT hour) |
| `london_session_end_hour` | `20` | London window close (SGT hour) |
| `us_session_start_hour` | `21` | US late window open (SGT hour) |
| `us_session_end_hour` | `23` | US late window close (SGT hour) |
| `us_session_early_end_hour` | `3` | US early-morning window close (SGT hour) |
| `dead_zone_start_hour` | `1` | Dead zone start — trade management only (SGT hour) |
| `dead_zone_end_hour` | `15` | Dead zone end (SGT hour) |

The Monday pre-open guard now reads `trading_day_start_hour_sgt` (already in settings)
instead of a literal `8`. The `_DEFAULT_ORB_HOURS` fallback in `signals.py` preserves
v1.0 behaviour when no settings dict is passed (unit tests).

---

### 🟢 Enhancement — Report Schedule Times Parameterised (`scheduler.py`, `settings.json`)

Telegram performance report times were hard-coded in `scheduler.py`. They are now
fully configurable via `settings.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `daily_report_hour_sgt` | `15` | Daily report hour (SGT, Mon–Fri) |
| `daily_report_minute_sgt` | `30` | Daily report minute |
| `weekly_report_hour_sgt` | `8` | Weekly report hour (SGT, Monday) |
| `weekly_report_minute_sgt` | `15` | Weekly report minute |
| `monthly_report_hour_sgt` | `8` | Monthly report hour (SGT, first Monday) |
| `monthly_report_minute_sgt` | `0` | Monthly report minute |

All six keys are registered in `config_loader.py` and `validate_settings()` so
existing deployments auto-populate defaults on first load without any manual edit.

---



### 🔴 Fix — Telegram Header Showed Wrong Version (`telegram_alert.py`)

**Problem:** Every Telegram alert showed `🤖 RF Scalp v1.0` in the header
regardless of the deployed version. This was hardcoded directly in
`telegram_alert.py` and was never updated across any of the v1.2.x releases.

**Fix:** The header now reads `bot_name` from `settings.json` on every send:
```python
_bot_name = load_settings().get("bot_name", "RF Scalp")
text = f"🤖 {_bot_name}\n{'─' * 22}\n{message}"
```

Going forward, bumping `bot_name` in `settings.json` (which happens
automatically on every version deploy) will update the Telegram header
automatically — no code change required.

### 🟡 Clean-up — All Stale `v1.0` References Removed

Every file that still referenced `v1.0` in docstrings, fallback defaults,
test messages, and documentation has been updated:

| File | Was | Now |
|---|---|---|
| `telegram_alert.py` | `RF Scalp v1.0` hardcoded | reads `bot_name` from settings |
| `telegram_templates.py` | docstring `v1.0` | version-neutral |
| `signals.py` | docstring `v1.0` | version-neutral |
| `bot.py` | fallback `"RF Scalp v1.0"` | fallback `"RF Scalp"` |
| `test_telegram.py` | hardcoded `v1.0` message | reads from settings |
| `README.md` | 13 references to `v1.0` | updated to `v1.3` |
| `CONFLUENCE_READY.md` | 9 references to `v1.0` | updated to `v1.3` |

### ✅ Clean Baseline

v1.3 is a clean, stable baseline incorporating all fixes from v1.2.0–v1.2.6:
- Settings always sync correctly from bundle (v1.2.3–v1.2.5)
- TP uses RR ratio, not raw pct (v1.2.4)
- SL re-entry gap fires after backfill (v1.2.2)
- ORB time decay — stale signals no longer score +2 (v1.2.6)
- Full parameterization — no hardcoded values in code (v1.2.6)
- 63 settings keys, all documented in SETTINGS.md (v1.2.6)
- Telegram header now reflects actual deployed version (v1.3.0)

---

## v1.2.6 — 2026-03-23

### 🔴 Fix — ORB Time Decay (`signals.py`)

**Problem:** The ORB scoring gave +2 points whether the breakout happened
30 minutes ago or 4 hours ago. This caused 4 consecutive losses on Day 1
(Trades 9–12, 18:37–20:10 SGT) where price was still below the ORB low from
the 16:15 session open — 2.5 to 4 hours earlier. The momentum of that breakout
had long since faded.

**Fix:** ORB points now decay based on how long ago the session opened:

```
0 – orb_fresh_minutes  (default 60):  +2 pts  (fresh break, full weight)
orb_fresh_minutes – orb_aging_minutes (default 120): +1 pt  (aging, half weight)
orb_aging_minutes+ :                   +0 pts  (stale, expired)
```

Both windows are configurable in `settings.json` via `orb_fresh_minutes`
and `orb_aging_minutes`. The ORB label in trade details now shows the age
tier (e.g. `bearish ORB break (+2) [fresh (<60min)]`).

**Day 1 impact:** Trades 9–12 would have scored 2 (below threshold 4) and
been skipped, avoiding 4 losses totalling ~$58. Trade 8 (+$22 win) at 125min
would also have been skipped — net saving of ~$36 on that day alone.

### 🟡 Foundation — Full Parameterization (`signals.py`, `bot.py`, `config_loader.py`, `calendar_fetcher.py`, `scheduler.py`)

All hardcoded "magic numbers" moved to `settings.json`. Every value the bot
uses to make decisions now has a single source of truth.

**New `settings.json` keys added:**

| Key | Default | Was |
|---|---|---|
| `orb_fresh_minutes` | `60` | hardcoded in `signals.py` |
| `orb_aging_minutes` | `120` | hardcoded in `signals.py` |
| `min_rr_ratio` | `2.0` | `rr_ratio < 2.0` hardcoded |
| `ema_fast_period` | `9` | `EMA_FAST = 9` hardcoded |
| `ema_slow_period` | `21` | `EMA_SLOW = 21` hardcoded |
| `orb_formation_minutes` | `15` | `minutes_since_open < 15` hardcoded |
| `calendar_prune_days_ahead` | `21` | `days_ahead=21` hardcoded |
| `startup_dedup_seconds` | `90` | `< 90` hardcoded |

All new keys have safe fallback defaults in `validate_settings()` (bot.py)
and `load_settings()` (config_loader.py) so existing deployments upgrade
without any manual settings.json editing.

**What this means:** To change EMA periods, ORB windows, or RR floor, you
edit `settings.json` and redeploy — no code changes required.

---

## v1.2.5 — 2026-03-20

### 🔴 Root Cause Fix — settings.json Not Deployed to Railway (`.gitignore`)

**Root cause (confirmed from log):**
```
Bundled settings.json not found or empty at /app/settings.json
```
The `.gitignore` file explicitly excluded `settings.json` with a comment
saying "The bot will recreate it from settings.json.example on first boot".
This was wrong — `config_loader.py` reads `settings.json`, not
`settings.json.example`. As a result, every Railway deployment ran with no
bundled settings file, fell back to code-level `setdefault()` values, and the
volume was never updated from the bundle.

This is the underlying cause of every settings-related bug across v1.2.0–v1.2.4.

**Fixes:**
1. `settings.json` removed from `.gitignore` — it now deploys to Railway.
2. `config_loader.py` also tries `settings.json.example` as a fallback if
   `settings.json` is missing, for maximum resilience.

### 🟡 Fix — TP Label in Trade Details String (`signals.py`)

When `tp_mode = "rr_multiple"`, the trade details showed
`TP=$29.12 (rr_multiple 0.35%)` — the `0.35%` was the raw `tp_pct` value,
misleading because the TP was not derived from that percentage. Now shows
`TP=$29.12 (rr_multiple 2.5x RR)`, which accurately reflects how the TP
was calculated.

### ✅ Bot Status After This Deployment

All settings will correctly sync from `settings.json` on startup:
- `sl_pct = 0.0025` (0.25% SL) ✅
- `tp_mode = rr_multiple`, `rr_ratio = 2.5` → TP = SL × 2.5 ✅
- `max_losing_trades_day = 8` ✅
- `max_losing_trades_session = 4` ✅
- `max_trades_day = 20`, `max_trades_london = 10`, `max_trades_us = 10` ✅

Startup log will show:
```
Settings synced on startup: RF Scalp v1.2.4 → RF Scalp v1.2.5
```

---

## v1.2.4 — 2026-03-20

### 🔴 Critical Fix — Every Trade Blocked by R:R Check (`signals.py`)

**Root cause (confirmed from log):** `signals.py` always computed TP as
`entry × tp_pct`, completely ignoring `tp_mode` and `rr_ratio` from settings.
With `sl_pct=0.0025` and `tp_pct=0.0035`, the computed RR was always
`0.0035/0.0025 = 1.40` — which always failed the mandatory `R:R ≥ 2` check.
Every single trade signal was silently blocked.

**Evidence from log:** `Scalp signal BLOCKED | R:R 1.40 < 1:2` on all cycles.

**Fix:** When `tp_mode = "rr_multiple"` (the default), TP is now correctly
computed as `SL × rr_ratio` (= `11.61 × 2.5 = $29.03`, RR=2.50 ✅). The
raw `tp_pct` path remains for any future `tp_mode = "scalp_pct"` usage.

### 🔴 Fix — `ensure_persistent_settings` Fires 5× Per Startup (`config_loader.py`)

**Root cause:** Writing `SETTINGS_FILE` on every call changed its `mtime`,
invalidating the `load_settings` cache, causing the next `load_settings()`
call to call `ensure_persistent_settings()` again — indefinitely. With 5
`load_settings()` calls per startup cycle, the sync ran 5 times, writing the
volume file 5 times and spamming the log with
`Settings synced on startup: RF Scalp Bot → unknown` repeatedly.

**Fix:** Added a module-level `_settings_synced` flag. Once
`ensure_persistent_settings()` has run once in the process lifetime, all
subsequent calls return immediately.

### 🔴 Fix — Empty Bundled Settings Guard (`config_loader.py`)

If `DEFAULT_SETTINGS_PATH` (`settings.json` next to `config_loader.py`)
cannot be read (e.g. a container path layout issue), the function previously
overwrote the volume with an empty `{}`. Now it logs a warning and leaves the
volume file unchanged, so the bot continues with whatever is on the volume.

### 🟡 Fix — Broken Alternate Calendar CDN Removed (`calendar_fetcher.py`)

`cdn-nfs.faireconomy.media` does not resolve (confirmed `NameResolutionError`
in log). The alternate CDN fallback was removed. Next-week 404s are now
suppressed on all weekdays (Mon–Fri) since the feed isn't reliably published
until the weekend anyway.

---

## v1.2.3 — 2026-03-20

### 🔴 Bug Fix — Volume Settings Never Actually Updated on Railway (`config_loader.py`)

**Root cause (the real one):** v1.2.2 introduced a full-sync that fired when
`bot_name` changed between the volume file and the bundled `settings.json`.
This worked exactly once — the first boot wrote the new `bot_name` to the
volume. Every subsequent restart saw the same `bot_name` → no sync → the
volume file kept all stale values (`max_losing_trades_day=3`, `sl_pct=0.0015`
etc.) permanently.

**Confirmed from logs:** `Daily loss cap hit (3/3)` appeared on the SECOND
start of v1.2.2 (first start wrote new bot_name, second start skipped sync),
and every restart since.

**Fix:** `ensure_persistent_settings()` now **unconditionally overwrites** the
volume `/data/settings.json` with the bundled `settings.json` on every startup.
The Railway volume stores trade state (history, runtime state, ORB cache) —
not configuration. Configuration lives in the bundled file under version
control. Redeploy to change settings, not manual volume edits.

The old dead first-boot `setdefault` block was also removed.

### 🔴 Bug Fix — Stale Fallback `=3` in Cooldown Alert (`bot.py`)

`msg_cooldown_started()` was called with `day_limit=settings.get("max_losing_trades_day", 3)`.
Updated fallback to `8`.

### 🟡 Bug Fix — Stale Fallbacks in Startup Telegram (`scheduler.py`)

`msg_startup()` was called with `max_trades_london=4`, `max_trades_us=4`,
`max_losing_day=3` as hardcoded fallbacks. Updated to `10`, `10`, `8`.

---

## v1.2.2 — 2026-03-20

### 🔴 Bug Fix — Railway Volume Ignoring Updated Settings (`config_loader.py`)

**Root cause (confirmed from logs):** Railway persists `/data/settings.json` on
a volume across deployments. The previous merge logic in `ensure_persistent_settings()`
only injected **missing** keys from the bundled `settings.json`. Any key that
already existed in the volume kept its old value forever — meaning `sl_pct`,
`max_losing_trades_day`, `max_losing_trades_session` and all other keys from
earlier versions were **silently ignored** on every redeploy.

**Evidence from log:** Every trade showed `sl_pct_used: 0.0015` (old value)
despite `settings.json` having `0.0025`. The daily cap fired at `3/3` losses
(old value) despite settings showing `8`.

**Fix:** When `bot_name` changes between the volume file and the bundled
defaults (i.e. a new deployment), all values are now **fully synced** from the
bundled file. Same-version restarts still only inject missing keys so manual
operator edits are preserved.

### 🔴 Bug Fix — Stale Hardcoded Fallback Defaults (`config_loader.py`, `bot.py`)

Both files had `setdefault()` calls with old v1.0/v1.1 values:

| Key | Old fallback | New fallback |
|---|---|---|
| `sl_pct` | `0.0015` | `0.0025` |
| `sl_max_usd` | `8.0` | `15.0` |
| `exhaustion_atr_mult` | `2.0` | `3.0` |
| `max_losing_trades_session` | `2` | `4` |
| `max_losing_trades_day` | `3` | `8` |
| `max_trades_day` | `8` | `20` |
| `max_trades_london` | `4` | `10` |
| `max_trades_us` | `4` | `10` |
| `rr_ratio` | `3.0` | `2.5` |

These shadowed the correct values for any key that might be absent from the
loaded settings dict, acting as a second layer of stale defaults.

### 🔴 Bug Fix — SL Re-entry Gap Missed Same-Cycle Closures (`bot.py`)

**Root cause:** The 5-minute SL re-entry gap check ran **before** the OANDA
login, but `backfill_pnl()` — which writes `last_sl_closed_at_sgt` to runtime
state — runs **after** login. So in the cycle where a SL closes, the state
isn't written yet when the gap check runs, the check passes, and a new trade
fires immediately in the same cycle.

**Evidence from log:** Trade 481 closed via SL at 17:53:52 SGT. Trade 487
was placed at 17:53:54 SGT — 2 seconds later in the same cycle.

**Fix:** SL re-entry gap check moved to after `backfill_pnl()` in the
post-login section, so it always sees the current cycle's SL closure.

---

## v1.2.1 — 2026-03-20

### Cap Tuning for Scalp-Frequency Trading (`settings.json`)

Updated all risk caps to match target scalping session density.
No code logic was changed — purely configuration.

| Setting                    | v1.2.0 | v1.2.1 | Note                          |
|----------------------------|--------|--------|-------------------------------|
| `max_trades_day`           | 8      | **20** | Higher throughput for scalping|
| `max_trades_london`        | 4      | **10** | London window up to 10 trades |
| `max_trades_us`            | 4      | **10** | US window up to 10 trades     |
| `max_losing_trades_day`    | 4      | **8**  | 60% win-rate floor enforced   |
| `max_losing_trades_session`| 2      | **4**  | Session loss cap widened      |
| `loss_streak_cooldown_min` | 30     | 30     | Unchanged                     |
| `sl_reentry_gap_min`       | 5      | 5      | Unchanged                     |
| `breakeven_enabled`        | true   | **false** | Disabled per user config   |

**Rationale:**
- At RR=2.5 the mathematical breakeven win rate is only 28.6%, so the caps —
  not the RR — are the active risk limiter. Widening them allows the strategy
  to run more cycles and find higher-conviction setups across a full session.
- Loss cooldown (30 min after 2 consecutive losses) and SL re-entry gap (5 min
  after any SL hit) remain in place as the primary per-trade brakes.
- Break-even disabled to avoid premature SL moves on volatile XAU/USD candles.

### Minor Fix — US Window Telegram Label (`bot.py`)

Session-open alert for `US Window` previously showed `00:00–00:59` only,
missing the primary `21:00–23:59` slot. Corrected to `21:00–00:59`.

---

## v1.2.0 — 2026-03-20

### 🔴 Critical Fix — Re-enable All Risk Guards (`bot.py`)

**Problem:** v1.1 commented out three critical guards:
- `max_losing_trades_day` daily loss hard-stop
- `max_trades_day` daily trade hard-stop
- `max_trades_london` / `max_trades_us` per-session window caps
- `max_losing_trades_session` per-session loss sub-cap

All four were marked "REMOVED" in code but still present in `settings.json`,
creating a misleading configuration. With no guards active the bot executed
7 losing trades in a single session, losing ~$59 before two wins recovered
some ground.

**Fix:** All four guards re-implemented in `prepare_trade_context()`.
`daily_totals()` already computed the needed counters — the check blocks were
simply restored and connected to their settings keys.

### 🔴 New Feature — Single-Candle SL Re-entry Gap (`bot.py`)

**Problem:** After every SL hit, the bot re-entered within 1–5 minutes into
the same price zone. Trades 4→5 and 7→8 in the transaction CSV are examples
— both were stopped out immediately.

**Fix:** Added `sl_reentry_gap_min` setting (default 5 min). On every SL
close `backfill_pnl()` writes `last_sl_closed_at_sgt` to runtime state.
`prepare_trade_context()` checks this timestamp and blocks new entries until
the gap has elapsed.

### 🟡 Fix — ORB Breakout Wrongly Penalised by Exhaustion Filter (`signals.py`)

**Problem:** At 16:16 SGT the London ORB formed and price broke out, but the
exhaustion penalty dropped the score from 2 to 0 — blocking the trade. An ORB
breakout *is* a stretch by definition; penalising it as "exhaustion noise"
incorrectly filters the best entry of the day.

**Fix:** Exhaustion penalty now skips when `orb_contributed=True` (i.e. ORB
contributed +2 to the score). The penalty still fires on pure EMA setups.
`exhaustion_atr_mult` also raised from 2.0 → 3.0 in settings.

### 🟡 Fix — Widen Stop Loss (`settings.json`)

`sl_pct` changed from `0.0015` (0.15%) to `0.0025` (0.25%).
At $4600 gold this widens the stop from ~$6.9 to ~$11.5 — outside the typical
5-minute candle wick range of XAU/USD. `sl_max_usd` raised from $8 to $15
accordingly.

### 🟡 Fix — Enable Breakeven (`settings.json`)

`breakeven_enabled` set to `true`. Trigger raised from $3 → $5 so breakeven
only fires when the trade has meaningful profit cushion.

### 🟠 Fix — Calendar: Wider Gold Keywords + Alternate Next-Week URL (`calendar_fetcher.py`)

- Added 16 new gold-relevant USD keywords: `jolts`, `initial jobless`,
  `consumer confidence`, `michigan`, `yield`, `treasury`, `bond auction`,
  etc.
- `suppress_nextweek_404` now only suppresses Mon–Wed (days 0–2). On Thu/Fri
  when FF *should* publish next-week data, a 404 triggers a retry against
  `cdn-nfs.faireconomy.media` alternate URL.
- `days_ahead` in `_prune_old_events` widened from 14 → 21 so next-week
  events fetched early in the week survive the prune step.

---

## v1.1.1 — 2026-03-19

### 🐛 Bug Fix — CPR TC/BC Inversion (`signals.py`)

**Problem found in logs:** `CPR fetched | pivot=5008.12 TC=5006.94 BC=5009.31`
TC was less than BC, violating the CPR convention (Top Central Pivot must be
above Bottom Central Pivot).

**Root cause:** When the prior day closes *below* its high-low midpoint
(bearish session), the formula `TC = 2×pivot − BC` produces `TC < BC`.
Mathematically the values are correct, but the labels are inverted.

**What was happening (v1.1):** The CPR cache validation only ran on the stale
cache read path (which was removed in v1.1). On the fresh-fetch path there was
no validation at all — inverted TC/BC values were silently passed to the bias
filter. This had no effect on scoring (which only uses `pivot`), but the
`cpr_width_pct` and `TC`/`BC` log values were misleading.

**Fix:** After computing TC and BC, swap them if TC < BC:
```python
if tc < bc:
    tc, bc = bc, tc  # bearish prior-day close — re-label top/bottom
```
TC is now always the top of the CPR band. Pivot is unchanged. The structural
validation (`_validate_cpr_levels`) now runs as a post-swap sanity check and
will only fail if candle data is genuinely corrupt or degenerate
(zero-width CPR, which has ~1/5000 probability per day with real XAU/USD data).

**Impact:** Cosmetic in v1.1 (scoring was unaffected). In v1.1.1 the fix ensures
`TC`, `BC`, and `cpr_width_pct` in logs and Telegram alerts are always correct.

---

## v1.1 — 2026-03-19

### 🔓 Caps & Limits Removed

| Setting | Was | Now |
|---|---|---|
| `max_losing_trades_day` | Hard stop after 3 losses/day | Retained in settings for reporting only — **no longer enforced** |
| `max_trades_day` | Hard stop after 8 trades/day | Retained in settings for reporting only — **no longer enforced** |
| `max_trades_london` / `max_trades_us` | Hard stop after 4 trades/session window | **Fully removed** |
| `max_losing_trades_session` | Hard stop after 2 losses/session | **Fully removed** |

**What is still enforced:**
- ✅ Loss-streak cooldown (2 consecutive losses → 30-minute pause)
- ✅ Max concurrent open trades (1 at a time)
- ✅ Spread guard
- ✅ News filter (hard block on major events, penalty on medium)
- ✅ Friday cutoff
- ✅ Dead zone / session window (London 16:00–20:59, US 21:00–00:59 SGT)

---

### 📊 Signal Quality Fix

**`session_thresholds` raised 3 → 4 in `settings.json`:**

```json
"session_thresholds": {
  "London": 4,
  "US": 4
}
```

Previously a score of 3 (EMA aligned + CPR bias only, **no ORB break**) could
trigger a trade. At threshold 4, ORB confirmation is now a de facto requirement
for any trade entry — matching the strategy's original design intent.

Score map recap:

| Score | Components | Position |
|---|---|---|
| 6 | Fresh EMA cross + ORB break + CPR bias | $100 |
| 5 | Fresh EMA cross + ORB break (no CPR) | $100 |
| 4 | Aligned EMA + ORB break + CPR bias ← **new minimum** | $66 |
| 3 | Aligned EMA + CPR only (no ORB) ← **was allowed, now blocked** | — |

---

### 🔄 CPR Cache Removed (`signals.py`)

Central Pivot Range levels were previously cached in `cpr_cache.json` and
served from disk for the entire trading day. This meant a stale or invalid
cache could persist through market sessions.

**New behaviour:** CPR levels are fetched fresh from OANDA on every 5-minute
cycle using the previous day's daily candle. No cache file is read or written.

---

### 🧹 Internal Cleanups (`bot.py`)

- **`new_day_resume` alert block removed** — this alert fired when today
  followed a loss-cap day. Since `loss_cap_state` is no longer written to
  `ops_state.json`, the alert would never trigger. Dead code removed.

- **Session-open alert decoupled from window cap** — the alert that fires
  when a new trading session opens was previously gated on
  `_window_cap_open > 0`. With window caps removed, the gate was rewritten
  to fire unconditionally whenever `session_hours_sgt` is populated. The
  alert now passes `trade_cap=0` to indicate unlimited.

- **`validate_settings()` required list cleaned up** — `max_trades_day` and
  `max_losing_trades_day` removed from the mandatory keys list. The bot
  will no longer raise a `ValueError` if these are absent from
  `settings.json`.

- **`bot_name` / `__version__` bumped** — `"RF Scalp v1.1"` in
  `settings.json` and `"1.1"` in `version.py`.

---

### ✅ Verified Unchanged (audited, no issues found)

| File | Status |
|---|---|
| `oanda_trader.py` — login, circuit breaker, retry policy | ✅ Clean |
| `reconcile_state.py` — startup + runtime reconcile | ✅ Clean |
| `scheduler.py` — health server, graceful shutdown, crash-loop guard | ✅ Clean |
| `state_utils.py` — atomic JSON writes, timestamp parsing | ✅ Clean |
| `reporting.py` — daily / weekly / monthly report builders | ✅ Clean |
| `news_filter.py` — major/medium classification, penalty scoring | ✅ Clean |
| `config_loader.py` — settings cache, secrets resolution | ✅ Clean |
| `startup_checks.py` — env/margin/calendar pre-flight checks | ✅ Clean |

---

## v1.0 — Initial release

EMA 9/21 crossover + Opening Range Breakout (ORB) + CPR bias scalping
strategy on XAU/USD. M5 candles, SGT session windows (London 16:00–20:59,
US 21:00–00:59). OANDA execution with Telegram alerts.
