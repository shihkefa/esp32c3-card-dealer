param([string]$Compiler = 'g++')
$ErrorActionPreference = 'Stop'
$dealerRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$dealerTestOut = Join-Path $dealerRoot '.build-tests'
New-Item -ItemType Directory -Force -Path $dealerTestOut | Out-Null
& $Compiler -std=c++17 -O2 -Wall -Wextra -Werror -I (Join-Path $dealerRoot 'CardDealer') (Join-Path $dealerRoot 'tests/core_tests.cpp') (Join-Path $dealerRoot 'CardDealer/DealerCore.cpp') -o (Join-Path $dealerTestOut 'core_tests.exe')
if ($LASTEXITCODE -ne 0) {exit $LASTEXITCODE}
& (Join-Path $dealerTestOut 'core_tests.exe')
exit $LASTEXITCODE
