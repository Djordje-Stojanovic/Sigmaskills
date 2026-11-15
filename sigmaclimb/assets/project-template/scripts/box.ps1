# box.ps1 - run a command on the Vast box, or copy files. Host/port come from state(.tmp)/instance.json.
#   .\scripts\box.ps1 'nvidia-smi'                                   run a remote bash command
#   .\scripts\box.ps1 -Push -Src local\file -Dst /remote/path        copy to the box (recursive)
#   .\scripts\box.ps1 -Pull -Src /remote/path -Dst local\dir         copy from the box (recursive)
param(
  [Parameter(Position = 0)][string]$Command,
  [switch]$Push,
  [switch]$Pull,
  [string]$Src,
  [string]$Dst
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$f = Join-Path $root 'state\instance.json'
if (-not (Test-Path $f)) { $f = Join-Path $root 'state.tmp\instance.json' }
$i = Get-Content $f -Raw | ConvertFrom-Json
$kh = Join-Path $root 'secrets\vast_known_hosts'
$opts = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o', 'StrictHostKeyChecking=accept-new',
          '-o', "UserKnownHostsFile=$kh", '-o', 'LogLevel=ERROR', '-o', 'ServerAliveInterval=30')
if (($Push -or $Pull) -and (-not $Src -or -not $Dst)) { throw 'Push/Pull need -Src and -Dst' }
if ($Push) {
  & scp @opts -r -P $i.ssh_port $Src "root@$($i.ssh_host):$Dst"
} elseif ($Pull) {
  & scp @opts -r -P $i.ssh_port "root@$($i.ssh_host):$Src" $Dst
} else {
  & ssh @opts -p $i.ssh_port "root@$($i.ssh_host)" $Command
}
exit $LASTEXITCODE
