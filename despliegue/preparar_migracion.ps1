# Prepara el paquete para pasar el bot de este PC al servidor: código + datos acumulados, SIN el archivo .env.
# Lo lanza herramientas\preparar-migracion.bat. Deja bot-migracion.tar.gz en el Escritorio.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$Raiz = Split-Path -Parent $PSScriptRoot
$Padre = Split-Path -Parent $Raiz
$Nombre = Split-Path -Leaf $Raiz
$Salida = Join-Path ([Environment]::GetFolderPath("Desktop")) "bot-migracion.tar.gz"

# ¿Sigue el bot en marcha? (escribe su estado cada pocos segundos)
$vivos = @("panel_datos.json", "carry_estado.json", "agresiva_estado.json") | ForEach-Object { Join-Path $Raiz $_ } |
    Where-Object { (Test-Path $_) -and ((Get-Date) - (Get-Item $_).LastWriteTime).TotalSeconds -lt 120 }
if ($vivos) {
    Write-Host "Parece que el bot o el carry SIGUEN EN MARCHA en este PC (han escrito datos hace menos de 2 minutos)." -ForegroundColor Yellow
    Write-Host "Cierra antes su ventana para que los datos copiados sean los últimos y no queden dos bots funcionando."
    $r = Read-Host "¿Seguir de todas formas? (S/N)"
    if ($r -notmatch '^[sS]') { exit 1 }
}
if (-not (Get-Command tar -ErrorAction SilentlyContinue)) {
    Write-Host "Este Windows no tiene 'tar' (viene con Windows 10 de 2018 en adelante)." -ForegroundColor Red
    Read-Host "Pulsa Enter para cerrar"; exit 1
}
Write-Host ">> Empaquetando el bot y sus datos (sin .env ni el entorno de Python)..." -ForegroundColor Cyan
& tar -czf $Salida --exclude=".venv" --exclude=".env" --exclude="datos_backtest" --exclude="__pycache__" `
      --exclude=".ruff_cache" --exclude="*.lock" --exclude="*.tmp" --exclude="bot.log*" --exclude="logs" `
      -C $Padre $Nombre
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Salida)) {
    Write-Host "No se pudo crear el paquete." -ForegroundColor Red; Read-Host "Pulsa Enter para cerrar"; exit 1
}
$mb = [math]::Round((Get-Item $Salida).Length / 1MB, 1)
Write-Host ""
Write-Host "Listo: $Salida ($mb MB). No contiene tus claves." -ForegroundColor Green
Write-Host ""
Write-Host "Para subirlo al servidor, en PowerShell (cambia la IP):"
Write-Host "  Hetzner:  scp `"$Salida`" root@IP_DEL_SERVIDOR:/root/"
Write-Host "  Oracle:   scp -i `"RUTA\A\TU\clave.key`" `"$Salida`" ubuntu@IP_DEL_SERVIDOR:~"
Write-Host "Y sigue la guia despliegue\GUIA_HETZNER.md (o GUIA_ORACLE.md)."
Read-Host "Pulsa Enter para cerrar"
