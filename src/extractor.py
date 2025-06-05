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
                category_button = await page.query_selector('button.DkEaL, button[jsaction*="category"]')
                if category_button:
                    category = await category_button.inner_text()
                    business_data["category"] = category.strip()
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
