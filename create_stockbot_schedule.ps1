# StockBot Auto-Start Scheduler — run from your normal Windows desktop
# (PowerShell as user Wande — no admin needed for your own tasks)
#
# Creates: daily task at 09:25 ET that launches top5_bot.py
#   -> bot's own code waits (standby) if 09:25 is before 09:30 market open
#   -> scans every 15 min Mon-Fri 09:30-16:00 ET
#   -> stops looping after first trade of the day
#
# Paste this whole block into PowerShell on your desktop and run it.

$Action = New-ScheduledTaskAction -Execute 'C:\Users\Wande\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe' -Argument 'C:\Users\Wande\stockbot\top5_bot.py'
$Trigger = New-ScheduledTaskTrigger -Daily -At '09:25'
# NO -RunLevel Highest — that needs elevation. Leave at default (limited) for your own user.

Register-ScheduledTask -TaskName 'StockBot_Top5_AutoStart' -Action $Action -Trigger $Trigger -Force

Write-Host "OK: StockBot_Top5_AutoStart scheduled daily at 09:25 ET"
