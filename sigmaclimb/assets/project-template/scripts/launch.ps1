# launch.ps1 - stage 0 + start one measured run on the box (returns at once; the run takes ~15-30 min).
#   .\scripts\launch.ps1 -Run 0005 -Serve candidate\serve.sh [-Record]
param(
  [Parameter(Mandatory)][string]$Run,
  [Parameter(Mandatory)][string]$Serve,
  [switch]$Record,
  [switch]$NoBenchy
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$box = Join-Path $PSScriptRoot 'box.ps1'
New-Item -ItemType Directory -Force "runs\$Run" | Out-Null
python scripts\bench\invariants.py $Serve "runs/$Run"
if ($LASTEXITCODE -ne 0) { throw 'invariants.py failed to run' }
$inv = Get-Content "runs\$Run\invariants.json" -Raw | ConvertFrom-Json
if (-not $inv.ok) { Write-Host "NOT LAUNCHED: invariants broken -> verdict VOID"; exit 2 }
& $box -Push -Src $Serve -Dst "/root/work/serve/$Run.sh"
$mode = if ($Record) { 'record' } else { '' }
$benchyEnv = if ($NoBenchy) { 'BENCHY=0' } else { 'BENCHY=1' }
& $box "sed -i 's/\r`$//' /root/work/serve/$Run.sh; rm -rf /root/runs/$Run; cd /root/work/bench && ($benchyEnv nohup bash run_experiment.sh $Run /root/work/serve/$Run.sh $mode > /root/work/launch-$Run.log 2>&1 &); sleep 2; echo launched $Run $benchyEnv"
