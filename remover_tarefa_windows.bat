@echo off
chcp 65001 >nul
echo Removendo tarefa agendada do Windows...
schtasks.exe /Delete /TN "MonitorConcursosMuzambinhoTI" /F
if %ERRORLEVEL% EQU 0 (
    echo [SUCESSO] Tarefa 'MonitorConcursosMuzambinhoTI' removida com sucesso.
) else (
    echo [INFO] Tarefa não encontrada ou já removida.
)
pause
