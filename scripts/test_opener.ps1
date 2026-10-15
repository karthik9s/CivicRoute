# Diagnostic: checks that the browser-opener helper used by start.ps1 can see the running app.
# Writes the result to a file instead of opening the browser.
$out = Join-Path $env:TEMP "civicroute_opener_test.txt"
Remove-Item $out -ErrorAction SilentlyContinue
$opener = "for (`$i = 0; `$i -lt 10; `$i++) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 " +
          "-Uri 'http://127.0.0.1:8000/api/health' | Out-Null; 'READY' | Out-File '$out'; exit } catch { Start-Sleep -Seconds 2 } }; 'TIMEOUT' | Out-File '$out'"
$p = Start-Process powershell -WindowStyle Hidden -PassThru -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $opener)
$p.WaitForExit(30000) | Out-Null
Write-Host ("Opener helper result: " + (Get-Content $out -ErrorAction SilentlyContinue))
