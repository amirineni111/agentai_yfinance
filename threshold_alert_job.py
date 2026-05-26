"""
Daily Price Threshold Alert Job
================================
Scans active monitored stocks from NSE_500 and NASDAQ_top100 and sends
a single HTML email alert when the latest close price breaches the
upper_threshold or lower_threshold set on each stock.

Trigger conditions:
  - monitor_startdate IS NOT NULL  (stock is being monitored)
  - monitor_enddate IS NULL        (monitoring still active)
  - upper_threshold or lower_threshold is set
  - latest close_price >= upper_threshold  →  "Target Hit"
  - latest close_price <= lower_threshold  →  "Stop-Loss Triggered"

Schedule via Windows Task Scheduler using run_threshold_alerts.bat
"""

import os
import sys
import pyodbc
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load .env from the same directory as this script
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg, level="INFO"):
    """Print timestamped log line (captured by BAT file into logs/)."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe = msg.encode('ascii', 'replace').decode('ascii')
    print(f"[{ts}] [{level}] {safe}", flush=True)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db_connection():
    """Windows-auth connection — same pattern as other daily jobs."""
    conn_str = (
        "DRIVER={SQL Server};"
        "SERVER=localhost\\MSSQLSERVER01;"
        "DATABASE=stockdata_db;"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)


def fetch_active_monitored_stocks(conn):
    """Return list of dicts for all actively monitored stocks that have at
    least one threshold set, across both NSE 500 and NASDAQ 100."""
    query = """
        SELECT ticker, company_name, upper_threshold, lower_threshold,
               'NSE 500' AS market, 'nse_500_hist_data' AS hist_table
        FROM dbo.NSE_500
        WHERE monitor_startdate IS NOT NULL
          AND monitor_enddate IS NULL
          AND (upper_threshold IS NOT NULL OR lower_threshold IS NOT NULL)

        UNION ALL

        SELECT ticker, company_name, upper_threshold, lower_threshold,
               'NASDAQ 100' AS market, 'nasdaq_100_hist_data' AS hist_table
        FROM dbo.NASDAQ_top100
        WHERE monitor_startdate IS NOT NULL
          AND monitor_enddate IS NULL
          AND (upper_threshold IS NOT NULL OR lower_threshold IS NOT NULL)
    """
    cursor = conn.cursor()
    cursor.execute(query)
    cols = [c[0] for c in cursor.description]
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    cursor.close()
    return rows


def fetch_latest_price(conn, ticker, hist_table):
    """Return (close_price, trading_date) for the most recent row, or (None, None)."""
    query = f"""
        SELECT TOP 1 CAST(close_price AS FLOAT) AS close_price, trading_date
        FROM dbo.{hist_table}
        WHERE ticker = ?
        ORDER BY trading_date DESC
    """
    cursor = conn.cursor()
    cursor.execute(query, (ticker,))
    row = cursor.fetchone()
    cursor.close()
    if row:
        return float(row[0]), row[1]
    return None, None


# ---------------------------------------------------------------------------
# Breach detection
# ---------------------------------------------------------------------------

def detect_breaches(stocks, conn):
    """Return list of alert dicts for every threshold breach found."""
    alerts = []
    for stock in stocks:
        ticker       = stock['ticker']
        company      = stock['company_name'] or ticker
        market       = stock['market']
        hist_table   = stock['hist_table']
        upper        = stock['upper_threshold']
        lower        = stock['lower_threshold']

        close, price_date = fetch_latest_price(conn, ticker, hist_table)

        if close is None:
            log(f"  SKIP {ticker} ({market}) — no price data found", "WARN")
            continue

        price_date_str = price_date.strftime('%Y-%m-%d') if hasattr(price_date, 'strftime') else str(price_date)

        if upper is not None and close >= float(upper):
            alerts.append({
                'Market':          market,
                'Ticker':          ticker,
                'Company':         company,
                'Latest Price':    round(close, 4),
                'Price Date':      price_date_str,
                'Upper Threshold': round(float(upper), 4),
                'Lower Threshold': round(float(lower), 4) if lower is not None else '—',
                'Alert Type':      'Target Hit',
                'alert_class':     'target',
            })
            log(f"  BREACH [{market}] {ticker} — price {close:.4f} >= upper {upper:.4f} (Target Hit)")

        if lower is not None and close <= float(lower):
            alerts.append({
                'Market':          market,
                'Ticker':          ticker,
                'Company':         company,
                'Latest Price':    round(close, 4),
                'Price Date':      price_date_str,
                'Upper Threshold': round(float(upper), 4) if upper is not None else '—',
                'Lower Threshold': round(float(lower), 4),
                'Alert Type':      'Stop-Loss Triggered',
                'alert_class':     'stoploss',
            })
            log(f"  BREACH [{market}] {ticker} — price {close:.4f} <= lower {lower:.4f} (Stop-Loss Triggered)")

    return alerts


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def build_html_email(alerts, run_date):
    """Return an HTML string summarising all breaches in a styled table."""
    rows_html = ""
    for a in alerts:
        if a['alert_class'] == 'target':
            bg = "#d4edda"   # green tint
            icon = "&#127919;"  # 🎯
        else:
            bg = "#f8d7da"   # red tint
            icon = "&#128721;"  # 🛑

        rows_html += f"""
        <tr style="background:{bg};">
          <td>{a['Market']}</td>
          <td><strong>{a['Ticker']}</strong></td>
          <td>{a['Company']}</td>
          <td style="text-align:right;">{a['Latest Price']}</td>
          <td style="text-align:right;">{a['Upper Threshold']}</td>
          <td style="text-align:right;">{a['Lower Threshold']}</td>
          <td>{icon} {a['Alert Type']}</td>
          <td>{a['Price Date']}</td>
        </tr>"""

    html = f"""
    <html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;">
      <h2 style="color:#1a1a2e;">&#128202; Price Threshold Alert</h2>
      <p><strong>{len(alerts)}</strong> threshold breach(es) detected on <strong>{run_date}</strong>.</p>
      <table border="1" cellpadding="6" cellspacing="0"
             style="border-collapse:collapse;width:100%;border-color:#ccc;">
        <thead>
          <tr style="background:#1a1a2e;color:#fff;">
            <th>Market</th><th>Ticker</th><th>Company</th>
            <th>Latest Price</th><th>Upper Threshold</th><th>Lower Threshold</th>
            <th>Alert Type</th><th>Price Date</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
      <br>
      <p style="font-size:12px;color:#888;">
        To stop alerts for a stock, set its <code>monitor_enddate</code> in the master table
        (NSE_500 or NASDAQ_top100) via the Master Data Editor in the Streamlit dashboard.
      </p>
    </body></html>
    """
    return html


def send_email(alerts, run_date):
    """Send a single HTML alert email via Gmail SMTP."""
    smtp_host   = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    smtp_port   = int(os.getenv('SMTP_PORT', '587'))
    smtp_pass   = os.getenv('SMTP_PASSWORD', '')
    alert_email = os.getenv('ALERT_EMAIL', '')

    if not smtp_pass or smtp_pass == 'FILL_IN_GMAIL_APP_PASSWORD':
        log("SMTP_PASSWORD not set in .env — skipping email send.", "ERROR")
        return False
    if not alert_email:
        log("ALERT_EMAIL not set in .env — skipping email send.", "ERROR")
        return False

    subject = f"Price Threshold Alert — {len(alerts)} stock(s) triggered | {run_date}"
    html_body = build_html_email(alerts, run_date)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = alert_email
    msg['To']      = alert_email
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(alert_email, smtp_pass)
            server.sendmail(alert_email, [alert_email], msg.as_string())
        log(f"Email sent to {alert_email} — subject: {subject}")
        return True
    except smtplib.SMTPAuthenticationError:
        log("Gmail authentication failed. Ensure SMTP_PASSWORD is a valid App Password (not your Gmail login password).", "ERROR")
        return False
    except Exception as e:
        log(f"Failed to send email: {e}", "ERROR")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    run_date = datetime.now().strftime("%Y-%m-%d")
    log("=" * 60)
    log("Price Threshold Alert Job starting")
    log(f"Run date : {run_date}")
    log("=" * 60)

    # Connect to database
    try:
        conn = get_db_connection()
        log("Database connection established.")
    except Exception as e:
        log(f"Cannot connect to database: {e}", "ERROR")
        sys.exit(1)

    # Fetch monitored stocks with thresholds
    try:
        stocks = fetch_active_monitored_stocks(conn)
    except Exception as e:
        log(f"Failed to fetch monitored stocks: {e}", "ERROR")
        conn.close()
        sys.exit(1)

    if not stocks:
        log("No active monitored stocks with thresholds set. Nothing to check.")
        conn.close()
        log("Job complete — no email sent.")
        sys.exit(0)

    log(f"Stocks to scan: {len(stocks)}")

    # Detect breaches
    try:
        alerts = detect_breaches(stocks, conn)
    except Exception as e:
        log(f"Error during breach detection: {e}", "ERROR")
        conn.close()
        sys.exit(1)

    conn.close()

    log(f"Breaches found: {len(alerts)}")

    if not alerts:
        log("No threshold breaches detected. No email sent.")
        log("Job complete.")
        sys.exit(0)

    # Send alert email
    success = send_email(alerts, run_date)
    if success:
        log("Job complete — alert email sent successfully.")
        sys.exit(0)
    else:
        log("Job complete — email send failed (check SMTP config in .env).", "ERROR")
        sys.exit(1)


if __name__ == '__main__':
    main()
