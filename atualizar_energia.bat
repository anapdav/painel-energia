@echo off
rem Rotina do pipeline Energia (agendada 2x/dia: 08:15 e 15:30)
rem 1) coleta as fontes  2) gera o dashboard  3) publica no GitHub Pages
cd /d C:\Users\anapa\Claude\Energia
echo ===== %date% %time% ===== >> log_atualiza.txt
python atualiza.py >> log_atualiza.txt 2>&1
python gera_dashboard.py >> log_atualiza.txt 2>&1

rem --- publicacao: so o dashboard entra no commit (nada de arquivo em edicao) ---
copy /Y energia_dashboard.html index.html >nul
git add index.html energia_dashboard.html >> log_atualiza.txt 2>&1
git diff --cached --quiet
if errorlevel 1 (
  git commit -q -m "Atualizacao automatica do painel - %date%" >> log_atualiza.txt 2>&1
  git push -q >> log_atualiza.txt 2>&1
  if errorlevel 1 (
    echo [PUBLICACAO] FALHOU o push - site pode estar desatualizado >> log_atualiza.txt
  ) else (
    echo [PUBLICACAO] site atualizado >> log_atualiza.txt
  )
) else (
  echo [PUBLICACAO] sem mudanca no dashboard, nada publicado >> log_atualiza.txt
)
