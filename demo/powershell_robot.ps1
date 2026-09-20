$ErrorActionPreference = "Stop"

$runId = $env:RCC_RUN_ID
$resultPath = $env:RCC_RESULT_PATH
$temporaryPath = "$resultPath.tmp"

Write-Output "Robo PowerShell executado pelo Zanella Orchestrator"
$payload = @{
    version = 1
    run_id = $runId
    status = "success"
    summary = "Processo PowerShell concluido com contrato de resultado"
} | ConvertTo-Json -Compress

[System.IO.File]::WriteAllText($temporaryPath, $payload, [System.Text.UTF8Encoding]::new($false))
Move-Item -LiteralPath $temporaryPath -Destination $resultPath -Force
