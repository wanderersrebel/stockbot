import subprocess
import sys
import os
import time
import datetime

STOCKBOT_DIR = r"C:\Users\Wande\stockbot"
WATCHDOG = os.path.join(STOCKBOT_DIR, "watchdog.py")
PYTHON = r"C:\Users\Wande\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"

def main():
    log_path = os.path.join(STOCKBOT_DIR, "watchdog_launcher.log")
    with open(log_path, "a") as log:
        log.write(f"[{datetime.datetime.now().isoformat()}] launcher: starting watchdog detach\n")
    
    # Use CREATE_NEW_PROCESS_GROUP + DETACHED_PROCESS so the child survives
    # even if the parent (this launcher) exits.
    proc = subprocess.Popen(
        [PYTHON, WATCHDOG],
        cwd=STOCKBOT_DIR,
        stdout=open(os.path.join(STOCKBOT_DIR, "watchdog.log"), "a"),
        stderr=subprocess.STDOUT,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    with open(log_path, "a") as log:
        log.write(f"[{datetime.datetime.now().isoformat()}] launcher: watchdog spawned PID {proc.pid}\n")
    
    # Give it a moment to start, then verify
    time.sleep(2)
    try:
        proc.kill()  # kill the PARENT (launcher), not the child — child is detached
    except:
        pass
    
    # Check if child survived
    time.sleep(1)
    with open(log_path, "a") as log:
        log.write(f"[{datetime.datetime.now().isoformat()}] launcher: launcher exiting, child should be independent\n")
    
    # Quick verify: check if watchdog log has the "starting" line
    try:
        with open(os.path.join(STOCKBOT_DIR, "watchdog.log")) as wf:
            last_lines = wf.read().strip().split('\n')[-3:]
            for line in last_lines:
                log.write(f"[{datetime.datetime.now().isoformat()}] launcher: watchdog log: {line}\n")
    except:
        pass

if __name__ == "__main__":
    main()
