# ══════════════════════════════════════════════════════════════
#  SONAR — Configurar inicio automático del worker de Facebook
#  Ejecutar UNA SOLA VEZ como Administrador:
#    Right-click → "Run as Administrator"
# ══════════════════════════════════════════════════════════════

$PROJECT = "C:\Users\Anny Vargas\Documents\MIRA\AnalisisRedesSociales\version2.5"
$USER    = $env:USERNAME

Write-Host "`n[SONAR] Configurando inicio automático...`n" -ForegroundColor Cyan

# ── Tarea 1: Túnel SSH ─────────────────────────────────────────
$tunnelAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PROJECT\tunnel-facebook.ps1`"" `
    -WorkingDirectory $PROJECT

$tunnelTrigger = New-ScheduledTaskTrigger -AtLogOn -User $USER

$tunnelSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask `
    -TaskName "SONAR - Tunel Facebook" `
    -TaskPath "\SONAR\" `
    -Action $tunnelAction `
    -Trigger $tunnelTrigger `
    -Settings $tunnelSettings `
    -RunLevel Highest `
    -Force | Out-Null

Write-Host "[OK] Tarea 'SONAR - Tunel Facebook' registrada" -ForegroundColor Green

# ── Tarea 2: Worker Docker ─────────────────────────────────────
# Delay de 90s para dar tiempo a que Docker Desktop arranque
$workerAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -Command `"docker compose -f '$PROJECT\docker-compose.facebook-worker.yml' up -d`"" `
    -WorkingDirectory $PROJECT

$workerTrigger = New-ScheduledTaskTrigger -AtLogOn -User $USER
$workerTrigger.Delay = "PT90S"   # esperar 90 segundos antes de ejecutar

$workerSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
    -TaskName "SONAR - Worker Facebook" `
    -TaskPath "\SONAR\" `
    -Action $workerAction `
    -Trigger $workerTrigger `
    -Settings $workerSettings `
    -RunLevel Highest `
    -Force | Out-Null

Write-Host "[OK] Tarea 'SONAR - Worker Facebook' registrada (inicia 90s despues del login)`n" -ForegroundColor Green

Write-Host "Tareas registradas en: Programador de tareas > Biblioteca > SONAR" -ForegroundColor Yellow
Write-Host "Para verificar: taskschd.msc`n" -ForegroundColor Yellow
