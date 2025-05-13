import asyncio
from utils import read_input_params, output_results, handle_error
from crawler import scrape_google_maps

async def main():
    try:
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
