"""
READ-ONLY: verify whether the training target in train_sector_model is computed
across ticker boundaries.

sector_df is pd.concat over all sector tickers, then sort_values('trading_date').
train_sector_model then does:
    future_ret = df['close_price'].shift(-7) / df['close_price'] - 1
If consecutive rows are different tickers, that is not a 7-day return -- it is a
price ratio between two unrelated companies.

Usage: python _harness_target_check.py "NASDAQ 100"
"""
import sys
import numpy as np
import pandas as pd
import daily_prediction_job as J

market = sys.argv[1] if len(sys.argv) > 1 else "NASDAQ 100"

conn = J.get_db_connection()
stocks = J.get_top_stocks(conn, market, limit=J.MAX_STOCKS_PER_MARKET)
tickers = stocks['ticker'].tolist()
all_stock_data = J.bulk_load_stock_data(conn, market, tickers)
for d in J.PREDICTION_DAYS:
    J.calibrate_flat_threshold(market, all_stock_data, d)
rsi = J.bulk_load_rsi_data(conn, market, tickers)
idx = J.load_index_returns(conn, market)
sent = J.load_sentiment_data(conn, market)
J.refresh_sector_map_from_db(conn, market)
groups = J.build_sector_groups(tickers, market)
sector, sector_tickers = max(groups.items(), key=lambda kv: len(kv[1]))

sector_df, _ = J.pool_sector_data(sector_tickers, all_stock_data, rsi, idx,
                                  sector_sentiment_df=sent.get(sector))
band = J.FLAT_THRESHOLD_7D_BY_MARKET.get(market, J.FLAT_THRESHOLD_7D)

print(f"\nPool: {sector}  rows={len(sector_df):,}  tickers={sector_df['ticker'].nunique()}")
print(f"FLAT band: {band}")
print("=" * 78)

# --- 1. Does shift(-7) stay within the same ticker? ------------------------
same = (sector_df['ticker'].shift(-7) == sector_df['ticker'])
print(f"\n1. shift(-7) lands on the SAME ticker: {same.sum():,} / {len(sector_df):,} "
      f"({same.mean()*100:.2f}%)")
print(f"   -> {(~same).mean()*100:.2f}% of training rows have a cross-ticker target")

# --- 2. Current (as-shipped) target ---------------------------------------
cur = sector_df['close_price'].shift(-7) / sector_df['close_price'].replace(0, np.nan) - 1
cur_t = np.where(cur > band, 2, np.where(cur < -band, 0, 1))
cur_t = pd.Series(cur_t)[cur.notna()]

# --- 3. Correct per-ticker target -----------------------------------------
g = sector_df.groupby('ticker')['close_price']
fix = g.shift(-7) / sector_df['close_price'].replace(0, np.nan) - 1
fix_t = np.where(fix > band, 2, np.where(fix < -band, 0, 1))
fix_t = pd.Series(fix_t)[fix.notna()]

print("\n2. CLASS BALANCE")
print(f"   {'':<22}{'DOWN':>8}{'FLAT':>8}{'UP':>8}")
for name, t in (("as-shipped (pooled)", cur_t), ("per-ticker (correct)", fix_t)):
    vc = t.value_counts(normalize=True) * 100
    print(f"   {name:<22}{vc.get(0,0):>7.1f}%{vc.get(1,0):>7.1f}%{vc.get(2,0):>7.1f}%")

print("\n3. TARGET MAGNITUDE  (|value| — a 7-day return should be a few percent)")
for name, v in (("as-shipped (pooled)", cur.dropna()), ("per-ticker (correct)", fix.dropna())):
    a = v.abs()
    print(f"   {name:<22} median={a.median()*100:>8.2f}%  p95={a.quantile(.95)*100:>10.2f}%  "
          f"max={a.max()*100:>12.1f}%")

# --- 4. Agreement ----------------------------------------------------------
both = cur.notna() & fix.notna()
agree = (np.where(cur > band, 2, np.where(cur < -band, 0, 1))[both]
         == np.where(fix > band, 2, np.where(fix < -band, 0, 1))[both])
print(f"\n4. LABEL AGREEMENT between the two: {agree.mean()*100:.1f}% "
      f"over {both.sum():,} rows")

# --- 5. Is the corrupted target ticker-identifiable? -----------------------
# If the target is really a cross-ticker price ratio, it should be almost
# constant per ticker -- i.e. predictable from ticker identity alone.
tmp = pd.DataFrame({'ticker': sector_df['ticker'], 'cur': cur, 'fix': fix}).dropna()
for name in ('cur', 'fix'):
    lab = np.where(tmp[name] > band, 2, np.where(tmp[name] < -band, 0, 1))
    tmp[name + '_lab'] = lab
    # share of each ticker's rows taking that ticker's most common label
    purity = tmp.groupby('ticker')[name + '_lab'].agg(
        lambda s: s.value_counts(normalize=True).iloc[0]).mean()
    tag = "as-shipped" if name == 'cur' else "per-ticker"
    print(f"5. {tag:<12} label purity within ticker: {purity*100:.1f}% "
          f"(33% = no ticker information, 100% = target IS the ticker)")

conn.close()
print("\nRead-only — nothing written.")
