@echo off
REM Stops any running CivicRoute server (the database keeps running in Docker).
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'app\.main:app' -and $_.CommandLine -like '*civicroute*' -and $_.Name -match 'python' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host ('Stopped CivicRoute (PID ' + $_.ProcessId + ')') }"
