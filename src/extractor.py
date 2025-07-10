import asyncio
from typing import Dict, Any
from playwright.async_api import Page
from src.utils import log_error, log_warning, log_debug, handle_exceptions
@handle_exceptions(message="Erro ao extrair dados do estabelecimento", default_return=None)
async def extract_business_data(page: Page, business_element) -> Dict[str, Any]:
    """
    Extrai dados de um estabelecimento comercial do Google Maps
    """
    business_data = {
        "name": None,
        "address": None,
        "phone": None,
        "category": None,
        "rating": None,
        "reviews": None
    }
    
    try:
        # Extrair o nome do estabelecimento
        name = await business_element.get_attribute('aria-label')
        
        if not name:
            name_element = await business_element.query_selector('div[role="heading"]')
            if name_element:
                name = await name_element.inner_text()
        
        if not name:
            name = await business_element.evaluate("""
                (el) => {
                    if (el.hasAttribute('aria-label')) return el.getAttribute('aria-label');
                    const heading = el.querySelector('[role="heading"], h1, h2, h3, .fontHeadlineLarge');
                    return heading ? heading.innerText : null;
                }
            """)
        
        if name:
            business_data["name"] = name.strip()
            
        # Clicar no elemento para abrir os detalhes
        try:
            await business_element.click()
            await page.wait_for_timeout(2000)  # Aguardar carregamento dos detalhes
            
            # Extrair endereço - tenta encontrar o botão com o endereço
            try:
                address_button = await page.query_selector('button[data-item-id="address"]')
                if address_button:
                    address_div = await address_button.query_selector('div.fontBodyMedium')
                    if address_div:
                        address = await address_div.inner_text()
                        business_data["address"] = address.strip()
            except Exception as e:
                log_error(f"Erro ao extrair endereço: {str(e)}")
                
            # Extrair número de telefone - tenta encontrar o botão com o telefone
            try:
                phone_button = await page.query_selector('button[data-item-id^="phone:tel:"]')
                if phone_button:
                    phone_div = await phone_button.query_selector('div.fontBodyMedium')
                    if phone_div:
                        phone = await phone_div.inner_text()
                        business_data["phone"] = phone.strip()
            except Exception as e:
                log_error(f"Erro ao extrair telefone: {str(e)}")
                
            # Extrair categoria do estabelecimento
            try:
                # Primeira tentativa: botão específico com jsaction contendo "category"
                category_button = await page.query_selector('button[jsaction*="category"]')
                if category_button:
                    category = await category_button.inner_text()
                    if category and category.strip():
                        business_data["category"] = category.strip()
                        log_debug(f"Categoria encontrada (jsaction): {category.strip()}")
                
                # Segunda tentativa: botão com classe DkEaL
                if not business_data["category"]:
                    category_button = await page.query_selector('button.DkEaL')
                    if category_button:
                        category = await category_button.inner_text()
                        if category and category.strip():
                            business_data["category"] = category.strip()
                            log_debug(f"Categoria encontrada (DkEaL): {category.strip()}")
                
                # Terceira tentativa: busca mais ampla por botões que podem conter a categoria
                if not business_data["category"]:
                    category_buttons = await page.query_selector_all('button.DkEaL, button[jsaction*="wfvdle470"]')
                    for button in category_buttons:
                        try:
                            text = await button.inner_text()
                            if text and text.strip() and len(text.strip()) > 2:
                                business_data["category"] = text.strip()
                                log_debug(f"Categoria encontrada (busca ampla): {text.strip()}")
                                break
                        except:
                            continue
                
                # Quarta tentativa: JavaScript para buscar o botão de categoria
                if not business_data["category"]:
                    category_js = await page.evaluate("""
                        () => {
                            // Busca por botões que contenham "category" no jsaction
                            const categoryButtons = Array.from(document.querySelectorAll('button[jsaction*="category"]'));
                            if (categoryButtons.length > 0) {
                                return categoryButtons[0].innerText.trim();
                            }
                            
                            // Busca por botões com classe DkEaL
                            const dkealButtons = Array.from(document.querySelectorAll('button.DkEaL'));
                            for (const button of dkealButtons) {
                                const text = button.innerText.trim();
                                if (text && text.length > 2) {
                                    return text;
                                }
                            }
                            
                            // Busca por botões que podem conter categoria próximos à avaliação
                            const allButtons = Array.from(document.querySelectorAll('button'));
                            for (const button of allButtons) {
                                const text = button.innerText.trim();
                                // Verifica se é uma possível categoria (não é número, não é muito longo)
                                if (text && text.length > 2 && text.length < 50 && 
                                    !text.match(/^[0-9,]+$/) && 
                                    !text.includes('avaliações') &&
                                    !text.includes('estrelas') &&
                                    !text.includes('(') &&
                                    button.jsAction && button.jsAction.includes('category')) {
                                    return text;
                                }
                            }
                            
                            return null;
                        }
                    """)
                    if category_js and category_js.strip():
                        business_data["category"] = category_js.strip()
                        log_debug(f"Categoria encontrada (JavaScript): {category_js.strip()}")
                
                if not business_data["category"]:
                    log_warning("Não foi possível extrair a categoria do estabelecimento")
                    # Debug da estrutura da página
                    debug_info = await debug_page_structure(page)
                    if debug_info and debug_info.get('possibleCategories'):
                        log_debug(f"Possíveis categorias encontradas: {[cat['text'] for cat in debug_info['possibleCategories']]}")
                
            except Exception as e:
                log_error(f"Erro ao extrair categoria: {str(e)}")
              # Extrair avaliação (rating)
            try:
                # Tenta extrair do primeiro seletor - página detalhada
                rating_element = await page.query_selector('span[aria-hidden="true"]')
                if rating_element:
                    rating = await rating_element.inner_text()
                    business_data["rating"] = rating.strip()
                
                # Se não encontrou, tenta extrair do elemento span com class ceNzKf (conforme no HTML exemplo)
                if not business_data["rating"]:
                    rating_element = await page.query_selector('span.ceNzKf[role="img"]')
                    if rating_element:
                        rating_text = await rating_element.get_attribute('aria-label')
                        if rating_text and "estrelas" in rating_text:
                            rating = rating_text.split('estrelas')[0].strip()
                            business_data["rating"] = rating
                
                # Tenta extrair diretamente do texto "4,8" que está em um span com aria-hidden="true"
                if not business_data["rating"]:
                    rating_span = await page.evaluate("""
                        () => {
                            const spans = Array.from(document.querySelectorAll('span[aria-hidden="true"]'));
                            const ratingSpan = spans.find(span => /^[0-9],[0-9]$/.test(span.innerText.trim()));
                            return ratingSpan ? ratingSpan.innerText : null;
                        }
                    """)
                    if rating_span:
                        business_data["rating"] = rating_span.strip()
            except Exception as e:
                log_error(f"Erro ao extrair avaliação: {str(e)}")
            
            # Extrair número de avaliações (reviews)
            try:
                reviews_element = await page.query_selector('span[aria-label$="avaliações"]')
                if reviews_element:
                    reviews_text = await reviews_element.get_attribute('aria-label')
                    if reviews_text:
                        reviews = reviews_text.split()[0]
                        business_data["reviews"] = reviews.strip()
                
                if not business_data["reviews"]:
                    reviews_element = await page.query_selector('span span span:has-text("(")')
                    if reviews_element:
                        reviews_text = await reviews_element.inner_text()
                        if reviews_text and '(' in reviews_text:
                            reviews = reviews_text.strip('()').strip()
                            business_data["reviews"] = reviews
            except Exception as e:
                log_error(f"Erro ao extrair número de avaliações: {str(e)}")
                
        except Exception as e:
            log_error(f"Erro ao clicar no elemento ou aguardar carregamento: {str(e)}")
            
    except Exception as e:
        log_error(f"Erro ao extrair dados: {str(e)}")
    
    # Retorna os dados mesmo se apenas alguns campos forem preenchidos
    return business_data if business_data["name"] else None

