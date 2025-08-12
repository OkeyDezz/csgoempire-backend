#!/usr/bin/env python3
"""
Módulo de otimização de memória para o backend
"""

import os
import gc
import sys

def optimize_memory_settings():
    """Configura otimizações de memória para o processo Python"""
    
    # Configurações de environment para reduzir consumo
    os.environ.setdefault('PYTHONHASHSEED', '0')
    os.environ.setdefault('HTTPX_DISABLE_HTTP2', '1')
    os.environ.setdefault('SUPABASE_UPSERT_BATCH', '150')  # Batch menor
    
    # Configurar garbage collection mais agressivo
    import gc
    gc.set_threshold(700, 10, 10)  # Valores menores = GC mais frequente
    
    # Configurar requests para usar menos memória
    try:
        import requests
        # Configurar sessão com pool menor
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=2,
            pool_maxsize=5,
            max_retries=1
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
    except ImportError:
        pass

def force_cleanup():
    """Força limpeza agressiva de memória"""
    gc.collect()
    gc.collect()  # Duas vezes para garantir

def get_memory_usage():
    """Retorna uso atual de memória em MB"""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return 0

def log_memory_usage(context=""):
    """Log do uso atual de memória"""
    memory_mb = get_memory_usage()
    if memory_mb > 0:
        print(f"[memory] {context}: {memory_mb:.1f}MB")
        
        # Alerta se próximo do limite
        if memory_mb > 400:  # 400MB = alerta (limite é 512MB)
            print(f"⚠️  [memory] ALERTA: Próximo do limite de 512MB!")
            force_cleanup()
    
    return memory_mb

def memory_limit_check(max_mb=450):
    """Verifica se está próximo do limite de memória"""
    current_mb = get_memory_usage()
    if current_mb > max_mb:
        print(f"🚨 [memory] LIMITE: {current_mb:.1f}MB > {max_mb}MB - Forçando limpeza...")
        force_cleanup()
        return True
    return False

if __name__ == "__main__":
    optimize_memory_settings()
    print("Configurações de memória aplicadas")
