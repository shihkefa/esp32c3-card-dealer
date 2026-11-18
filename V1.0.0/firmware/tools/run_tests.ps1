param([string]$Compiler = 'g++', [string[]]$CompilerArgs = @())
$ErrorActionPreference = 'Stop'
$dealerRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$dealerTestOut = Join-Path $dealerRoot '.build-tests'
New-Item -ItemType Directory -Force -Path $dealerTestOut | Out-Null
$dealerSuites = @(
    @{Name='core_tests'; LinkCore=$true},
    @{Name='exit_sampler_tests'; LinkCore=$false},
    @{Name='exit_pipeline_tests'; LinkCore=$true},
    @{Name='flight_log_tests'; LinkCore=$true; FlightLog=$true}
)
foreach ($dealerSuite in $dealerSuites) {
    $dealerSources = @((Join-Path $dealerRoot ('tests/' + $dealerSuite.Name + '.cpp')))
    if ($dealerSuite.LinkCore) {$dealerSources += (Join-Path $dealerRoot 'CardDealer/DealerCore.cpp')}
    $dealerTestIncludes = @()
    if ($dealerSuite.FlightLog) {
        $dealerSources += (Join-Path $dealerRoot 'CardDealer/FlightLog.cpp')
        $dealerTestIncludes = @('-I', (Join-Path $dealerRoot 'tests/flight_stubs'))
    }
    $dealerExecutable = Join-Path $dealerTestOut ($dealerSuite.Name + '.exe')
    & $Compiler @CompilerArgs -std=c++17 -O2 -Wall -Wextra -Werror -I (Join-Path $dealerRoot 'CardDealer') @dealerTestIncludes @dealerSources -o $dealerExecutable
    if ($LASTEXITCODE -ne 0) {exit $LASTEXITCODE}
    & $dealerExecutable
    if ($LASTEXITCODE -ne 0) {exit $LASTEXITCODE}
}
exit 0
