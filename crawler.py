import asyncio
from typing import Dict, List, Any
from playwright.async_api import async_playwright, Page

from utils import log_error, normalize_url_string
from extractor import extract_business_data

async def scroll_to_load_more(page: Page, max_scrolls: int = 5):
    try:
        scroll_containers = [
            'div[role="feed"]',
            'div.m6QErb[role="region"]',
            'div.m6QErb-qJTHM-haAclf'
        ]
        
        container_selector = None
        for selector in scroll_containers:
            container = await page.query_selector(selector)
            if container:
                container_selector = selector
                break
        
        if not container_selector:
            log_error("Não foi possível encontrar o contêiner de resultados para scroll")
            return
        
        initial_count = await page.evaluate(f'''
            () => {{
                const container = document.querySelector('{container_selector}');
                return container ? container.querySelectorAll('a[href^="https://www.google.com/maps/place"]').length : 0;
            }}
        ''')
        
        total_scrolls = 0
        for i in range(max_scrolls):
            await page.evaluate(f'''
                () => {{
                    const container = document.querySelector('{container_selector}');
                    if (container) {{
                        container.scrollTop = container.scrollHeight;
                        return true;
                    }}
                    return false;
                }}
            ''')
            
            await asyncio.sleep(2)
            
            new_count = await page.evaluate(f'''
                () => {{
                    const container = document.querySelector('{container_selector}');
                    return container ? container.querySelectorAll('a[href^="https://www.google.com/maps/place"]').length : 0;
                }}
            ''')
            
            if new_count <= initial_count and i > 0:
                break
                
            total_scrolls = i + 1
            initial_count = new_count
            
            if new_count >= 30:
                break
                
        log_error(f"{total_scrolls} rolagens: {initial_count} elementos encontrados")
    
    except Exception as e:
        log_error(f"Erro durante o scroll: {str(e)}")

async def scrape_google_maps(region: str, business_type: str, max_results: int = 10, keywords: str = None) -> List[Dict[str, Any]]:
    results = []
    
    # Garante que os caracteres são exibidos corretamente no log
    try:
        region_display = region.encode('latin1').decode('utf-8')
    except:
        region_display = region
        
    log_error(f"Iniciando busca por '{business_type}' em '{region_display}'...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.set_viewport_size({"width": 1366, "height": 768})
        search_query = f"{business_type} em {region}"
        if keywords:
            search_query += f" {keywords}"
        
        # Normaliza a query removendo acentos e caracteres especiais
        encoded_query = normalize_url_string(search_query)
        url = f"https://www.google.com/maps/search/{encoded_query}"
        
        log_error(f"Navegando: {url}")
        try:
            await page.goto(url, timeout=120000)
            
            try:
                await page.wait_for_selector(
                    'div[role="feed"], a[href^="https://www.google.com/maps/place"], h1', 
                    timeout=30000
                )
                log_error("Elementos carregados")
            except Exception as e:
                log_error(f"Aviso: Não conseguiu detectar elementos específicos: {str(e)}")
                await asyncio.sleep(5)
                
            await asyncio.sleep(3)
            
        except Exception as e:
            log_error(f"Erro ao navegar para a página: {str(e)}")
            await browser.close()
            return results
        
        await scroll_to_load_more(page, max_scrolls=5)
        
        log_error("\nExtraindo dados dos estabelecimentos...")
        
        try:
            business_elements = await page.query_selector_all('a.hfpxzc[aria-label]')
            log_error(f"Encontrados {len(business_elements)} estabelecimentos")
            
            if not business_elements or len(business_elements) == 0:
                business_elements = await page.query_selector_all('a[href^="https://www.google.com/maps/place"][aria-label]')
                log_error(f"Encontrados {len(business_elements)} elementos de negócios com aria-label (busca alternativa)")
            
            if not business_elements or len(business_elements) == 0:
                business_elements = await page.query_selector_all('a[href^="https://www.google.com/maps/place"]')
                log_error(f"Encontrados {len(business_elements)} elementos pelo seletor de links")
            
            count = 0
            for element in business_elements:
                if count >= max_results:
                    break
                try:
                    business_data = await extract_business_data(page, element)
                    
                    if business_data and business_data.get("name"):
                        results.append(business_data)
                        count += 1
                except Exception as e:
                    log_error(f"Erro ao processar elemento: {str(e)}")
            
            log_error(f"\nTotal de {len(results)} estabelecimentos extraídos.")
            
        except Exception as e:
            log_error(f"Erro durante a extração: {str(e)}")
        
        await browser.close()
        
    return results
