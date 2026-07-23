@echo off
rem Atualizacao do pipeline Energia (agendada 2x/dia: 08:15 e 15:30)
cd /d C:\Users\anapa\Claude\Energia
echo ===== %date% %time% ===== >> log_atualiza.txt
python atualiza.py >> log_atualiza.txt 2>&1
python gera_dashboard.py >> log_atualiza.txt 2>&1
