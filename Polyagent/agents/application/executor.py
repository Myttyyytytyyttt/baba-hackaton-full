import os
import json
import ast
import re
from typing import List, Dict, Any, Optional
import math
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from colorama import Fore, Style
from collections import defaultdict
import spacy  # Para NLP
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer  # Para vectorización de texto
import random
import logging

from agents.polymarket.gamma import GammaMarketClient as Gamma
from agents.connectors.chroma import PolymarketRAG as Chroma
from agents.utils.objects import SimpleEvent, SimpleMarket
from agents.application.prompts import Prompter
from agents.polymarket.polymarket import Polymarket
from agents.connectors.search import MarketSearch
from agents.connectors.news import News  # Añadir importación del conector de noticias
from agents.connectors.perplexity import PerplexityConnector  # Nueva importación para Perplexity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

def retain_keys(data, keys_to_retain):
    if isinstance(data, dict):
        return {
            key: retain_keys(value, keys_to_retain)
            for key, value in data.items()
            if key in keys_to_retain
        }
    elif isinstance(data, list):
        return [retain_keys(item, keys_to_retain) for item in data]
    else:
        return data

class Executor:
    def __init__(self, default_model='gpt-4-1106-preview', test_mode: bool = False) -> None:
        load_dotenv()
        max_token_model = { 
            'gpt-4-1106-preview': 128000,  # Modelo más reciente con ventana de contexto mucho mayor
            'gpt-4o': 32000,               # GPT-4o también disponible
            'gpt-4': 8000                  # Modelo base de GPT-4
        }
        self.token_limit = max_token_model.get(default_model)
        self.prompter = Prompter()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.llm = ChatOpenAI(
            model=default_model, 
            temperature=0,
        )
        self.gamma = Gamma()
        self.chroma = Chroma()
        self.polymarket = Polymarket()
        self.search = MarketSearch()
        self.news = News()  # Inicializar el conector de noticias
        
        # Inicializar conector de Perplexity
        self.perplexity = PerplexityConnector()
        self.use_perplexity = os.getenv("USE_PERPLEXITY", "true").lower() == "true"
        
        # Si Perplexity está disponible, notificar
        if self.perplexity.is_available() and self.use_perplexity:
            print(f"{Fore.GREEN}Perplexity API available for real-time analysis{Style.RESET_ALL}")
        
        # Cargar modelo de spaCy para NLP
        self.nlp = spacy.load("en_core_web_sm")
        
        # Definir categorías y sus palabras clave principales
        self.category_keywords = {
            "sports": {
                "leagues": ["nfl", "nba", "mlb", "nhl", "epl", "uefa", "fifa", "f1"],
                "events": ["super bowl", "world cup", "champions league", "stanley cup", "playoffs"],
                "roles": ["player", "coach", "team", "manager", "mvp", "rookie"],
                "actions": ["win", "score", "lead", "defeat", "qualify", "advance"],
                "metrics": ["points", "goals", "assists", "rebounds", "touchdowns", "yards"],
                "competitions": ["tournament", "championship", "series", "match", "game", "race"]
            },
            "crypto": {
                "assets": ["bitcoin", "ethereum", "solana", "btc", "eth", "sol"],
                "metrics": ["price", "market cap", "volume", "liquidity", "supply"],
                "actions": ["buy", "sell", "trade", "mine", "stake", "yield"],
                "concepts": ["blockchain", "defi", "nft", "dao", "token", "coin"],
                "events": ["halving", "fork", "upgrade", "launch", "listing", "airdrop"]
            },
            "politics": {
                "roles": ["president", "senator", "governor", "minister", "candidate"],
                "events": ["election", "vote", "debate", "campaign", "inauguration"],
                "institutions": ["congress", "senate", "parliament", "fed", "court"],
                "policies": ["bill", "law", "regulation", "reform", "policy"],
                "economic": ["rate", "inflation", "recession", "budget", "debt"]
            },
            "entertainment": {
                "awards": ["oscar", "grammy", "emmy", "golden globe", "tony"],
                "media": ["movie", "film", "song", "album", "show", "series"],
                "roles": ["actor", "actress", "director", "producer", "artist"],
                "events": ["premiere", "release", "concert", "festival", "ceremony"],
                "metrics": ["box office", "ratings", "views", "sales", "streams"]
            },
            "tech": {
                "companies": ["apple", "google", "microsoft", "meta", "openai"],
                "products": ["iphone", "android", "windows", "chatgpt", "tesla"],
                "concepts": ["ai", "cloud", "quantum", "metaverse", "web3"],
                "events": ["launch", "release", "update", "acquisition", "ipo"],
                "metrics": ["revenue", "users", "growth", "valuation", "share"]
            }
        }
        
        # Entrenar vectorizador
        self.vectorizer = self._train_vectorizer()
        self.test_mode = test_mode
        logging.info(f"Executor inicializado. Test mode: {test_mode}")

    def _train_vectorizer(self):
        # Crear corpus de entrenamiento desde keywords
        corpus = []
        labels = []
        for category, keyword_groups in self.category_keywords.items():
            for group in keyword_groups.values():
                corpus.extend(group)
                labels.extend([category] * len(group))
                
        vectorizer = TfidfVectorizer(ngram_range=(1, 3))
        vectorizer.fit(corpus)
        return vectorizer

    def get_llm_response(self, user_input: str) -> str:
        system_message = SystemMessage(content=str(self.prompter.market_analyst()))
        human_message = HumanMessage(content=user_input)
        messages = [system_message, human_message]
        result = self.llm.invoke(messages)
        return result.content

    def chat_completion(self, system_prompt: str, prompt: str, temperature: float = 0.0) -> str:
        """
        Método para obtener completados de chat con un system prompt personalizado
        
        Args:
            system_prompt: El prompt de sistema para el modelo
            prompt: El mensaje del usuario
            temperature: La temperatura para la generación (0.0 = determinista, 1.0 = creativo)
            
        Returns:
            El texto generado por el modelo
        """
        try:
            # Modificar temporalmente la temperatura del modelo
            original_temp = self.llm.temperature
            self.llm.temperature = temperature
            
            # Crear mensajes para el chat
            system_message = SystemMessage(content=system_prompt)
            human_message = HumanMessage(content=prompt)
            messages = [system_message, human_message]
            
            # Invocar el modelo
            result = self.llm.invoke(messages)
            
            # Restaurar temperatura original
            self.llm.temperature = original_temp
            
            return result.content
        except Exception as e:
            print(f"{Fore.RED}Error in chat_completion: {e}{Style.RESET_ALL}")
            return f"Error generating response: {str(e)}"

    def get_superforecast(
        self, event_title: str, market_question: str, outcome: str
    ) -> str:
        messages = self.prompter.superforecaster(
            description=event_title, question=market_question, outcome=outcome
        )
        result = self.llm.invoke(messages)
        return result.content


    def estimate_tokens(self, text: str) -> int:
        # This is a rough estimate. For more accurate results, consider using a tokenizer.
        return len(text) // 4  # Assuming average of 4 characters per token

    def process_data_chunk(self, data1: List[Dict[Any, Any]], data2: List[Dict[Any, Any]], user_input: str) -> str:
        system_message = SystemMessage(
            content=str(self.prompter.prompts_polymarket(data1=data1, data2=data2))
        )
        human_message = HumanMessage(content=user_input)
        messages = [system_message, human_message]
        result = self.llm.invoke(messages)
        return result.content


    def divide_list(self, original_list, i):
        # Calculate the size of each sublist
        sublist_size = math.ceil(len(original_list) / i)
        
        # Use list comprehension to create sublists
        return [original_list[j:j+sublist_size] for j in range(0, len(original_list), sublist_size)]
    
    def get_polymarket_llm(self, user_input: str) -> str:
        data1 = self.gamma.get_current_events()
        data2 = self.gamma.get_current_markets()
        
        combined_data = str(self.prompter.prompts_polymarket(data1=data1, data2=data2))
        
        # Estimate total tokens
        total_tokens = self.estimate_tokens(combined_data)
        
        # Set a token limit (adjust as needed, leaving room for system and user messages)
        token_limit = self.token_limit
        if total_tokens <= token_limit:
            # If within limit, process normally
            return self.process_data_chunk(data1, data2, user_input)
        else:
            # If exceeding limit, process in chunks
            chunk_size = len(combined_data) // ((total_tokens // token_limit) + 1)
            print(f'total tokens {total_tokens} exceeding llm capacity, now will split and answer')
            group_size = (total_tokens // token_limit) + 1 # 3 is safe factor
            keys_no_meaning = ['image','pagerDutyNotificationEnabled','resolvedBy','endDate','clobTokenIds','negRiskMarketID','conditionId','updatedAt','startDate']
            useful_keys = ['id','questionID','description','liquidity','clobTokenIds','outcomes','outcomePrices','volume','startDate','endDate','question','questionID','events']
            data1 = retain_keys(data1, useful_keys)
            cut_1 = self.divide_list(data1, group_size)
            cut_2 = self.divide_list(data2, group_size)
            cut_data_12 = zip(cut_1, cut_2)

            results = []

            for cut_data in cut_data_12:
                sub_data1 = cut_data[0]
                sub_data2 = cut_data[1]
                sub_tokens = self.estimate_tokens(str(self.prompter.prompts_polymarket(data1=sub_data1, data2=sub_data2)))

                result = self.process_data_chunk(sub_data1, sub_data2, user_input)
                results.append(result)
            
            combined_result = " ".join(results)
            
        
            
            return combined_result
    def filter_events(self, events: "list[SimpleEvent]") -> str:
        prompt = self.prompter.filter_events(events)
        result = self.llm.invoke(prompt)
        return result.content

    def detect_category(self, question: str) -> str:
        # Preprocesar texto
        doc = self.nlp(question.lower())
        
        # Extraer entidades nombradas y frases clave
        entities = [ent.text for ent in doc.ents]
        noun_phrases = [chunk.text for chunk in doc.noun_chunks]
        
        # Calcular scores para cada categoría
        scores = defaultdict(float)
        
        # 1. Coincidencia directa con palabras clave
        for category, keyword_groups in self.category_keywords.items():
            for group_name, keywords in keyword_groups.items():
                weight = 2.0 if group_name == "primary" else 1.0
                for keyword in keywords:
                    if keyword in question.lower():
                        scores[category] += weight
                        
        # 2. Análisis de entidades y frases
        for entity in entities + noun_phrases:
            # Vectorizar y comparar con keywords de cada categoría
            entity_vector = self.vectorizer.transform([entity])
            for category, keyword_groups in self.category_keywords.items():
                for keywords in keyword_groups.values():
                    keyword_vectors = self.vectorizer.transform(keywords)
                    similarity = np.mean(entity_vector.dot(keyword_vectors.T).toarray())
                    scores[category] += similarity
        
        # Normalizar scores
        total = sum(scores.values())
        if total > 0:
            scores = {k: v/total for k, v in scores.items()}
            
        # Retornar categoría con mayor score si supera un umbral
        best_category = max(scores.items(), key=lambda x: x[1], default=("other", 0))
        return best_category[0] if best_category[1] > 0.3 else "other"

    def filter_events_with_rag(self, events: "list[tuple[SimpleEvent, float]]") -> "list[tuple[SimpleEvent, float]]":
        """Filtra eventos por categoría"""
        market_category = str(os.getenv("MARKET_CATEGORY", "all")).lower().strip()
        print(f"\nFiltering {len(events)} events for category: {market_category}")
        
        # Si es 'all', retornar todos los eventos
        if market_category == 'all':
            print(f"Returning all {len(events)} events")
            return events
        
        filtered_events = []
        for event_tuple in events:
            event = event_tuple[0]
            question = event.metadata.get("question", event.title)
            event_category = self.detect_category(question)
            
            print(f"Question: {question}")
            print(f"Detected category: {event_category}")
            
            if event_category == market_category:
                filtered_events.append(event_tuple)
        
        print(f"\nFound {len(filtered_events)} {market_category} markets")
        if not filtered_events:
            print(f"\nNo markets found for category: {market_category}")
        
        return filtered_events

    def map_filtered_events_to_markets(
        self, filtered_events: "list[tuple[Dict, float]]"
    ) -> "list[tuple[SimpleMarket, float]]":
        if not filtered_events:
            return []
            
        markets = []
        
        for event_tuple in filtered_events:
            event_dict = event_tuple[0]  # Ahora es un diccionario
            event = event_dict['event']  # Obtener el SimpleEvent del diccionario
            trade_data = event_dict['trade']  # Obtener los datos del trade
            
            if not isinstance(event, SimpleEvent):
                continue
                
            # Usar metadata para obtener los market_ids
            market_ids = event.metadata.get("markets", "").split(",")
            
            for market_id in market_ids:
                if not market_id:
                    continue
                try:
                    # Usar los datos del trade si están disponibles
                    market_data = trade_data.get('market_data', self.gamma.get_market(market_id))
                    
                    # Crear SimpleMarket
                    simple_market = SimpleMarket(
                        id=int(market_data.get("id")),
                        question=market_data.get("question", ""),
                        description=market_data.get("description", ""),
                        end=market_data.get("endDate", ""),
                        active=True,
                        funded=True,
                        rewardsMinSize=0.0,
                        rewardsMaxSpread=0.0,
                        spread=0.0,
                        outcomes=str(market_data.get("outcomes", "[]")),
                        outcome_prices=str(market_data.get("outcomePrices", "[]")),
                        clob_token_ids=str(market_data.get("clobTokenIds", "[]"))
                    )
                    markets.append((simple_market, event_tuple[1]))
                    
                except Exception as e:
                    print(f"{Fore.RED}Error getting market {market_id}: {str(e)}{Style.RESET_ALL}")
                    continue
                    
        return markets

    def filter_markets(self, markets) -> "list[tuple]":
        if not markets:
            print(f"{Fore.YELLOW}No markets to filter{Style.RESET_ALL}")
            return []
            
        prompt = self.prompter.filter_markets()
        print()
        print("... prompting ... ", prompt)
        print()
        return self.chroma.markets(markets, prompt)

    def extract_probability(self, completion: str) -> float:
        """Extrae la probabilidad numérica de la respuesta del LLM"""
        try:
            # Intentar encontrar un valor de probabilidad en el texto
            import re
            
            # Buscar patrones como "probabilidad de 0.75" o "75%"
            probability_patterns = [
                r"probabilidad de (\d+\.\d+)",
                r"probabilidad del (\d+\.\d+)",
                r"probabilidad: (\d+\.\d+)",
                r"likelihood of (\d+\.\d+)",
                r"likelihood: (\d+\.\d+)",
                r"probability of (\d+\.\d+)",
                r"probability: (\d+\.\d+)",
                r"probability is (\d+\.\d+)",
                r"assessment of (\d+\.\d+)",
                r"assessment: (\d+\.\d+)",
                r"estimate of (\d+\.\d+)",
                r"estimate: (\d+\.\d+)",
                r"estimación de (\d+\.\d+)",
                r"estimación: (\d+\.\d+)",
                r"(\d+)%"
            ]
            
            for pattern in probability_patterns:
                matches = re.findall(pattern, completion.lower())
                if matches:
                    value = float(matches[0])
                    # Convertir porcentaje a decimal si es necesario
                    if pattern == r"(\d+)%":
                        value = value / 100
                    return min(max(value, 0.0), 1.0)  # Asegurar que esté entre 0 y 1
            
            # Si no encontramos patrones específicos, busquemos números entre 0 y 1 o porcentajes
            decimal_pattern = r"(?<!\d)0?\.\d+(?!\d)" # Números entre 0 y 1 (ej: 0.75, .65)
            percentage_pattern = r"(\d{1,2})(?=\s*%|\s*percent|\s*por ciento)" # Números seguidos de % (ej: 75%, 65 percent)
            
            # Primero intentamos con números decimales entre 0 y 1
            decimal_matches = re.findall(decimal_pattern, completion.lower())
            if decimal_matches:
                probabilities = [float(match) for match in decimal_matches]
                # Filtrar solo valores que probablemente sean probabilidades (entre 0.01 y 0.99)
                valid_probs = [p for p in probabilities if 0.01 <= p <= 0.99]
                if valid_probs:
                    # Devolvemos el primer valor válido encontrado
                    return valid_probs[0]
            
            # Después intentamos con porcentajes
            percentage_matches = re.findall(percentage_pattern, completion.lower())
            if percentage_matches:
                percentages = [int(match) for match in percentage_matches]
                # Filtrar solo valores que probablemente sean porcentajes (entre 1% y 99%)
                valid_percentages = [p for p in percentages if 1 <= p <= 99]
                if valid_percentages:
                    # Devolvemos el primer valor válido encontrado como decimal
                    return valid_percentages[0] / 100
            
            # Si no encontramos ninguna probabilidad, intentamos buscar "YES" o "NO" con palabras que indiquen alta probabilidad
            positive_patterns = [
                r"(muy probable|highly likely|almost certain|casi seguro|definitely|definitivamente|certainly|ciertamente).*?yes",
                r"yes.*?(muy probable|highly likely|almost certain|casi seguro|definitely|definitivamente|certainly|ciertamente)",
            ]
            
            negative_patterns = [
                r"(muy probable|highly likely|almost certain|casi seguro|definitely|definitivamente|certainly|ciertamente).*?no",
                r"no.*?(muy probable|highly likely|almost certain|casi seguro|definitely|definitivamente|certainly|ciertamente)",
            ]
            
            for pattern in positive_patterns:
                if re.search(pattern, completion.lower()):
                    return 0.9  # Valor alto para indicar una fuerte preferencia por YES
                    
            for pattern in negative_patterns:
                if re.search(pattern, completion.lower()):
                    return 0.1  # Valor bajo para indicar una fuerte preferencia por NO
            
            return None  # No se encontró probabilidad
        except Exception as e:
            print(f"Error extracting probability: {e}")
            return None

    def extract_trading_decision(self, analysis_text: str) -> tuple:
        """
        Extrae la recomendación de trading del texto de análisis
        
        Returns:
            tuple: (should_trade, position) donde should_trade es boolean y position es "YES", "NO" o ""
        """
        try:
            import re
            
            # Buscar la recomendación explícita
            recommendation_pattern = r"RECOMENDACIÓN FINAL:.*?(OPERAR|NO OPERAR)(?:\s+posición\s+(YES|NO))?|(?:Recomendación|Recommendation).*?(OPERAR|NO OPERAR|TRADE|DO NOT TRADE)(?:\s+posición\s+(YES|NO))?|(?:recomiendo|I recommend).*?(OPERAR|NO OPERAR|TRADE|DO NOT TRADE)(?:\s+posición\s+(YES|NO))?"
            matches = re.search(recommendation_pattern, analysis_text, re.IGNORECASE | re.DOTALL)
            
            if matches:
                groups = matches.groups()
                # Filtrar None de los grupos
                groups = [g for g in groups if g is not None]
                
                # Determinar decisión de operar
                decision = None
                for g in groups:
                    if g.upper() in ["OPERAR", "TRADE"]:
                        decision = True
                        break
                    elif g.upper() in ["NO OPERAR", "DO NOT TRADE"]:
                        decision = False
                        break
                
                if decision is None:
                    return False, ""
                
                # Si decidimos operar, buscar posición
                position = ""
                if decision:
                    for g in groups:
                        if g.upper() in ["YES", "NO"]:
                            position = g.upper()
                            break
                    
                    # Si no hay posición explícita, buscar en el texto
                    if not position:
                        yes_pattern = r"(?:position|posición|should take|tomar).*?(?:YES|yes|YES side|buy YES)"
                        no_pattern = r"(?:position|posición|should take|tomar).*?(?:NO|no|NO side|buy NO)"
                        
                        if re.search(yes_pattern, analysis_text, re.IGNORECASE):
                            position = "YES"
                        elif re.search(no_pattern, analysis_text, re.IGNORECASE):
                            position = "NO"
                
                return decision, position
            
            # Si no encontró una recomendación explícita, buscar frases indicativas
            if re.search(r"(?:recomiendo|recommend|should|deber[ií]a).*?(?:YES|yes)", analysis_text, re.IGNORECASE):
                return True, "YES"
            elif re.search(r"(?:recomiendo|recommend|should|deber[ií]a).*?(?:NO|no)", analysis_text, re.IGNORECASE):
                return True, "NO"
            elif re.search(r"(?:no.*?recomiendo|don't recommend|should not|no deber[ií]a|avoid|evitar)", analysis_text, re.IGNORECASE):
                return False, ""
            
            # Por defecto, no operar
            return False, ""
        except Exception as e:
            print(f"Error extracting trading decision: {e}")
            return False, ""
            
    def get_market_analysis_with_perplexity(self, market_question: str, market_data: Optional[Dict] = None) -> Dict:
        """
        Obtiene análisis en tiempo real de un mercado usando Perplexity
        
        Args:
            market_question: La pregunta del mercado a analizar
            market_data: Datos adicionales del mercado (opcional)
            
        Returns:
            Diccionario con análisis y probabilidad estimada
        """
        # Verificar si Perplexity está disponible
        if not self.perplexity.is_available() or not self.use_perplexity:
            print(f"{Fore.YELLOW}Perplexity not available, using standard analysis{Style.RESET_ALL}")
            return {
                "analysis": "",
                "probability": 0.5,
                "success": False
            }
        
        # Preparar contexto adicional si hay datos del mercado
        additional_context = ""
        if market_data:
            try:
                # Incluir precios actuales si están disponibles
                if hasattr(market_data, 'outcome_prices') and market_data.outcome_prices:
                    prices = ast.literal_eval(market_data.outcome_prices)
                    additional_context += f"Current prices in the market: YES: {prices[0]}, NO: {prices[1]}\n"
                
                # Incluir volumen si está disponible
                if hasattr(market_data, 'volume') and market_data.volume:
                    additional_context += f"Market volume: ${float(market_data.volume):,.2f}\n"
                    
                # Incluir descripción si está disponible
                if hasattr(market_data, 'description') and market_data.description:
                    additional_context += f"Market description: {market_data.description}\n"
            except Exception as e:
                print(f"Error preparing context for Perplexity: {e}")
        
        # Obtener análisis de Perplexity
        print(f"{Fore.CYAN}Getting real-time analysis with Perplexity...{Style.RESET_ALL}")
        result = self.perplexity.get_market_analysis(market_question, additional_context)
        
        if not result.get("success", False):
            print(f"{Fore.RED}Error with Perplexity: {result.get('error', 'Unknown error')}{Style.RESET_ALL}")
            return {
                "analysis": "",
                "probability": 0.5,
                "success": False
            }
        
        # Extraer probabilidad del análisis
        analysis_text = result.get("analysis", "")
        probability = self.perplexity.extract_probability(analysis_text)
        
        print(f"{Fore.GREEN}Perplexity analysis completed. Estimated probability: {probability:.2f}{Style.RESET_ALL}")
        
        return {
            "analysis": analysis_text,
            "probability": probability,
            "success": True
        }

    def source_best_trade(self, market_tuple, show_news_analysis=False) -> dict:
        """Método para encontrar la mejor operación basada en análisis de mercado"""
        market_data = market_tuple[0]  # SimpleMarket
        
        print(f"\n{Fore.CYAN}=== Evaluating Market ===")
        print(f"Market: {market_data.question}{Style.RESET_ALL}")
        
        # Intentar usar Perplexity primero (si está habilitado y disponible)
        use_perplexity_result = False
        perplexity_result = {}
        
        if self.use_perplexity and self.perplexity.is_available():
            try:
                perplexity_result = self.get_market_analysis_with_perplexity(market_data.question, market_data)
                use_perplexity_result = perplexity_result.get("success", False)
            except Exception as e:
                print(f"{Fore.RED}Error using Perplexity: {e}{Style.RESET_ALL}")
                use_perplexity_result = False
        
        # Si Perplexity no está disponible o falló, usar el método tradicional
        if not use_perplexity_result:
            print(f"{Fore.YELLOW}Using traditional analysis (without real-time internet access){Style.RESET_ALL}")
            
            # El resto del método original sigue aquí
            try:
                # Obtener noticias relacionadas
                news_query = market_data.question
                related_news = self.get_related_news(news_query)
                
                # Aquí continuaría el resto del método original...
                # [Código existente]
            except Exception as e:
                print(f"{Fore.RED}Error in traditional analysis: {e}{Style.RESET_ALL}")
                return {"error": str(e)}
        else:
            # Usar los resultados de Perplexity
            print(f"{Fore.GREEN}Using real-time Perplexity analysis{Style.RESET_ALL}")
            
            # Extraer análisis y probabilidad
            news_analysis = perplexity_result.get("analysis", "")
            ai_probability = perplexity_result.get("probability", 0.5)
            
            # Mostrar análisis si se solicita
            if show_news_analysis:
                print(f"\n{Fore.YELLOW}=== NEWS ANALYSIS ===")
                print(f"{news_analysis}{Style.RESET_ALL}")
            
            # Preparar datos de precios
            try:
                prices = ast.literal_eval(market_data.outcome_prices)
                yes_price = float(prices[0])
                no_price = float(prices[1])
            except:
                yes_price = 0.5
                no_price = 0.5
            
            # Calcular ventaja (edge)
            edge_yes = ai_probability - yes_price
            edge_no = (1 - ai_probability) - no_price
            
            # Determinar si se debe operar y qué posición tomar
            should_trade = False
            position = "NO"
            price = no_price
            
            edge_threshold = 0.03  # Mínimo 3% de ventaja para operar
            
            if abs(edge_yes) > edge_threshold or abs(edge_no) > edge_threshold:
                should_trade = True
                if edge_yes > edge_no:
                    position = "YES"
                    price = yes_price
                    edge = edge_yes
                else:
                    position = "NO"
                    price = no_price
                    edge = edge_no
            else:
                edge = max(edge_yes, edge_no)
            
            # Formatear decisión final
            decision_reasoning = (
                f"=== DECISION REASONING ===\n"
                f"PROBABILITY ANALYSIS:\n"
                f"The estimated probability is {ai_probability:.2f} based on news analysis and current data.\n\n"
                f"MARKET EDGE ANALYSIS:\n"
                f"Edge for YES: {edge_yes:.4f} (Prob. {ai_probability:.2f} - Price {yes_price:.2f})\n"
                f"Edge for NO: {edge_no:.4f} (Prob. {1-ai_probability:.2f} - Price {no_price:.2f})\n\n"
                f"FINAL RECOMMENDATION:\n"
                f"{'TRADE' if should_trade else 'DO NOT TRADE'}\n\n"
                f"RECOMMENDATION REASONING:\n"
                f"{'The detected edge exceeds the minimum required threshold.' if should_trade else 'There is not enough edge to justify a trade.'}"
            )
            
            trade_result = {
                "market": market_data.question,
                "news_analysis": news_analysis,
                "decision_reasoning": decision_reasoning,
                "ai_probability": ai_probability,
                "should_trade": should_trade,
                "position": position,
                "price": price,
                "edge": edge,
                "confidence": "High" if abs(edge) > 0.1 else "Medium" if abs(edge) > 0.05 else "Low"
            }
            
            # Mostrar decisión final
            print(f"\n{Fore.GREEN}=== FINAL DECISION ===")
            print(f"Decision: {'TRADE' if should_trade else 'DO NOT TRADE'}")
            print(f"AI Probability: {ai_probability:.2f}")
            print(f"Market YES price: {yes_price:.4f}")
            print(f"Market NO price: {no_price:.4f}")
            print(f"{Style.RESET_ALL}")
            
            return trade_result

    def format_trade_prompt_for_execution(self, best_trade: str) -> float:
        if isinstance(best_trade, str):
            # Si es string, parsearlo
            data = best_trade.split(",")
            size = re.findall("\d+\.\d+", data[1])[0]
            return float(1.0)  # Monto fijo de 1 USDC para pruebas
        elif isinstance(best_trade, dict):
            # Si ya es diccionario, usar el size directamente
            return float(best_trade.get('size', 1.0))
        
        # Por defecto, retornar 1 USDC
        return 1.0

    def source_best_market_to_create(self, filtered_markets) -> str:
        prompt = self.prompter.create_new_market(filtered_markets)
        print()
        print("... prompting ... ", prompt)
        print()
        result = self.llm.invoke(prompt)
        content = result.content
        return content

    def analyze_with_assistant(self, context: Dict) -> str:
        """
        Analiza el contexto del mercado utilizando un asistente AI
        
        Args:
            context: Diccionario con el contexto del mercado, incluyendo:
                - market_id: ID del mercado
                - question: Pregunta del mercado
                - description: Descripción del mercado
                - prices: Precios actuales (YES/NO)
                - end_date: Fecha de cierre
                - news: Artículos de noticias relevantes
                
        Returns:
            Texto con el análisis completo del asistente
        """
        try:
            logging.info(f"Analizing market {context.get('market_id')} with assistant")
            
            # Construir prompt para el asistente
            prompt = self._build_analysis_prompt(context)
            
            # En un sistema real, aquí conectaríamos con OpenAI o Claude
            # Para esta versión simplificada, simulamos la respuesta
            if self.test_mode:
                response = self._simulate_assistant_response(context)
            else:
                # Simulamos la respuesta para esta versión
                response = self._simulate_assistant_response(context)
                
                # En un sistema real, sería algo como:
                # response = openai.ChatCompletion.create(
                #     model="gpt-4",
                #     messages=[{"role": "user", "content": prompt}],
                #     temperature=0.2,
                # ).choices[0].message.content
            
            logging.info(f"Analysis completed for {context.get('market_id')}")
            return response
            
        except Exception as e:
            logging.error(f"Error analyzing with assistant: {e}")
            return ""
    
    def _build_analysis_prompt(self, context: Dict) -> str:
        """
        Construye el prompt para el asistente
        
        Args:
            context: Diccionario con el contexto del mercado
            
        Returns:
            Prompt formateado para el asistente
        """
        # Extraer información relevante
        question = context.get("question", "")
        description = context.get("description", "")
        prices = context.get("prices", {})
        yes_price = prices.get("YES", 0.5)
        no_price = prices.get("NO", 0.5)
        end_date = context.get("end_date", "unknown")
        
        # Formatear noticias
        news_section = ""
        if context.get("news"):
            news_section = "\n\nRELATED NEWS ARTICLES:\n"
            for i, article in enumerate(context.get("news", []), 1):
                news_section += f"\nARTICLE {i}:\n"
                news_section += f"Title: {article.get('title', '')}\n"
                news_section += f"Source: {article.get('source', '')}\n"
                news_section += f"Date: {article.get('published_at', '')}\n"
                news_section += f"Content: {article.get('content', '')}\n"
                news_section += f"URL: {article.get('url', '')}\n"
        
        # Construir prompt completo
        prompt = f"""Analyze the following prediction market:

QUESTION: {question}

DESCRIPTION: {description}

CURRENT PRICES:
- YES: {yes_price:.2f}
- NO: {no_price:.2f}

END DATE: {end_date}
{news_section}

Instructions:
1. Analyze the question and the real probability of it happening.
2. Evaluate the provided news and how they affect the probability.
3. Compare your estimated probability with the market prices.
4. Determine if there is a significant difference (more than 5%) between your estimated probability and the market price.
5. Recommend a position: "YES" if you think the YES price is undervalued, "NO" if you think the NO price is undervalued, or "NO TRADE" if there is no clear advantage.

Provide your analysis in the following format:
- Initial Summary
- Probability Analysis
- Key Factors
- Value Analysis
- FINAL RECOMMENDATION: [YES/NO/NO TRADE]
- REASONING: [Explain your reasoning]
- ESTIMATED PROBABILITY: [Your estimated probability of the event]
"""
        
        return prompt
    
    def _simulate_assistant_response(self, context: Dict) -> str:
        """
        Simula una respuesta del asistente para testing
        
        Args:
            context: Diccionario con el contexto del mercado
            
        Returns:
            Texto simulado del análisis
        """
        question = context.get("question", "")
        prices = context.get("prices", {})
        yes_price = prices.get("YES", 0.5)
        no_price = prices.get("NO", 0.5)
        
        # Crear una estimación de probabilidad simple (para simulación)
        estimated_prob = random.uniform(0.3, 0.7)
        
        # Determinar si hay ventaja
        yes_edge = estimated_prob - yes_price
        no_edge = (1 - estimated_prob) - no_price
        
        recommendation = "NO TRADE"
        edge_threshold = 0.05  # 5% de ventaja mínima
        
        if yes_edge > edge_threshold:
            recommendation = "YES"
            reasoning = f"The YES price ({yes_price:.2f}) is significantly below my estimated probability ({estimated_prob:.2f}), offering an edge of {yes_edge:.2f}."
        elif no_edge > edge_threshold:
            recommendation = "NO"
            reasoning = f"The NO price ({no_price:.2f}) is significantly below my estimated probability for NO ({1-estimated_prob:.2f}), offering an edge of {no_edge:.2f}."
        else:
            reasoning = f"There is not enough edge between my estimated probability ({estimated_prob:.2f}) and the market prices (YES: {yes_price:.2f}, NO: {no_price:.2f})."
        
        # Construir respuesta simulada
        response = f"""# Market Analysis: {question}

## Initial Summary
I analyzed the prediction market about the question: "{question}". This analysis will consider the available information and evaluate if there is an opportunity for trading.

## Probability Analysis
Based on the available information, I estimate that the probability of this event happening is approximately {estimated_prob:.2f} or {estimated_prob*100:.1f}%.

## Key Factors
- The nature of the question suggests some uncertainty
- The current market prices are YES: {yes_price:.2f} and NO: {no_price:.2f}
- There are {len(context.get('news', []))} relevant news articles I considered

## Value Analysis
Comparing my estimated probability ({estimated_prob:.2f}) with the market prices:
- For YES: Edge = {yes_edge:.3f}
- For NO: Edge = {no_edge:.3f}

A positive edge indicates a possible opportunity for trading.

## FINAL RECOMMENDATION: {recommendation}

## REASONING: {reasoning}

## ESTIMATED PROBABILITY: {estimated_prob:.2f}
"""
        
        return response
    
    def extract_decision(self, analysis_text: str) -> Optional[Dict]:
        """
        Extrae la decisión de trading de un análisis completo.
        
        Args:
            analysis_text: Texto completo del análisis
            
        Returns:
            Diccionario con la decisión estructurada o None si no se pudo extraer
        """
        try:
            # Buscar la recomendación final en el texto
            recommendation_match = re.search(r'FINAL RECOMMENDATION:[\s\n]*(.*?)[\s\n]*(?:REASONING|$)', analysis_text, re.IGNORECASE | re.DOTALL)
            
            if not recommendation_match:
                logging.error(f"No se encontró sección de recomendación final")
                return None
                
            recommendation = recommendation_match.group(1).strip()
            
            # Normalizar recomendación
            if "YES" in recommendation.upper():
                recommendation = "YES"
            elif "NO" in recommendation.upper() and "NO TRADE" not in recommendation.upper():
                recommendation = "NO"
            else:
                recommendation = "NO TRADE"
                
            # Buscar razonamiento
            reasoning_match = re.search(r'REASONING:[\s\n]*(.*?)[\s\n]*(?:ESTIMATED PROBABILITY|$)', analysis_text, re.IGNORECASE | re.DOTALL)
            reasoning = reasoning_match.group(1).strip() if reasoning_match else ""
            
            # Buscar probabilidad estimada
            probability_match = re.search(r'ESTIMATED PROBABILITY:[\s\n]*(.*?)[\s\n]*', analysis_text, re.IGNORECASE | re.DOTALL)
            probability_str = probability_match.group(1).strip() if probability_match else ""
            
            # Convertir probabilidad a float
            probability = None
            if probability_str:
                # Extraer posibles números de la cadena
                prob_numbers = re.findall(r'0\.\d+|\d+\.\d+|\d+', probability_str)
                if prob_numbers:
                    try:
                        probability = float(prob_numbers[0])
                        # Si la probabilidad está en porcentaje (>1), convertir a decimal
                        if probability > 1:
                            probability /= 100
                    except:
                        logging.warning(f"No se pudo convertir probabilidad: {probability_str}")
            
            decision = {
                "recommendation": recommendation,
                "reasoning": reasoning,
                "probability": probability
            }
            
            logging.info(f"Decision extracted: {recommendation}")
            return decision
            
        except Exception as e:
            logging.error(f"Error extracting decision: {e}")
            return None

    def get_related_news(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Obtiene noticias relacionadas con una consulta específica
        
        Args:
            query: La consulta para buscar noticias
            max_results: Número máximo de noticias a devolver
            
        Returns:
            Lista de artículos de noticias relacionados
        """
        try:
            if not self.news:
                print("News connector not initialized")
                return []
            
            # Llamar al conector de noticias para obtener los resultados
            news_results = self.news.search_news(query, max_results=max_results)
            
            # Convertir a formato estándar si es necesario
            if news_results and isinstance(news_results, list):
                # Ya está en formato correcto
                return news_results[:max_results] if max_results else news_results
            elif news_results and isinstance(news_results, dict) and "articles" in news_results:
                # Formato de respuesta de API de noticias
                return news_results["articles"][:max_results] if max_results else news_results["articles"]
            else:
                print(f"Formato de noticias no reconocido: {type(news_results)}")
                return []
        except Exception as e:
            print(f"Error obtaining news: {e}")
            return []
