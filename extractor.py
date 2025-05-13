import asyncio
from typing import Dict, Any
from playwright.async_api import Page
from utils import log_error

async def extract_business_data(page: Page, business_element) -> Dict[str, Any]:
    business_data = {
        "name": None,
        "address": None,
        "phone": None
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
                
        except Exception as e:
            log_error(f"Erro ao clicar no elemento ou aguardar carregamento: {str(e)}")
            
    except Exception as e:
        log_error(f"Erro ao extrair dados: {str(e)}")
    
    # Retorna os dados mesmo se apenas alguns campos forem preenchidos
    return business_data if business_data["name"] else None

# Mantém a função original para compatibilidade
async def extract_business_name(page: Page, business_element) -> Dict[str, Any]:
    return await extract_business_data(page, business_element)
