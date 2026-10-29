@echo off
chcp 65001 >nul
echo ==================================================================
echo   Radar de Concursos TI - Servidor Local
echo ==================================================================
echo.
echo Abrindo http://localhost:8000 no seu navegador padrao...
start http://localhost:8000
echo.
echo Servidor rodando em http://localhost:8000/
echo Pressione Ctrl+C para encerrar o servidor.
echo.
python -m http.server 8000
