# Настройка автозапуска Courier Monitor каждое воскресенье в 8:00
# Запускать от имени администратора: правой кнопкой -> "Запуск от имени администратора"

# ── Настройки ────────────────────────────────────────────────────────────────
$TaskName = "CourierMonitor"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonPath = (Get-Command python).Source
$ScriptPath = Join-Path $ScriptDir "run_monitor.py"
$ApiKey = $env:ANTHROPIC_API_KEY

if (-not $ApiKey) {
    Write-Host "❌ ANTHROPIC_API_KEY не найден. Установи переменную и запусти снова." -ForegroundColor Red
    Write-Host "   `$env:ANTHROPIC_API_KEY='sk-ant-...'" -ForegroundColor Yellow
    exit 1
}

# ── Создаём задачу ───────────────────────────────────────────────────────────

# Действие: запустить python run_monitor.py
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument $ScriptPath `
    -WorkingDirectory $ScriptDir

# Триггер: каждое воскресенье в 08:00
$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Sunday `
    -At "08:00AM"

# Настройки: запускать даже если не залогинен, не останавливать через час
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RunOnlyIfNetworkAvailable $true

# Переменная окружения для API ключа
$Env = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

# Регистрируем задачу
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Env `
    -Force | Out-Null

# Добавляем API ключ в переменные окружения системы (постоянно)
[System.Environment]::SetEnvironmentVariable(
    "ANTHROPIC_API_KEY",
    $ApiKey,
    [System.EnvironmentVariableTarget]::User
)

Write-Host "✅ Задача '$TaskName' создана успешно!" -ForegroundColor Green
Write-Host "   Запуск: каждое воскресенье в 08:00" -ForegroundColor Cyan
Write-Host "   Скрипт: $ScriptPath" -ForegroundColor Cyan
Write-Host "   API ключ сохранён в переменных окружения пользователя" -ForegroundColor Cyan
Write-Host ""
Write-Host "Управление задачей:" -ForegroundColor Yellow
Write-Host "  Запустить вручную: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  Удалить задачу:    Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
Write-Host "  Статус задачи:     Get-ScheduledTask -TaskName '$TaskName'"
