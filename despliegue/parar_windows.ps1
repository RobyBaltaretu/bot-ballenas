# Deja ESTE PC sin nada del bot en marcha, para pasarlo a un servidor (Hetzner, Oracle...): nunca deben funcionar
# dos bots a la vez. Lo lanza herramientas\parar-para-migrar.bat.
#   1) Si el bot sigue en marcha, pide cerrar su ventana (apagado ordenado) y espera.
#   2) Para el panel y el carry que queden en segundo plano (solo los de ESTA carpeta).
#   3) Quita el arranque automatico y las tareas programadas de laboratorio e investigacion.
# No toca datos, .env ni config.json, ni el tunel de Cloudflare (se desconecta despues, cuando el servidor ya lo tenga).
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$Raiz = Split-Path -Parent $PSScriptRoot
$patron = [regex]::Escape($Raiz)

function Procesos($que) {
    Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -match $patron -and $_.CommandLine -match $que }
}

Write-Host ">> 1/3 El bot" -ForegroundColor Cyan
if (Procesos 'bot\.py') {
    Write-Host "El bot SIGUE EN MARCHA. Cierra su ventana ('Bot de ballenas - NO CERRAR ESTA VENTANA') para que se apague"
    Write-Host "de forma ordenada. Espero hasta 2 minutos..."
    $limite = (Get-Date).AddMinutes(2)
    while ((Procesos 'bot\.py') -and (Get-Date) -lt $limite) { Start-Sleep 3 }
    if (Procesos 'bot\.py') {
        $r = Read-Host "Sigue en marcha. ¿Lo paro a la fuerza? (S/N)  (en simulado no se pierde nada: el registro y la cuenta se guardan en cada cambio)"
        if ($r -notmatch '^[sS]') { Write-Host "No he parado nada. Vuelve a lanzarlo cuando el bot este cerrado."; Read-Host "Pulsa Enter para cerrar"; exit 1 }
        Procesos 'bot\.py' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
}
Write-Host "   bot parado." -ForegroundColor Green

Write-Host ">> 2/3 Panel y carry en segundo plano" -ForegroundColor Cyan
$sueltos = @(Procesos 'panel\.py|carry\.motor|agresiva\.motor|laboratorio|investigacion')
$sueltos | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Host "   $($sueltos.Count) proceso(s) parado(s)." -ForegroundColor Green

Write-Host ">> 3/3 Arranque automatico y tareas programadas" -ForegroundColor Cyan
Remove-Item ([Environment]::GetFolderPath('Startup') + '\Bot de ballenas.lnk') -ErrorAction SilentlyContinue
foreach ($t in 'Bot ballenas - laboratorio semanal', 'Bot ballenas - investigacion') {
    if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $t -Confirm:$false
        Write-Host "   tarea '$t' quitada."
    }
}
Write-Host ""
Write-Host "Listo: en este PC ya no queda nada del bot en marcha ni programado." -ForegroundColor Green
Write-Host "Siguiente paso: herramientas\preparar-migracion.bat"
Write-Host "Para volver a usarlo en el PC: INICIAR.bat (y los activar-*.bat de herramientas)."
Read-Host "Pulsa Enter para cerrar"
