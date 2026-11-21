# Резервная копия студии «Искра»: настройки, пресеты, персонажи, workflow, история (без моделей и результатов).
param([string]$Tag = "manual", [switch]$Quiet)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dst = Join-Path $root "backups"
New-Item -ItemType Directory -Force $dst | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$zip = Join-Path $dst "iskra_${stamp}_$Tag.zip"
$tmp = Join-Path $env:TEMP "iskra_backup_$stamp"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
New-Item -ItemType Directory $tmp | Out-Null

$items = @("presets", "config", "prompt-templates", "workflows", "studio", "app\web\src", "app\web\public", "app\web\package.json",
           "app\iskra.ico", "tools\*.py", "tools\*.ps1", "tests", "PROGRESS.md", "README.md", ".env",
           "data\studio.db", "data\settings.json", "data\model_usage.json")
foreach ($i in $items) {
    Get-Item (Join-Path $root $i) -ErrorAction SilentlyContinue | ForEach-Object {
        $rel = $_.FullName.Substring($root.Length + 1)
        $target = Join-Path $tmp $rel
        New-Item -ItemType Directory -Force (Split-Path $target) | Out-Null
        Copy-Item $_.FullName $target -Recurse -Force
    }
}
# картинки персонажей (референсы лежат во входной папке ComfyUI)
$refs = Join-Path $tmp "data\input"
New-Item -ItemType Directory -Force $refs | Out-Null
Get-ChildItem (Join-Path $root "data\input") -File -ErrorAction SilentlyContinue | Where-Object { $_.Length -lt 50MB } | Copy-Item -Destination $refs
# версии движка и нод — чтобы можно было откатиться
$v = @("studio: " + (git -C $root rev-parse HEAD), "ComfyUI: " + (git -C (Join-Path $root "ComfyUI") rev-parse HEAD))
Get-ChildItem (Join-Path $root "ComfyUI\custom_nodes") -Directory | ForEach-Object {
    if (Test-Path (Join-Path $_.FullName ".git")) { $v += "$($_.Name): " + (git -C $_.FullName rev-parse HEAD) }
}
$v | Out-File -Encoding utf8 (Join-Path $tmp "versions.txt")
Get-ChildItem $tmp -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Compress-Archive -Path (Join-Path $tmp "*") -DestinationPath $zip -Force
Remove-Item -Recurse -Force $tmp
# храним 10 последних копий
Get-ChildItem $dst -Filter "iskra_*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 10 | Remove-Item -Force
$mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
if (-not $Quiet) { Write-Host "Резервная копия готова: $zip ($mb МБ)" -ForegroundColor Green }
$zip
