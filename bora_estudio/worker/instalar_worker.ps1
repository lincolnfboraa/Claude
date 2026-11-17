# Instalador do render worker do Bora Studio no Windows (Acer).
# Uso (PowerShell, na pasta onde quer instalar):
#   powershell -ExecutionPolicy Bypass -File instalar_worker.ps1            -> instala/atualiza e liga o worker
#   powershell -ExecutionPolicy Bypass -File instalar_worker.ps1 -SoTeste   -> só confere Docker, placa e codificadores
# Não altera nada no VPS nem no Supabase. O worker só pega trabalho quando o VPS estiver com BORA_RENDER_EXTERNO=1.
param([switch]$SoTeste, [string]$Pasta = "$HOME\bora-render")
$ErrorActionPreference = 'Stop'
$Ramo = 'claude/upbeat-tesla-qu1g6k'
$Repo = 'https://github.com/lincolnfboraa/Claude.git'
function Passo($t) { Write-Host "`n== $t" -ForegroundColor Cyan }
function Falha($t) { Write-Host "ERRO: $t" -ForegroundColor Red; exit 1 }

Passo 'Conferindo Git e Docker Desktop'
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Falha 'instale o Git: https://git-scm.com/download/win' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Falha 'instale o Docker Desktop: https://www.docker.com/products/docker-desktop/' }
docker info *> $null
if ($LASTEXITCODE -ne 0) { Falha 'abra o Docker Desktop e espere ficar "Engine running"' }
Write-Host 'ok'

Passo 'Conferindo a máquina'
$cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1)
$ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
Write-Host "Processador: $($cpu.Name) ($($cpu.NumberOfLogicalProcessors) threads), RAM: $ram GB"
if ($ram -lt 12) { Write-Host 'Aviso: menos de 12 GB de RAM; um 4K usa uns 4 a 5 GB no pico.' -ForegroundColor Yellow }
$nvidia = $false
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $gpu = (nvidia-smi --query-gpu=name,driver_version --format=csv,noheader) 2>$null
    if ($LASTEXITCODE -eq 0 -and $gpu) { $nvidia = $true; Write-Host "Placa NVIDIA: $gpu" }
}
if (-not $nvidia) { Write-Host 'Sem placa NVIDIA (ou driver): o worker usa só a CPU (x265).' }

Passo 'Baixando ou atualizando o Bora Studio'
if (Test-Path "$Pasta\.git") { git -C $Pasta fetch -q origin $Ramo; git -C $Pasta checkout -q $Ramo; git -C $Pasta reset -q --hard "origin/$Ramo" }
else { git clone -q -b $Ramo $Repo $Pasta }
Set-Location $Pasta
$W = 'bora_estudio\worker'
$arqs = @('-f', "$W\docker-compose.worker.yml")
if ($nvidia) { $arqs += @('-f', "$W\docker-compose.worker.gpu.yml") }

if (-not (Test-Path "$W\worker.env")) {
    Passo 'Configurando o worker'
    $tok = Read-Host 'Cole o BORA_WORKER_TOKEN (está no /opt/bora/bora.env do VPS)'
    if ($tok.Length -lt 32) { Falha 'token curto demais; confira o valor no VPS' }
    $nome = Read-Host 'Nome deste computador no Bora Studio [acer]'
    if (-not $nome) { $nome = 'acer' }
    "BORA_EDITOR=https://editor.borasolucoesdigitais.com`nBORA_WORKER_TOKEN=$tok`nBORA_WORKER_NOME=$nome" | Set-Content -Encoding ascii "$W\worker.env"
    Write-Host "Gravado em $W\worker.env (fica só neste computador)"
}

Passo 'Montando o worker (a primeira vez demora alguns minutos)'
docker compose @arqs build
if ($LASTEXITCODE -ne 0) { Falha 'a montagem do container falhou' }

Passo 'Teste dos codificadores (HEVC 10 bits, HLG, BT.2020)'
docker compose @arqs run --rm bora-render python3 bora_estudio/worker/render_worker.py --teste
if ($LASTEXITCODE -ne 0) { Falha 'o teste não rodou' }
if ($SoTeste) { Write-Host "`nSó teste: nada foi ligado." -ForegroundColor Green; exit 0 }

Passo 'Ligando o worker (reinicia sozinho com o Docker Desktop)'
docker compose @arqs up -d
if ($LASTEXITCODE -ne 0) { Falha 'não consegui ligar o worker' }
Write-Host "`nPronto. Acompanhar: docker logs -f bora-render" -ForegroundColor Green
Write-Host 'Deixe o Acer ligado e sem hibernar enquanto houver 4K na fila.'
