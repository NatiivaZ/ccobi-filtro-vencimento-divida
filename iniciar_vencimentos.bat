@echo off
chcp 65001 >nul
echo ========================================
echo   Sistema de Análise por Ano de Vencimento
echo   Autos de Infração ANTT
echo ========================================
echo.
echo Verificando Python...
py --version
if errorlevel 1 (
    echo ERRO: Python não encontrado! Instale o Python primeiro.
    pause
    exit /b 1
)
echo.
echo Instalando/Atualizando dependências...
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERRO: Falha ao instalar dependências!
    pause
    exit /b 1
)
echo.
echo Configurando Streamlit (evita tela de e-mail)...
py "%~dp0..\config_streamlit.py"
echo.
echo ========================================
echo Iniciando sistema...
echo ========================================
echo.
echo O navegador abrirá automaticamente.
echo Para parar o sistema, pressione Ctrl+C
echo.
py -m streamlit run app_vencimentos.py --server.headless false
pause

