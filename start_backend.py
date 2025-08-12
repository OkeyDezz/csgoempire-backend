#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import subprocess
import signal
import threading
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

def run_flask():
    """Executa o Flask backend em background."""
    try:
        print("🚀 Iniciando Flask backend...")
        process = subprocess.Popen([
            sys.executable, "license_backend.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Aguarda um pouco para Flask inicializar
        time.sleep(5)
        
        print("✅ Flask backend iniciado com PID:", process.pid)
        return process
        
    except Exception as e:
        print(f"❌ Erro ao iniciar Flask: {e}")
        return None

def run_scheduler():
    """Executa o scheduler uma vez."""
    try:
        print("🔄 Executando scheduler...")
        result = subprocess.run([
            sys.executable, "scheduler_refresh.py", "--once"
        ], capture_output=True, text=True, timeout=300)  # 5 minutos timeout
        
        if result.returncode == 0:
            print("✅ Scheduler executado com sucesso")
            print("Output:", result.stdout)
        else:
            print("⚠️ Scheduler executou com warnings")
            print("Output:", result.stdout)
            print("Errors:", result.stderr)
            
    except subprocess.TimeoutExpired:
        print("⚠️ Scheduler demorou muito - continuando...")
    except Exception as e:
        print(f"❌ Erro no scheduler: {e}")

def main():
    """Função principal que gerencia ambos os processos."""
    print("🚀 Iniciando CSGOEmpire Backend...")
    
    # Inicia Flask em background
    flask_process = run_flask()
    if not flask_process:
        print("❌ Falha ao iniciar Flask - saindo")
        sys.exit(1)
    
    # Executa scheduler uma vez
    run_scheduler()
    
    print("✅ Backend configurado - Flask rodando continuamente")
    print("📊 Scheduler será executado via Cron Schedule a cada 6h")
    
    try:
        # Mantém o processo principal vivo
        while True:
            time.sleep(60)  # Verifica a cada minuto
            
            # Verifica se Flask ainda está rodando
            if flask_process.poll() is not None:
                print("❌ Flask parou inesperadamente - reiniciando...")
                flask_process = run_flask()
                if not flask_process:
                    print("❌ Falha ao reiniciar Flask - saindo")
                    break
            
    except KeyboardInterrupt:
        print("\n🛑 Recebido sinal de parada...")
    finally:
        # Limpa processos
        if flask_process:
            print("🛑 Parando Flask...")
            flask_process.terminate()
            flask_process.wait()
        print("✅ Backend parado")

if __name__ == "__main__":
    main()
