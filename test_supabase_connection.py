#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from dotenv import load_dotenv

# Carrega .env
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE") or os.environ.get("SUPABASE_ANON_KEY")
MARKET_TABLE = os.environ.get("SUPABASE_MARKET_TABLE", "market_data")

print(f"🔍 Testando conexão com Supabase...")
print(f"URL: {SUPABASE_URL}")
print(f"Key: {SUPABASE_KEY[:20]}..." if SUPABASE_KEY else "❌ Key não encontrada")
print(f"Tabela: {MARKET_TABLE}")

try:
    from supabase import create_client
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL ou SUPABASE_KEY não configurados")
        exit(1)
    
    # Cria cliente
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Cliente Supabase criado")
    
    # Testa conexão básica
    print("\n🔍 Testando conexão básica...")
    response = sb.table("_test_connection").select("1").limit(1).execute()
    print("✅ Conexão básica OK")
    
except Exception as e:
    print(f"❌ Erro na conexão básica: {e}")
    exit(1)

try:
    # Testa acesso à tabela market_data
    print(f"\n🔍 Testando acesso à tabela '{MARKET_TABLE}'...")
    
    # Primeiro, lista todas as tabelas
    print("📋 Listando tabelas disponíveis...")
    response = sb.rpc("get_tables").execute()
    print(f"Tabelas: {response.data}")
    
except Exception as e:
    print(f"⚠️ Erro ao listar tabelas: {e}")
    
    # Tenta acessar diretamente
    try:
        print(f"\n🔍 Tentando acessar '{MARKET_TABLE}' diretamente...")
        response = sb.table(MARKET_TABLE).select("*").limit(1).execute()
        print(f"✅ Tabela {MARKET_TABLE} acessível")
        print(f"Dados: {response.data}")
        
    except Exception as e2:
        print(f"❌ Erro ao acessar {MARKET_TABLE}: {e2}")
        
        # Verifica se a tabela existe
        try:
            print(f"\n🔍 Verificando estrutura da tabela...")
            response = sb.table(MARKET_TABLE).select("count").execute()
            print(f"✅ Tabela {MARKET_TABLE} existe")
            
        except Exception as e3:
            print(f"❌ Tabela {MARKET_TABLE} não existe ou não acessível")
            print(f"Erro: {e3}")

print("\n✅ Teste concluído!")
