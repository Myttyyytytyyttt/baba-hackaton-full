import os
import json
import time
import argparse
import glob
import re
from typing import List, Dict, Any
from web3 import Web3
from web3.middleware import geth_poa_middleware
import requests
from dotenv import load_dotenv
import logging
import random  # Para seleccionar mercados aleatorios en modo prueba
import firebase_admin
from firebase_admin import credentials, firestore

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

class PolymarketRedeemer:
    def __init__(self, wallet_address=None, private_key=None, debug_mode=False):
        # Configurar web3 para Polygon
        self.w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # Configurar credenciales
        self.wallet_address = wallet_address or os.getenv("WALLET_ADDRESS")
        self.private_key = private_key or os.getenv("PRIVATE_KEY")
        
        # Modo debug para mostrar información detallada
        self.debug_mode = debug_mode
        
        if not self.wallet_address or not self.private_key:
            raise ValueError("Wallet address and private key are required")
        
        # Asegurar que la dirección está en formato checksum
        self.wallet_address = Web3.to_checksum_address(self.wallet_address)
        
        # Configurar contratos y endpoints
        self.ctf_address = Web3.to_checksum_address("0x4D97DCd97eC945f40cF65F87097ACe5EA0476045")
        self.gamma_api_url = "https://gamma-api.polymarket.com"
        
        # ABI del contrato CTF para la función redeem
        self.ctf_abi = '''[
            {
                "inputs": [
                    {"name": "collateralToken", "type": "address"},
                    {"name": "parentCollectionId", "type": "bytes32"},
                    {"name": "conditionId", "type": "bytes32"},
                    {"name": "indexSets", "type": "uint256[]"}
                ],
                "name": "redeemPositions",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]'''
        
        # Inicializar contrato
        self.ctf_contract = self.w3.eth.contract(address=self.ctf_address, abi=json.loads(self.ctf_abi))
        
        # USDC en Polygon
        self.usdc_address = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")
        
        # Inicializar Firebase para obtener historial de trades
        self.db = None
        self.init_firebase()
        
        logger.info(f"Redeemer initialized for wallet: {self.wallet_address}")
        if self.debug_mode:
            logger.info("DEBUG MODE ENABLED - Will show detailed information")
    
    def init_firebase(self):
        """Inicializar conexión a Firebase"""
        try:
            # Inicializar Firebase utilizando archivo de credenciales
            cred_path = os.path.join(os.path.dirname(__file__), '../../config/babavangabd.json')
            
            if not os.path.exists(cred_path):
                logger.warning(f"Firebase credentials file not found at {cred_path}")
                logger.warning("Will use local predictions only")
                return
                
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            
            self.db = firestore.client()
            logger.info("Firebase initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            logger.warning("Will use local predictions only")
    
    def get_all_markets(self) -> List[Dict[str, Any]]:
        """Obtener todos los mercados disponibles desde la API de Gamma"""
        try:
            markets = []
            # Obtener tanto mercados activos como archivados
            for archived in [False, True]:
                params = {
                    "limit": "1000",
                    "archived": str(archived).lower()
                }
                
                headers = {
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                
                response = requests.get(
                    f"{self.gamma_api_url}/markets",
                    params=params,
                    headers=headers
                )
                
                if response.status_code == 200:
                    batch = response.json()
                    markets.extend(batch)
                    logger.info(f"Retrieved {len(batch)} {'archived' if archived else 'active'} markets")
                else:
                    logger.error(f"Error fetching {'archived' if archived else 'active'} markets: {response.status_code} - {response.text}")
            
            logger.info(f"Total markets retrieved: {len(markets)}")
            return markets
        except Exception as e:
            logger.error(f"Error getting markets: {e}")
            return []
    
    def get_user_trades_from_firebase(self) -> List[Dict[str, Any]]:
        """Obtener los trades realizados por el usuario desde Firebase"""
        trades = []
        
        if not self.db:
            logger.warning("Firebase not initialized, skipping Firebase trades lookup")
            return trades
            
        try:
            # Consultar colección de predicciones
            query = self.db.collection('predictions').get()
            
            for doc in query:
                trade_data = doc.to_dict()
                trades.append({
                    'market_id': trade_data.get('market_id'),
                    'question': trade_data.get('question'),
                    'prediction': trade_data.get('prediction', 'UNKNOWN')  # YES o NO
                })
                
            logger.info(f"Retrieved {len(trades)} trades from Firebase")
            return trades
        except Exception as e:
            logger.error(f"Error retrieving trades from Firebase: {e}")
            return []
    
    def get_user_trades_from_local(self) -> List[Dict[str, Any]]:
        """Obtener los trades realizados por el usuario desde archivos locales"""
        trades = []
        
        try:
            local_dir = 'local_predictions'
            if not os.path.exists(local_dir):
                logger.warning(f"Local predictions directory not found: {local_dir}")
                return trades
                
            # Buscar todos los archivos de predicciones
            prediction_files = glob.glob(os.path.join(local_dir, "*.txt"))
            
            for file_path in prediction_files:
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        
                        # Extraer datos básicos del archivo
                        market_id_match = re.search(r"Market ID: (\d+)", content)
                        market_match = re.search(r"Market: (.*?)\n", content)
                        prediction_match = re.search(r"Prediction: (YES|NO)", content)
                        
                        if market_id_match and market_match:
                            market_id = market_id_match.group(1)
                            market_name = market_match.group(1)
                            prediction = prediction_match.group(1) if prediction_match else "UNKNOWN"
                            
                            trades.append({
                                'market_id': market_id,
                                'question': market_name,
                                'prediction': prediction
                            })
                except Exception as e:
                    logger.error(f"Error parsing prediction file {file_path}: {e}")
                    continue
                    
            logger.info(f"Retrieved {len(trades)} trades from local files")
            return trades
        except Exception as e:
            logger.error(f"Error retrieving trades from local files: {e}")
            return []
    
    def get_all_user_trades(self) -> List[Dict[str, Any]]:
        """Combinar trades de Firebase y archivos locales"""
        # Obtener trades de ambas fuentes
        firebase_trades = self.get_user_trades_from_firebase()
        local_trades = self.get_user_trades_from_local()
        
        # Combinar y eliminar duplicados basados en market_id
        all_trades = firebase_trades + local_trades
        unique_trades = {}
        
        for trade in all_trades:
            market_id = str(trade.get('market_id'))
            if market_id and market_id not in unique_trades:
                unique_trades[market_id] = trade
                
        result = list(unique_trades.values())
        logger.info(f"Total unique markets traded: {len(result)}")
        return result
    
    def get_resolved_markets(self) -> List[Dict[str, Any]]:
        """Obtener mercados resueltos o finalizados"""
        markets = self.get_all_markets()
        resolved_markets = []
        
        for market in markets:
            # Verificar si el mercado está resuelto o finalizado
            is_finished = False
            
            # Comprobar diferentes campos que pueden indicar que el mercado ha finalizado
            if market.get("status") == "Resolved" or market.get("status") == "RESOLVED":
                is_finished = True
            elif market.get("isResolved") == True:
                is_finished = True
            elif market.get("resultValue") is not None:
                is_finished = True
            elif market.get("result") is not None:
                is_finished = True
            elif market.get("winningOutcome") is not None:
                is_finished = True
            # Comprobar si está archivado o inactivo
            elif market.get("archived") == True:
                is_finished = True
            elif market.get("active") == False:
                is_finished = True
            elif market.get("isActive") == False:
                is_finished = True
            # Comprobar fechas de cierre
            elif market.get("end") and not market.get("end").startswith("0"):
                is_finished = True
            elif market.get("endDate") and not isinstance(market.get("endDate"), bool):
                end_date = market.get("endDate")
                # Verificar si la fecha de cierre ya pasó
                if isinstance(end_date, str) and "T" in end_date:
                    try:
                        import datetime
                        end_date_obj = datetime.datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                        if end_date_obj < datetime.datetime.now(datetime.timezone.utc):
                            is_finished = True
                    except:
                        pass
            
            # Solo añadir el mercado si está acabado
            if is_finished:
                resolved_markets.append(market)
                if self.debug_mode:
                    logger.info(f"Found market: {market.get('question', 'Unknown')}")
                    # Datos de resolución
                    for field in ["status", "isResolved", "resultValue", "result", "winningOutcome", "archived", "active", "isActive", "end", "endDate"]:
                        logger.info(f"  {field}: {market.get(field)}")
        
        logger.info(f"Found {len(resolved_markets)} finished/resolved markets")
        return resolved_markets
        
    def get_user_resolved_markets(self) -> List[Dict[str, Any]]:
        """Obtener los mercados resueltos en los que el usuario ha participado"""
        # Obtener todos los trades del usuario
        user_trades = self.get_all_user_trades()
        
        # Crear un mapa de IDs de mercado
        user_market_ids = {str(trade.get('market_id')): trade for trade in user_trades}
        
        # Obtener todos los mercados resueltos
        resolved_markets = self.get_resolved_markets()
        
        # Filtrar solo los mercados en los que el usuario participó
        user_resolved_markets = []
        for market in resolved_markets:
            market_id = str(market.get('id'))
            if market_id in user_market_ids:
                # Añadir la predicción del usuario al mercado
                market['user_prediction'] = user_market_ids[market_id].get('prediction', 'UNKNOWN')
                user_resolved_markets.append(market)
        
        logger.info(f"Found {len(user_resolved_markets)} resolved markets where you participated")
        return user_resolved_markets
    
    def get_condition_id_from_market(self, market_data: Dict[str, Any]) -> str:
        """Extraer el condition ID de los datos del mercado"""
        try:
            # En muchos casos, el conditionId está disponible directamente
            if "conditionId" in market_data:
                logger.info(f"Found conditionId directly in market data: {market_data['conditionId']}")
                return market_data["conditionId"]
                
            # Alternativa: usar questionID si está disponible
            question_id = market_data.get("questionID") or market_data.get("questionId")
            if question_id:
                logger.info(f"Using questionID as conditionId: {question_id}")
                return question_id
            
            # Podría estar en metadatos
            metadata = market_data.get("metadata", {})
            if isinstance(metadata, dict) and "conditionId" in metadata:
                logger.info(f"Found conditionId in metadata: {metadata['conditionId']}")
                return metadata["conditionId"]
            
            # Buscar en campos de condición
            condition = market_data.get("condition", {})
            if isinstance(condition, dict) and "id" in condition:
                logger.info(f"Found conditionId in condition object: {condition['id']}")
                return condition["id"]
            
            # Imprimir estructura del mercado para depuración
            if self.debug_mode:
                logger.warning("Could not find conditionId. Market structure:")
                for key, value in market_data.items():
                    logger.warning(f"  {key}: {type(value).__name__}")
                
            # Último recurso: el ID del mercado puede ser útil
            market_id = market_data.get('id', '0')
            logger.warning(f"Using market ID as last resort: {market_id}")
            if isinstance(market_id, int):
                return f"0x{market_id:064x}"
            else:
                return f"0x{int(market_id):064x}" if market_id.isdigit() else f"0x{'0':064}"
        except Exception as e:
            logger.error(f"Error extracting condition ID: {e}")
            return ""
    
    def dump_market_data(self, market):
        """Imprime la estructura completa de un mercado para debug"""
        if not self.debug_mode:
            return
            
        logger.info("=" * 50)
        logger.info(f"MARKET DEBUG DUMP: {market.get('question', 'Unknown market')}")
        logger.info("-" * 50)
        
        # Imprimir todos los campos de primer nivel
        for key, value in market.items():
            if isinstance(value, (dict, list)):
                logger.info(f"{key}: {type(value).__name__} - {len(value)} items")
            else:
                logger.info(f"{key}: {value}")
        
        # Imprimir campos de interés especial en detalle
        special_fields = ["clobTokenIds", "tokenIds", "outcomes", "condition", "metadata"]
        for field in special_fields:
            if field in market:
                logger.info(f"\nDetailed {field}:")
                logger.info(f"{json.dumps(market[field], indent=2)}")
        
        logger.info("=" * 50)
        
    def redeem_position(self, market_data: Dict[str, Any]) -> bool:
        """Redimir posiciones ganadoras para un mercado específico"""
        try:
            market_name = market_data.get("question", "Unknown market")
            logger.info(f"Attempting to redeem position for: {market_name}")
            
            # Obtener datos necesarios del mercado
            condition_id = self.get_condition_id_from_market(market_data)
            if not condition_id:
                logger.error(f"Could not determine condition ID for market: {market_name}")
                return False
            
            # Asegurarnos de que condition_id es un string hexadecimal con 0x
            if not condition_id.startswith('0x'):
                condition_id = f"0x{condition_id}"
            
            # Determinar el índice del resultado ganador
            winning_index = None
            outcomes = market_data.get("outcomes", [])
            result_value = market_data.get("resultValue") or market_data.get("result") or market_data.get("winningOutcome")
            
            # Obtener la predicción del usuario
            user_prediction = market_data.get("user_prediction", "UNKNOWN")
            
            # Mostrar información detallada en modo debug
            if self.debug_mode:
                logger.info(f"Market data for redeeming:")
                logger.info(f"  Result value: {result_value}")
                logger.info(f"  Condition ID: {condition_id}")
                logger.info(f"  Outcomes: {outcomes}")
                logger.info(f"  User prediction: {user_prediction}")
            
            if not result_value:
                # Intentar obtener el resultado desde la API si no está en los datos del mercado
                try:
                    market_id = market_data.get("id")
                    if market_id:
                        # Consultar API para el resultado
                        market_details_url = f"{self.gamma_api_url}/markets/{market_id}"
                        response = requests.get(market_details_url)
                        if response.status_code == 200:
                            market_details = response.json()
                            result_value = market_details.get("resultValue") or market_details.get("result") or market_details.get("winningOutcome")
                            logger.info(f"Retrieved result from API: {result_value}")
                except Exception as e:
                    logger.error(f"Error retrieving market details: {e}")
            
            if not result_value:
                logger.warning(f"Market {market_name} does not have a result value yet")
                return False
                
            # Buscar el índice ganador
            for i, outcome in enumerate(outcomes):
                # Comparar con el valor del resultado (puede variar según la API)
                outcome_value = outcome
                if isinstance(outcome, dict):
                    outcome_value = outcome.get("value") or outcome.get("name")
                
                if str(outcome_value) == str(result_value):
                    winning_index = i
                    break
            
            if winning_index is None:
                logger.error(f"Could not determine winning index for market: {market_name}")
                logger.error(f"Result value: {result_value}")
                logger.error(f"Available outcomes: {outcomes}")
                return False
            
            # Verificar si el usuario ganó este mercado
            user_won = False
            if user_prediction == "YES" and winning_index == 1:  # YES suele ser el índice 1
                user_won = True
            elif user_prediction == "NO" and winning_index == 0:  # NO suele ser el índice 0
                user_won = True
                
            if not user_won:
                logger.info(f"You did not win in market '{market_name}'. Your prediction: {user_prediction}, Winning outcome: {outcomes[winning_index]}")
                return False
                
            logger.info(f"You won in market '{market_name}'! Your prediction: {user_prediction}, Winning outcome: {outcomes[winning_index]}")
            
            # Calcular el indexSet (1 << winning_index)
            index_set = 1 << winning_index
            
            # Parent collection ID (generalmente 0 para mercados simples)
            parent_collection_id = "0x0000000000000000000000000000000000000000000000000000000000000000"
            
            # Construir la transacción
            logger.info(f"Redeeming position for market: {market_name}")
            logger.info(f"Condition ID: {condition_id}")
            logger.info(f"Winning Index: {winning_index} (IndexSet: {index_set})")
            
            # Convertir condition_id a bytes si es necesario
            condition_id_bytes = Web3.to_bytes(hexstr=condition_id)
            
            tx = self.ctf_contract.functions.redeemPositions(
                self.usdc_address,  # Collateral token (USDC)
                Web3.to_bytes(hexstr=parent_collection_id),
                condition_id_bytes,
                [index_set]
            ).build_transaction({
                'from': self.wallet_address,
                'gas': 500000,  # Aumentar el gas para transacciones más complejas
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.wallet_address)
            })
            
            # Firmar y enviar la transacción
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f"Transaction sent: {tx_hash.hex()}")
            logger.info("Waiting for confirmation...")
            
            # Esperar confirmación
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            if receipt.status == 1:
                logger.info(f"✅ Successfully redeemed position for market: {market_name}")
                return True
            else:
                logger.error(f"❌ Transaction failed for market: {market_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error redeeming position: {e}")
            return False
    
    def redeem_all_winning_positions(self, limit=None, randomize=False):
        """Redimir todas las posiciones ganadoras disponibles"""
        try:
            # Obtener mercados resueltos donde tenemos posiciones
            resolved_markets = self.get_user_resolved_markets()
            
            if not resolved_markets:
                logger.info("No resolved markets found where you participated")
                return
            
            # En modo debug, mostrar información detallada de cada mercado
            if self.debug_mode:
                logger.info("\n\nDEBUG: Showing detailed market information")
                for i, market in enumerate(resolved_markets):
                    logger.info(f"\n{i+1}. {market.get('question', 'Unknown')} - Your prediction: {market.get('user_prediction', 'UNKNOWN')}")
                    self.dump_market_data(market)
            
            # Limitar el número de mercados a procesar si es necesario
            if randomize and resolved_markets:
                # Seleccionar aleatoriamente
                if limit and limit < len(resolved_markets):
                    markets_to_process = random.sample(resolved_markets, limit)
                else:
                    markets_to_process = resolved_markets.copy()
                    random.shuffle(markets_to_process)
            elif limit and limit < len(resolved_markets):
                # Seleccionar los primeros N mercados
                markets_to_process = resolved_markets[:limit]
            else:
                markets_to_process = resolved_markets
            
            # Procesar cada mercado
            redeemed_count = 0
            
            for market in markets_to_process:
                try:
                    # Intenta redimir la posición
                    if self.redeem_position(market):
                        redeemed_count += 1
                        # Esperar un poco entre transacciones
                        time.sleep(2)
                except Exception as e:
                    logger.error(f"Error processing market {market.get('id')}: {e}")
                    continue
            
            logger.info(f"Completed redemption process. Successfully redeemed {redeemed_count}/{len(markets_to_process)} positions.")
            
        except Exception as e:
            logger.error(f"Error redeeming all positions: {e}")

