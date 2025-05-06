from agents.application.executor import Executor as Agent
from agents.polymarket.gamma import GammaMarketClient as Gamma
from agents.polymarket.polymarket import Polymarket
from colorama import init, Fore, Style
from agents.predictions.prediction_store import PredictionStore
import datetime  # Añadido para tracking de tiempo
import shutil
import os
import ast
import time
import random  # Añadir al inicio del archivo
import re
import logging  # Para el sistema de registro
import asyncio

init()  # Inicializar colorama

# Función para extraer valores numéricos de variables de entorno
def get_env_int(name, default):
    """
    Extrae un valor entero de una variable de entorno, ignorando cualquier comentario.
    
    Args:
        name: Nombre de la variable de entorno
        default: Valor por defecto si la variable no existe o no puede ser convertida
        
    Returns:
        Valor entero extraído de la variable de entorno
    """
    value = os.getenv(name, str(default))
    # Extraer solo la parte numérica al inicio de la cadena
    match = re.search(r'^\d+', value)
    if match:
        return int(match.group(0))
    return default

# Configurar sistema de registro
def setup_logging():
    # Crear directorio para logs si no existe
    os.makedirs('logs', exist_ok=True)
    
    # Configurar el logger principal
    logger = logging.getLogger('polyagent')
    logger.setLevel(logging.INFO)
    
    # Formato que incluye tiempo y nivel
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Handler para archivo (un archivo por día)
    log_file = f"logs/polyagent_{datetime.datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    
    # Añadir los handlers al logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

