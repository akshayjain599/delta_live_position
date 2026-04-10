import hashlib
import hmac
import os
import time
import requests
from datetime import datetime

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
API_KEY        = "testesetset"
API_SECRET     = "testestesetset"

REST_BASE      = "https://api.india.delta.exchange"
POLL_INTERVAL  = 2   # seconds
BTC_SYMBOL     = "BTCUSD"   # used to fetch spot BTC mark price
# ─────────────────────────────────────────

G  = "\033[92m";  R  = "\033[91m";  Y  = "\033[93m"
W  = "\033[97m";  DIM= "\033[2m";   RST= "\033[0m";  BLD= "\033[1m"
CY = "\033[96m"   # cyan


# ══════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════
def make_headers(method: str, path: str) -> dict:
    ts  = str(int(time.time()))
    msg = method + ts + path
    sig = hmac.new(API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return {"api-key": API_KEY, "timestamp": ts, "signature": sig}


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
#  CALCULATIONS
# ══════════════════════════════════════════
def contract_val(p: dict) -> float:
    return float(p.get("contract_value") or p.get("product", {}).get("contract_value", 1))

def calc_live_pnl(p: dict, live_mark: float) -> float:
    size  = float(p.get("size", 0))
    entry = float(p.get("entry_price") or 0)
    return size * (live_mark - entry) * contract_val(p)

def calc_profit_eod(positions: list[dict]) -> float:
    """
    Profit EOD = (Σ short_leg_size × entry) − (Σ long_leg_size × entry)
    size from API is in contracts; convert to BTC via contract_value.
    """
    short_sum = 0.0
    long_sum  = 0.0
    for p in positions:
        size  = float(p.get("size", 0))
        entry = float(p.get("entry_price") or 0)
        cv    = contract_val(p)
        btc   = abs(size) * cv        # actual BTC size
        if size < 0:                  # short leg
            short_sum += btc * entry
        else:                         # long leg
            long_sum  += btc * entry
    return short_sum - long_sum


# ══════════════════════════════════════════
#  DISPLAY HELPERS
# ══════════════════════════════════════════
COL = {"symbol": 26, "size": 14, "entry": 12, "mark": 14, "live": 18}
LINE_W = sum(COL.values()) + 6

def clr(v: float, t: str) -> str:
    return (G if v > 0 else R if v < 0 else W) + t + RST

def fmt_pnl(v: float) -> str:
    arrow = "▲" if v > 0 else "▼" if v < 0 else "●"
    color = G if v > 0 else R if v < 0 else W
    return f"{color}{BLD}{arrow} {v:+.4f} USD{RST}"

def fmt_pct(v: float) -> str:
    arrow = "▲" if v > 0 else "▼" if v < 0 else "●"
    color = G if v > 0 else R if v < 0 else W
    return f"{color}{BLD}{arrow} {v:+.2f}%{RST}"


# ══════════════════════════════════════════
#  RENDER
# ══════════════════════════════════════════
def render(positions: list[dict], live_marks: dict[str, float],
           elapsed_ms: int, error: str | None = None) -> None:
    os.system("cls" if os.name == "nt" else "clear")

    total_live = sum(
        calc_live_pnl(p, live_marks[p.get("product_symbol") or p.get("symbol")])
        for p in positions
        if (p.get("product_symbol") or p.get("symbol")) in live_marks
    )
    profit_eod = calc_profit_eod(positions)
    pct_achieved = (total_live / profit_eod * 100) if profit_eod != 0 else 0.0
    btc_mark   = live_marks.get(BTC_SYMBOL)
    now        = datetime.now().strftime("%H:%M:%S")

    # ── Header bar ───────────────────────────────────────────────
    print()
    print(f"  {'─'*LINE_W}")

    btc_str = f"{CY}{BLD}BTC  ${btc_mark:,.2f}{RST}" if btc_mark else f"{Y}BTC  …{RST}"
    print(
        f"  {BLD}  Delta Exchange  ·  Positions ({len(positions)}){RST}"
        f"    {btc_str}"
        f"   {DIM}{now}  ·  {elapsed_ms}ms{RST}"
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
        symbol = p.get("product_symbol") or p.get("symbol", "—")
        size   = float(p.get("size", 0))
        entry  = float(p.get("entry_price") or 0)
        cv     = contract_val(p)
        btc_sz = size * cv

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

    # ── Summary footer ────────────────────────────────────────────
    print(f"\n  {'─'*LINE_W}")

    pad = COL['symbol'] + COL['size'] + COL['entry'] + COL['mark']

    # Row 1 — Total Live UPNL
    print(f"  {DIM}{'Total Live UPNL':{pad}}{RST}  {fmt_pnl(total_live)}")

    # Row 2 — Profit EOD
    print(f"  {DIM}{'Profit EOD (short credit − long debit)':{pad}}{RST}  {fmt_pnl(profit_eod)}")

    # Row 3 — % Achieved
    print(f"  {DIM}{'% of Profit EOD Achieved':{pad}}{RST}  {fmt_pct(pct_achieved)}")

    print(f"  {'─'*LINE_W}")
    print(f"\n  {DIM}Polling every {POLL_INTERVAL}s  |  Ctrl+C to stop{RST}\n")


# ══════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════
def main():
    print("\n  Starting Delta Exchange Live PnL Monitor…\n")

    while True:
        t0 = time.monotonic()
        positions, live_marks, error = [], {}, None

        try:
            positions  = fetch_positions()
            symbols    = [p.get("product_symbol") or p.get("symbol") for p in positions]
            # also fetch BTC mark price
            all_syms   = list(set([s for s in symbols if s] + [BTC_SYMBOL]))
            live_marks = fetch_live_marks(all_syms)
        except requests.exceptions.HTTPError as e:
            error = f"HTTP {e.response.status_code}: {e.response.text[:80]}"
        except requests.exceptions.ConnectionError:
            error = "Connection error — check internet / API endpoint."
        except requests.exceptions.Timeout:
            error = "Request timed out."
        except RuntimeError as e:
            error = str(e)

        elapsed = int((time.monotonic() - t0) * 1000)
        render(positions, live_marks, elapsed, error)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Stopped. Bye!\n")
