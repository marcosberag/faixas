# Vigilante de la corrida provincial: bucle que comprueba cada 5 min si
# procesa_comarca.py sigue vivo y lo relanza si no (es reanudable, no repite
# trabajo). Cura los cierres silenciosos de Windows (Application Hang tras
# transiciones de sesion) sin intervencion. Se lanza huerfano:
#   Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','scripts\vigila_pontevedra.ps1' -WindowStyle Hidden
# Se para matando su PID (datos/procesado/lidar/vigilante.pid) o al completarse
# la malla: si el pipeline termina con todo hecho, sale en segundos y el
# vigilante lo detecta por la marca 'hecho' y se apaga solo.

$raiz = 'C:\Users\PC\¿\mis\personal\faixas'
$vlog = Join-Path $raiz 'datos\procesado\lidar\vigilante.log'
$PID | Set-Content (Join-Path $raiz 'datos\procesado\lidar\vigilante.pid')
Add-Content $vlog "$(Get-Date -Format 'yyyy-MM-dd HH:mm') vigilante arrancado (PID $PID)"

$relanzamientos_rapidos = 0
while ($true) {
    $corriendo = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'procesa_comarca' }

    if (-not $corriendo) {
        # si el pipeline sale limpio en <120 s dos veces seguidas es que la
        # malla esta completa: no hay nada que relanzar, el vigilante se apaga
        if ($relanzamientos_rapidos -ge 2) {
            Add-Content $vlog "$(Get-Date -Format 'yyyy-MM-dd HH:mm') malla completa (2 salidas rapidas seguidas): vigilante fuera"
            break
        }
        $sello = Get-Date -Format 'yyyyMMdd_HHmm'
        $log = Join-Path $raiz "datos\procesado\lidar\pontevedra_run_$sello.log"
        $err = Join-Path $raiz "datos\procesado\lidar\pontevedra_run_${sello}_err.log"
        $t0 = Get-Date
        $p = Start-Process -FilePath python `
            -ArgumentList 'scripts\procesa_comarca.py', '--malla', 'datos\procesado\malla_lidar_pontevedra.csv' `
            -WorkingDirectory $raiz -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $log -RedirectStandardError $err
        $p.Id | Set-Content (Join-Path $raiz 'datos\procesado\lidar\pontevedra_run.pid')
        Add-Content $vlog "$(Get-Date -Format 'yyyy-MM-dd HH:mm') muerto -> relanzado PID $($p.Id), log $sello"
        # espera a que muera o a que lleve 120 s vivo, para medir salidas rapidas
        $salio = $p.WaitForExit(120000)
        if ($salio -and ((Get-Date) - $t0).TotalSeconds -lt 120) {
            $relanzamientos_rapidos += 1
        } else {
            $relanzamientos_rapidos = 0
        }
    }
    Start-Sleep -Seconds 300
}
