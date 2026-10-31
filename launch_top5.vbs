' StockBot detached launcher — starts top5_bot.py hidden & detached so
' Task Scheduler's console teardown cannot kill it (fixes STATUS_CONTROL_C_EXIT).
' Launched by task "StockBot_Top5_AutoStart".

Dim shell
Set shell = CreateObject("WScript.Shell")

' Run python.exe directly with the script path as argument.
' Window style 0 = hidden, False = do not wait (fully detached).
shell.Run """C:\Users\Wande\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"" ""C:\Users\Wande\stockbot\top5_bot.py""", 0, False
