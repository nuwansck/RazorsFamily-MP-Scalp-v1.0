# RF Scalp Bot — Settings Reference

All bot behaviour is controlled by `settings.json`. No hardcoded values exist
in the code — everything is read from this file and has a safe fallback default.

> **Note:** JSON does not support comments. This file documents every key.
> Edit `settings.json` and redeploy to change any setting. Changes take effect
> on the next Railway container restart.

---

## Bot Identity

| Key | Default | Description |
|---|---|---|
| `bot_name` | `"RF Scalp v1.2.6"` | Shown in Telegram alerts and logs. Change when deploying a new version. |
| `demo_mode` | `true` | `true` = OANDA demo account. Set to `false` for live trading. |
| `trade_gold` | `true` | Master on/off switch for trading. Set to `false` to pause without stopping the bot. |
| `enabled` | `true` | Secondary on/off switch. `false` = bot skips all trade cycles but stays running. Use `trade_gold` for normal pausing. |

---

## Signal Engine

These control how the bot scores each 5-minute candle and decides whether to trade.

| Key | Default | Description |
|---|---|---|
| `signal_threshold` | `4` | Minimum score (out of 6) required to place a trade. Raise to 5 for higher-quality signals only. |
| `session_thresholds` | `{"London": 4, "US": 4, "Tokyo": 5}` | Per-session score threshold. Tokyo defaults to 5 (stricter) since EUR/USD and GBP/USD are quieter in Asian hours. |
| `ema_fast_period` | `9` | Fast EMA period. Used for crossover detection. |
| `ema_slow_period` | `21` | Slow EMA period. EMA fast crossing above/below slow is the primary direction signal. |
| `m5_candle_count` | `40` | Number of M5 candles fetched from OANDA per cycle. Must be > `ema_slow_period + 3`. |

### Scoring breakdown (max 6 points):
- **EMA fresh cross** (9 just crossed 21 this candle): **+3 pts**
- **EMA trend only** (9 already above/below 21, no fresh cross): **+1 pt**
- **ORB break** (price outside opening range, time-decayed): **+2 / +1 / +0 pts**
- **CPR bias** (price on correct side of daily pivot): **+1 pt**

---

## Opening Range Breakout (ORB)

Controls how the ORB signal is scored based on how fresh the breakout is.

| Key | Default | Description |
|---|---|---|
| `orb_formation_minutes` | `15` | Minutes after session open before the ORB is considered formed. ORB = first completed M15 candle. |
| `orb_fresh_minutes` | `60` | ORB break within this many minutes of session open scores **+2 pts** (full weight). |
| `orb_aging_minutes` | `120` | ORB break between `orb_fresh_minutes` and this value scores **+1 pt** (half weight). After this it scores **+0 pts** (expired). |

**Example with defaults:**
```
London ORB forms at 16:15 SGT
  16:15 – 17:15 (0–60 min):   ORB break = +2 pts  [fresh]
  17:15 – 18:15 (60–120 min): ORB break = +1 pt   [aging]
  18:15+ (120+ min):           ORB break = +0 pts  [stale — expired]
```

After the ORB expires, only a **fresh EMA cross (+3) + CPR (+1) = 4** can reach the threshold.

---

## ATR (Average True Range)

Used for the exhaustion penalty — prevents trading when price is over-stretched.

| Key | Default | Description |
|---|---|---|
| `atr_period` | `14` | Lookback period for ATR calculation on M5 candles. Standard value — rarely needs changing. |
| `exhaustion_atr_mult` | `3.0` | If price is stretched more than this many ATR from the EMA midpoint, score is penalised by −1. Does not apply to ORB breakouts. |

---

## Stop Loss & Take Profit