class Trader:
    def __init__(self):
        # Inicializar el logger
        self.logger = setup_logging()
        self.logger.info("Inicializando PolyAgent con monitoreo continuo")
        
        self.polymarket = Polymarket()
        self.gamma = Gamma()
        self.agent = Agent()
        
        # Simplificar la lógica del dry run - false por defecto
        self.dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        
        # Configurar delay único entre 2 y 6 horas
        self.min_trade_delay = 2 * 60 * 60  # 2 horas en segundos
        self.max_trade_delay = 6 * 60 * 60  # 6 horas en segundos
        
        # Inicializar timestamps de seguimiento
        self.last_check_time = datetime.datetime.now()
        self.last_periodic_analysis = datetime.datetime.now()
        
        if self.dry_run:
            self.logger.info("🔍 Ejecutando en modo DRY RUN - no se ejecutarán transacciones reales")
            print(f"\n{Fore.GREEN}🔍 Running in DRY RUN mode - no transactions will be executed")
            print(f"Analysis delay disabled in DRY RUN mode{Style.RESET_ALL}\n")
        else:
            self.logger.info(f"Delay de análisis configurado entre {self.min_trade_delay/3600} y {self.max_trade_delay/3600} horas")
            print(f"{Fore.BLUE}Analysis delay set between {self.min_trade_delay/3600} and {self.max_trade_delay/3600} hours{Style.RESET_ALL}")
            print(f"{Fore.BLUE}Running in LIVE mode - real transactions will be executed{Style.RESET_ALL}\n")

        self.prediction_store = PredictionStore()
        
        # Almacenamiento para análisis de noticias
        self.news_analysis_history = []
        
        # Sistema de tracking de mercados nuevos
        self.known_markets = set()  # Conjunto para almacenar IDs de mercados ya conocidos

    def get_random_delay(self) -> int:
        """Genera un delay aleatorio entre trades"""
        return random.randint(self.min_trade_delay, self.max_trade_delay)

    def pre_trade_logic(self) -> None:
        self.clear_local_dbs()

    def clear_local_dbs(self) -> None:
        try:
            shutil.rmtree("local_db_events")
        except:
            pass
        try:
            shutil.rmtree("local_db_markets")
        except:
            pass

    def one_best_trade(self) -> None:
        """

        one_best_trade is a strategy that evaluates all events, markets, and orderbooks

        leverages all available information sources accessible to the autonomous agent

        then executes that trade without any human intervention

        """
        try:
            self.logger.info("Iniciando bucle de monitoreo continuo")
            print(f"\n{Fore.CYAN}=== INICIANDO MONITOREO CONTINUO DE POLYMARKET ==={Style.RESET_ALL}")
            print(f"Analizando mercados cada {self.min_trade_delay/3600:.1f} horas")
            print(f"Buscando nuevos mercados cada {self.max_trade_delay/3600:.1f} horas")
            print(f"{Fore.CYAN}================================================={Style.RESET_ALL}\n")
            
            while True:  # Bucle infinito para seguir ejecutando
                current_time = datetime.datetime.now()
                self.pre_trade_logic()

                # 1. Verificar si hay nuevos mercados primero (prioridad alta)
                new_markets = self.check_for_new_markets()
                if new_markets:
                    self.logger.info(f"Detectados {len(new_markets)} nuevos mercados")
                    print(f"{Fore.MAGENTA}⭐ NUEVOS MERCADOS DETECTADOS: {len(new_markets)} ⭐{Style.RESET_ALL}")
                    # Priorizar el análisis de nuevos mercados
                    for market in new_markets:
                        self.analyze_single_market(market)
                        time.sleep(5)  # Pequeña pausa entre análisis de mercados nuevos
                
                # 2. Verificar si es hora de hacer un análisis periódico profundo (prioridad media)
                time_since_last_analysis = (current_time - self.last_periodic_analysis).total_seconds()
                if time_since_last_analysis >= self.max_trade_delay:
                    self.logger.info("Realizando análisis periódico profundo de mercados seleccionados")
                    print(f"\n{Fore.GREEN}=== ANÁLISIS PERIÓDICO PROGRAMADO ==={Style.RESET_ALL}")
                    self.periodic_deep_analysis()
                    self.last_periodic_analysis = datetime.datetime.now()
                
                # 3. Análisis regular de eventos actuales (prioridad normal)
                self.regular_market_analysis()
                
                # 4. Esperar antes del próximo ciclo
                print(f"\n{Fore.BLUE}Esperando {self.min_trade_delay/3600:.1f} horas antes del próximo análisis...{Style.RESET_ALL}")
                time.sleep(self.min_trade_delay/3600)

        except KeyboardInterrupt:
            self.logger.info("Program interrupted by user")
            print(f"\n{Fore.YELLOW}Program interrupted by user. Finishing...{Style.RESET_ALL}")
            return
        except Exception as e:
            self.logger.error(f"Error crítico: {e}")
            print(f"Error {e}")
            random_delay = self.get_random_delay()
            minutes = round(random_delay / 60)
            print(f"\n{Fore.RED}Critical error occurred. Waiting {minutes} minutes before retrying...{Style.RESET_ALL}")
            time.sleep(random_delay)
            
    def execute_trade(self, market_data, amount, position):
        """Ejecuta una transacción con manejo de errores y reintentos"""
        max_retries = 3
        retry_delay = 60  # segundos
        
        # Añadir information de position a market_data
        if not hasattr(market_data, 'trade'):
            market_data.trade = {}
        market_data.trade['position'] = position
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Intentando transacción (intento {attempt + 1}/{max_retries})")
                print(f"Executing trade for position: {position}")
                trade = self.polymarket.execute_market_order(market_data, amount)
                
                if trade:
                    self.logger.info("Transacción ejecutada exitosamente")
                    return trade
                    
            except Exception as e:
                self.logger.error(f"Error en intento {attempt + 1}: {str(e)}")
                
                # Si es un error de Cloudflare, esperar más tiempo
                if "Cloudflare" in str(e):
                    retry_delay = 300  # 5 minutos para errores de Cloudflare
                
                if attempt < max_retries - 1:
                    self.logger.info(f"Esperando {retry_delay} segundos antes de reintentar...")
                    time.sleep(retry_delay)
                else:
                    self.logger.error("Se alcanzó el número máximo de reintentos")
                    return None
        
        return None

    def regular_market_analysis(self):
        """Realizar el análisis regular de mercados existentes"""
        self.logger.info("Starting regular market analysis")
        
        # Obtener todos los eventos
        events = self.polymarket.get_all_events()
        print(f"{Fore.LIGHTBLUE_EX}1. FOUND {len(events)} EVENTS{Style.RESET_ALL}")

        # Filtrar primero por volumen y pins
        high_quality_events = []
        for event in events:
            try:
                event_data = event.dict()
                market_ids = event_data.get('markets', '').split(',')
                
                for market_id in market_ids:
                    if not market_id:
                        continue
                        
                    market_data = self.gamma.get_market(market_id)
                    volume = float(market_data.get('volume', 0))
                    is_pinned = market_data.get('featured', False)
                    
                    if volume > 10000 or is_pinned:
                        # Crear un diccionario con el evento y sus datos de trade
                        event_with_trade = {
                            'event': event,
                            'trade': {
                                'market_data': market_data
                            }
                        }
                        high_quality_events.append((event_with_trade, 1.0))
                        print(f"\nHigh quality market found: {market_data.get('question', '')}")
                        print(f"Volume: ${volume:,.2f}")
                        print(f"Featured: {is_pinned}")
                        print("---")
                        break
                        
            except Exception as e:
                print(f"Error processing event: {e}")
                continue

        print(f"{Fore.LIGHTBLUE_EX}2. FOUND {len(high_quality_events)} HIGH QUALITY EVENTS{Style.RESET_ALL}")

        # Continuar con el filtrado RAG solo para eventos de alta calidad
        filtered_events = self.agent.filter_events_with_rag(high_quality_events)
        print(f"{Fore.LIGHTBLUE_EX}3. FILTERED {len(filtered_events)} EVENTS{Style.RESET_ALL}")

        markets = self.agent.map_filtered_events_to_markets(filtered_events)
        print()
        print(f"{Fore.LIGHTBLUE_EX}4. FOUND {len(markets)} MARKETS{Style.RESET_ALL}")

        print()
        filtered_markets = self.agent.filter_markets(markets)
        print(f"{Fore.LIGHTBLUE_EX}5. FILTERED {len(filtered_markets)} MARKETS{Style.RESET_ALL}")

        # Para las respuestas de la IA
        print(f"\n{Fore.YELLOW}AI analyzing markets...{Style.RESET_ALL}")

        for market_tuple in filtered_markets:
            try:
                market_data = market_tuple[0]  # SimpleMarket
                print(f"\n{Fore.YELLOW}=== Analyzing Market ===")
                print(f"Market: {market_data.question}")
                print(f"Current Prices:")
                prices = ast.literal_eval(market_data.outcome_prices)
                print(f"YES: ${prices[0]} ({Fore.RED}{float(prices[0])*100:.1f}%{Style.RESET_ALL})")
                print(f"NO: ${prices[1]} ({Fore.RED}{float(prices[1])*100:.1f}%{Style.RESET_ALL})")
                print(f"Volume: ${float(market_data.volume if hasattr(market_data, 'volume') else 0):,.2f}")

                if not hasattr(market_data, 'clob_token_ids') or not market_data.clob_token_ids:
                    print(f"Market {market_data.question} does not have token IDs")
                    continue

                # Usar show_news_analysis=True para mostrar el análisis de noticias
                best_trade = self.agent.source_best_trade(market_tuple, show_news_analysis=True)
                
                # Guardar el análisis en el histórico
                if best_trade and isinstance(best_trade, dict):
                    self.news_analysis_history.append({
                        'timestamp': datetime.datetime.now(),
                        'market': market_data.question,
                        'news_analysis': best_trade.get('news_analysis', 'No disponible'),
                        'decision_reasoning': best_trade.get('decision_reasoning', 'No disponible')
                    })
                    
                    print(f"\nAI Decision:")
                    position = best_trade.get('position', 'UNKNOWN')
                    print(f"Action: BUY {position}")
                    
                    # Asegurar que el precio es float
                    target_price = float(best_trade.get('price', 0))
                    edge = best_trade.get('edge', 0)
                    
                    print(f"Target Price: ${target_price}")
                    print(f"Expected Edge: ${edge:.4f}")
                    print(f"Confidence: High based on market conditions")
                    print(f"Reasoning: {best_trade.get('prediction', 'No prediction available')}")
                    print(f"===================={Style.RESET_ALL}")
                    
                    amount = 1.0
                    best_trade['size'] = amount
                    best_trade['price'] = target_price
                    
                    # Agregar información del trade a market_data
                    if not hasattr(market_data, 'trade'):
                        market_data.trade = {}
                    market_data.trade.update(best_trade)
                    
                    print(f"\n{Fore.GREEN}6. TRYING TRADE FOR MARKET {market_data.question}")
                    print(f"   Amount: ${amount} USDC")
                    print(f"   Price: {best_trade['price']}")
                    print(f"   Side: BUY {best_trade.get('position')}{Style.RESET_ALL}")
                    
                    # Verificar que la posición está correctamente asignada
                    print(f"   Verified position in market_data: {market_data.trade.get('position', 'UNKNOWN')}")

                    # Store prediction regardless of dry run mode
                    prediction_id = self.prediction_store.store_trade_prediction(
                        market_data=market_data,
                        trade_data=best_trade,
                        analysis=best_trade.get('analysis', '')
                    )
                    
                    if prediction_id:
                        print(f"Stored prediction with ID: {prediction_id}")

                    if self.dry_run:
                        print("\n🔍 DRY RUN: Trade would be executed with these parameters")
                        print(f"   Token ID: {market_data.clob_token_ids}")
                        print(f"   Market Question: {market_data.question}")
                        print("Skipping actual transaction...")
                        time.sleep(5)  # Pequeña pausa en dry run
                        continue

                    # Usar el nuevo método execute_trade con reintentos
                    trade = self.execute_trade(market_data, amount, position)
                    
                    if trade:
                        self.logger.info(f"Trade executed successfully in new market")
                        print(f"7. TRADED SUCCESSFULLY {trade}")
                        random_delay = self.get_random_delay()
                        hours = round(random_delay / 3600, 1)  # Convertir a horas
                        print(f"\n{Fore.BLUE}Trade successful! Waiting {hours} hours before next trade...{Style.RESET_ALL}")
                        time.sleep(random_delay)
                        return  # Salir completamente de la función para respetar el delay
                    else:
                        print("Trade failed after all retry attempts, trying next market...")
                        time.sleep(5)  # Pequeña pausa entre intentos de trade
                        continue

            except Exception as e:
                print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
                print(f"\n{Fore.BLUE}Waiting 5 seconds before next market analysis...{Style.RESET_ALL}")
                time.sleep(5)
                continue

        print("\nNo eligible markets found for trading")
            
    def periodic_deep_analysis(self):
        """
        Realiza un análisis profundo periódico en mercados específicos seleccionados
        por su importancia o potencial
        """
        self.logger.info("Iniciando análisis profundo periódico")
        
        try:
            # 1. Obtener mercados con mayor volumen (top 5)
            print(f"{Fore.GREEN}Analyzing most important markets by volume...{Style.RESET_ALL}")
            all_markets = self.gamma.get_all_current_markets(limit=100)
            
            # Ordenar por volumen (mayor a menor)
            volume_markets = sorted(
                all_markets, 
                key=lambda x: float(x.get('volume', 0)), 
                reverse=True
            )[:5]
            
            for market in volume_markets:
                print(f"\n{Fore.MAGENTA}=== DEEP ANALYSIS OF IMPORTANT MARKET ==={Style.RESET_ALL}")
                print(f"Market: {market.get('question', 'No title')}")
                print(f"Volume: ${float(market.get('volume', 0)):,.2f}")
                
                # Convertir a formato SimpleMarket para análisis
                simple_market = self.polymarket.map_api_to_market(market)
                market_tuple = (simple_market, 1.0)
                
                # Análisis profundo con más contexto
                best_trade = self.agent.source_best_trade(market_tuple, show_news_analysis=True)
                
                # Guardar resultados del análisis
                self.save_analysis_report(
                    market.get('question', 'Unknown'), 
                    best_trade, 
                    is_deep_analysis=True
                )
                
                # Pequeña pausa entre análisis profundos
                time.sleep(10)
                
        except Exception as e:
            self.logger.error(f"Error in periodic analysis: {e}")
            print(f"{Fore.RED}Error in periodic analysis: {e}{Style.RESET_ALL}")
            
    def save_analysis_report(self, market_title, analysis_data, is_deep_analysis=False):
        """
        Saves an analysis report to a file for later review
        """
        try:
            # Create directory for reports
            reports_dir = 'market_reports'
            os.makedirs(reports_dir, exist_ok=True)
            
            # Create filename based on date and market
            safe_title = re.sub(r'[^\w\s-]', '', market_title).strip().replace(' ', '_')
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{reports_dir}/{timestamp}_{safe_title[:30]}.txt"
            
            with open(filename, 'w') as f:
                f.write(f"=== MARKET ANALYSIS: {market_title} ===\n")
                f.write(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Type: {'Periodic deep analysis' if is_deep_analysis else 'Regular analysis'}\n\n")
                
                if analysis_data and isinstance(analysis_data, dict):
                    # Main prediction
                    f.write("=== PREDICTION ===\n")
                    f.write(analysis_data.get('prediction', 'Not available'))
                    f.write("\n\n")
                    
                    # News analysis
                    f.write("=== NEWS ANALYSIS ===\n")
                    f.write(analysis_data.get('news_analysis', 'Not available'))
                    f.write("\n\n")
                    
                    # Decision reasoning
                    f.write("=== DECISION REASONING ===\n")
                    f.write(analysis_data.get('decision_reasoning', 'Not available'))
                    f.write("\n\n")
                    
                    # Technical data
                    f.write("=== TECHNICAL DATA ===\n")
                    f.write(f"AI Probability: {analysis_data.get('ai_probability', 0):.2%}\n")
                    f.write(f"Position: {analysis_data.get('position', 'N/A')}\n")
                    f.write(f"Target Price: ${analysis_data.get('price', 0):.4f}\n")
                    f.write(f"Calculated Edge: {analysis_data.get('edge', 0):.4f}\n")
                    f.write(f"Recommendation: {'TRADE' if analysis_data.get('should_trade', False) else 'NO TRADE'}\n")
                    
                    # Market context
                    f.write("\n=== MARKET CONTEXT ===\n")
                    f.write(f"Current Volume: ${analysis_data.get('volume', 0):,.2f}\n")
                    f.write(f"Market Type: {analysis_data.get('market_type', 'N/A')}\n")
                    f.write(f"Market Category: {analysis_data.get('category', 'N/A')}\n")
                    
                    # Key factors
                    f.write("\n=== KEY FACTORS ===\n")
                    if 'key_factors' in analysis_data:
                        for factor in analysis_data['key_factors']:
                            f.write(f"- {factor}\n")
                    
                    # Detailed analysis
                    f.write("\n=== DETAILED ANALYSIS ===\n")
                    if 'detailed_analysis' in analysis_data:
                        f.write(analysis_data['detailed_analysis'])
                    
                    # Risk assessment
                    f.write("\n=== RISK ASSESSMENT ===\n")
                    f.write(f"Risk Level: {analysis_data.get('risk_level', 'N/A')}\n")
                    f.write(f"Confidence Score: {analysis_data.get('confidence_score', 'N/A')}\n")
                    
                    # Historical context
                    f.write("\n=== HISTORICAL CONTEXT ===\n")
                    if 'historical_context' in analysis_data:
                        f.write(analysis_data['historical_context'])
                    
                    # External factors
                    f.write("\n=== EXTERNAL FACTORS ===\n")
                    if 'external_factors' in analysis_data:
                        for factor in analysis_data['external_factors']:
                            f.write(f"- {factor}\n")
                    
                    # Market sentiment
                    f.write("\n=== MARKET SENTIMENT ===\n")
                    f.write(f"Sentiment Score: {analysis_data.get('sentiment_score', 'N/A')}\n")
                    f.write(f"Sentiment Trend: {analysis_data.get('sentiment_trend', 'N/A')}\n")
                    
                    # Trading strategy
                    f.write("\n=== TRADING STRATEGY ===\n")
                    f.write(f"Entry Strategy: {analysis_data.get('entry_strategy', 'N/A')}\n")
                    f.write(f"Exit Strategy: {analysis_data.get('exit_strategy', 'N/A')}\n")
                    f.write(f"Position Size: {analysis_data.get('position_size', 'N/A')}\n")
                    
                    # Additional notes
                    f.write("\n=== ADDITIONAL NOTES ===\n")
                    f.write(analysis_data.get('additional_notes', 'No additional notes'))
                else:
                    f.write("Could not obtain analysis for this market.")
            
            self.logger.info(f"Analysis report saved: {filename}")
            print(f"{Fore.GREEN}Analysis report saved: {filename}{Style.RESET_ALL}")
            
            # Add to history for daily report
            report_entry = {
                'timestamp': datetime.datetime.now(),
                'market': market_title,
                'analysis_type': 'Deep Analysis' if is_deep_analysis else 'Regular Analysis',
                'recommendation': 'TRADE' if analysis_data and analysis_data.get('should_trade', False) else 'NO TRADE',
                'position': analysis_data.get('position', 'N/A') if analysis_data else 'N/A',
                'edge': analysis_data.get('edge', 0) if analysis_data else 0,
                'ai_probability': analysis_data.get('ai_probability', 0) if analysis_data else 0,
                'market_volume': analysis_data.get('volume', 0) if analysis_data else 0,
                'risk_level': analysis_data.get('risk_level', 'N/A') if analysis_data else 'N/A',
                'confidence_score': analysis_data.get('confidence_score', 'N/A') if analysis_data else 'N/A',
                'sentiment_score': analysis_data.get('sentiment_score', 'N/A') if analysis_data else 'N/A',
                'file': filename
            }
            
            # Save to history
            if not hasattr(self, 'daily_report_history'):
                self.daily_report_history = []
            self.daily_report_history.append(report_entry)
            
            # Check if it's time to generate a daily report
            self.check_for_daily_report()
            
        except Exception as e:
            self.logger.error(f"Error saving analysis report: {e}")
            print(f"{Fore.RED}Error saving report: {e}{Style.RESET_ALL}")
            
    def check_for_daily_report(self):
        """
        Verifica si es hora de generar un informe diario resumiendo todos los análisis
        """
        try:
            # Verificar si ya existe un atributo con la última fecha de informe
            if not hasattr(self, 'last_daily_report_date'):
                self.last_daily_report_date = datetime.datetime.now().date()
                return
            
            # Si hemos cambiado de día, generar informe
            current_date = datetime.datetime.now().date()
            if current_date > self.last_daily_report_date and hasattr(self, 'daily_report_history'):
                self.generate_daily_report(self.last_daily_report_date)
                self.last_daily_report_date = current_date
                # Reiniciar historial después de generar informe
                self.daily_report_history = []
        except Exception as e:
            self.logger.error(f"Error verificando informe diario: {e}")
    
    def generate_daily_report(self, report_date):
        """
        Genera un informe diario con todos los análisis realizados en el día
        """
        try:
            if not hasattr(self, 'daily_report_history') or not self.daily_report_history:
                return  # No hay datos para generar informe
            
            # Crear directorio para informes diarios
            reports_dir = 'daily_reports'
            os.makedirs(reports_dir, exist_ok=True)
            
            # Nombre del archivo de informe
            date_str = report_date.strftime('%Y-%m-%d')
            filename = f"{reports_dir}/informe_diario_{date_str}.txt"
            
            with open(filename, 'w') as f:
                f.write(f"=== INFORME DIARIO DE ANÁLISIS DE MERCADOS ===\n")
                f.write(f"Fecha: {date_str}\n\n")
                
                # Estadísticas generales
                total_markets = len(self.daily_report_history)
                recommended_trades = sum(1 for item in self.daily_report_history if item['recommendation'] == 'TRADE')
                avg_edge = sum(item['edge'] for item in self.daily_report_history) / max(1, total_markets)
                
                f.write(f"ESTADÍSTICAS GENERALES:\n")
                f.write(f"- Mercados analizados: {total_markets}\n")
                f.write(f"- Operaciones recomendadas: {recommended_trades} ({recommended_trades/max(1, total_markets)*100:.1f}%)\n")
                f.write(f"- Edge promedio: {avg_edge:.4f}\n\n")
                
                # Detalles de cada análisis
                f.write(f"DETALLE DE ANÁLISIS:\n")
                # Ordenar por timestamp
                sorted_history = sorted(self.daily_report_history, key=lambda x: x['timestamp'])
                
                for i, entry in enumerate(sorted_history, 1):
                    timestamp = entry['timestamp'].strftime('%H:%M:%S')
                    f.write(f"{i}. {timestamp} - {entry['market']}\n")
                    f.write(f"   Tipo: {entry['analysis_type']}\n")
                    f.write(f"   Recomendación: {entry['recommendation']}\n")
                    if entry['recommendation'] == 'TRADE':
                        f.write(f"   Posición: {entry['position']}\n")
                        f.write(f"   Edge: {entry['edge']:.4f}\n")
                    f.write(f"   Archivo de análisis: {entry['file']}\n\n")
            
            self.logger.info(f"Daily report generated: {filename}")
            print(f"\n{Fore.CYAN}=== DAILY REPORT GENERATED ==={Style.RESET_ALL}")
            print(f"Daily report has been generated for date {date_str}")
            print(f"File: {filename}")
            print(f"{Fore.CYAN}==============================={Style.RESET_ALL}\n")
            
        except Exception as e:
            self.logger.error(f"Error generating daily report: {e}")
            print(f"{Fore.RED}Error generating daily report: {e}{Style.RESET_ALL}")

    def maintain_positions(self):
        pass

    def incentive_farm(self):
        pass

    def check_for_new_markets(self):
        """Detecta mercados nuevos entre chequeos consecutivos"""
        current_time = datetime.datetime.now()
        time_diff = (current_time - self.last_check_time).total_seconds()
        
        # Solo verificar nuevos mercados cada cierto intervalo
        if time_diff < self.max_trade_delay:
            return []
            
        print(f"{Fore.YELLOW}Looking for new markets...{Style.RESET_ALL}")
        
        # Obtener todos los mercados actuales
        current_markets = self.gamma.get_all_current_markets(limit=100)
        current_market_ids = set(market['id'] for market in current_markets)
        
        # Encontrar mercados nuevos (no en el conjunto conocido)
        new_markets = [market for market in current_markets 
                      if str(market['id']) not in self.known_markets]
        
        # Ordenar mercados nuevos por fecha de creación (más recientes primero)
        new_markets.sort(key=lambda x: x.get('createdDate', ''), reverse=True)
        
        # Actualizar conjuntos para el próximo chequeo
        self.known_markets.update(str(market['id']) for market in current_markets)
        self.last_check_time = current_time
        
        # Mostrar información sobre mercados nuevos
        if new_markets:
            print(f"\n{Fore.MAGENTA}=== NEW MARKETS DETECTED ==={Style.RESET_ALL}")
            for market in new_markets[:5]:  # Show the 5 most recent
                print(f"- {market.get('question', 'No title')}")
                print(f"  Created: {market.get('createdDate', 'Unknown date')}")
                print(f"  Volume: ${float(market.get('volume', 0)):,.2f}")
                print()
            
        return new_markets
        
    def analyze_single_market(self, market_data):
        """Analiza un único mercado nuevo"""
        try:
            self.logger.info(f"Analyzing new market: {market_data.get('question', 'Unknown')}")
            print(f"\n{Fore.YELLOW}=== Analyzing New Market ===")
            print(f"Market: {market_data.get('question', 'Unknown')}")
            print(f"Current Prices:")
            prices = market_data.get('outcomePrices', [0.5, 0.5])
            if isinstance(prices, str):
                prices = ast.literal_eval(prices)
            print(f"YES: ${prices[0]} ({Fore.RED}{float(prices[0])*100:.1f}%{Style.RESET_ALL})")
            print(f"NO: ${prices[1]} ({Fore.RED}{float(prices[1])*100:.1f}%{Style.RESET_ALL})")
            print(f"Volume: ${float(market_data.get('volume', 0)):,.2f}")
            
            # Convertir a formato que espera el agente
            simple_market = self.polymarket.map_api_to_market(market_data)
            market_tuple = (simple_market, 1.0)
            
            # Realizar análisis con el agente usando show_news_analysis=True para ver el análisis detallado
            best_trade = self.agent.source_best_trade(market_tuple, show_news_analysis=True)
            
            # Guardar el informe detallado de análisis
            self.save_analysis_report(
                market_data.get('question', 'Unknown'),
                best_trade,
                is_deep_analysis=False
            )
            
            if best_trade and isinstance(best_trade, dict):
                print(f"\n{Fore.GREEN}AI Decision for New Market:{Style.RESET_ALL}")
                position = best_trade.get('position', 'UNKNOWN')
                print(f"Action: BUY {position}")
                
                # Asegurar que el precio es float
                target_price = float(best_trade.get('price', 0))
                edge = best_trade.get('edge', 0)
                
                print(f"Target Price: ${target_price}")
                print(f"Expected Edge: ${edge:.4f}")
                print(f"Reasoning: {best_trade.get('prediction', 'No prediction available')}")
                print(f"===================={Style.RESET_ALL}")
                
                # Si hay análisis de noticias, mostrarlo
                if 'news_analysis' in best_trade:
                    print(f"\n{Fore.CYAN}News Analysis:{Style.RESET_ALL}")
                    print(best_trade['news_analysis'])
                    
                # Mostrar el razonamiento de decisión
                if 'decision_reasoning' in best_trade:
                    print(f"\n{Fore.GREEN}Decision Reasoning:{Style.RESET_ALL}")
                    print(best_trade['decision_reasoning'])
                
                # Si modo dry run, solo mostrar el resultado
                if self.dry_run:
                    print("\n🔍 DRY RUN: Trade would be executed with these parameters")
                    return
                
                # Decisión: ¿Ejecutar la operación?
                if best_trade.get('should_trade', False):
                    self.logger.info(f"Decision to operate in new market: {market_data.get('question', 'Unknown')}")
                    amount = 1.0
                    best_trade['size'] = amount
                    best_trade['price'] = target_price
                    
                    # Almacenar predicción
                    prediction_id = self.prediction_store.store_trade_prediction(
                        market_data=simple_market,
                        trade_data=best_trade,
                        analysis=best_trade.get('analysis', '')
                    )
                    
                    # Ejecutar trade
                    trade = self.polymarket.execute_market_order(simple_market, amount)
                    if trade:
                        self.logger.info(f"Trade executed successfully in new market")
                        print(f"{Fore.GREEN}Trade executed successfully!{Style.RESET_ALL}")
                else:
                    self.logger.info(f"Decision to NOT trade in new market: {market_data.get('question', 'Unknown')}")
                    print(f"{Fore.YELLOW}AI decided not to trade on this market{Style.RESET_ALL}")
                
        except Exception as e:
            self.logger.error(f"Error analyzing single market: {e}")
            print(f"{Fore.RED}Error analyzing single market: {str(e)}{Style.RESET_ALL}")

    async def analyze_all_markets(self):
        """Versión asíncrona del análisis de mercados"""
        self.logger.info("Analyzing all markets asynchronously")
        try:
            # Versión asíncrona del análisis regular
            # Por ahora simplemente llama a la versión sincrónica
            # En el futuro, se puede mejorar para que sea realmente asíncrona
            print(f"{Fore.YELLOW}Running market analysis...{Style.RESET_ALL}")
            self.regular_market_analysis()
            print(f"{Fore.GREEN}Market analysis completed{Style.RESET_ALL}")
            return True
        except Exception as e:
            self.logger.error(f"Error in asynchronous market analysis: {e}")
            print(f"{Fore.RED}Error in async market analysis: {str(e)}{Style.RESET_ALL}")
            return False
    
    async def monitor_events(self):
        """Monitorea eventos en tiempo real de forma asíncrona"""
        try:
            # Verificar si hay nuevos mercados
            new_markets = self.check_for_new_markets()
            if new_markets:
                self.logger.info(f"Found {len(new_markets)} new markets during async monitoring")
                print(f"{Fore.MAGENTA}Found {len(new_markets)} new markets during async monitoring{Style.RESET_ALL}")
                
                # Analizar los nuevos mercados
                for market in new_markets[:3]:  # Limitar a los 3 más recientes para no sobrecargar
                    self.analyze_single_market(market)
                    await asyncio.sleep(2)  # Pequeña pausa asíncrona entre análisis
            
            return True
        except Exception as e:
            self.logger.error(f"Error monitoring events: {e}")
            print(f"{Fore.RED}Error monitoring events: {str(e)}{Style.RESET_ALL}")
            return False

    async def monitor_markets(self):
        """Monitorea continuamente los mercados y ejecuta análisis periódicos"""
        self.logger.info("Starting continuous market monitoring")
        print(f"{Fore.CYAN}Starting continuous market monitoring (Windows-compatible async mode){Style.RESET_ALL}")
        
        while True:
            try:
                current_time = datetime.datetime.now()
                
                # Verificar si es momento de actualizar la lista de mercados
                if (current_time - self.last_check_time).total_seconds() >= self.max_trade_delay:
                    self.logger.info("Updating market list...")
                    self.known_markets = set()  # Reset para obtener todos los mercados
                    self.last_check_time = current_time
                
                # Verificar si es momento de análisis periódico
                if (current_time - self.last_periodic_analysis).total_seconds() >= self.max_trade_delay:
                    self.logger.info("Starting periodic market analysis...")
                    await self.analyze_all_markets()
                    self.last_periodic_analysis = current_time
                
                # Monitorear eventos en tiempo real
                await self.monitor_events()
                
                # Aplicar delay solo si no estamos en dry run
                if not self.dry_run:
                    delay = self.get_random_delay()
                    hours = round(delay / 3600, 1)
                    self.logger.info(f"Waiting {hours} hours before next analysis...")
                    print(f"{Fore.BLUE}Waiting {hours} hours before next analysis...{Style.RESET_ALL}")
                    await asyncio.sleep(delay)
                else:
                    # En dry run, usar un delay más corto
                    print(f"{Fore.YELLOW}DRY RUN: Using short delay (5 seconds){Style.RESET_ALL}")
                    await asyncio.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring: {str(e)}")
                print(f"{Fore.RED}Error in market monitoring: {str(e)}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Waiting 60 seconds before retrying...{Style.RESET_ALL}")
                await asyncio.sleep(60)  # Esperar 1 minuto antes de reintentar


if __name__ == "__main__":
    import platform
    import asyncio
    
    # Configurar el bucle de eventos para Windows
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print(f"{Fore.CYAN}Windows detected, setting appropriate event loop policy{Style.RESET_ALL}")
    
    try:
        # Crear una instancia del trader
        trader = Trader()
        
        # Si prefieres la versión sincrónica (la original)
        if os.getenv("USE_ASYNC", "false").lower() != "true":
            print(f"{Fore.CYAN}Running in synchronous mode{Style.RESET_ALL}")
            trader.one_best_trade()
        else:
            # Versión asincrónica
            print(f"{Fore.CYAN}Running in asynchronous mode{Style.RESET_ALL}")
            loop = asyncio.get_event_loop()
            try:
                loop.run_until_complete(trader.monitor_markets())
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Program interrupted by user. Shutting down...{Style.RESET_ALL}")
            finally:
                loop.close()
    except Exception as e:
        print(f"{Fore.RED}Critical error: {str(e)}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
