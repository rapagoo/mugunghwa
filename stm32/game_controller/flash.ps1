# STM32 Flash Script for Nucleo-F411RE
$cliPath = "C:\ST\STM32CubeIDE_2.2.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.win32_2.2.500.202603051304\tools\bin\STM32_Programmer_CLI.exe"
$binPath = "$PSScriptRoot\build\Debug\stm32_project.bin"

if (-not (Test-Path $binPath)) {
    Write-Host "[ERROR] Binary not found at $binPath" -ForegroundColor Red
    Write-Host "Please build first using: cmake --build --preset Debug" -ForegroundColor Yellow
    exit 1
}

Write-Host ">>> Flashing $binPath to STM32F411RE via ST-LINK..." -ForegroundColor Cyan

if (Test-Path $cliPath) {
    & $cliPath -c port=SWD -w $binPath 0x08000000 -v -rst
} else {
    # STM32_Programmer_CLI path fallback
    STM32_Programmer_CLI -c port=SWD -w $binPath 0x08000000 -v -rst
}
exit $LASTEXITCODE