| Key | Default | Description |
|---|---|---|
| `sl_mode` | `"pct_based"` | SL calculation method. `pct_based` = percentage of entry price. |
| `sl_pct` | `0.0025` | SL as a fraction of entry price. `0.0025` = 0.25%. At $4650 gold this is ~$11.60. |
| `sl_min_usd` | `2.0` | Minimum SL in USD. Prevents extremely tight stops on small price moves. |
| `sl_max_usd` | `15.0` | Maximum SL in USD. Caps the SL size on volatile candles. |
| `tp_mode` | `"rr_multiple"` | TP calculation method. `rr_multiple` = SL × `rr_ratio`. `fixed_usd` = fixed dollar amount. |
| `tp_pct` | `0.0035` | TP percentage — only used when `tp_mode` is `scalp_pct`. |
| `rr_ratio` | `2.5` | TP = SL × this value when `tp_mode` is `rr_multiple`. At SL=$11.60, TP = $29.00. |
| `min_rr_ratio` | `2.0` | Minimum acceptable RR before a trade is blocked. If actual RR < this, signal is rejected. |
| `fixed_tp_usd` | `null` | Fixed TP in USD — only used when `tp_mode` is `fixed_usd`. |
| `pair_sl_tp` | see below | **Per-pair fixed pip overrides** — takes priority over `sl_pct` / `rr_ratio` when set. Each pair entry has `sl_pips` and `tp_pips`. Remove a pair's entry to revert to percentage mode. Set to `{}` to disable fixed pips for all pairs. See table below. |
| `breakeven_enabled` | `false` | Move SL to breakeven when trade reaches `breakeven_trigger_usd` profit. Off by default. |
| `breakeven_trigger_usd` | `5.0` | Profit in USD needed before SL moves to breakeven. Only active if `breakeven_enabled` is `true`. |

### `pair_sl_tp` — Per-Pair Fixed Pip Values (v1.6.1)

```json
"pair_sl_tp": {
  "GBP_USD": {"sl_pips": 20, "tp_pips": 50, "pip_value_usd": 10.0},
  "EUR_USD": {"sl_pips": 15, "tp_pips": 38, "pip_value_usd": 10.0},
  "GBP_JPY": {"sl_pips": 35, "tp_pips": 88, "pip_value_usd":  6.7},
  "USD_JPY": {"sl_pips": 20, "tp_pips": 50, "pip_value_usd":  6.7}
}
```

> **`pip_value_usd`** = dollar value of 1 pip for 1 standard lot (100,000 units).
> USD-quoted pairs (GBP/USD, EUR/USD) are always **10.0**. JPY-quoted pairs
> (GBP/JPY, USD/JPY) are approximately **6.7** at USD/JPY ~150 — update this
> if USD/JPY moves more than 10 points from current rate.
> Without this field the bot falls back to `10.0`, which under-sizes JPY pairs.

| Pair | SL | TP | RR | TP% ADR | pip_value_usd | $/pip (full) | SL risk | TP reward |
|---|---|---|---|---|---|---|---|---|
| GBP/USD | 20p | 50p | 2.50× | 62% | 10.0 | $1.50 | $30 | $75 |
| EUR/USD | 15p | 38p | 2.53× | 58% | 10.0 | $2.00 | $30 | $76 |
| GBP/JPY | 35p | 88p | 2.51× | 68% | 6.7  | $0.86 | $30 | $76 |
| USD/JPY | 20p | 50p | 2.50× | 67% | 6.7  | $1.50 | $30 | $75 |

---

## Position Sizing

| Key | Default | Description |
|---|---|---|
| `position_full_usd` | `30` | Risk amount in USD for high-conviction signals (score 5–6). At 1.5% risk on a $2,000 account = $30. Bot back-calculates units from SL distance automatically. |
| `position_partial_usd` | `20` | Risk amount in USD for standard signals (score 4). At 1.0% risk on a $2,000 account = $20. Scale both values proportionally if account grows. |
| `account_balance_override` | `0` | Override the live balance for sizing calculations. `0` = use real balance from OANDA. |

---

## Risk Controls & Caps

