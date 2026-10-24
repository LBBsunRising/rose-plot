param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AppArgs
)
$env:MSBUILDDISABLENODEREUSE = '1'
$env:DOTNET_CLI_USE_MSBUILD_SERVER = '0'
Push-Location $PSScriptRoot
try {
    dotnet run --project .\RoseChartStudio.App\RoseChartStudio.App.csproj -c Release -- @AppArgs
}
finally {
    Pop-Location
}
