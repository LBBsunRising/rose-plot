$ErrorActionPreference = 'Stop'
$env:MSBUILDDISABLENODEREUSE = '1'
$env:DOTNET_CLI_USE_MSBUILD_SERVER = '0'
Push-Location $PSScriptRoot
try {
    dotnet build .\RoseChartStudio.TestRunner\RoseChartStudio.TestRunner.csproj -c Release -m:1 -nr:false
    if ($LASTEXITCODE -ne 0) { throw "test build failed ($LASTEXITCODE)" }
    & .\RoseChartStudio.TestRunner\bin\Release\net10.0-windows\RoseChartStudio.TestRunner.exe
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
