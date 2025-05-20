import asyncio
import sys
import json
from src.utils import read_input_params, output_results, handle_error
from src.crawler import scrape_google_maps

async def main():
    try:
        # Verifica se foi passado um arquivo de parâmetros como argumento
        if len(sys.argv) > 1:
            params_file = sys.argv[1]
            with open(params_file, 'r', encoding='utf-8') as f:
                params = json.load(f)
        else:
            # Usa o método tradicional de leitura dos parâmetros
            params = read_input_params()
            
        results = await scrape_google_maps(
            region=params["region"],
            business_type=params["business_type"],
            max_results=params["max_results"],
            keywords=params["keywords"]
        )
        output_results(results)
    except Exception as e:
        handle_error(e)

if __name__ == "__main__":
    asyncio.run(main())