async def debug_page_structure(page: Page):
    """
    Função auxiliar para debugar a estrutura da página quando não conseguir extrair dados
    """
    try:
        debug_info = await page.evaluate("""
            () => {
                const result = {
                    categoryButtons: [],
                    allButtons: [],
                    possibleCategories: []
                };
                
                // Encontra todos os botões com categoria
                const categoryBtns = document.querySelectorAll('button[jsaction*="category"]');
                categoryBtns.forEach(btn => {
                    result.categoryButtons.push({
                        text: btn.innerText.trim(),
                        jsaction: btn.getAttribute('jsaction'),
                        className: btn.className
                    });
                });
                
                // Encontra botões DkEaL
                const dkealBtns = document.querySelectorAll('button.DkEaL');
                dkealBtns.forEach(btn => {
                    result.allButtons.push({
                        text: btn.innerText.trim(),
                        className: btn.className,
                        jsaction: btn.getAttribute('jsaction')
                    });
                });
                
                // Busca por possíveis categorias
                const allBtns = document.querySelectorAll('button');
                allBtns.forEach(btn => {
                    const text = btn.innerText.trim();
                    if (text && text.length > 2 && text.length < 50 && 
                        !text.match(/^[0-9,]+$/) && 
                        !text.includes('avaliações') &&
                        !text.includes('estrelas') &&
                        !text.includes('(') &&
                        !text.includes('Direções') &&
                        !text.includes('Ligar')) {
                        result.possibleCategories.push({
                            text: text,
                            className: btn.className,
                            jsaction: btn.getAttribute('jsaction')
                        });
                    }
                });
                
                return result;
            }
        """)
        
        log_debug(f"Estrutura da página para debug: {debug_info}")
        return debug_info
        
    except Exception as e:
        log_error(f"Erro ao debugar estrutura da página: {str(e)}")
        return None
