import yfinance as yf
import pandas as pd
import numpy as np

def analyze_monthly_ohlc(ticker):
    """
    Analyze monthly OHLC data from Jan 2021 to Dec 2025
    with STRICT 6-month rolling averages (previous months only).
    """

    #----------YYYY-MM-DD-----
    START_DATE = "2020-01-01"
    END_DATE = "2026-03-31"

    # -----------------------------
    # 1. Download Monthly Data
    # -----------------------------
    df = yf.download(
        ticker,
        start=START_DATE,
        end=END_DATE,
        interval="1mo",
        progress=False
    )

    if df.empty:
        print("No data fetched. Check ticker.")
        return

    # -----------------------------
    # 2. FIX: Flatten MultiIndex Columns
    # -----------------------------
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # -----------------------------
    # 3. Drop rows with missing OHLC
    # -----------------------------
    required_cols = ["Open", "High", "Low"]
    df = df.dropna(subset=required_cols)

    # -----------------------------
    # 4. Extract Month & Year
    # -----------------------------
    df["Year"] = df.index.year
    df["Month"] = df.index.month_name()

    # -----------------------------
    # 5. Percentage Calculations
    # -----------------------------
    df["Open_to_High_%"] = ((df["High"] - df["Open"]) / df["Open"]) * 100
    df["Open_to_Low_%"] = ((df["Low"] - df["Open"]) / df["Open"]) * 100

    # -----------------------------
    # 6. Rolling Averages (LAST 6 COMPLETED MONTHS ONLY)
    # -----------------------------
    df["Avg_Open_to_High_%_Last_6M"] = (
        df["Open_to_High_%"]
        .shift(1)
        .rolling(window=6, min_periods=1)
        .mean()
    )

    df["Avg_Open_to_Low_%_Last_6M"] = (
        df["Open_to_Low_%"]
        .shift(1)
        .rolling(window=6, min_periods=1)
        .mean()
    )

    df["Avg_High_to_Low_%"] = ((df["High"] - df["Low"]) / df["Low"]) * 100


    # -----------------------------
    # 7. Round Values
    # -----------------------------
    numeric_cols = [
        "Open_to_High_%",
        "Open_to_Low_%",
        "Avg_Open_to_High_%_Last_6M",
        "Avg_Open_to_Low_%_Last_6M",
        "Avg_High_to_Low_%"
    ]
    df[numeric_cols] = df[numeric_cols].round(2)

    # -----------------------------
    # 8. Final Output
    # -----------------------------
    final_df = df[
        [
            "Month",
            "Year",
            "Open_to_High_%",
            "Open_to_Low_%",
            "Avg_High_to_Low_%"
        ]
    ].reset_index(drop=True)

    final_df.columns = [
        "Month",
        "Year",
        "O→H % Change",
        "O→L % Change",
        "Avg H → L%"
    ]

    print(f"\nMonthly OHLC Analysis for {ticker} (2021–2025)\n")
    print(final_df.to_string(index=False))


# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    analyze_monthly_ohlc("RELIANCE.NS")  # Example: BANK NIFTY

    
#     "NIFTY 50": "^NSEI",
#     "BANK NIFTY": "^NSEBANK",
#     "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
#     "MIDCAP NIFTY": "NIFTY_MID_SELECT.NS",
#     "BSE SENSEX": "^BSESN"
# }

# | Stock Name                   | NSE Ticker      |
# | ---------------------------- | --------------- |
# | **Adani Enterprises**        | `ADANIENT.NS`   |
# | **Adani Ports**              | `ADANIPORTS.NS` |
# | **Yes Bank**                 | `YESBANK.NS`    |
# | **Vodafone Idea**            | `IDEA.NS`       |
# | **Tata Motors**              | `TATAMOTORS.NS` |
# | **Adani Power**              | `ADANIPOWER.NS` |
# | **Steel Authority of India** | `SAIL.NS`       |
# | **Zomato**                   | `ZOMATO.NS`     |
# | **MCX**                      | `MCX.NS`        |
# | **Adani Green Energy**       | `ADANIGREEN.NS` |



# Stock Name,Yahoo Finance Ticker
# AMC Entertainment,AMC
# Netflix,NFLX
# Beyond Meat,BYND
# Valens Semiconductor,VLN
# iQIYI,IQ
# Canopy Growth,CGC
# Aeva Technologies,AEVA
# Novavax,NVAX
# Dave & Buster's Entertainment,PLAY
# Ambarella,AMBA



