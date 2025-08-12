#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import subprocess
import signal
import requests
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

def run_flask():
    """Executa o Flask backend em background."""
    try:
        print("🚀 Iniciando Flask backend...")
        
        # Usa nohup para garantir que Flask continue rodando
        process = subprocess.Popen([
            sys.executable, "license_backend.py"
        ], 
        stdout=subprocess.DEVNULL,  # Redireciona output para não sobrecarregar logs
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid)  # Cria novo grupo de processos
        
        # Aguarda apenas 3 segundos para Flask inicializar
        time.sleep(3)
        
        print("✅ Flask backend iniciado com PID:", process.pid)
        return process
        
    except Exception as e:
        print(f"❌ Erro ao iniciar Flask: {e}")
        return None

def check_flask_health():
    """Verifica se o Flask está respondendo."""
    try:
        response = requests.get("http://localhost:8080/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def run_scheduler():
    """Executa o scheduler uma vez de forma otimizada."""
    try:
        print("🔄 Executando scheduler...")
        
        # SEM timeout - permite que o scheduler termine naturalmente
        result = subprocess.run([
            sys.executable, "scheduler_refresh.py", "--once"
        ], 
        capture_output=True, 
        text=True)  # Sem timeout
        
        if result.returncode == 0:
            print("✅ Scheduler executado com sucesso")
            # Log apenas resumo para não sobrecarregar
            lines = result.stdout.strip().split('\n')
            if lines:
                print(f"📊 Última linha: {lines[-1]}")
        else:
            print("⚠️ Scheduler executou com warnings")
            if result.stderr:
                print(f"❌ Erros: {result.stderr[:200]}...")  # Limita output
            
    except Exception as e:
        print(f"❌ Erro no scheduler: {e}")

def main():
    """Função principal otimizada."""
    print("🚀 Iniciando CSGOEmpire Backend...")
    
    # Inicia Flask em background
    flask_process = run_flask()
    if not flask_process:
        print("❌ Falha ao iniciar Flask - saindo")
        sys.exit(1)
    
    # Aguarda Flask inicializar completamente
    print("⏳ Aguardando Flask inicializar...")
    max_wait = 30  # Máximo 30 segundos
    for i in range(max_wait):
        if check_flask_health():
            print("✅ Flask está respondendo corretamente")
            break
        time.sleep(1)
        if i % 5 == 0:
            print(f"⏳ Aguardando Flask... ({i+1}/{max_wait}s)")
    else:
        print("⚠️ Flask demorou para inicializar, mas continuando...")
    
    # Executa scheduler uma vez
    run_scheduler()
    
    print("✅ Backend configurado - Flask rodando continuamente")
    print("📊 Scheduler será executado via Cron Schedule a cada 6h")
    print("💤 Processo principal entrando em modo sleep...")
    
    try:
        # Modo ultra-eficiente: apenas verifica a cada 5 minutos
        check_interval = 300  # 5 minutos
        
        while True:
            # Sleep longo para economizar recursos
            time.sleep(check_interval)
            
            # Verifica se Flask ainda está rodando e respondendo
            if flask_process.poll() is not None:
                print("❌ Flask parou inesperadamente - reiniciando...")
                flask_process = run_flask()
                if not flask_process:
                    print("❌ Falha ao reiniciar Flask - saindo")
                    break
                print("✅ Flask reiniciado com sucesso")
            elif not check_flask_health():
                print("⚠️ Flask não está respondendo - pode estar travado")
                # Não reinicia, apenas monitora
            else:
                print("✅ Flask rodando normalmente - verificando em 5 minutos...")
            
    except KeyboardInterrupt:
        print("\n🛑 Recebido sinal de parada...")
    finally:
        # Limpa processos de forma mais eficiente
        if flask_process:
            print("🛑 Parando Flask...")
            try:
                # Mata todo o grupo de processos
                os.killpg(os.getpgid(flask_process.pid), signal.SIGTERM)
                flask_process.wait(timeout=5)
            except:
                # Force kill se necessário
                flask_process.kill()
        print("✅ Backend parado")

if __name__ == "__main__":
    main()
