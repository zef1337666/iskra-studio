# Безопасное обновление «Искры»: резервная копия → обновление ComfyUI и нод → самопроверка → при ошибке откат.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "venv\Scripts\python.exe"
$uv = Join-Path $root "tools\uv\uv.exe"
$env:UV_CACHE_DIR = Join-Path $root "tools\uv-cache"
$env:VIRTUAL_ENV = Join-Path $root "venv"
$env:PYTHONUTF8 = "1"
function Say($t, $c = "White") { Write-Host $t -ForegroundColor $c }

try { Invoke-WebRequest "http://127.0.0.1:7860/api/status" -UseBasicParsing -TimeoutSec 2 | Out-Null; Say "Сначала закройте окно «Искра», потом запустите обновление снова." Yellow; exit 1 } catch {}
if (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*ComfyUI\main.py*" }) {
    Say "Движок ComfyUI ещё работает. Закройте «Искру» и подождите 10 секунд." Yellow; exit 1
}

Say "1/5 Резервная копия…" Cyan
$backup = & (Join-Path $PSScriptRoot "backup.ps1") -Tag "before-update" -Quiet
Say "   $backup"
$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$freeze = Join-Path $root "backups\freeze_$stamp.txt"
& $uv pip freeze | Out-File -Encoding utf8 $freeze

# запоминаем версии для отката
$repos = @{ "ComfyUI" = (Join-Path $root "ComfyUI") }
Get-ChildItem (Join-Path $root "ComfyUI\custom_nodes") -Directory | Where-Object { Test-Path (Join-Path $_.FullName ".git") } | ForEach-Object { $repos[$_.Name] = $_.FullName }
$before = @{}
foreach ($k in $repos.Keys) { $before[$k] = (git -C $repos[$k] rev-parse HEAD) }

# torch и ускорения не трогаем: они подобраны под RTX 50 и CUDA 13
$cons = Join-Path $env:TEMP "iskra_constraints.txt"
& $uv pip freeze | Select-String -Pattern "^(torch|torchvision|torchaudio|sageattention|triton-windows)==" | ForEach-Object { $_.Line } | Out-File -Encoding ascii $cons

Say "2/5 Обновление ComfyUI и нод…" Cyan
$changed = @()
foreach ($k in $repos.Keys) {
    git -C $repos[$k] fetch -q 2>$null
    git -C $repos[$k] pull -q --ff-only 2>$null
    $now = git -C $repos[$k] rev-parse HEAD
    if ($now -ne $before[$k]) { $changed += $k; Say "   обновлено: $k" }
}
if (-not $changed) { Say "   всё уже последних версий" }

Say "3/5 Зависимости…" Cyan
$reqs = @(Join-Path $root "ComfyUI\requirements.txt") + ($repos.Values | ForEach-Object { Join-Path $_ "requirements.txt" } | Where-Object { Test-Path $_ })
foreach ($r in ($reqs | Select-Object -Unique)) { & $uv pip install -q -r $r -c $cons 2>&1 | Out-Null }

Say "4/5 Самопроверка движка…" Cyan
$log = Join-Path $root "data\update_check.log"
& $py (Join-Path $root "ComfyUI\main.py") --quick-test-for-ci --cpu --extra-model-paths-config (Join-Path $root "config\extra_model_paths.yaml") *> $log
$text = Get-Content $log -Raw
$torch = & $py -c "import torch,sageattention;print(torch.__version__, torch.cuda.is_available())"
$bad = ($LASTEXITCODE -ne 0) -or ($text -match "IMPORT FAILED") -or ($torch -notmatch "True")

if ($bad) {
    Say "5/5 Проверка не прошла — откатываю обновление…" Red
    foreach ($k in $repos.Keys) { git -C $repos[$k] checkout -q $before[$k] 2>$null; git -C $repos[$k] reset -q --hard $before[$k] 2>$null }
    & $uv pip install -q -r $freeze 2>&1 | Out-Null
    Say "Откат выполнен, студия в прежнем рабочем состоянии. Подробности: $log" Yellow
    exit 2
}

Say "5/5 Пересборка интерфейса…" Cyan
if (Get-Command npm -ErrorAction SilentlyContinue) {
    Push-Location (Join-Path $root "app\web"); npm install --no-audit --no-fund *> $null; npx vite build *> $null; Pop-Location
}
Say "Готово. Обновлено: $(if ($changed) { $changed -join ', ' } else { 'ничего (всё актуально)' }). Запускайте «Искру»." Green
