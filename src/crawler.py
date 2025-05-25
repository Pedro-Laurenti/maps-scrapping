import asyncio
from typing import Dict, List, Any
from playwright.async_api import async_playwright, Page

from src.utils import log_error, normalize_url_string
from src.extractor import extract_business_data

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
        
        log_error(f"Contagem inicial: {initial_count} elementos")
        
        total_scrolls = 0
        previous_count = initial_count
        no_change_count = 0
        
        for i in range(max_scrolls):
            # Executa o scroll
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
            
            # Aguarda um pouco para carregar
            await asyncio.sleep(2)
            
            # Para grandes volumes, ocasionalmente faça clique em "Mostrar mais resultados"
            if i % 3 == 0:
                try:
                    # Tenta clicar em diferentes botões que podem carregar mais resultados
                    for button_selector in [
                        'button[jsaction*="load-more"]', 
                        'button:has-text("Mostrar mais")', 
                        'button:has-text("Ver mais")',
                        'button:has-text("Load more")',
                        'button[aria-label*="results"]'
                    ]:
                        load_more_button = await page.query_selector(button_selector)
                        if load_more_button:
                            await load_more_button.click()
                            await asyncio.sleep(3)  # Aguarda mais tempo após clicar
                            break
                except Exception as e:
                    log_error(f"Erro ao tentar clicar em 'Mostrar mais': {str(e)}")
            
            # Verifica se carregou mais itens
            new_count = await page.evaluate(f'''
                () => {{
                    const container = document.querySelector('{container_selector}');
                    return container ? container.querySelectorAll('a[href^="https://www.google.com/maps/place"]').length : 0;
                }}
            ''')
            
            log_error(f"Scroll {i+1}: {new_count} elementos encontrados")
            
            # Se não houver mudança em 3 tentativas consecutivas, podemos parar
            if new_count <= previous_count:
                no_change_count += 1
                if no_change_count >= 3:
                    log_error("Nenhum novo item carregado após 3 tentativas, parando o scroll")
                    break
            else:
                no_change_count = 0  # Reseta o contador de "sem mudança"
                
            total_scrolls = i + 1
            previous_count = new_count
            
            # Se tivermos carregado muitos itens, podemos parar
            if new_count >= 100:
                log_error("Atingido um grande número de itens, parando o scroll")
                break
                
        log_error(f"{total_scrolls} rolagens: {previous_count} elementos encontrados")
    
    except Exception as e:
        log_error(f"Erro durante o scroll: {str(e)}")

async def scrape_google_maps(region: str, business_type: str, max_results: int = 10, keywords: str = None, batch_size: int = None, offset: int = 0) -> List[Dict[str, Any]]:
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
        
        # Para grande volume de resultados, faça mais scrolls
        max_scrolls = 5
        if max_results > 20:
            max_scrolls = max(10, max_results // 5)
            
        await scroll_to_load_more(page, max_scrolls=max_scrolls)
        
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
            
            # Se tivermos um offset, pule os primeiros elementos
            if offset > 0:
                if offset < len(business_elements):
                    business_elements = business_elements[offset:]
                else:
                    business_elements = []
            
            count = 0
            for element in business_elements:
                if count >= max_results:
                    break
                try:
                    business_data = await extract_business_data(page, element)
                    
                    if business_data and business_data.get("name"):
                        results.append(business_data)
                        count += 1
                        
                        # A cada 10 itens processados, pausa brevemente para evitar bloqueios
                        if count % 10 == 0:
                            await asyncio.sleep(1)
                except Exception as e:
                    log_error(f"Erro ao processar elemento: {str(e)}")
            
            log_error(f"\nTotal de {len(results)} estabelecimentos extraídos.")
            
        except Exception as e:
            log_error(f"Erro durante a extração: {str(e)}")
        
        await browser.close()
        
    return results
