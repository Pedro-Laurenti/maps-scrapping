import asyncio
from typing import Dict, List, Any
from playwright.async_api import async_playwright, Page

from src.utils import log_error, log_warning, log_info, log_debug, normalize_url_string, handle_exceptions
from src.extractor import extract_business_data
from src.database import check_phone_exists

@handle_exceptions(message="Erro durante o scroll para carregar mais resultados", default_return=None)
async def scroll_to_load_more(page: Page, max_scrolls: int = 5):
    # Removido bloco try/except redundante pois já temos o decorator @handle_exceptions
    scroll_containers = [
        'div[role="feed"]',
        'div.m6QErb[role="region"]',
        'div.m6QErb-qJTHM-haAclf',
        'div.m6QErb',
        'div[role="main"]'  # Container mais externo, caso não encontre os específicos
    ]
    
    container_selector = None
    for selector in scroll_containers:
        container = await page.query_selector(selector)
        if container:
            container_selector = selector
            break
    
    if not container_selector:
        log_warning("Não foi possível encontrar o contêiner de resultados para scroll. Tentando scroll na página toda.")
        # Se não encontrar container específico, tenta scroll na página toda
        container_selector = "body"
    
    initial_count = await page.evaluate(f'''
        () => {{
            const container = document.querySelector('{container_selector}');
            return container ? document.querySelectorAll('a[href^="https://www.google.com/maps/place"]').length : 0;
        }}
    ''')
    
    log_info(f"Contagem inicial: {initial_count} elementos")
    
    total_scrolls = 0
    previous_count = initial_count
    no_change_count = 0
    
    for i in range(max_scrolls):
        # Executa o scroll de duas maneiras diferentes para maior eficácia
        await page.evaluate(f'''
            () => {{
                // Método 1: Scroll no container específico
                const container = document.querySelector('{container_selector}');
                if (container) {{
                    container.scrollTop = container.scrollHeight;
                }}
                
                // Método 2: Scroll usando window para garantir
                window.scrollTo(0, document.body.scrollHeight);
                
                return true;
            }}
        ''')
        
        # Varia o tempo de espera para dar chance dos elementos carregarem
        wait_time = 2 + (i % 2)  # Alterna entre 2 e 3 segundos
        await asyncio.sleep(wait_time)
        
        # A cada iteração tenta uma estratégia diferente para garantir carregamento de novos itens
        try:
            if i % 4 == 0:
                # Cliques em botões "Carregar mais"
                for button_selector in [
                    'button[jsaction*="load-more"]', 
                    'button:has-text("Mostrar mais")', 
                    'button:has-text("Ver mais")',
                    'button:has-text("Load more")',
                    'button[aria-label*="results"]',
                    'button[aria-label*="Próxima"]',
                    'button[aria-label*="Next"]'
                ]:
                    load_more_button = await page.query_selector(button_selector)
                    if load_more_button:
                        await load_more_button.click()
                        await asyncio.sleep(3)
                        log_info(f"Clicou em botão '{button_selector}' para carregar mais resultados")
                        break
            elif i % 4 == 1:
                # Simula pressionar Page Down para um scroll mais natural
                await page.keyboard.press("PageDown")
                await asyncio.sleep(1)
            elif i % 4 == 2:
                # Move o mouse para a parte inferior para ativar carregamentos baseados em hover
                await page.mouse.move(500, 700)
                await asyncio.sleep(1)
        except Exception as e:
            log_warning(f"Erro em operações adicionais de scroll: {str(e)}")
        
        # Verifica se carregou mais itens
        new_count = await page.evaluate(f'''
            () => {{
                return document.querySelectorAll('a[href^="https://www.google.com/maps/place"]').length;
            }}
        ''')
        
        log_info(f"Scroll {i+1}: {new_count} elementos encontrados")
        
        # Lógica aprimorada para determinar quando parar
        if new_count <= previous_count:
            no_change_count += 1
            # Se já tentamos diferentes técnicas e nada mudou, talvez esteja no fim
            if no_change_count >= 4:
                log_info("Nenhum novo item carregado após múltiplas tentativas, parando o scroll")
                break
        else:
            no_change_count = 0  # Reseta o contador
            
        total_scrolls = i + 1
        previous_count = new_count
        
        # Se tivermos carregado um número muito grande de itens, podemos considerar suficiente
        if new_count >= 150:
            log_info("Atingido um grande número de itens, parando o scroll")
            break
        
        # Pausa aleatória para evitar detecção de automação
        random_pause = 0.3 + (i % 3) * 0.2  # Entre 0.3 e 0.7 segundos
        await asyncio.sleep(random_pause)
            
    log_info(f"{total_scrolls} rolagens: {previous_count} elementos encontrados")

