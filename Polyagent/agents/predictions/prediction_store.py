import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from typing import Dict, Optional, Any
from colorama import Fore, Style, init
from agents.utils.objects import SimpleMarket

init()  # Initialize colorama

class PredictionStore:
    def __init__(self):
        try:
            # Initialize Firebase using credentials file
            cred_path = os.path.join(os.path.dirname(__file__), '../../config/babavangabd.json')
            
            if not os.path.exists(cred_path):
                print(f"{Fore.RED}Error: Firebase credentials file not found at {cred_path}{Style.RESET_ALL}")
                print("Please download the credentials file from Firebase console and save it as config/babavangabd.json")
                raise FileNotFoundError("Firebase credentials file not found")
                
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            
            self.db = firestore.client()
            print(f"{Fore.GREEN}Firebase initialized successfully{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{Fore.RED}Failed to initialize Firebase: {str(e)}{Style.RESET_ALL}")
            raise
        
    def store_trade_prediction(self, market_data: SimpleMarket, trade_data: Dict, analysis: str) -> Optional[str]:
        """
        Store a prediction when a trade is executed
        """
        try:
            # Convert SimpleMarket to dict
            prediction = {
                'timestamp': datetime.now(),
                'market_id': getattr(market_data, 'id', None),
                'question': getattr(market_data, 'question', None),
                'description': getattr(market_data, 'description', None),
                'prediction': trade_data.get('position', 'UNKNOWN'),
                'confidence': trade_data.get('confidence', 0),
                'entry_price': trade_data.get('price', 0),
                'size': trade_data.get('size', 0),
                'reasoning': trade_data.get('analysis', ''),
                'category': getattr(market_data, 'category', 'unknown'),
                'status': 'active',
                'volume': getattr(market_data, 'volume', 0),
                'analysis_details': {
                    'full_analysis': analysis,
                    'edge': trade_data.get('edge', 0),
                    'prediction_text': trade_data.get('prediction', ''),
                    'news_analysis': trade_data.get('news_analysis', ''),
                    'decision_reasoning': trade_data.get('decision_reasoning', ''),
                    'ai_probability': trade_data.get('ai_probability', 0.5),
                    'should_trade': trade_data.get('should_trade', False)
                }
            }
            
            # Add to Firestore
            doc_ref = self.db.collection('predictions').add(prediction)
            
            # Print detailed console log
            print(f"\n{Fore.CYAN}=== Prediction Stored in Firebase ==={Style.RESET_ALL}")
            print(f"{Fore.GREEN}ID: {doc_ref[1].id}")
            print(f"Market: {prediction['question']}")
            print(f"Prediction: {prediction['prediction']} @ ${prediction['entry_price']}")
            print(f"AI Probability: {prediction['analysis_details']['ai_probability']:.2%}")
            print(f"Size: ${prediction['size']} USDC")
            print(f"Edge: {prediction['analysis_details']['edge']:.4f}")
            print(f"Trade Executed: {prediction['analysis_details']['should_trade']}")
            print(f"Timestamp: {prediction['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{Fore.CYAN}==================================={Style.RESET_ALL}\n")
            
            # Guardar un registro local para seguimiento sin Firebase
            self._save_local_record(prediction, doc_ref[1].id)
            
            return doc_ref[1].id
            
        except Exception as e:
            print(f"{Fore.RED}Error storing prediction: {e}{Style.RESET_ALL}")
            
            # Intentar guardar localmente en caso de error con Firebase
            try:
                local_id = f"local_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                self._save_local_record({
                    'timestamp': datetime.now(),
                    'market_id': getattr(market_data, 'id', None),
                    'question': getattr(market_data, 'question', None),
                    'prediction': trade_data.get('position', 'UNKNOWN'),
                    'entry_price': trade_data.get('price', 0),
                    'edge': trade_data.get('edge', 0),
                    'analysis': analysis
                }, local_id)
                return local_id
            except:
                pass
                
            return None
            
    def _save_local_record(self, prediction_data: Dict, prediction_id: str) -> None:
        """Guarda un registro local de la predicción para casos donde Firebase no está disponible"""
        try:
            # Crear directorio si no existe
            os.makedirs('local_predictions', exist_ok=True)
            
            # Crear archivo con registro de la predicción
            file_path = os.path.join('local_predictions', f"{prediction_id}.txt")
            
            with open(file_path, 'w') as f:
                f.write(f"=== Prediction {prediction_id} ===\n")
                f.write(f"Timestamp: {prediction_data['timestamp']}\n")
                f.write(f"Market: {prediction_data['question']}\n")
                f.write(f"Prediction: {prediction_data['prediction']} @ ${prediction_data['entry_price']}\n")
                
                # Escribir análisis detallado si está disponible
                if 'analysis_details' in prediction_data:
                    f.write("\n=== ANÁLISIS DE NOTICIAS ===\n")
                    f.write(prediction_data['analysis_details'].get('news_analysis', 'No available'))
                    
                    f.write("\n\n=== RAZONAMIENTO DE DECISIÓN ===\n")
                    f.write(prediction_data['analysis_details'].get('decision_reasoning', 'No available'))
                
            print(f"{Fore.GREEN}Backup local guardado en {file_path}{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{Fore.RED}Error guardando backup local: {e}{Style.RESET_ALL}")
            
    def update_prediction_status(self, prediction_id: str, status: str, outcome: Optional[str] = None) -> bool:
        """
        Update the status of a prediction
        """
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.now()
            }
            
            if outcome:
                update_data['outcome'] = outcome
                
            self.db.collection('predictions').document(prediction_id).update(update_data)
            return True
            
        except Exception as e:
            print(f"Error updating prediction: {e}")
            return False 