# | No. | Stock Name                          | Yahoo Ticker  | 3Y Beta (≈) |
# | --: | ----------------------------------- | ------------- | ----------- |
# |   1 | Adani Enterprises Ltd               | ADANIENT.NS   | 1.45        |
# |   2 | Adani Ports and SEZ Ltd             | ADANIPORTS.NS | 1.20        |
# |   3 | Apollo Hospitals Enterprise Ltd     | APOLLOHOSP.NS | 0.65        |
# |   4 | Asian Paints Ltd                    | ASIANPAINT.NS | 0.75        |
# |   5 | Axis Bank Ltd                       | AXISBANK.NS   | 1.15        |
# |   6 | Bajaj Auto Ltd                      | BAJAJ-AUTO.NS | 0.85        |
# |   7 | Bajaj Finance Ltd                   | BAJFINANCE.NS | 1.30        |
# |   8 | Bajaj Finserv Ltd                   | BAJAJFINSV.NS | 1.25        |
# |   9 | Bharat Electronics Ltd              | BEL.NS        | 0.90        |
# |  10 | Bharti Airtel Ltd                   | BHARTIARTL.NS | 0.80        |
# |  11 | Cipla Ltd                           | CIPLA.NS      | 0.55        |
# |  12 | Coal India Ltd                      | COALINDIA.NS  | 0.70        |
# |  13 | Dr. Reddy’s Laboratories Ltd        | DRREDDY.NS    | 0.60        |
# |  14 | Eicher Motors Ltd                   | EICHERMOT.NS  | 1.05        |
# |  15 | Grasim Industries Ltd               | GRASIM.NS     | 1.10        |
# |  16 | HCL Technologies Ltd                | HCLTECH.NS    | 0.90        |
# |  17 | HDFC Bank Ltd                       | HDFCBANK.NS   | 0.95        |
# |  18 | HDFC Life Insurance Co Ltd          | HDFCLIFE.NS   | 0.70        |
# |  19 | Hindustan Unilever Ltd              | HINDUNILVR.NS | 0.55        |
# |  20 | ICICI Bank Ltd                      | ICICIBANK.NS  | 1.10        |
# |  21 | Infosys Ltd                         | INFY.NS       | 0.85        |
# |  22 | ITC Ltd                             | ITC.NS        | 0.60        |
# |  23 | JSW Steel Ltd                       | JSWSTEEL.NS   | 1.35        |
# |  24 | Kotak Mahindra Bank Ltd             | KOTAKBANK.NS  | 0.85        |
# |  25 | Larsen & Toubro Ltd                 | LT.NS         | 1.05        |
# |  26 | Mahindra & Mahindra Ltd             | M&M.NS        | 1.10        |
# |  27 | Maruti Suzuki India Ltd             | MARUTI.NS     | 0.80        |
# |  28 | NTPC Ltd                            | NTPC.NS       | 0.65        |
# |  29 | Oil & Natural Gas Corporation Ltd   | ONGC.NS       | 0.90        |
# |  30 | Power Grid Corporation of India Ltd | POWERGRID.NS  | 0.55        |
# |  31 | Reliance Industries Ltd             | RELIANCE.NS   | 1.00        |
# |  32 | SBI Life Insurance Co Ltd           | SBILIFE.NS    | 0.75        |
# |  33 | State Bank of India                 | SBIN.NS       | 1.20        |
# |  34 | Shriram Finance Ltd                 | SHRIRAMFIN.NS | 1.30        |
# |  35 | Sun Pharmaceutical Industries Ltd   | SUNPHARMA.NS  | 0.65        |
# |  36 | Tata Consultancy Services Ltd       | TCS.NS        | 0.70        |
# |  37 | Tata Consumer Products Ltd          | TATACONSUM.NS | 0.75        |
# |  38 | Tata Motors Ltd                     | TATAMOTORS.NS | 1.40        |
# |  39 | Tata Steel Ltd                      | TATASTEEL.NS  | 1.45        |
# |  40 | Tech Mahindra Ltd                   | TECHM.NS      | 0.95        |
# |  41 | Titan Company Ltd                   | TITAN.NS      | 0.85        |
# |  42 | Trent Ltd                           | TRENT.NS      | 1.10        |
# |  43 | UltraTech Cement Ltd                | ULTRACEMCO.NS | 0.95        |
# |  44 | Wipro Ltd                           | WIPRO.NS      | 0.80        |
# |  45 | Nestlé India Ltd                    | NESTLEIND.NS  | 0.45        |
# |  46 | Jio Financial Services Ltd          | JIOFIN.NS     | 1.20        |