@handle_exceptions(message="Erro durante a extração de dados do Google Maps", default_return=[])
async def scrape_google_maps(region: str, business_type: str, max_results: int = 10, keywords: str = None, batch_size: int = None, offset: int = 0) -> List[Dict[str, Any]]:
    results = []
    
    # Garante que os caracteres são exibidos corretamente no log
    try:
        region_display = region.encode('latin1').decode('utf-8')
    except:
        region_display = region
        
    log_info(f"Iniciando busca por '{business_type}' em '{region_display}'...")
    
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
        
        log_info(f"Navegando: {url}")
        try:
            await page.goto(url, timeout=120000)
            
            try:
                await page.wait_for_selector(
                    'div[role="feed"], a[href^="https://www.google.com/maps/place"], h1', 
                    timeout=30000
                )
                log_debug("Elementos carregados")
            except Exception as e:
                log_warning(f"Não conseguiu detectar elementos específicos: {str(e)}")
                await asyncio.sleep(5)
                
            await asyncio.sleep(3)
            
        except Exception as e:
            log_error(f"Erro ao navegar para a página: {str(e)}")
            await browser.close()
            return results
        
        # Para grande volume de resultados, faça mais scrolls
        # Inicialmente faz metade dos scrolls calculados, poderá fazer mais se necessário
        max_scrolls = 5
        if max_results > 20:
            max_scrolls = max(10, max_results // 5)
        
        initial_scrolls = max(3, max_scrolls // 2)
        await scroll_to_load_more(page, max_scrolls=initial_scrolls)
        
        log_info("Extraindo dados dos estabelecimentos...")
        
        try:
            business_elements = await page.query_selector_all('a.hfpxzc[aria-label]')
            log_info(f"Encontrados {len(business_elements)} estabelecimentos")
            
            if not business_elements or len(business_elements) == 0:
                business_elements = await page.query_selector_all('a[href^="https://www.google.com/maps/place"][aria-label]')
                log_info(f"Encontrados {len(business_elements)} elementos de negócios com aria-label (busca alternativa)")
            
            if not business_elements or len(business_elements) == 0:
                business_elements = await page.query_selector_all('a[href^="https://www.google.com/maps/place"]')
                log_info(f"Encontrados {len(business_elements)} elementos pelo seletor de links")
            
            # Se tivermos um offset, pule os primeiros elementos
            if offset > 0:
                if offset < len(business_elements):
                    business_elements = business_elements[offset:]
                else:
                    business_elements = []
            
            count = 0
            processed = 0
            max_attempts = 3  # Número máximo de tentativas adicionais de scroll quando não encontramos novos leads
            
            # Função auxiliar para processar elementos do Google Maps
            async def process_elements(elements):
                nonlocal count, processed
                
                for i, element in enumerate(elements):
                    if count >= max_results:
                        return True  # Indica que completamos o número necessário
                        
                    try:
                        processed += 1
                        business_data = await extract_business_data(page, element)
                        
                        if business_data and business_data.get("name"):
                            # Requisito #2: Verifica se tem número de telefone
                            if not business_data.get("phone"):
                                log_warning(f"Negócio '{business_data.get('name')}' descartado: não possui telefone")
                                continue
                            
                            # Requisito #1: Verifica se o número de telefone já existe no banco de dados
                            if await check_phone_exists(business_data.get("phone", "")):
                                log_info(f"Negócio '{business_data.get('name')}' com telefone '{business_data.get('phone')}' já existe no banco. Pulando...")
                                continue
                                
                            # Se chegou aqui, o negócio tem telefone e não está duplicado
                            results.append(business_data)
                            count += 1
                            log_info(f"Adicionado negócio #{count}/{max_results}: {business_data.get('name')} - {business_data.get('phone')}")
                            
                            # A cada 10 itens processados, pausa brevemente para evitar bloqueios
                            if count % 10 == 0:
                                await asyncio.sleep(1)
                    except Exception as e:
                        log_warning(f"Erro ao processar elemento: {str(e)}")
                
                return False  # Indica que ainda precisamos de mais elementos
            
            # Primeira passagem pelos elementos já coletados
            completed = await process_elements(business_elements)
            
            # Continue fazendo scrolls e tentando obter mais elementos até atingir max_results
            remaining_scrolls = 30  # Aumentamos o limite de scrolls para garantir mais dados
            attempts_without_new_elements = 0
            last_success = True  # Indica se o último scroll trouxe novos elementos
            max_failed_attempts = max_attempts  # Contador de tentativas sem novos elementos
            
            # Lógica aprimorada: continuar tentando enquanto não alcançamos max_results
            while count < max_results and (max_failed_attempts > 0):
                log_info(f"Coletados {count}/{max_results} leads válidos. Realizando mais scrolls para encontrar leads adicionais...")
                
                if attempts_without_new_elements >= 3 and not last_success:
                    # Se estamos tendo dificuldades em achar novos elementos, tenta rolar mais e procurar em outras áreas
                    log_info("Tentando estratégia alternativa para encontrar mais leads...")
                    try:
                        # Tenta clicar em "Mostrar mais resultados" ou similar
                        for button_selector in [
                            'button[jsaction*="load-more"]', 
                            'button:has-text("Mostrar mais")', 
                            'button:has-text("Ver mais")',
                            'button:has-text("Load more")',
                            'button:has-text("Next")',
                            'button[aria-label*="Próxima"]',
                            'button[aria-label*="Next"]',
                            'button[aria-label*="results"]'
                        ]:
                            load_more_button = await page.query_selector(button_selector)
                            if load_more_button:
                                await load_more_button.click()
                                log_info(f"Clicou em botão '{button_selector}' para carregar mais resultados")
                                await asyncio.sleep(3)  # Aguarda mais tempo após clicar
                                break
                    except Exception as e:
                        log_warning(f"Erro ao tentar estratégia alternativa: {str(e)}")
                
                # Faz mais scroll para tentar encontrar mais leads
                scroll_count = 3  # Aumentamos para fazer 3 scrolls por vez
                if remaining_scrolls <= 0:
                    log_warning("Limite de scrolls atingido. Aumentando o limite para obter mais resultados.")
                    remaining_scrolls = 10  # Damos mais algumas tentativas
                
                remaining_scrolls -= scroll_count
                
                # Executa mais scrolls
                await scroll_to_load_more(page, max_scrolls=scroll_count)
                
                # Obtém a lista atualizada de elementos após o scroll
                old_element_count = len(business_elements)
                business_elements = await page.query_selector_all('a.hfpxzc[aria-label]')
                
                if not business_elements or len(business_elements) == 0:
                    business_elements = await page.query_selector_all('a[href^="https://www.google.com/maps/place"][aria-label]')
                
                if not business_elements or len(business_elements) == 0:
                    business_elements = await page.query_selector_all('a[href^="https://www.google.com/maps/place"]')
                
                # Verifica se conseguimos mais elementos
                if len(business_elements) <= old_element_count:
                    attempts_without_new_elements += 1
                    last_success = False
                    max_failed_attempts -= 1
                    log_warning(f"Não foram encontrados novos elementos. Tentativas restantes: {max_failed_attempts}")
                    
                    # Se já tentamos várias vezes sem sucesso, esperamos um pouco e tentamos novamente
                    if attempts_without_new_elements % 3 == 0:
                        log_info("Aguardando um pouco mais antes da próxima tentativa...")
                        await asyncio.sleep(5)  # Espera um pouco mais entre tentativas
                else:
                    # Processa apenas os novos elementos
                    new_elements = business_elements[old_element_count:]
                    log_info(f"Encontrados {len(new_elements)} novos elementos após scroll adicional")
                    
                    attempts_without_new_elements = 0  # Reseta o contador de falhas
                    last_success = True
                    max_failed_attempts = max_attempts  # Restaura o número de tentativas
                    
                    # Processa os novos elementos
                    completed = await process_elements(new_elements)
                    if completed:
                        break  # Atingimos max_results
                        
                # Verifica se já processamos muitos elementos sem sucesso (eficiência)
                if processed > max_results * 5 and count < max_results * 0.5:
                    log_warning(f"Eficiência muito baixa: {count}/{processed} ({count/processed*100:.1f}%). Verificando se devemos continuar...")
                    
                    # Se a eficiência for muito baixa, reduzimos o número de tentativas restantes
                    if max_failed_attempts > 2:
                        max_failed_attempts = 2
            
            if count >= max_results:
                log_info(f"Meta atingida: {count}/{max_results} estabelecimentos válidos extraídos de {processed} processados.")
            else:
                log_warning(f"Meta parcialmente atingida: {count}/{max_results} estabelecimentos válidos extraídos de {processed} processados.")
                if count == 0:
                    log_warning("Nenhum resultado válido encontrado que atenda aos critérios.")
                
            efficiency = (count / processed * 100) if processed > 0 else 0
            log_info(f"Eficiência da extração: {efficiency:.1f}% (quanto maior, melhor)")
            
        except Exception as e:
            log_error(f"Erro durante a extração: {str(e)}")
        
        await browser.close()
        
    return results
