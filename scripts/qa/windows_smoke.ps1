$ErrorActionPreference = 'Stop'
$exe = Join-Path $PSScriptRoot '..\..\dist\TriadaNetwork\TriadaNetwork.exe'
$exe = [System.IO.Path]::GetFullPath($exe)
if (-not (Test-Path $exe)) { throw "Missing desktop artifact: $exe" }
$info = Get-Item $exe
if ($info.Length -lt 100000) { throw "Desktop artifact is unexpectedly small: $($info.Length) bytes" }
Write-Host "Triada desktop artifact OK: $($info.FullName) ($($info.Length) bytes)"
