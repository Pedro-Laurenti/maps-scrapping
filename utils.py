import json
import sys
from typing import Dict, Any

def read_input_params() -> Dict[str, Any]:
    try:
        input_data = json.loads(sys.stdin.read())
        region = input_data.get("region", "")
        business_type = input_data.get("business_type", "")
        max_results = int(input_data.get("max_results", 10))
        keywords = input_data.get("keywords", "")
        if not region or not business_type:
            error_msg = {
                "error": "Parâmetros insuficientes",
                "message": "É necessário fornecer ao menos região e tipo de negócio"
            }
            print(json.dumps(error_msg))
            sys.exit(1)
        return {
            "region": region,
            "business_type": business_type,
            "max_results": max_results,
            "keywords": keywords
        }
    except json.JSONDecodeError:
        error_msg = {
            "error": "Formato inválido",
            "message": "Os parâmetros devem ser fornecidos em formato JSON"
        }
        print(json.dumps(error_msg))
        sys.exit(1)

def output_results(results: list) -> None:
    print(json.dumps(results, ensure_ascii=False))

def log_error(message: str) -> None:
    print(message, file=sys.stderr)

def handle_error(error: Exception) -> None:
    error_msg = {
        "error": "Erro durante a execução",
        "message": str(error)
    }
    print(json.dumps(error_msg))
    sys.exit(1)

def normalize_url_string(text: str) -> str:
    """
    Normaliza uma string para uso em URLs, removendo acentos e substituindo caracteres especiais
    """
    import unicodedata
    import re
    
    # Normaliza a string: remove acentos, mas mantém as letras
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    
    # Remove caracteres especiais, mantém apenas letras, números, espaços e alguns caracteres básicos
    text = re.sub(r'[^\w\s\-]', '', text)
    
    # Substitui espaços por +
    text = text.replace(' ', '+')
    
    return text
