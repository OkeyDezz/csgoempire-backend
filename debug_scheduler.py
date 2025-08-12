#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from dotenv import load_dotenv

print("🔍 DEBUG: Iniciando diagnóstico do scheduler...")

# Carrega .env
load_dotenv()

# Verifica variáveis
print(f"SUPABASE_URL: {'✅' if os.getenv('SUPABASE_URL') else '❌'}")
print(f"SUPABASE_ANON_KEY: {'✅' if os.getenv('SUPABASE_ANON_KEY') else '❌'}")
print(f"SUPABASE_SERVICE_ROLE: {'✅' if os.getenv('SUPABASE_SERVICE_ROLE') else '❌'}")
print(f"SUPABASE_MARKET_TABLE: {'✅' if os.getenv('SUPABASE_MARKET_TABLE') else '❌'}")

try:
    print("\n🔍 Testando import do Supabase...")
    from supabase import create_client
    print("✅ Supabase import OK")
    
    # Cria cliente
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE') or os.getenv('SUPABASE_ANON_KEY')
    
    print(f"URL: {url}")
    print(f"Key: {key[:20]}..." if key else "❌ Key não encontrada")
    
    sb = create_client(url, key)
    print("✅ Cliente Supabase criado")
    
    # Testa conexão básica
    print("\n🔍 Testando conexão básica...")
    try:
        response = sb.table("_test_connection").select("1").limit(1).execute()
        print("✅ Conexão básica OK")
    except Exception as e:
        print(f"⚠️ Conexão básica falhou (esperado): {e}")
    
    # Testa acesso à tabela market_data
    table_name = os.getenv('SUPABASE_MARKET_TABLE', 'market_data')
    print(f"\n🔍 Testando acesso à tabela '{table_name}'...")
    
    try:
        # Tenta fazer um select simples
        response = sb.table(table_name).select("*").limit(1).execute()
        print(f"✅ Tabela {table_name} acessível")
        print(f"Dados retornados: {len(response.data)} registros")
        
    except Exception as e:
        print(f"❌ Erro ao acessar {table_name}: {e}")
        print(f"Tipo de erro: {type(e).__name__}")
        
        # Tenta verificar se a tabela existe
        try:
            print(f"\n🔍 Verificando se a tabela existe...")
            response = sb.table(table_name).select("count").execute()
            print(f"✅ Tabela {table_name} existe")
            
        except Exception as e2:
            print(f"❌ Tabela {table_name} não existe ou não acessível")
            print(f"Erro: {e2}")
            
            # Lista tabelas disponíveis
            try:
                print(f"\n🔍 Listando tabelas disponíveis...")
                # Tenta acessar uma tabela que sabemos que existe
                response = sb.table("purchases").select("*").limit(1).execute()
                print("✅ Tabela 'purchases' acessível")
                
            except Exception as e3:
                print(f"❌ Nenhuma tabela acessível: {e3}")
                
except Exception as e:
    print(f"❌ Erro geral: {e}")
    print(f"Tipo: {type(e).__name__}")
    import traceback
    traceback.print_exc()

print("\n✅ Diagnóstico concluído!")