| Key | Default | Description |
|---|---|---|
| `max_concurrent_trades` | `1` | Maximum open trades **per pair** at any time. With 4 pairs this allows up to 4 total, but `max_total_open_trades` acts as the hard ceiling. |
| `max_total_open_trades` | `2` | Hard cap on open trades **across all pairs combined** (broker-verified on every cycle). `0` = disabled. **Set to 2** to run max 2 simultaneous positions regardless of how many pairs have signals. |
| `max_trades_day` | `20` | Maximum total trades per trading day per pair (resets at `trading_day_start_hour_sgt`). |
| `max_losing_trades_day` | `8` | Maximum losing trades per day per pair. Bot stops trading for the day after this many losses. |
| `max_trades_london` | `10` | Maximum trades in the London session per pair. |
| `max_trades_us` | `10` | Maximum trades in the US session per pair. |
| `max_trades_tokyo` | `10` | Maximum trades in the Tokyo/Asian session per pair. |
| `max_losing_trades_session` | `4` | Maximum losing trades per session window per pair. |
| `loss_streak_cooldown_min` | `30` | Minutes to pause after 2 consecutive losses. Prevents revenge-trading streaks. |
| `sl_reentry_gap_min` | `5` | Minutes to wait after a stop-loss before entering a new trade on the same pair. |

---

## Session Windows

| Key | Default | Description |
|---|---|---|
| `session_only` | `true` | `true` = only trade during active sessions. `false` = trade any time (not recommended). |
| `trading_day_start_hour_sgt` | `8` | Hour (SGT) when daily counters reset (trade count, loss count). Also used as the Monday market-open guard. |
| `friday_cutoff_hour_sgt` | `23` | Stop trading on Friday after this hour SGT. |
| `friday_cutoff_minute_sgt` | `0` | Minute past the Friday cutoff hour. |
| `cycle_minutes` | `5` | How often the bot runs its trade evaluation loop. Do not change unless testing. |
| `tokyo_session_start_hour` | `8` | Tokyo/Asian window open hour (SGT, inclusive). |
| `tokyo_session_end_hour` | `15` | Tokyo/Asian window close hour (SGT, inclusive). |
| `london_session_start_hour` | `16` | London window open hour (SGT, inclusive). |
| `london_session_end_hour` | `20` | London window close hour (SGT, inclusive). |
| `us_session_start_hour` | `21` | US late window open hour (SGT, inclusive). |
| `us_session_end_hour` | `23` | US late window close hour (SGT, inclusive). |
| `us_session_early_end_hour` | `3` | US early-morning window close hour (SGT, inclusive). |
| `dead_zone_start_hour` | `4` | Dead zone start — no new entries (SGT). Now only 04:00–07:59, the pre-Tokyo gap. |
| `dead_zone_end_hour` | `7` | Dead zone end hour (SGT, inclusive). |

**Session schedule (SGT):**
```
00:00–03:59  US continuation (early)   threshold 3/6
04:00–07:59  Dead zone                 no trading
08:00–15:59  Tokyo/Asian window        threshold 5/6
16:00–20:59  London window             threshold 4/6
21:00–23:59  US session                threshold 4/6
```

**Tokyo threshold note:** The default threshold of 5/6 is intentionally higher than London/US. The JPY pairs (USD_JPY, GBP_JPY) are most active in Tokyo hours; EUR/USD and GBP/USD are quieter. Raise to 6/6 to effectively disable Tokyo for specific pairs via per-pair settings, or lower to 4 if you want parity across all sessions.

---

## Spread Filter

| Key | Default | Description |
|---|---|---|
| `spread_limits` | `{"London": 130, "US": 130}` | Maximum spread in pips per session. XAU/USD pips are in cents — 130 pips = $1.30 spread. |
| `max_spread_pips` | `150` | Global spread cap across all sessions. |

---

## News Filter

| Key | Default | Description |
|---|---|---|
| `news_filter_enabled` | `true` | Block trading around high-impact USD/gold news events. |
| `news_block_before_min` | `30` | Minutes before a news event to stop entering new trades. |
| `news_block_after_min` | `30` | Minutes after a news event before resuming trading. |
| `news_lookahead_min` | `120` | How far ahead (in minutes) to look for upcoming news events. |
| `news_medium_penalty_score` | `-1` | Score penalty for medium-impact news within the lookahead window. |

