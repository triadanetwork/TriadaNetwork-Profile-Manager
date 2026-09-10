param([string]$Root = (Get-Location))
$ErrorActionPreference = "Stop"
$exe = Join-Path $Root "dist\TriadaNetwork\TriadaNetwork.exe"
if (!(Test-Path $exe)) { throw "Missing TriadaNetwork.exe: $exe" }
$item = Get-Item $exe
if ($item.Length -lt 5MB) { throw "Desktop executable looks too small: $($item.Length) bytes" }
$iss = Join-Path $Root "packaging\installer\triada-network.iss"
if (!(Test-Path $iss)) { throw "Missing installer script" }
Write-Host "Windows release preflight: PASS"
Write-Host "EXE=$($item.FullName)"
Write-Host "SIZE=$($item.Length)"
