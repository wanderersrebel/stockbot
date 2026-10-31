@echo off
echo Starting StockBot watchdog at %DATE% %TIME% >> "C:\Users\Wande\stockbot\watchdog_launcher.log"
"C:\Users\Wande\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" "C:\Users\Wande\stockbot\watchdog.py" >> "C:\Users\Wande\stockbot\watchdog.log" 2>&1
echo Watchdog exited at %DATE% %TIME% >> "C:\Users\Wande\stockbot\watchdog_launcher.log"
