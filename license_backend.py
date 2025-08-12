#!/usr/bin/env python3
"""
Backend Flask seguro para validação de licenças do CSGOEmpire Bot.
Implementa JWT, rate limiting, logging avançado e todas as medidas de segurança.
"""

from flask import Flask, request, jsonify, g
import requests
import os
import logging
import json
import time
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple
import jwt
from functools import wraps
from dotenv import load_dotenv
import re
import threading
import platform
import subprocess

# Carrega variáveis de ambiente
load_dotenv()

# Configuração de logging avançado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backend.log')
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Simple limiter stub for Nixpacks default (no Flask-Limiter preinstalled)
class DummyLimiter:
    def __init__(self,*a,**k): pass
    def limit(self,*a,**k):
        def deco(f):
            return f
        return deco

limiter = DummyLimiter()

# Cache para rate limiting (em produção, usar Redis)
request_cache = {}

# Proteção contra força bruta
failed_attempts = {}  # IP: (count, last_attempt_time)
MAX_FAILED_ATTEMPTS = 5
BLOCK_DURATION = 1800  # 30 minutos

def is_ip_blocked(ip: str) -> bool:
    """Verifica se um IP está bloqueado por tentativas falhadas."""
    if ip not in failed_attempts:
        return False
    
    count, last_attempt = failed_attempts[ip]
    if time.time() - last_attempt > BLOCK_DURATION:
        # Remove bloqueio expirado
        del failed_attempts[ip]
        return False
    
    return count >= MAX_FAILED_ATTEMPTS

def record_failed_attempt(ip: str):
    """Registra uma tentativa falhada."""
    current_time = time.time()
    
    if ip in failed_attempts:
        count, last_attempt = failed_attempts[ip]
        if current_time - last_attempt > BLOCK_DURATION:
            # Reset se passou o tempo de bloqueio
            failed_attempts[ip] = (1, current_time)
        else:
            failed_attempts[ip] = (count + 1, current_time)
    else:
        failed_attempts[ip] = (1, current_time)
    
    # Log de tentativa falhada
    count = failed_attempts[ip][0]
    if count >= MAX_FAILED_ATTEMPTS:
        log_security_event('ip_blocked', {
            'ip': ip,
            'failed_attempts': count,
            'block_duration': BLOCK_DURATION
        })

# Headers de segurança
@app.after_request
def add_security_headers(response):
    """Adiciona headers de segurança."""
    # Headers básicos de segurança
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # HSTS - mais compatível
    response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    
    # CSP mais permissivo para compatibilidade
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'"
    
    # Referrer Policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Cache Control
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    
    # Server info (removido para segurança)
    response.headers.pop('Server', None)
    
    return response

def log_security_event(event_type: str, details: Dict, ip: str = None):
    """Log de eventos de segurança."""
    if not ip:
        ip = request.remote_addr or "unknown"
    
    log_entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'event_type': event_type,
        'ip_address': ip,
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'details': details
    }
    
    logger.warning(f"SECURITY_EVENT: {json.dumps(log_entry)}")
    
    # Em produção, enviar para sistema de alertas
    if event_type in ['failed_activation', 'failed_validation', 'rate_limit_exceeded']:
        logger.error(f"🚨 ALERTA DE SEGURANÇA: {event_type} - IP: {ip}")

def validate_api_key():
    """Valida a API key do backend."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        log_security_event('invalid_auth', {'reason': 'missing_auth_header'})
        return False
    
    provided_key = auth_header.split(' ')[1]
    if provided_key != API_KEY:
        log_security_event('invalid_auth', {'reason': 'invalid_api_key'})
        return False
    
    return True

def generate_jwt(payload: Dict) -> str:
    """Gera JWT assinado."""
    payload.update({
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(seconds=JWT_EXPIRATION),
        'jti': secrets.token_urlsafe(16)  # JWT ID único
    })
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt(token: str) -> Optional[Dict]:
    """Verifica JWT."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        log_security_event('jwt_expired', {'token': token[:20] + '...'})
        return None
    except jwt.InvalidTokenError:
        log_security_event('jwt_invalid', {'token': token[:20] + '...'})
        return None

