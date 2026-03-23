"""Quick test: verify all 4 core modules can initialize loggers from any directory."""
import os, sys
# Simulate running from a completely different directory
os.chdir('C:\\Windows\\System32')
print(f"CWD: {os.getcwd()}")

# Add script dir to sys.path so imports work
script_dir = r'C:\Users\sreea\OneDrive\Desktop\streamlit-trading-dashboard'
sys.path.insert(0, script_dir)

for module_name, func_name in [
    ('macd_refresh_core', 'get_logger'),
    ('ema_refresh_core', 'get_logger'),
    ('atr_refresh_core', 'get_logger'),
    ('rsi_refresh_core', 'get_logger'),
]:
    mod = __import__(module_name)
    get_logger = getattr(mod, func_name)
    # Force fresh logger by removing cached handlers
    import logging
    logger_name = f'{module_name.replace("_refresh_core","")}_refresh_test'
    logging.Logger.manager.loggerDict.pop(logger_name, None)
    
    try:
        log = get_logger('test')
        # Check where the file handler points
        for h in log.handlers:
            if isinstance(h, logging.FileHandler):
                log_path = h.baseFilename
                in_script_dir = log_path.startswith(script_dir)
                print(f"  {module_name}: log -> {log_path} {'OK' if in_script_dir else 'WRONG DIR!'}")
                h.close()
                # Clean up test log file
                if os.path.exists(log_path):
                    os.remove(log_path)
        # Reset for next module
        log.handlers.clear()
    except Exception as e:
        print(f"  {module_name}: FAILED - {e}")

print("\nDone.")
