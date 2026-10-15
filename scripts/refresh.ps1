# Weekly data refresh: re-crawl official PAN pages, detect changes, update Hindi/Telugu translations.
#   powershell -ExecutionPolicy Bypass -File C:\Users\karth\civicroute\scripts\refresh.ps1
# To run it automatically every Sunday 06:00 (run once, in your own terminal):
#   schtasks /Create /SC WEEKLY /D SUN /ST 06:00 /TN "CivicRoute refresh" /TR "powershell -ExecutionPolicy Bypass -File C:\Users\karth\civicroute\scripts\refresh.ps1"
$ErrorActionPreference = "Continue"
$backend = Join-Path (Split-Path $PSScriptRoot -Parent) "backend"
$log = Join-Path $backend "data\refresh.log"
Set-Location $backend
"`n===== $(Get-Date -Format 'yyyy-MM-dd HH:mm') refresh =====" | Out-File $log -Append -Encoding utf8

Write-Host "1/2 Re-crawling official sources and updating the index..." -ForegroundColor Cyan
python -m ingest.run 2>&1 | Tee-Object -FilePath $log -Append

Write-Host "2/2 Translating new or changed text (Hindi, Telugu)..." -ForegroundColor Cyan
python -m ingest.translate 2>&1 | Tee-Object -FilePath $log -Append

$report = Get-Content (Join-Path $backend "data\ingest_report.json") -Raw | ConvertFrom-Json
if ($report.cards_to_review.Count -gt 0) {
    Write-Host "ACTION NEEDED: official pages changed - re-check these service cards in data\services.json:" -ForegroundColor Yellow
    $report.cards_to_review | ForEach-Object { Write-Host "  - $($_.title)" -ForegroundColor Yellow }
} else {
    Write-Host "No official page changes detected." -ForegroundColor Green
}
if ($report.failed_sources.Count -gt 0) {
    Write-Host "Could not fetch (site down or blocking bots):" -ForegroundColor DarkYellow
    $report.failed_sources | ForEach-Object { Write-Host "  - $($_.url) ($($_.status))" -ForegroundColor DarkYellow }
}
Write-Host "Done. Restart the app (start.bat) to serve the refreshed data. Log: $log" -ForegroundColor Green
