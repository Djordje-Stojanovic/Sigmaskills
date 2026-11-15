# wait.ps1 - wait until a run on the box writes DONE, then copy its raw files to runs/<id>/raw.
# Meant for run_in_background: it prints one line per stage change and a final status line.
# SSH hiccups never end the wait: every box call is retried (night of 2026-10-23 lost 8 h to one failure).
#   .\scripts\wait.ps1 -Run 0005 [-MaxMinutes 90]
param(
  [Parameter(Mandatory)][string]$Run,
  [int]$MaxMinutes = 90
)
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$box = Join-Path $PSScriptRoot 'box.ps1'
$t0 = Get-Date
$last = ''
while ($true) {
  $state = $null
  try { $state = & $box "test -f /root/runs/$Run/DONE && echo DONE || tail -1 /root/runs/$Run/progress.log 2>/dev/null" 2>$null } catch { $state = $null }
  if ($state -and $state -ne $last) { Write-Host "$((Get-Date).ToString('HH:mm:ss')) $state"; $last = $state }
  if ($state -match '^DONE') { break }
  if (((Get-Date) - $t0).TotalMinutes -gt $MaxMinutes) { Write-Host "WAIT TIMEOUT after $MaxMinutes min"; exit 3 }
  Start-Sleep 30
}
New-Item -ItemType Directory -Force "runs\$Run\raw" | Out-Null
for ($i = 1; $i -le 10; $i++) {
  try { & $box -Pull -Src "/root/runs/$Run/." -Dst "runs\$Run\raw" 2>$null } catch {}
  if (Test-Path "runs\$Run\raw\meta.json") { break }
  Write-Host "pull attempt $i failed, retrying in 30 s"; Start-Sleep 30
}
$meta = Get-Content "runs\$Run\raw\meta.json" -Raw | ConvertFrom-Json
Write-Host "RUN $Run FINISHED status=$($meta.status) start_s=$($meta.start_s) low_mem_gib=$($meta.low_mem_gib) kv=$($meta.kv_tokens) minutes=$([math]::Round(((Get-Date)-$t0).TotalMinutes,1))"
