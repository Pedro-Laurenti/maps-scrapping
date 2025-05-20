import json
import sys
from typing import Dict, Any

def read_input_params() -> Dict[str, Any]:
    """
    Função legada mantida para compatibilidade com o script original.
    Na API, usamos o modelo Pydantic diretamente.
    """
    try:
        with open("params.json", "r", encoding="utf-8") as f:
            input_data = json.load(f)
        
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
    except (json.JSONDecodeError, FileNotFoundError):
        error_msg = {
            "error": "Formato inválido ou arquivo não encontrado",
            "message": "Os parâmetros devem ser fornecidos em formato JSON no arquivo params.json"
        }
        print(json.dumps(error_msg))
        sys.exit(1)

def output_results(results: list) -> None:
    """
    Imprime os resultados como JSON.
    Garante que a saída é UTF-8 válido e que os caracteres especiais são mantidos.
    """
    # Serializa para JSON com encoding UTF-8 e garantindo que caracteres não-ASCII são mantidos
    output = json.dumps(results, ensure_ascii=False)
    
    # Para maior compatibilidade, explicitamente codifica como UTF-8 e imprime os bytes
    # Isso ajuda a evitar problemas de codificação no pipe do subprocess
    if hasattr(sys.stdout, 'buffer'):
        # Se stdout suporta buffer (normal no Python 3)
        sys.stdout.buffer.write(output.encode('utf-8'))
        sys.stdout.buffer.write(b'\n')
        sys.stdout.buffer.flush()
    else:
        # Fallback para o comportamento padrão
        print(output)

def log_error(message: str) -> None:
    print(message, file=sys.stderr)

def handle_error(error: Exception) -> None:
    error_msg = {
        "error": "Erro durante a execução",
        "message": str(error)
    }
    print(json.dumps(error_msg, ensure_ascii=False))
    # Removido sys.exit(1) para não encerrar o servidor API

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
