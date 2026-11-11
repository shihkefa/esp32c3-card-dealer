param(
    [string]$Cli = 'arduino-cli',
    [string]$Fqbn = 'esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashMode=dio'
)
$ErrorActionPreference = 'Stop'
$dealerRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$dealerAlias = $null
$dealerOriginalTemp = $env:TEMP
$dealerOriginalTmp = $env:TMP
$dealerExit = 1
try {
    $dealerWorkingRoot = $dealerRoot
    # Some installed ESP32 linkers cannot write an ELF to a Unicode path.
    # Use an unused, temporary DOS drive alias; no source files are moved.
    if ($dealerRoot -match '[^\x00-\x7F]') {
        foreach ($dealerLetter in @('W','V','U','T','S','R','Z','Y','X')) {
            if (-not (Get-PSDrive -Name $dealerLetter -ErrorAction SilentlyContinue)) {
                & subst.exe ($dealerLetter + ':') $dealerRoot
                if ($LASTEXITCODE -eq 0) {
                    $dealerAlias = $dealerLetter + ':'
                    $dealerWorkingRoot = $dealerAlias + '\'
                    break
                }
            }
        }
        if (-not $dealerAlias) {throw 'No free drive alias. Extract the project to an ASCII-only path.'}
    }
    $dealerBuild = Join-Path $dealerWorkingRoot '.build'
    # Arduino CLI may clean the build directory before preprocessing.
    # TEMP must survive that cleanup, so keep it beside the build directory.
    $dealerTemp = Join-Path $dealerWorkingRoot '.build-temp'
    $dealerBin = Join-Path $dealerWorkingRoot 'bin'
    New-Item -ItemType Directory -Force -Path $dealerBuild,$dealerTemp,$dealerBin | Out-Null
    $env:TEMP = $dealerTemp
    $env:TMP = $dealerTemp
    & $Cli compile --fqbn $Fqbn --build-path $dealerBuild --output-dir $dealerBin --warnings all (Join-Path $dealerWorkingRoot 'CardDealer')
    $dealerExit = $LASTEXITCODE
} finally {
    $env:TEMP = $dealerOriginalTemp
    $env:TMP = $dealerOriginalTmp
    if ($dealerAlias) {& subst.exe $dealerAlias /D}
}
exit $dealerExit