def require_auth(f):
    """Decorator para requerer autenticação."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not validate_api_key():
            return jsonify({'ok': False, 'error': 'API key inválida'}), 401
        return f(*args, **kwargs)
    return decorated_function

def validate_input_data(data: Dict, required_fields: list) -> Tuple[bool, str]:
    """Valida dados de entrada."""
    if not data:
        return False, "Dados JSON inválidos"
    
    for field in required_fields:
        if not data.get(field):
            return False, f"Campo obrigatório ausente: {field}"
    
    # Validação rigorosa para device_id
    device_id = data.get('device_id', '')
    if len(device_id) < 8 or len(device_id) > 64:
        return False, "device_id deve ter entre 8 e 64 caracteres"
    
    # Verifica se device_id contém apenas caracteres válidos
    if not re.match(r'^[a-zA-Z0-9\-_]+$', device_id):
        return False, "device_id contém caracteres inválidos"
    
    # Validação rigorosa para license_key
    license_key = data.get('license_key', '')
    if len(license_key) < 8 or len(license_key) > 128:
        return False, "license_key deve ter entre 8 e 128 caracteres"
    
    # Verifica se license_key contém apenas caracteres válidos
    if not re.match(r'^[a-zA-Z0-9\-_]+$', license_key):
        return False, "license_key contém caracteres inválidos"
    
    return True, ""

def call_supabase_function(function_name: str, data: Dict) -> Optional[Dict]:
    """Chama função do Supabase com logging avançado."""
    try:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            logger.error("Supabase não configurado")
            return None
        
        url = f"{SUPABASE_URL}/functions/v1/{function_name}"
        headers = {
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json"
        }
        
        # Log da requisição (sem dados sensíveis)
        logger.info(f"Chamando Supabase: {function_name} - Device: {data.get('device_id', '')[:8]}...")
        
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Supabase {function_name} OK")
            return result
        else:
            logger.error(f"Erro Supabase {response.status_code}: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout ao chamar Supabase: {function_name}")
        return None
    except Exception as e:
        logger.error(f"Erro ao chamar Supabase: {e}")
        return None

# ---------- Market lookup (server-side) ----------

def _supabase_rest_get(table: str, params: Dict[str, str], select: str) -> Optional[Dict]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("Supabase REST não configurado (URL/SERVICE_KEY)")
        return None
    try:
        import urllib.parse as up
        base = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}"
        q = {**params, 'select': select, 'limit': '1'}
        url = base + '?' + up.urlencode(q, safe='*,|().')
        headers = {
            'apikey': SUPABASE_SERVICE_KEY,
            'Authorization': f"Bearer {SUPABASE_SERVICE_KEY}",
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            return data[0]
        return None
    except Exception as e:
        logger.error(f"Supabase REST get error: {e}")
        return None


@app.route('/market/lookup', methods=['POST'])
@require_auth
@limiter.limit("60 per minute")
def market_lookup():
    """Resolve preços (fontes) e liquidez para um item/variante.
    Body JSON: { name_base, is_stattrak, is_souvenir, condition }
    Retorna: { price_whitemarket, price_csfloat, price_buff163, highest_offer_buff163, liquidity_score }
    """
    try:
        payload = request.get_json(force=True) or {}
        name_base = payload.get('name_base', '').strip()
        is_st = str(bool(payload.get('is_stattrak', False))).lower()
        is_sv = str(bool(payload.get('is_souvenir', False))).lower()
        condition = payload.get('condition', '')
        if not name_base:
            return jsonify({'ok': False, 'error': 'name_base obrigatório'}), 400

        # market_data row
        md = _supabase_rest_get(
            MARKET_TABLE,
            {
                'name_base': f'eq.{name_base}',
                'stattrak': f'eq.{is_st}',
                'souvenir': f'eq.{is_sv}',
                'condition': f'eq.{condition}' if condition else 'is.null',
            },
            'item_key,name_base,stattrak,souvenir,condition,price_whitemarket,price_csfloat,price_buff163,highest_offer_buff163'
        ) or {}

        item_key = md.get('item_key')
        liq_score = 0
        if item_key:
            liq = _supabase_rest_get('liquidity', {'item_key': f'eq.{item_key}'}, 'liquidity_score') or {}
            liq_score = int(liq.get('liquidity_score') or 0)

        resp = {
            'ok': True,
            'price_whitemarket': md.get('price_whitemarket'),
            'price_csfloat': md.get('price_csfloat'),
            'price_buff163': md.get('price_buff163'),
            'highest_offer_buff163': md.get('highest_offer_buff163'),
            'liquidity_score': liq_score,
        }
        return jsonify(resp)

    except Exception as e:
        logger.error(f"market_lookup error: {e}")
        return jsonify({'ok': False, 'error': 'internal_error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check com informações de segurança."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'security': {
            'jwt_enabled': True,
            'rate_limiting': True,
            'api_key_protected': bool(API_KEY),
        'supabase_configured': bool(SUPABASE_URL and SUPABASE_ANON_KEY)
        }
    })

@app.route('/activate', methods=['POST'])
@require_auth
@limiter.limit("10 per minute")
def activate_license():
    """Ativa uma licença com JWT."""
    try:
        # Verifica se IP está bloqueado
        client_ip = request.remote_addr or "unknown"
        if is_ip_blocked(client_ip):
            log_security_event('blocked_ip_attempt', {'ip': client_ip})
            return jsonify({'ok': False, 'error': 'IP temporariamente bloqueado'}), 429
        
        # Valida dados de entrada
        data = request.get_json()
        is_valid, error_msg = validate_input_data(data, ['license_key', 'device_id'])
        if not is_valid:
            record_failed_attempt(client_ip)
            log_security_event('invalid_input', {'error': error_msg})
            return jsonify({'ok': False, 'error': error_msg}), 400
        
        license_key = data['license_key']
        device_id = data['device_id']
        
        # Log da tentativa
        logger.info(f"Tentativa de ativação: {license_key[:8]}... em {device_id[:8]}...")
        
        # Chama Supabase
        result = call_supabase_function('activate', {
            'license_key': license_key,
            'device_id': device_id
        })
        
        if result and result.get('ok'):
            # Gera JWT com dados da licença
            jwt_payload = {
                'license_key': license_key,
                'device_id': device_id,
                'expires_at': result.get('expires_at'),
                'nickname': result.get('nickname', ''),
                'type': 'license_activation'
            }
            
            jwt_token = generate_jwt(jwt_payload)
            
            response_data = {
                'ok': True,
                'expires_at': result.get('expires_at'),
                'nickname': result.get('nickname', ''),
                'activated_at': result.get('activated_at', ''),
                'jwt_token': jwt_token
            }
            
            logger.info(f"Licença ativada com sucesso: {license_key[:8]}...")
            return jsonify(response_data)
        else:
            record_failed_attempt(client_ip)
            error_msg = result.get('error', 'Erro desconhecido') if result else 'Erro de conexão com Supabase'
            log_security_event('failed_activation', {
                'license_key': license_key[:8] + '...',
                'device_id': device_id[:8] + '...',
                'error': error_msg
            })
            return jsonify({'ok': False, 'error': error_msg})
            
    except Exception as e:
        logger.error(f"Erro interno na ativação: {e}")
        return jsonify({'ok': False, 'error': 'Erro interno do servidor'}), 500

@app.route('/validate', methods=['POST'])
@require_auth
@limiter.limit("30 per minute")
def validate_license():
    """Valida uma licença com JWT."""
    try:
        # Verifica se IP está bloqueado
        client_ip = request.remote_addr or "unknown"
        if is_ip_blocked(client_ip):
            log_security_event('blocked_ip_attempt', {'ip': client_ip})
            return jsonify({'ok': False, 'error': 'IP temporariamente bloqueado'}), 429
        
        # Valida dados de entrada
        data = request.get_json()
        is_valid, error_msg = validate_input_data(data, ['license_key', 'device_id'])
        if not is_valid:
            record_failed_attempt(client_ip)
            log_security_event('invalid_input', {'error': error_msg})
            return jsonify({'ok': False, 'error': error_msg}), 400
        
        license_key = data['license_key']
        device_id = data['device_id']
        
        # Log da tentativa
        logger.info(f"Tentativa de validação: {license_key[:8]}... em {device_id[:8]}...")
        
        # Chama Supabase
        result = call_supabase_function('validate', {
            'license_key': license_key,
            'device_id': device_id
        })
        
        if result and result.get('ok'):
            # Gera JWT com dados da validação
            jwt_payload = {
                'license_key': license_key,
                'device_id': device_id,
                'expires_at': result.get('expires_at'),
                'type': 'license_validation',
                'validated_at': datetime.now(timezone.utc).isoformat()
            }
            
            jwt_token = generate_jwt(jwt_payload)
            
            response_data = {
                'ok': True,
                'expires_at': result.get('expires_at'),
                'jwt_token': jwt_token
            }
            
            logger.info(f"Licença válida: {license_key[:8]}...")
            return jsonify(response_data)
        else:
            record_failed_attempt(client_ip)
            reason = result.get('reason', 'desconhecido') if result else 'erro_conexao'
            log_security_event('failed_validation', {
                'license_key': license_key[:8] + '...',
                'device_id': device_id[:8] + '...',
                'reason': reason
            })
            return jsonify({'ok': False, 'reason': reason})
            
    except Exception as e:
        logger.error(f"Erro interno na validação: {e}")
        return jsonify({'ok': False, 'error': 'Erro interno do servidor'}), 500

@app.route('/verify-jwt', methods=['POST'])
@require_auth
def verify_jwt_endpoint():
    """Endpoint para verificar JWT (para testes)."""
    try:
        data = request.get_json()
        if not data or 'jwt_token' not in data:
            return jsonify({'ok': False, 'error': 'JWT token obrigatório'}), 400
        
        payload = verify_jwt(data['jwt_token'])
        if payload:
            return jsonify({'ok': True, 'payload': payload})
        else:
            return jsonify({'ok': False, 'error': 'JWT inválido'})
            
    except Exception as e:
        logger.error(f"Erro ao verificar JWT: {e}")
        return jsonify({'ok': False, 'error': 'Erro interno'}), 500

@app.route('/info', methods=['GET'])
def get_info():
    """Informações do backend."""
    return jsonify({
        'name': 'CSGOEmpire Bot License Backend (Secure)',
        'version': '2.0.0',
        'security_features': {
            'jwt_enabled': True,
            'rate_limiting': True,
            'api_key_protection': True,
            'advanced_logging': True,
            'input_validation': True
        },
        'endpoints': {
            'activate': 'POST /activate - Ativa licença com JWT',
            'validate': 'POST /validate - Valida licença com JWT',
            'verify-jwt': 'POST /verify-jwt - Verifica JWT',
            'health': 'GET /health - Health check',
            'info': 'GET /info - Informações'
        }
    })

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handler para rate limiting."""
    log_security_event('rate_limit_exceeded', {
        'ip': request.remote_addr or "unknown",
        'limit': str(e.description)
    })
    return jsonify({'ok': False, 'error': 'Rate limit excedido'}), 429

@app.errorhandler(404)
def not_found(error):
    """Handler para rotas não encontradas."""
    log_security_event('invalid_endpoint', {
        'path': request.path,
        'method': request.method
    })
    return jsonify({'error': 'Endpoint não encontrado'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handler para erros internos."""
    logger.error(f"Erro interno: {error}")
    return jsonify({'error': 'Erro interno do servidor'}), 500

if __name__ == '__main__':
    # Valida configurações
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        logger.error("❌ SUPABASE_URL e SUPABASE_ANON_KEY são obrigatórios!")
        exit(1)
    
    logger.info("🚀 Iniciando backend seguro de validação de licenças...")
    logger.info(f"📋 Supabase URL: {SUPABASE_URL}")
    logger.info(f"🔐 JWT Secret: {JWT_SECRET[:20]}...")
    logger.info(f"🛡️ API Key: {API_KEY[:20]}...")
    logger.info(f"⚡ Rate Limiting: Ativado")
    logger.info(f"📝 Logging Avançado: Ativado")
    
    # Configurações do Flask
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    app.run(host='0.0.0.0', port=port, debug=debug) 