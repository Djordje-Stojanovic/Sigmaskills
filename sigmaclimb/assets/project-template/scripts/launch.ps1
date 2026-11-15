# launch.ps1 - stage 0 + start one pass on the box (returns at once). The serving example's launcher.
#   .\scripts\launch.ps1 -Run 0005 -Serve candidate\serve.sh [-Full] [-Record] [-Benchy]
# -Full runs both stages whatever stage 1 says (baseline and A/A runs). -Record also records the gate's references.
param(
  [Parameter(Mandatory)][string]$Run,
  [Parameter(Mandatory)][string]$Serve,
  [switch]$Full,
  [switch]$Record,
  [switch]$Benchy
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
# the box judges stage 1 itself, so it needs the scorer, the settings and the champion it compares with
& $box '[ -d /root/work/scripts ] && rm -rf /root/work/scripts.prev && mv /root/work/scripts /root/work/scripts.prev; mkdir -p /root/work/state /root/work/serve'
& $box -Push -Src scripts -Dst '/root/work/'
foreach ($f in 'project.json', 'evaluator.lock', 'state\champion.json') {
  if (Test-Path $f) { & $box -Push -Src $f -Dst "/root/work/$($f -replace '\','/')" }
}
& $box -Push -Src $Serve -Dst "/root/work/serve/$Run.sh"
$mode = if ($Full -or $Record) { 'full' } else { '' }
$env_ = "RECORD=$([int][bool]$Record) BENCHY=$([int][bool]$Benchy)"
& $box "sed -i 's/\r`$//' /root/work/serve/$Run.sh /root/work/scripts/bench/*.sh; cd /root/work && ($env_ nohup bash scripts/bench/run_experiment.sh /root/runs/$Run /root/work/serve/$Run.sh $mode > /root/work/launch-$Run.log 2>&1 &); sleep 2; echo launched $Run $mode"
