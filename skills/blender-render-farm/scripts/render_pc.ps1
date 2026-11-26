# Render a baked .blend on this PC with N Blender processes at once (each takes every N-th frame).
# Usage:  powershell -File render_pc.ps1 -Blend renders\kitchen_anim.blend -Out renders\frames -Samples 20 -Width 720 -Start 1 -End 945 -Procs 2
param([string]$Blend, [string]$Out, [int]$Samples = 20, [int]$Width = 720, [int]$Start = 1, [int]$End = 945, [int]$Procs = 2)
$B = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force $Out | Out-Null
for ($p = 0; $p -lt $Procs; $p++) {
  $frames = ($Start..$End | Where-Object { ($_ - $Start) % $Procs -eq $p } | Where-Object { -not (Test-Path (Join-Path $Out ("k_{0:D4}.png" -f $_))) }) -join ","
  if (-not $frames) { continue }
  $f = Join-Path $env:TEMP "frames_$p.txt"; Set-Content $f $frames -Encoding ascii
  Start-Process -NoNewWindow -FilePath $B -ArgumentList @("-b", $Blend, "-P", "$here\render_frames.py", "--", $Out, $Samples, $Width, "@$f") -RedirectStandardOutput (Join-Path $Out "log_$p.txt")
}
"started $Procs Blender processes -> $Out  (log_*.txt shows FRAME lines)"
