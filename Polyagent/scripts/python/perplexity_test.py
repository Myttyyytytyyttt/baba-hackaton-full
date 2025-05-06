#!/usr/bin/env python
"""
Script para probar la integración de Perplexity con PolyAgent
"""

import os
import sys
import time
from colorama import Fore, Style, init

# Asegurar que la ruta base del proyecto está en sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Importar módulos de PolyAgent
from agents.connectors.perplexity import PerplexityConnector
from agents.polymarket.gamma import GammaMarketClient

# Inicializar colorama
init()

def test_perplexity_connector():
    """
    Prueba el conector de Perplexity con un mercado de ejemplo
    """
    print(f"{Fore.CYAN}=== Probando integración de Perplexity con PolyAgent ==={Style.RESET_ALL}")
    
    # Comprobar si la API key está configurada
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print(f"{Fore.RED}Error: No se encontró PERPLEXITY_API_KEY en las variables de entorno.{Style.RESET_ALL}")
        print("Por favor, añade esta variable a tu archivo .env")
        return False
    
    print(f"{Fore.GREEN}API key de Perplexity encontrada ✓{Style.RESET_ALL}")
    
    # Inicializar conector
    perplexity = PerplexityConnector()
    
    # Comprobar disponibilidad
    if not perplexity.is_available():
        print(f"{Fore.RED}Error: El conector de Perplexity no está disponible.{Style.RESET_ALL}")
        return False
    
    print(f"{Fore.GREEN}Conector de Perplexity inicializado correctamente ✓{Style.RESET_ALL}")
    
    # Obtener un mercado real de Polymarket para probar
    try:
        gamma = GammaMarketClient()
        print(f"{Fore.BLUE}Obteniendo mercados activos de Polymarket...{Style.RESET_ALL}")
        
        # Obtener mercados con mayor volumen
        markets = gamma.get_markets(
            querystring_params={
                "active": True, 
                "closed": False, 
                "limit": 5,
                "order": "volume",
                "ascending": False
            }
        )
        
        if not markets or len(markets) == 0:
            print(f"{Fore.RED}No se encontraron mercados activos en Polymarket.{Style.RESET_ALL}")
            # Usar un mercado de ejemplo en su lugar
            test_market = "Will Trump win the 2024 US Presidential Election?"
            print(f"{Fore.YELLOW}Usando mercado de ejemplo: {test_market}{Style.RESET_ALL}")
        else:
            # Usar el mercado con mayor volumen
            test_market = markets[0]["question"]
            market_id = markets[0]["id"]
            volume = float(markets[0].get("volume", 0))
            print(f"{Fore.GREEN}Mercado seleccionado: {test_market}")
            print(f"ID: {market_id}")
            print(f"Volumen: ${volume:,.2f}{Style.RESET_ALL}")
            
        # Realizar análisis con Perplexity
        print(f"\n{Fore.CYAN}Obteniendo análisis en tiempo real con Perplexity...{Style.RESET_ALL}")
        print(f"Esto puede tardar unos segundos mientras Perplexity busca información actualizada...")
        
        start_time = time.time()
        result = perplexity.get_market_analysis(test_market)
        end_time = time.time()
        
        if not result.get("success", False):
            print(f"{Fore.RED}Error obteniendo análisis: {result.get('error', 'Error desconocido')}{Style.RESET_ALL}")
            return False
        
        # Mostrar resultados
        print(f"{Fore.GREEN}Análisis completado en {end_time - start_time:.2f} segundos ✓{Style.RESET_ALL}")
        
        analysis = result.get("analysis", "")
        probability = perplexity.extract_probability(analysis)
        
        print(f"\n{Fore.YELLOW}=== ANÁLISIS DE PERPLEXITY ===")
        print(f"{analysis[:1000]}...")  # Mostrar primeros 1000 caracteres
        print(f"\n{Fore.CYAN}... (análisis truncado) ...{Style.RESET_ALL}")
        
        print(f"\n{Fore.MAGENTA}=== PROBABILIDAD EXTRAÍDA ===")
        print(f"Probabilidad estimada: {probability:.4f} ({probability*100:.2f}%){Style.RESET_ALL}")
        
        return True
        
    except Exception as e:
        print(f"{Fore.RED}Error durante la prueba: {str(e)}{Style.RESET_ALL}")
        return False

if __name__ == "__main__":
    success = test_perplexity_connector()
    
    if success:
        print(f"\n{Fore.GREEN}✅ Prueba completada con éxito! Perplexity está correctamente integrado con PolyAgent.{Style.RESET_ALL}")
        print(f"Ahora puedes usar Perplexity para análisis de mercados en tiempo real.")
    else:
        print(f"\n{Fore.RED}❌ La prueba falló. Por favor revisa los errores anteriores.{Style.RESET_ALL}")
        print(f"Asegúrate de que la API key de Perplexity está configurada correctamente en tu archivo .env") 