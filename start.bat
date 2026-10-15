@echo off
REM Double-click to start CivicRoute (opens the browser when ready).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 pause
