@echo off
chcp 65001 >nul
echo ==================================================================
echo   Configuração da Automação de Concursos (Windows Task Scheduler)
echo ==================================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0agendar_tarefa_windows.ps1"
pause
