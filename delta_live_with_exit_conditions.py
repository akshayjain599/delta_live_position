

"""
Delta Exchange India — Live Position Monitor with Auto-Exit
===========================================================
Auto-exit triggers (market close-all):
  STOP LOSS  → % of Profit EOD Achieved <= -150%
  TARGET     → % of Profit EOD Achieved >= +80%

Requirements:
    pip install requests
"""

import hashlib
import hmac
import json
import os
import time
import requests
from datetime import datetime

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
API_KEY        = "test"
API_SECRET     = "test2"

REST_BASE     = "https://api.india.delta.exchange"
POLL_INTERVAL = 2        # seconds
BTC_SYMBOL    = "BTCUSD"

TARGET_PCT    = 90.0     # exit when % achieved >= +80%
STOPLOSS_PCT  = -150.0   # exit when % achieved <= -150%
# ─────────────────────────────────────────

G  = "\033[92m";  R  = "\033[91m";  Y  = "\033[93m"
W  = "\033[97m";  DIM= "\033[2m";   RST= "\033[0m";  BLD= "\033[1m"
CY = "\033[96m";  MG = "\033[95m"


# ══════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════
def make_headers(method: str, path: str, body: str = "") -> dict:
    ts  = str(int(time.time()))
    msg = method + ts + path + body
    sig = hmac.new(API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return {
        "api-key":      API_KEY,
        "timestamp":    ts,
        "signature":    sig,
        "Content-Type": "application/json",
    }


# ══════════════════════════════════════════
#  FETCH POSITIONS
# ══════════════════════════════════════════
def fetch_positions() -> list[dict]:
    path = "/v2/positions/margined"
    resp = requests.get(REST_BASE + path, headers=make_headers("GET", path), timeout=8)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(data.get("error", "Unknown API error"))
    return [p for p in data.get("result", []) if float(p.get("size", 0)) != 0]


# ══════════════════════════════════════════
#  FETCH LIVE MARK PRICES  (public)
# ══════════════════════════════════════════
def fetch_live_marks(symbols: list[str]) -> dict[str, float]:
    if not symbols:
        return {}
    params = {"symbols": ",".join(symbols)}
    resp   = requests.get(REST_BASE + "/v2/tickers", params=params, timeout=8)
    resp.raise_for_status()
    marks  = {}
    for t in resp.json().get("result", []):
        sym  = t.get("symbol")
        mark = t.get("mark_price")
        if sym and mark:
            marks[sym] = float(mark)
    return marks


# ══════════════════════════════════════════
#  CLOSE ALL POSITIONS  (market orders)
# ══════════════════════════════════════════
def close_position(p: dict, reason: str) -> dict:
    """
    Places a reduce-only market order to fully close one position.
    If size > 0 (long)  → sell
    If size < 0 (short) → buy
    """
    size       = float(p.get("size", 0))
    product_id = p.get("product_id")
    symbol     = p.get("product_symbol") or p.get("symbol", "?")
    side       = "sell" if size > 0 else "buy"
    abs_size   = abs(int(size))   # Delta expects integer contracts

    payload = {
        "product_id":   product_id,
        "size":         abs_size,
        "side":         side,
        "order_type":   "market_order",
        "reduce_only":  True,
    }
    body = json.dumps(payload)
    path = "/v2/orders"

    resp = requests.post(
        REST_BASE + path,
        headers=make_headers("POST", path, body),
        data=body,
        timeout=10,
    )
    result = resp.json()
    status = "OK" if result.get("success") else f"FAILED: {result.get('error','?')}"
    return {"symbol": symbol, "side": side, "size": abs_size, "status": status, "is_short": size < 0}
    status = "OK" if result.get("success") else f"FAILED: {result.get('error','?')}"
    return {"symbol": symbol, "side": side, "size": abs_size, "status": status, "is_short": size < 0}


def close_all_positions(positions: list[dict], reason: str) -> list[dict]:
    # Short legs first (most negative size → releases margin) then long legs
    ordered = sorted(positions, key=lambda p: float(p.get("size", 0)))
    results = []
    for p in ordered:
        r = close_position(p, reason)
        results.append(r)
        time.sleep(0.3)   # 300ms gap — lets exchange release margin before next order
    return results


# ══════════════════════════════════════════
#  CALCULATIONS
# ══════════════════════════════════════════
def contract_val(p: dict) -> float:
    return float(p.get("contract_value") or p.get("product", {}).get("contract_value", 1))

def calc_live_pnl(p: dict, live_mark: float) -> float:
    size  = float(p.get("size", 0))
    entry = float(p.get("entry_price") or 0)
    return size * (live_mark - entry) * contract_val(p)

def calc_profit_eod(positions: list[dict]) -> float:
    short_sum = 0.0
    long_sum  = 0.0
    for p in positions:
        size  = float(p.get("size", 0))
        entry = float(p.get("entry_price") or 0)
        cv    = contract_val(p)
        btc   = abs(size) * cv
        if size < 0:
            short_sum += btc * entry
        else:
            long_sum  += btc * entry
    return short_sum - long_sum


# ══════════════════════════════════════════
#  DISPLAY HELPERS
# ══════════════════════════════════════════
COL    = {"symbol": 26, "size": 14, "entry": 12, "mark": 14, "live": 18}
LINE_W = sum(COL.values()) + 6

def clr(v: float, t: str) -> str:
    return (G if v > 0 else R if v < 0 else W) + t + RST

def fmt_pnl(v: float) -> str:
    arrow = "▲" if v > 0 else "▼" if v < 0 else "●"
    color = G if v > 0 else R if v < 0 else W
    return f"{color}{BLD}{arrow} {v:+.4f} USD{RST}"

def fmt_pct(v: float, target: float, stoploss: float) -> str:
    arrow = "▲" if v > 0 else "▼" if v < 0 else "●"
    # colour based on proximity to limits
    if v >= target:
        color = G
    elif v <= stoploss:
        color = R
    elif v >= target * 0.7:          # within 70% of target → yellow warning
        color = Y
    elif v <= stoploss * 0.7:        # within 70% of SL → yellow warning
        color = Y
    else:
        color = G if v > 0 else R
    return f"{color}{BLD}{arrow} {v:+.2f}%{RST}"


# ══════════════════════════════════════════
#  RENDER
# ══════════════════════════════════════════
def render(positions, live_marks, elapsed_ms, pct_achieved,
           total_live, profit_eod, btc_mark, error=None) -> None:
    os.system("cls" if os.name == "nt" else "clear")
    now = datetime.now().strftime("%H:%M:%S")

    # ── Header ───────────────────────────────────────────────────
    print()
    print(f"  {'─'*LINE_W}")
    btc_str = f"{CY}{BLD}BTC  ${btc_mark:,.2f}{RST}" if btc_mark else f"{Y}BTC  …{RST}"
    print(
        f"  {BLD}  Delta Exchange  ·  Positions ({len(positions)}){RST}"
        f"    {btc_str}"
        f"   {DIM}{now}  ·  {elapsed_ms}ms{RST}"
    )
    print(f"  {'─'*LINE_W}")

    # ── Guard rails ───────────────────────────────────────────────
    tgt_color = G if pct_achieved >= TARGET_PCT * 0.7 else DIM
    sl_color  = R if pct_achieved <= STOPLOSS_PCT * 0.7 else DIM
    print(
        f"  {tgt_color}TARGET  {TARGET_PCT:+.0f}%{RST}"
        f"   {sl_color}STOP LOSS  {STOPLOSS_PCT:+.0f}%{RST}"
    )
    print(f"  {'─'*LINE_W}")

    if error:
        print(f"\n  {R}⚠  {error}{RST}\n")
        return
    if not positions:
        print(f"\n  {Y}No open positions.{RST}\n")
        return

    # ── Column headers ───────────────────────────────────────────
    print(
        f"\n  {BLD}"
        f"{'Symbol':<{COL['symbol']}}"
        f"{'Size':>{COL['size']}}"
        f"{'Entry':>{COL['entry']}}"
        f"{'Mark (Live)':>{COL['mark']}}"
        f"{'Live UPNL':>{COL['live']}}"
        f"{RST}"
    )
    print(f"  {'─'*LINE_W}")

    # ── Position rows ─────────────────────────────────────────────
    for p in positions:
        symbol    = p.get("product_symbol") or p.get("symbol", "—")
        size      = float(p.get("size", 0))
        entry     = float(p.get("entry_price") or 0)
        cv        = contract_val(p)
        btc_sz    = size * cv
        live_mark = live_marks.get(symbol)

        if live_mark is not None:
            live_pnl = calc_live_pnl(p, live_mark)
            mark_str = f"{live_mark:.2f}"
            live_str = fmt_pnl(live_pnl)
        else:
            mark_str = f"{Y}—{RST}"
            live_str = f"{Y}waiting…{RST}"

        size_str = clr(size, f"{btc_sz:+.4f} BTC")
        print(
            f"  {W}{symbol:<{COL['symbol']}}{RST}"
            f"{size_str:>{COL['size']+10}}"
            f"{entry:>{COL['entry']}.2f}"
            f"{mark_str:>{COL['mark']}}"
            f"  {live_str}"
        )

    # ── Summary ───────────────────────────────────────────────────
    pad = COL['symbol'] + COL['size'] + COL['entry'] + COL['mark']
    print(f"\n  {'─'*LINE_W}")
    print(f"  {DIM}{'Total Live UPNL':{pad}}{RST}  {fmt_pnl(total_live)}")
    print(f"  {DIM}{'Profit EOD (short credit − long debit)':{pad}}{RST}  {fmt_pnl(profit_eod)}")
    print(
        f"  {DIM}{'% of Profit EOD Achieved':{pad}}{RST}  "
        f"{fmt_pct(pct_achieved, TARGET_PCT, STOPLOSS_PCT)}"
    )
    print(f"  {'─'*LINE_W}")
    print(f"\n  {DIM}Polling every {POLL_INTERVAL}s  |  "
          f"Target {TARGET_PCT:+.0f}%  |  SL {STOPLOSS_PCT:+.0f}%  |  Ctrl+C to stop{RST}\n")


def render_exit_banner(reason: str, pct: float, results: list[dict]) -> None:
    """Full-screen alert shown after auto-exit fires."""
    os.system("cls" if os.name == "nt" else "clear")
    color = G if "TARGET" in reason else R
    now   = datetime.now().strftime("%H:%M:%S")

    print()
    print(f"  {color}{BLD}{'█'*LINE_W}{RST}")
    print(f"  {color}{BLD}  AUTO-EXIT TRIGGERED — {reason}   ({pct:+.2f}%)   {now}{RST}")
    print(f"  {color}{BLD}{'█'*LINE_W}{RST}")
    print()
    print(f"  {'Symbol':<28} {'Leg':<8} {'Side':<8} {'Contracts':>10}   Status")
    print(f"  {'─'*LINE_W}")
    for i, r in enumerate(results):
        leg      = f"{R}{BLD}SHORT{RST}" if r['is_short'] else f"{G}{BLD}LONG{RST}"
        seq      = f"[{i+1}]"
        st_color = G if r['status'] == 'OK' else R
        print(
            f"  {seq} {W}{r['symbol']:<26}{RST}"
            f" {leg:<18}"
            f" {r['side']:<8}"
            f" {r['size']:>10}"
            f"   {st_color}{r['status']}{RST}"
        )
    print(f"  {'─'*LINE_W}")
    print(f"\n  {MG}{BLD}All positions closed. Monitor stopped.{RST}\n")


# ══════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════
def main():
    print(f"\n  {BLD}Delta Exchange Live PnL Monitor — Auto-Exit Edition{RST}")
    print(f"  Target {G}{TARGET_PCT:+.0f}%{RST}   Stop Loss {R}{STOPLOSS_PCT:+.0f}%{RST}\n")

    while True:
        t0 = time.monotonic()
        positions, live_marks, error = [], {}, None
        total_live = profit_eod = pct_achieved = btc_mark = 0.0

        try:
            positions  = fetch_positions()
            symbols    = [p.get("product_symbol") or p.get("symbol") for p in positions]
            all_syms   = list(set([s for s in symbols if s] + [BTC_SYMBOL]))
            live_marks = fetch_live_marks(all_syms)

            total_live = sum(
                calc_live_pnl(p, live_marks[p.get("product_symbol") or p.get("symbol")])
                for p in positions
                if (p.get("product_symbol") or p.get("symbol")) in live_marks
            )
            profit_eod   = calc_profit_eod(positions)
            pct_achieved = (total_live / profit_eod * 100) if profit_eod != 0 else 0.0
            btc_mark     = live_marks.get(BTC_SYMBOL, 0.0)

        except requests.exceptions.HTTPError as e:
            error = f"HTTP {e.response.status_code}: {e.response.text[:80]}"
        except requests.exceptions.ConnectionError:
            error = "Connection error — check internet / API endpoint."
        except requests.exceptions.Timeout:
            error = "Request timed out."
        except RuntimeError as e:
            error = str(e)

        elapsed = int((time.monotonic() - t0) * 1000)

        # ── Render table ─────────────────────────────────────────
        render(positions, live_marks, elapsed, pct_achieved,
               total_live, profit_eod, btc_mark, error)

        # ── Auto-exit check (only when we have valid data) ───────
        if not error and positions:

            if pct_achieved >= TARGET_PCT:
                reason  = "TARGET HIT"
                results = close_all_positions(positions, reason)
                render_exit_banner(reason, pct_achieved, results)
                break

            elif pct_achieved <= STOPLOSS_PCT:
                reason  = "STOP LOSS HIT"
                results = close_all_positions(positions, reason)
                render_exit_banner(reason, pct_achieved, results)
                break

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Stopped manually. Bye!\n")
