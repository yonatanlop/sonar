# ══════════════════════════════════════════════════════════════
#  Túnel SSH persistente hacia Oracle — para worker de Facebook
#
#  Redirige:
#    localhost:5432  →  Oracle PostgreSQL
#    localhost:6379  →  Oracle Redis
#
#  Uso: ejecutar este script antes de levantar el worker
#    .\tunnel-facebook.ps1
#
#  Para que inicie automáticamente al encender la PC:
#    Crear tarea en Programador de tareas de Windows apuntando a este script
# ══════════════════════════════════════════════════════════════

$SSH_KEY  = "C:\Users\Anny Vargas\Documents\MIRA\AnalisisRedesSociales\sonar\ssh-key-2026-03-28.key"
$ORACLE_IP = "163.176.221.142"
$ORACLE_USER = "ubuntu"

Write-Host "[Tunel Facebook] Iniciando conexion SSH hacia Oracle..."
Write-Host "[Tunel Facebook] PostgreSQL disponible en localhost:5432"
Write-Host "[Tunel Facebook] Redis disponible en localhost:6379"
Write-Host "[Tunel Facebook] Presiona Ctrl+C para detener"

while ($true) {
    ssh -N `
        -o ServerAliveInterval=30 `
        -o ServerAliveCountMax=3 `
        -o ExitOnForwardFailure=yes `
        -o StrictHostKeyChecking=no `
        -L 5432:localhost:5432 `
        -L 6379:localhost:6379 `
        -i $SSH_KEY `
        "$ORACLE_USER@$ORACLE_IP"

    Write-Host "[Tunel Facebook] Conexion perdida. Reconectando en 10 segundos..."
    Start-Sleep -Seconds 10
}