# Uso del programa
if __name__ == "__main__":
    # Parsear argumentos de línea de comandos
    parser = argparse.ArgumentParser(description="Redeem winning positions on Polymarket")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--dry-run", action="store_true", help="Don't execute actual transactions")
    parser.add_argument("--wallet", type=str, help="Wallet address (overrides .env)")
    parser.add_argument("--key", type=str, help="Private key (overrides .env)")
    parser.add_argument("--limit", type=int, help="Limit the number of markets to process")
    parser.add_argument("--random", action="store_true", help="Process markets in random order")
    args = parser.parse_args()
    
    # ADVERTENCIA: No es recomendable incluir claves privadas directamente en el código
    # En producción, usa variables de entorno o archivos de configuración seguros
    wallet = args.wallet or "0x0157A249F411b7F7348265b7EaA57c36FA1C5d89"
    key = args.key or "ea437a176be716961c22a6e7bf2f4837d2aa37e210eee24e25535a8cb4f31a9c"
    
    redeemer = PolymarketRedeemer(wallet_address=wallet, private_key=key, debug_mode=args.debug)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No transactions will be executed")
        # Solo mostrar mercados y posiciones
        markets = redeemer.get_user_resolved_markets()
        if args.limit and args.limit < len(markets):
            if args.random:
                markets = random.sample(markets, args.limit)
            else:
                markets = markets[:args.limit]
                
        for market in markets:
            redeemer.dump_market_data(market)
    else:
        redeemer.redeem_all_winning_positions(limit=args.limit, randomize=args.random)