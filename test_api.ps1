# Script para testar a API do Google Maps Scraper no PowerShell

# Função para testar a API
function Test-GoogleMapsScraperAPI {
    param (
        [string]$Region = "Parque Brasília, Anápolis",
        [string]$BusinessType = "Restaurante",
        [int]$MaxResults = 10,
        [string]$Keywords = "rodizio, vegano",
        [switch]$Debug
    )

    $params = @{
        region = $Region
        business_type = $BusinessType
        max_results = $MaxResults
        keywords = $Keywords
    }

    $jsonBody = $params | ConvertTo-Json

    Write-Host "Enviando requisição para iniciar busca..." -ForegroundColor Cyan
    Write-Host "Parâmetros: $jsonBody" -ForegroundColor Gray

    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/scrape" -Method POST -ContentType "application/json" -Body $jsonBody
        
        Write-Host "Requisição aceita. Task ID: $($response.task_id)" -ForegroundColor Green
        
        # Verifica o status da tarefa a cada 2 segundos
        $taskId = $response.task_id
        $taskCompleted = $false
        $attempts = 0
        $maxAttempts = 60  # Timeout após 2 minutos
        
        Write-Host "Verificando status da tarefa..." -ForegroundColor Yellow
        
        while (-not $taskCompleted -and $attempts -lt $maxAttempts) {
            Start-Sleep -Seconds 2
            $attempts++
            
            try {
                $taskResponse = Invoke-RestMethod -Uri "http://localhost:8000/task/$taskId" -Method GET
                
                if ($taskResponse.status -eq "in_progress") {
                    Write-Host "Tarefa em andamento... (verificação $attempts)" -ForegroundColor Yellow
                    
                    # Se estiver no modo debug, mostra informações adicionais se disponíveis
                    if ($Debug -and $taskResponse.PSObject.Properties.Name -contains "progress") {
                        Write-Host "  Progresso: $($taskResponse.progress)" -ForegroundColor Gray
                    }
                }
                elseif ($taskResponse.status -eq "completed") {
                    Write-Host "Tarefa concluída com sucesso!" -ForegroundColor Green
                    $taskCompleted = $true
                    
                    # Exibe os resultados
                    $resultCount = if ($taskResponse.PSObject.Properties.Name -contains "results") { $taskResponse.results.Count } else { 0 }
                    Write-Host "`nResultados encontrados: $resultCount" -ForegroundColor Cyan
                      if ($resultCount -gt 0) {
                        $taskResponse.results | ForEach-Object {
                            Write-Host "- $($_.name)" -ForegroundColor White
                            Write-Host "  Endereço: $($_.address)" -ForegroundColor Gray
                            if ($null -ne $_.phone -and $_.phone -ne "") { Write-Host "  Telefone: $($_.phone)" -ForegroundColor Gray }
                            if ($null -ne $_.website -and $_.website -ne "") { Write-Host "  Website: $($_.website)" -ForegroundColor Gray }
                            if ($null -ne $_.rating) { 
                                $reviewsText = if ($_.reviews_count) { "($($_.reviews_count) avaliações)" } else { "" }
                                Write-Host "  Avaliação: $($_.rating)/5 $reviewsText" -ForegroundColor Gray 
                            }
                            Write-Host ""
                        }
                    } else {
                        Write-Host "Nenhum resultado retornado." -ForegroundColor Yellow
                    }
                    
                    # Opcionalmente, salvamos os resultados em um arquivo
                    $resultsFile = "results_$( (Get-Date).ToString("yyyyMMdd_HHmmss") ).json"
                    $taskResponse.results | ConvertTo-Json -Depth 5 | Out-File -FilePath $resultsFile -Encoding UTF8
                    Write-Host "Resultados salvos em: $resultsFile" -ForegroundColor Cyan
                }
                elseif ($taskResponse.status -eq "error") {
                    Write-Host "Erro ao processar a tarefa:" -ForegroundColor Red
                    Write-Host $taskResponse.message -ForegroundColor Red
                    
                    # Se estiver no modo debug, mostra informações adicionais
                    if ($Debug) {
                        if ($taskResponse.PSObject.Properties.Name -contains "error_details") {
                            Write-Host "`nDetalhes do erro:" -ForegroundColor Red
                            Write-Host $taskResponse.error_details -ForegroundColor Gray
                        }
                    }
                    
                    $taskCompleted = $true
                }
            }
            catch {
                Write-Host "Erro ao verificar status da tarefa: $_" -ForegroundColor Red
                # Tenta novamente
                Start-Sleep -Seconds 1
            }
        }
        
        if (-not $taskCompleted) {
            Write-Host "Timeout ao aguardar a conclusão da tarefa." -ForegroundColor Red
            
            # Tenta uma última verificação para ver o estado atual
            try {
                $taskResponse = Invoke-RestMethod -Uri "http://localhost:8000/task/$taskId" -Method GET
                Write-Host "Status atual da tarefa: $($taskResponse.status)" -ForegroundColor Yellow
                
                if ($Debug) {
                    $taskResponse | ConvertTo-Json -Depth 3 | Write-Host -ForegroundColor Gray
                }
            }
            catch {
                Write-Host "Não foi possível obter o status final da tarefa." -ForegroundColor Red
            }
        }
    }
    catch {
        Write-Host "Erro ao fazer requisição: $_" -ForegroundColor Red
        
        # Informações adicionais para depuração
        if ($Debug) {
            Write-Host "`nDetalhes da exceção:" -ForegroundColor Red
            $_ | Format-List * -Force | Out-String | Write-Host -ForegroundColor Gray
        }
    }
}

# Argumentos passados para o script
$scriptArgs = @{}

# Processa os argumentos na linha de comando
$argIndex = 0
while ($argIndex -lt $args.Count) {
    $arg = $args[$argIndex]
    
    switch -Wildcard ($arg) {
        "-Region" { 
            $scriptArgs["Region"] = $args[$argIndex + 1]
            $argIndex += 2
        }
        "-BusinessType" { 
            $scriptArgs["BusinessType"] = $args[$argIndex + 1]
            $argIndex += 2
        }
        "-MaxResults" { 
            $scriptArgs["MaxResults"] = [int]$args[$argIndex + 1]
            $argIndex += 2
        }
        "-Keywords" { 
            $scriptArgs["Keywords"] = $args[$argIndex + 1]
            $argIndex += 2
        }
        "-Debug" { 
            $scriptArgs["Debug"] = $true
            $argIndex += 1
        }
        default { 
            Write-Host "Argumento desconhecido: $arg" -ForegroundColor Yellow
            $argIndex += 1
        }
    }
}

# Executa o teste com os argumentos fornecidos
Test-GoogleMapsScraperAPI @scriptArgs
