$ErrorActionPreference = 'Stop'
$env:MSBUILDDISABLENODEREUSE = '1'
$env:DOTNET_CLI_USE_MSBUILD_SERVER = '0'
Push-Location $PSScriptRoot
try {
    dotnet build .\RoseChartStudio.slnx -c Release -m:1 -nr:false
    if ($LASTEXITCODE -ne 0) { throw "build failed ($LASTEXITCODE)" }
    Write-Host "OK: build succeeded"
}
finally {
    Pop-Location
}
