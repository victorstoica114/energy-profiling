param(
    [Parameter(Mandatory=$true)][string]$ArmGccBin,
    [string]$DepsRoot,
    [string]$BuildRoot,
    [string]$Elf2Uf2,
    [ValidateSet('both','stm32','rp2040')][string]$Only = 'both',
    [switch]$Diagnostics
)
$ErrorActionPreference = 'Stop'
$Stm32Target = 'stm32f446'
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not $DepsRoot) { $DepsRoot = Join-Path $ProjectRoot '.deps' }
if (-not $BuildRoot) { $BuildRoot = Join-Path $ProjectRoot 'build' }
$ArmGccBin = (Resolve-Path -LiteralPath $ArmGccBin).Path.Replace('\','/')
$DepsRoot = (Resolve-Path -LiteralPath $DepsRoot).Path
$Compiler = Join-Path $ArmGccBin 'arm-none-eabi-gcc.exe'
$CompilerVersion = (& $Compiler --version | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or $CompilerVersion -notmatch '9\.2\.1 20191025') {
    throw "Profile requires GNU Arm Embedded GCC 9.2.1 20191025. Found: $CompilerVersion"
}
Write-Output $CompilerVersion

function Resolve-LockedSdk([string]$Target, [string]$Name) {
    $LockPath = Join-Path $ProjectRoot "firmware/targets/$Target/sdk.lock.json"
    $Sdk = $null
    foreach ($Entry in (Get-Content -Raw -LiteralPath $LockPath | ConvertFrom-Json)) {
        if ($Entry.name -eq $Name) { $Sdk = $Entry; break }
    }
    if (-not $Sdk) { throw "No locked SDK $Name" }
    $SdkPath = Join-Path $DepsRoot ($Sdk.name + '-' + $Sdk.commit.Substring(0,12))
    if (-not (Test-Path -LiteralPath (Join-Path $SdkPath '.energy_sdk.json'))) {
        throw "Run scripts/fetch_native_sdks.py --dest $DepsRoot first; missing $SdkPath"
    }
    $Record = Get-Content -Raw -LiteralPath (Join-Path $SdkPath '.energy_sdk.json') | ConvertFrom-Json
    if ($Record.commit -ne $Sdk.commit -or $Record.archive_sha256 -ne $Sdk.archive_sha256) {
        throw "SDK record differs from locked identity: $SdkPath"
    }
    return $SdkPath.Replace('\','/')
}
if ($Only -ne 'stm32') { $PicoSdk = Resolve-LockedSdk 'rp2040' 'pico-sdk' }
if ($Only -ne 'rp2040') {
    $StmDevice = Resolve-LockedSdk $Stm32Target 'cmsis-device-f4'
    $CmsisCore = Resolve-LockedSdk $Stm32Target 'CMSIS_5'
}
# All three exist: the fetch tool verifies their full extracted tree without downloads.
& python (Join-Path $PSScriptRoot 'fetch_native_sdks.py') --dest $DepsRoot
if ($LASTEXITCODE -ne 0) { throw 'SDK tree verification failed' }
$BuildSuffix = if ($Diagnostics) { '-diagnostic' } else { '' }
$DiagnosticValue = if ($Diagnostics) { 'ON' } else { 'OFF' }
$StmBuild = Join-Path $BuildRoot ($Stm32Target + $BuildSuffix)
$PicoBuild = Join-Path $BuildRoot ('rp2040' + $BuildSuffix)
if ($Only -ne 'rp2040') {
& cmake -S (Join-Path $ProjectRoot "firmware/targets/$Stm32Target") -B $StmBuild -G Ninja "-DARM_GCC_BIN=$ArmGccBin" "-DSTM32_CMSIS_DEVICE_PATH=$StmDevice" "-DCMSIS_CORE_PATH=$CmsisCore" "-DBENCH_DIAGNOSTICS=$DiagnosticValue"
if ($LASTEXITCODE -ne 0) { throw 'STM32 configure failed' }
& cmake --build $StmBuild --parallel
if ($LASTEXITCODE -ne 0) { throw 'STM32 build failed' }
}
if ($Only -ne 'stm32') {
$env:PICO_TOOLCHAIN_PATH = Split-Path -Parent $ArmGccBin
& cmake -S (Join-Path $ProjectRoot 'firmware/targets/rp2040') -B $PicoBuild -G Ninja "-DPICO_SDK_PATH=$PicoSdk" "-DBENCH_DIAGNOSTICS=$DiagnosticValue"
if ($LASTEXITCODE -ne 0) { throw 'RP2040 configure failed' }
& cmake --build $PicoBuild --parallel
if ($LASTEXITCODE -ne 0) { throw 'RP2040 build failed' }
if ($Elf2Uf2) {
    & $Elf2Uf2 (Join-Path $PicoBuild 'energy_bench_rp2040.elf') (Join-Path $PicoBuild 'energy_bench_rp2040.uf2')
    if ($LASTEXITCODE -ne 0) { throw 'UF2 conversion failed' }
}
}
Write-Output 'Selected native ARM builds passed. No device was flashed.'
