$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
try {
    $pythonCandidates = @()
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) { $pythonCandidates += @{ Path = $launcher.Source; Args = @('-3') } }
    foreach ($commandName in @('python', 'python3')) {
        $installedCommand = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($installedCommand -and $installedCommand.Source -notlike '*\Microsoft\WindowsApps\*') {
            $pythonCandidates += @{ Path = $installedCommand.Source; Args = @() }
        }
    }
    $installRoots = @("$env:LOCALAPPDATA\Programs\Python", "$env:ProgramFiles", "$env:LOCALAPPDATA\Python")
    foreach ($installRoot in $installRoots) {
        if (Test-Path -LiteralPath $installRoot) {
            foreach ($folder in (Get-ChildItem -LiteralPath $installRoot -Directory -Filter 'Python*' -ErrorAction SilentlyContinue)) {
                $pythonPath = Join-Path $folder.FullName 'python.exe'
                if (Test-Path -LiteralPath $pythonPath) { $pythonCandidates += @{ Path = $pythonPath; Args = @() } }
            }
        }
    }
    $selectedPython = $null
    # Las instalaciones de Microsoft Store tienen ejecutables propios, no solo aliases.
    $storeRoot = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'
    if (Test-Path -LiteralPath $storeRoot) {
        foreach ($folder in (Get-ChildItem -LiteralPath $storeRoot -Directory -Filter 'PythonSoftwareFoundation.Python.3*' -ErrorAction SilentlyContinue)) {
            $pythonPath = Join-Path $folder.FullName 'python.exe'
            if (Test-Path -LiteralPath $pythonPath) { $pythonCandidates += @{ Path = $pythonPath; Args = @() } }
        }
    }
    foreach ($candidate in $pythonCandidates) {
        try {
            $candidateArguments = @($candidate.Args) + @('-c', 'import sys; assert sys.version_info >= (3,11); print(sys.executable)')
            $probeResult = & $candidate.Path @candidateArguments 2>$null
            if ($LASTEXITCODE -eq 0) { $selectedPython = $candidate; break }
        } catch { }
    }
    if (-not $selectedPython) {
        throw 'No encontramos Python. Instala Python 3.12, cierra esta ventana y abre ABRIR de nuevo. Si ya lo tienes, solicita ayuda para localizarlo.'
    }
    Write-Host 'Preparando la herramienta. Espera un momento...'
    $venvArguments = @($selectedPython.Args) + @('-m', 'venv', '.venv')
    & $selectedPython.Path @venvArguments
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno.' }
    & .\.venv\Scripts\python.exe -m pip install 'selenium>=4.30,<5' *> (Join-Path $PSScriptRoot 'preparacion.log')
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar la herramienta. Revisa tu conexion a internet y vuelve a intentar.' }
    Write-Host 'Listo. Ya puedes usar ABRIR.'
    exit 0
} catch {
    Write-Host $_.Exception.Message
    Read-Host 'Pulsa Enter para cerrar'
    exit 1
}
