"""
READ-ONLY harness for the Phase 6 changes.

Exercises train_sector_model -> predict_for_ticker_v4 exactly as the daily job
does, but never calls store_prediction. Safe to run any number of times per day
(the job's dedup would otherwise make same-day reruns a no-op).

Usage:  python harness_phase6.py "Forex"
"""
import sys
import numpy as np
import daily_prediction_job as J

market = sys.argv[1] if len(sys.argv) > 1 else "Forex"

conn = J.get_db_connection()
stocks = J.get_top_stocks(conn, market, limit=J.MAX_STOCKS_PER_MARKET)
tickers = stocks['ticker'].tolist()
print(f"{market}: {len(tickers)} tickers")

all_stock_data = J.bulk_load_stock_data(conn, market, tickers)
for d in J.PREDICTION_DAYS:
    J.calibrate_flat_threshold(market, all_stock_data, d)
band = J.FLAT_THRESHOLD_7D_BY_MARKET.get(market, J.FLAT_THRESHOLD_7D)
print(f"calibrated band = {band}")

rsi = J.bulk_load_rsi_data(conn, market, tickers)
idx = J.load_index_returns(conn, market)
sent = J.load_sentiment_data(conn, market)
groups = J.build_sector_groups(tickers, market)

rows = []
for sector, sector_tickers in groups.items():
    sector_df, ticker_latest = J.pool_sector_data(
        sector_tickers, all_stock_data, rsi, idx,
        sector_sentiment_df=sent.get(sector)
    )
    if len(sector_df) < J.MIN_SECTOR_SAMPLES:
        print(f"  {sector}: too thin ({len(sector_df)}), skipped")
        continue

    print(f"\n  Sector {sector}: {len(sector_df):,} pooled rows")
    (lgb_m, lr_m, sc, wf, w1, w2, cal) = J.train_sector_model(sector_df, 7, market)
    if lgb_m is None:
        print("    training failed")
        continue

    for ticker, tdf in ticker_latest.items():
        out = J.predict_for_ticker_v4(tdf, lgb_m, lr_m, sc, wf, 7,
                                      lgb_weight=w1, lr_weight=w2, calibrator=cal)
        if out[0] is None:
            continue
        _, chg, conf, pdir, suspect = out
        rows.append((ticker, pdir, conf, chg, suspect))

if not rows:
    print("\nNo predictions produced.")
    sys.exit(1)

confs = np.array([r[2] for r in rows])
print(f"\n{'='*62}\nCONFIDENCE DISTRIBUTION  (n={len(confs)})")
print(f"  min={confs.min():.2f}  p25={np.percentile(confs,25):.2f}  "
      f"median={np.median(confs):.2f}  p75={np.percentile(confs,75):.2f}  max={confs.max():.2f}")
print(f"  distinct values: {len(np.unique(np.round(confs,2)))}")

at_old_bounds = np.sum((np.round(confs, 2) == 30.00) | (np.round(confs, 2) == 80.00))
print(f"  pinned at old [30,80] clamp: {at_old_bounds}  (expect 0)")

mags = np.array([abs(r[3]) for r in rows])
n_susp = sum(1 for r in rows if r[4])
print(f"\nMAGNITUDE SANITY  (cap={J.MAX_PREDICTED_MOVE_PCT}%)")
print(f"  |predicted_change_pct|: max={mags.max():.1f}%  median={np.median(mags):.1f}%")
print(f"  over cap: {(mags > J.MAX_PREDICTED_MOVE_PCT + 1e-9).sum()}  (expect 0)")
print(f"  flagged PRICE_ARTIFACT: {n_susp}/{len(rows)}")

print("\nDIRECTION MIX / actionability at "
      f"ACTIONABLE_CONFIDENCE_MIN={J.ACTIONABLE_CONFIDENCE_MIN}")
for d in ('UP', 'FLAT', 'DOWN'):
    sub = [r for r in rows if r[1] == d]
    if not sub:
        continue
    c = np.array([r[2] for r in sub])
    act = sum(1 for r in sub
              if d != 'FLAT' and not r[4] and r[2] >= J.ACTIONABLE_CONFIDENCE_MIN)
    print(f"  {d:<5}: n={len(sub):<5} conf mean={c.mean():.1f}  "
          f"range=[{c.min():.1f},{c.max():.1f}]  actionable={act}")

conn.close()
print("\nRead-only harness complete — nothing written.")
