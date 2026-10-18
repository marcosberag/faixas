# Ejecutar desde la raiz despues de generar, verificar y commitear el visor.
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Push-Location -LiteralPath $taskRoot
try {
    $taskPending = git status --porcelain -- salidas/visor/pontevedra
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo consultar git.' }
    if ($taskPending) { throw 'Hay cambios del visor sin commit. Revisalos y guardalos antes de publicar.' }
    $taskSiteCommit = git subtree split --prefix=salidas/visor/pontevedra HEAD
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar la rama del visor.' }
    git push origin "${taskSiteCommit}:refs/heads/gh-pages"
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo publicar gh-pages. No se fuerza ni sobrescribe su historial.' }
    Write-Host 'Visor enviado. GitHub Pages lo desplegara desde gh-pages.'
} finally {
    Pop-Location
}
