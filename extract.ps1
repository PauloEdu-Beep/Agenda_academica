# Define o diretório base como o local atual.
$basePath = (Get-Location).Path
# Define o caminho do arquivo de saída.
$outputFilePath = Join-Path -Path $basePath -ChildPath "output.txt"

Write-Host "Iniciando extração..."

# O bloco '& { ... }' agrupa todos os comandos, e o '| Out-File' salva tudo de uma vez.
& {
    # --- 1. Lista de arquivos individuais para extrair ---
    $individualFiles = @("app.py", "db_config.py")

    foreach ($fileName in $individualFiles) {
        $filePath = Join-Path -Path $basePath -ChildPath $fileName
        
        if (Test-Path $filePath -PathType Leaf) {
            $fullPath = (Resolve-Path $filePath).Path
            Write-Output "# $fullPath"
            Write-Output ""
            Get-Content -Path $fullPath -Raw | Write-Output
            Write-Output ""
        }
        else {
            # Mensagem opcional no console, não vai para o arquivo output.txt
            Write-Host "Aviso: '$fileName' não encontrado." -ForegroundColor Yellow
        }
    }

    # --- 2. Extrair todos os arquivos da pasta 'templates' ---
    $templatesFolder = Join-Path -Path $basePath -ChildPath "templates"

    if (Test-Path $templatesFolder -PathType Container) {
        $templateFiles = Get-ChildItem -Path $templatesFolder -File
        foreach ($file in $templateFiles) {
            $fullPath = $file.FullName
            Write-Output "# $fullPath"
            Write-Output ""
            Get-Content -Path $fullPath -Raw | Write-Output
            Write-Output ""
        }
    }
    else {
        Write-Host "Aviso: Pasta 'templates' não encontrada." -ForegroundColor Yellow
    }

} | Out-File -FilePath $outputFilePath -Encoding UTF8

Write-Host "Sucesso! Conteúdo extraído para: $outputFilePath" -ForegroundColor Green