---

## Economic Calendar

| Key | Default | Description |
|---|---|---|
| `calendar_fetch_interval_min` | `60` | Minutes between calendar fetches from Forex Factory. |
| `calendar_retry_after_min` | `15` | Minutes to wait before retrying after a failed fetch. |
| `calendar_prune_days_ahead` | `21` | Days ahead to keep events in the local cache. Events beyond this are pruned. |

---

## Margin & OANDA

| Key | Default | Description |
|---|---|---|
| `margin_safety_factor` | `0.6` | Fraction of free margin available for new trades. `0.6` = use at most 60% of free margin. |
| `margin_retry_safety_factor` | `0.4` | Reduced safety factor used when retrying after a margin rejection. |
| `margin_rate_override` | `0.0` | Override broker margin rate for all instruments. `0.0` = use live OANDA rate. |
| `auto_scale_on_margin_reject` | `true` | Automatically reduce position size and retry if OANDA rejects due to insufficient margin. |
| `telegram_show_margin` | `true` | Include margin details in Telegram trade alerts. |

---

## Reporting & Maintenance

| Key | Default | Description |
|---|---|---|
| `startup_dedup_seconds` | `90` | Suppress duplicate startup Telegram messages sent within this window (seconds). Prevents spam on rapid Railway restarts. |
| `db_retention_days` | `90` | Days of trade history to keep in the local SQLite database. Older records are purged. |
| `db_cleanup_hour_sgt` | `0` | Hour (SGT) when the daily database cleanup runs. |
| `db_cleanup_minute_sgt` | `15` | Minute past the hour when cleanup runs. Default: 00:15 SGT. |
| `db_vacuum_weekly` | `true` | Run SQLite VACUUM weekly (Sundays) to reclaim disk space. |
| `daily_report_hour_sgt` | `15` | Hour (SGT, Mon–Fri) to send the daily performance Telegram report. |
| `daily_report_minute_sgt` | `30` | Minute for the daily report. Default: 15:30 SGT (30 min before London open). |
| `weekly_report_hour_sgt` | `8` | Hour (SGT, every Monday) to send the weekly performance report. |
| `weekly_report_minute_sgt` | `15` | Minute for the weekly report. Default: 08:15 SGT. |
| `monthly_report_hour_sgt` | `8` | Hour (SGT, first Monday of month) to send the monthly performance report. |
| `monthly_report_minute_sgt` | `0` | Minute for the monthly report. Default: 08:00 SGT. |
| `tp2_rr_reference` | `3.0` | R:R multiplier for the TP2 reference level shown in trade opened Telegram alerts. Displayed as a manual take-profit reference — no second order is placed. Set to `0` to hide. |

---

## Quick Reference — Most Commonly Tuned

```json
"signal_threshold": 4,          ← raise to 5 = fewer but better trades
"session_thresholds": {
  "London": 4,                  ← raise to 5 if London win rate < 45%
  "US": 4
},
"orb_fresh_minutes": 60,        ← lower = stricter ORB freshness
"orb_aging_minutes": 120,       ← lower = ORB expires sooner
"pair_sl_tp": {                  ← fixed pip SL/TP per pair (v1.6.1 default)
  "GBP_USD": {"sl_pips": 20, "tp_pips": 50},
  "EUR_USD": {"sl_pips": 15, "tp_pips": 38},
  "GBP_JPY": {"sl_pips": 35, "tp_pips": 88},
  "USD_JPY": {"sl_pips": 20, "tp_pips": 50}
},                               ← set to {} to revert to sl_pct mode
"rr_ratio": 2.5,                ← only used when pair_sl_tp is empty
"sl_pct": 0.002,                ← only used when pair_sl_tp is empty
"loss_streak_cooldown_min": 30, ← raise to 45 if streaks persist
"sl_reentry_gap_min": 5         ← raise to 10 to slow re-entry after SL
```
