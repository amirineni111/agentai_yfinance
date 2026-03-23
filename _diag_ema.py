"""Diagnose EMA NSE refresh failure by running from System32 dir."""
import subprocess
result = subprocess.run(
    [r'C:\Users\sreea\AppData\Local\Programs\Python\Python312\python.exe',
     r'C:\Users\sreea\OneDrive\Desktop\streamlit-trading-dashboard\refresh_ema_nse.py'],
    capture_output=True, text=True, timeout=300,
    cwd=r'C:\Windows\System32'
)
with open(r'C:\Users\sreea\OneDrive\Desktop\streamlit-trading-dashboard\_ema_diag.txt', 'w') as f:
    f.write(f"EXIT CODE: {result.returncode}\n")
    f.write(f"--- STDOUT ---\n{result.stdout[-3000:]}\n")
    f.write(f"--- STDERR ---\n{result.stderr[-3000:]}\n")
print("Done. Check _ema_diag.txt")
