"""Quick test: run EMA NSE refresh and log result."""
import subprocess, sys

result = subprocess.run(
    [r'C:\Users\sreea\AppData\Local\Programs\Python\Python312\python.exe',
     r'C:\Users\sreea\OneDrive\Desktop\streamlit-trading-dashboard\refresh_ema_nse.py'],
    capture_output=True, text=True, timeout=300,
    cwd=r'C:\Windows\System32'
)
print(f"EXIT CODE: {result.returncode}")
print(f"--- STDOUT (last 20 lines) ---")
for line in result.stdout.strip().splitlines()[-20:]:
    print(line)
print(f"--- STDERR (last 20 lines) ---")
for line in result.stderr.strip().splitlines()[-20:]:
    print(line)
