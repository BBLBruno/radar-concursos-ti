<#
.SYNOPSIS
    Registra a automação do Monitor de Concursos no Agendador de Tarefas do Windows.
.DESCRIPTION
    Cria uma tarefa agendada para rodar toda Segunda, Quarta e Sexta-feira às 08:00 da manhã.
    Configura StartWhenAvailable para executar assim que o computador for ligado caso estivesse desligado no horário.
#>

param(
    [string]$Horario = "08:00",
    [string]$NomeTarefa = "MonitorConcursosMuzambinhoTI"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source

if (-not $PythonExe) {
    Write-Host "[ERRO] Python não foi localizado no PATH do sistema!" -ForegroundColor Red
    exit 1
}

$ScriptPath = Join-Path $ScriptDir "concursos_muzambinho.py"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Configuração da Automação no Agendador de Tarefas do Windows" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "Tarefa: $NomeTarefa"
Write-Host "Python: $PythonExe"
Write-Host "Script: $ScriptPath --raio 250"
Write-Host "Dias: Segunda, Quarta e Sexta-feira (com execução garantida ao ligar o PC)"
Write-Host "Horário: $Horario"
Write-Host ""

try {
    $Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptPath`" --raio 250" -WorkingDirectory $ScriptDir
    $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Wednesday,Friday -At $Horario
    $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $NomeTarefa -Action $Action -Trigger $Trigger -Settings $Settings -Force -ErrorAction Stop | Out-Null
    Write-Host "[SUCESSO] Tarefa agendada com sucesso (com StartWhenAvailable ativo)!" -ForegroundColor Green
    Write-Host "Caso o PC esteja desligado às $Horario, a varredura rodará automaticamente assim que o Windows iniciar." -ForegroundColor Green
} catch {
    # Fallback via schtasks caso executado sem elevação completa
    $cmdPt = "schtasks.exe /Create /TN `"$NomeTarefa`" /TR `"`"$PythonExe`" `"$ScriptPath`" --raio 250`" /SC WEEKLY /D SEG,QUA,SEX /ST $Horario /F"
    $cmdEn = "schtasks.exe /Create /TN `"$NomeTarefa`" /TR `"`"$PythonExe`" `"$ScriptPath`" --raio 250`" /SC WEEKLY /D MON,WED,FRI /ST $Horario /F"
    Invoke-Expression $cmdPt 2>$null
    if ($LASTEXITCODE -ne 0) {
        Invoke-Expression $cmdEn
    }
}
