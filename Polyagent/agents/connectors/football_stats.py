"""
Conector para obtener estadísticas de fútbol utilizando la API de api-sports.io
"""

import os
import sys
import json
import time
import logging
import requests
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
import re
from pathlib import Path
import pickle

logger = logging.getLogger(__name__)

class FootballStats:
    """
    Conector para obtener estadísticas de fútbol usando la API de api-sports.io
    Proporciona métodos para obtener información de equipos, partidos, y estadísticas
    para ayudar en la predicción de mercados relacionados con fútbol.
    
    Utiliza caché para minimizar las solicitudes a la API y respetar los límites diarios.
    """
    
    def __init__(self, log_level=logging.INFO, cache_dir="cache"):
        """
        Inicializa el conector de estadísticas de fútbol
        
        Args:
            log_level: Nivel de logging (default: logging.INFO)
            cache_dir: Directorio para almacenar la caché (default: "cache")
        """
        # Configurar logging
        self.logger = logging.getLogger("FootballStats")
        self.logger.setLevel(log_level)
        
        # Configurar handler si no existe
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
        # Obtener API key
        self.api_key = os.environ.get("FOOTBALL_API_KEY")
        if not self.api_key:
            self.logger.warning("FOOTBALL_API_KEY not found in environment variables")
            
        # Configurar caché
        self.cache_dir = Path(cache_dir) / "football_stats"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Cargar contador de solicitudes diarias
        self.request_count_file = self.cache_dir / "request_count.json"
        self.request_count = self._load_request_count()
        
        # Cargar caché
        self.cache_file = self.cache_dir / "api_cache.pkl"
        self.cache = self._load_cache()
        
        self.logger.info("FootballStats connector initialized")
        
    def _load_request_count(self) -> Dict:
        """Carga el contador de solicitudes desde el archivo"""
        if self.request_count_file.exists():
            try:
                with open(self.request_count_file, 'r') as f:
                    data = json.load(f)
                    
                # Verificar si el contador es de hoy
                today = datetime.now().strftime("%Y-%m-%d")
                if data.get("date") != today:
                    # Reiniciar contador si es de otro día
                    data = {"date": today, "count": 0}
                    
                return data
            except Exception as e:
                self.logger.error(f"Error loading request count: {e}")
                
        # Crear contador inicial
        today = datetime.now().strftime("%Y-%m-%d")
        return {"date": today, "count": 0}
        
    def _save_request_count(self):
        """Guarda el contador de solicitudes al archivo"""
        try:
            with open(self.request_count_file, 'w') as f:
                json.dump(self.request_count, f)
        except Exception as e:
            self.logger.error(f"Error saving request count: {e}")
            
    def _load_cache(self) -> Dict:
        """Carga la caché desde el archivo"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                self.logger.error(f"Error loading cache: {e}")
                
        return {}
        
    def _save_cache(self):
        """Guarda la caché al archivo"""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
        except Exception as e:
            self.logger.error(f"Error saving cache: {e}")
            
    def _check_rate_limit(self) -> bool:
        """
        Verifica si se ha alcanzado el límite diario de solicitudes
        
        Returns:
            bool: True si se puede hacer otra solicitud, False si se ha alcanzado el límite
        """
        # Verificar si el contador es de hoy
        today = datetime.now().strftime("%Y-%m-%d")
        if self.request_count.get("date") != today:
            # Reiniciar contador
            self.request_count = {"date": today, "count": 0}
            
        # Verificar límite (100 solicitudes por día)
        if self.request_count["count"] >= 100:
            self.logger.warning("Daily API request limit reached (100 requests)")
            return False
            
        return True
        
    def _make_api_request(self, endpoint: str, params: Dict = None) -> Dict:
        """
        Realiza una solicitud a la API, respetando los límites y usando caché
        
        Args:
            endpoint: Endpoint de la API (e.g., "teams")
            params: Parámetros de la solicitud
            
        Returns:
            Dict: Respuesta de la API
        """
        if not self.api_key:
            return {"error": "API key not configured"}
            
        # Crear clave de caché
        cache_key = f"{endpoint}_{json.dumps(params, sort_keys=True)}"
        cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
        
        # Verificar caché
        if cache_hash in self.cache:
            cache_entry = self.cache[cache_hash]
            # Caché válida por 24 horas para datos que no cambian rápidamente
            if datetime.now() - cache_entry["timestamp"] < timedelta(hours=24):
                self.logger.debug(f"Cache hit for {endpoint}")
                return cache_entry["data"]
                
        # Verificar límite de solicitudes
        if not self._check_rate_limit():
            return {"error": "API request limit reached"}
            
        # Preparar solicitud
        url = f"https://v3.football.api-sports.io/{endpoint}"
        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "v3.football.api-sports.io"
        }
        
        try:
            # Realizar solicitud
            response = requests.get(url, headers=headers, params=params)
            
            # Incrementar contador
            self.request_count["count"] += 1
            self._save_request_count()
            
            # Verificar respuesta
            if response.status_code == 200:
                data = response.json()
                
                # Guardar en caché
                self.cache[cache_hash] = {
                    "timestamp": datetime.now(),
                    "data": data
                }
                self._save_cache()
                
                return data
            else:
                self.logger.error(f"API error: {response.status_code} - {response.text}")
                return {"error": f"API error: {response.status_code}"}
                
        except Exception as e:
            self.logger.error(f"Request error: {str(e)}")
            return {"error": f"Request error: {str(e)}"}
            
    def get_team_info(self, team_name: str) -> Dict:
        """
        Obtiene información sobre un equipo
        
        Args:
            team_name: Nombre del equipo
            
        Returns:
            Dict: Información del equipo
        """
        # Buscar equipo por nombre
        params = {"name": team_name}
        response = self._make_api_request("teams", params)
        
        if "error" in response:
            return response
            
        # Procesar respuesta
        if response.get("results", 0) > 0:
            team = response["response"][0]
            return {
                "id": team["team"]["id"],
                "name": team["team"]["name"],
                "country": team["team"]["country"],
                "founded": team["team"]["founded"],
                "logo": team["team"]["logo"],
                "league": team["league"]["name"] if "league" in team else None,
            }
        else:
            return {"error": f"Team not found: {team_name}"}
            
    def get_h2h(self, team1: str, team2: str) -> Dict:
        """
        Obtiene estadísticas de enfrentamientos directos entre dos equipos
        
        Args:
            team1: Nombre del primer equipo
            team2: Nombre del segundo equipo
            
        Returns:
            Dict: Estadísticas de enfrentamientos directos
        """
        # Obtener IDs de equipos
        team1_info = self.get_team_info(team1)
        if "error" in team1_info:
            return team1_info
            
        team2_info = self.get_team_info(team2)
        if "error" in team2_info:
            return team2_info
            
        # Obtener enfrentamientos directos
        params = {
            "h2h": f"{team1_info['id']}-{team2_info['id']}",
            "last": 10  # Últimos 10 enfrentamientos
        }
        response = self._make_api_request("fixtures/headtohead", params)
        
        if "error" in response:
            return response
            
        # Procesar respuesta
        fixtures = response.get("response", [])
        
        if not fixtures:
            return {
                "teams": {
                    "team1": team1,
                    "team2": team2
                },
                "matches": 0,
                "team1_wins": 0,
                "team2_wins": 0,
                "draws": 0,
                "error": "No head-to-head matches found"
            }
            
        # Analizar resultados
        team1_wins = 0
        team2_wins = 0
        draws = 0
        
        for fixture in fixtures:
            home_team = fixture["teams"]["home"]["name"]
            away_team = fixture["teams"]["away"]["name"]
            home_goals = fixture["goals"]["home"]
            away_goals = fixture["goals"]["away"]
            
            if home_goals is None or away_goals is None:
                continue  # Partido no finalizado
                
            if home_team == team1_info["name"]:
                if home_goals > away_goals:
                    team1_wins += 1
                elif home_goals < away_goals:
                    team2_wins += 1
                else:
                    draws += 1
            else:  # home_team == team2_info["name"]
                if home_goals > away_goals:
                    team2_wins += 1
                elif home_goals < away_goals:
                    team1_wins += 1
                else:
                    draws += 1
                    
        # Crear resumen
        return {
            "teams": {
                "team1": team1,
                "team2": team2
            },
            "matches": len(fixtures),
            "team1_wins": team1_wins,
            "team2_wins": team2_wins,
            "draws": draws,
            "team1_win_rate": team1_wins / len(fixtures) if len(fixtures) > 0 else 0,
            "team2_win_rate": team2_wins / len(fixtures) if len(fixtures) > 0 else 0,
            "draw_rate": draws / len(fixtures) if len(fixtures) > 0 else 0,
            "last_matches": [
                {
                    "date": fixture["fixture"]["date"],
                    "home": fixture["teams"]["home"]["name"],
                    "away": fixture["teams"]["away"]["name"],
                    "score": f"{fixture['goals']['home']} - {fixture['goals']['away']}",
                    "winner": fixture["teams"]["home"]["name"] if fixture["goals"]["home"] > fixture["goals"]["away"] else
                             fixture["teams"]["away"]["name"] if fixture["goals"]["away"] > fixture["goals"]["home"] else "Draw"
                }
                for fixture in fixtures[:5]  # Últimos 5 partidos
            ]
        }
        
    def get_team_form(self, team_name: str, last_matches: int = 10) -> Dict:
        """
        Obtiene la forma reciente de un equipo
        
        Args:
            team_name: Nombre del equipo
            last_matches: Número de partidos a considerar
            
        Returns:
            Dict: Forma reciente del equipo
        """
        # Obtener ID del equipo
        team_info = self.get_team_info(team_name)
        if "error" in team_info:
            return team_info
            
        # Obtener últimos partidos
        params = {
            "team": team_info["id"],
            "last": last_matches
        }
        response = self._make_api_request("fixtures", params)
        
        if "error" in response:
            return response
            
        # Procesar respuesta
        fixtures = response.get("response", [])
        
        if not fixtures:
            return {
                "team": team_name,
                "matches": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "error": "No recent matches found"
            }
            
        # Analizar resultados
        wins = 0
        draws = 0
        losses = 0
        goals_scored = 0
        goals_conceded = 0
        
        for fixture in fixtures:
            home_team_id = fixture["teams"]["home"]["id"]
            home_goals = fixture["goals"]["home"]
            away_goals = fixture["goals"]["away"]
            
            if home_goals is None or away_goals is None:
                continue  # Partido no finalizado
                
            if home_team_id == team_info["id"]:
                goals_scored += home_goals
                goals_conceded += away_goals
                
                if home_goals > away_goals:
                    wins += 1
                elif home_goals < away_goals:
                    losses += 1
                else:
                    draws += 1
            else:
                goals_scored += away_goals
                goals_conceded += home_goals
                
                if away_goals > home_goals:
                    wins += 1
                elif away_goals < home_goals:
                    losses += 1
                else:
                    draws += 1
                    
        # Calcular forma
        form_value = 0
        if wins + draws + losses > 0:
            form_value = (wins * 3 + draws) / ((wins + draws + losses) * 3)
            
        # Crear resumen
        return {
            "team": team_name,
            "matches": wins + draws + losses,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "win_rate": wins / (wins + draws + losses) if (wins + draws + losses) > 0 else 0,
            "goals_scored": goals_scored,
            "goals_conceded": goals_conceded,
            "goals_per_match": goals_scored / (wins + draws + losses) if (wins + draws + losses) > 0 else 0,
            "form_value": form_value,  # 0-1, donde 1 es perfecto
            "recent_results": [
                {
                    "date": fixture["fixture"]["date"],
                    "home": fixture["teams"]["home"]["name"],
                    "away": fixture["teams"]["away"]["name"],
                    "score": f"{fixture['goals']['home']} - {fixture['goals']['away']}",
                    "result": "W" if (fixture["teams"]["home"]["id"] == team_info["id"] and fixture["goals"]["home"] > fixture["goals"]["away"]) or 
                                   (fixture["teams"]["away"]["id"] == team_info["id"] and fixture["goals"]["away"] > fixture["goals"]["home"]) else
                              "L" if (fixture["teams"]["home"]["id"] == team_info["id"] and fixture["goals"]["home"] < fixture["goals"]["away"]) or 
                                   (fixture["teams"]["away"]["id"] == team_info["id"] and fixture["goals"]["away"] < fixture["goals"]["home"]) else
                              "D"
                }
                for fixture in fixtures if fixture["goals"]["home"] is not None and fixture["goals"]["away"] is not None
            ][:5]  # Últimos 5 partidos finalizados
        }
        
    def predict_match(self, team1: str, team2: str) -> Dict:
        """
        Predice el resultado de un partido entre dos equipos
        
        Args:
            team1: Nombre del primer equipo
            team2: Nombre del segundo equipo
            
        Returns:
            Dict: Predicción del partido
        """
        # Obtener estadísticas de enfrentamientos directos
        h2h = self.get_h2h(team1, team2)
        if "error" in h2h and not h2h.get("matches", 0):
            h2h = {
                "teams": {"team1": team1, "team2": team2},
                "team1_win_rate": 0,
                "team2_win_rate": 0,
                "draw_rate": 0
            }
            
        # Obtener forma reciente de equipos
        team1_form = self.get_team_form(team1)
        if "error" in team1_form and not team1_form.get("matches", 0):
            team1_form = {"form_value": 0.5, "win_rate": 0.5, "goals_per_match": 1.5}
            
        team2_form = self.get_team_form(team2)
        if "error" in team2_form and not team2_form.get("matches", 0):
            team2_form = {"form_value": 0.5, "win_rate": 0.5, "goals_per_match": 1.5}
            
        # Calcular predicción
        # Pesos para diferentes factores
        h2h_weight = 0.3
        form_weight = 0.7
        
        # Calcular probabilidades base
        team1_win_prob = 0
        team2_win_prob = 0
        draw_prob = 0
        
        # Considerar H2H si hay datos
        if h2h.get("matches", 0) > 0:
            team1_win_prob += h2h_weight * h2h["team1_win_rate"]
            team2_win_prob += h2h_weight * h2h["team2_win_rate"]
            draw_prob += h2h_weight * h2h["draw_rate"]
        else:
            # Sin H2H, distribuir uniformemente
            team1_win_prob += h2h_weight * 0.4
            team2_win_prob += h2h_weight * 0.4
            draw_prob += h2h_weight * 0.2
            
        # Considerar forma reciente
        team1_form_score = team1_form.get("form_value", 0.5)
        team2_form_score = team2_form.get("form_value", 0.5)
        
        # Calcular margen entre equipos
        form_margin = team1_form_score - team2_form_score
        
        # Convertir margen a probabilidades
        if form_margin > 0:
            team1_form_prob = 0.5 + (form_margin * 0.5)  # Max 0.75 cuando form_margin=0.5
            team2_form_prob = 1 - team1_form_prob - 0.2  # Asignar 0.2 para empate
            draw_form_prob = 0.2
        else:
            team2_form_prob = 0.5 + (abs(form_margin) * 0.5)
            team1_form_prob = 1 - team2_form_prob - 0.2
            draw_form_prob = 0.2
            
        # Asegurar mínimo 0.1 para cada resultado
        team1_form_prob = max(0.1, min(0.8, team1_form_prob))
        team2_form_prob = max(0.1, min(0.8, team2_form_prob))
        draw_form_prob = max(0.1, 1 - team1_form_prob - team2_form_prob)
        
        # Sumar con pesos
        team1_win_prob += form_weight * team1_form_prob
        team2_win_prob += form_weight * team2_form_prob
        draw_prob += form_weight * draw_form_prob
        
        # Normalizar probabilidades
        total_prob = team1_win_prob + team2_win_prob + draw_prob
        team1_win_prob /= total_prob
        team2_win_prob /= total_prob
        draw_prob /= total_prob
        
        # Calcular probabilidad de over/under y ambos equipos marcan
        expected_goals_team1 = team1_form.get("goals_per_match", 1.5)
        expected_goals_team2 = team2_form.get("goals_per_match", 1.5)
        
        # Over 2.5 goles
        expected_total_goals = expected_goals_team1 + expected_goals_team2
        over_2_5_prob = 0.5 + (expected_total_goals - 2.5) * 0.1
        over_2_5_prob = max(0.1, min(0.9, over_2_5_prob))
        
        # Ambos equipos marcan
        btts_prob = 0.5 + ((expected_goals_team1 * expected_goals_team2) / 4)
        btts_prob = max(0.1, min(0.9, btts_prob))
        
        # Preparar explicación
        explanation = []
        
        if h2h.get("matches", 0) > 0:
            explanation.append(f"En los últimos {h2h['matches']} enfrentamientos directos, "
                               f"{team1} ganó {h2h['team1_wins']} ({h2h['team1_win_rate']:.0%}), "
                               f"{team2} ganó {h2h['team2_wins']} ({h2h['team2_win_rate']:.0%}), "
                               f"y {h2h['draws']} terminaron en empate ({h2h['draw_rate']:.0%}).")
                               
        explanation.append(f"{team1} ha mostrado una forma reciente de {team1_form.get('form_value', 0.5):.0%} "
                          f"con {team1_form.get('wins', 0)} victorias, {team1_form.get('draws', 0)} empates, "
                          f"y {team1_form.get('losses', 0)} derrotas en sus últimos {team1_form.get('matches', 0)} partidos.")
                          
        explanation.append(f"{team2} ha mostrado una forma reciente de {team2_form.get('form_value', 0.5):.0%} "
                          f"con {team2_form.get('wins', 0)} victorias, {team2_form.get('draws', 0)} empates, "
                          f"y {team2_form.get('losses', 0)} derrotas en sus últimos {team2_form.get('matches', 0)} partidos.")
                          
        # Crear resultado
        return {
            "teams": {
                "team1": team1,
                "team2": team2
            },
            "prediction": {
                "team1_win": team1_win_prob,
                "draw": draw_prob,
                "team2_win": team2_win_prob,
            },
            "additional_predictions": {
                "over_2_5_goals": over_2_5_prob,
                "both_teams_to_score": btts_prob,
                "expected_goals_team1": expected_goals_team1,
                "expected_goals_team2": expected_goals_team2
            },
            "explanation": " ".join(explanation),
            "confidence": min(0.8, (h2h.get("matches", 0) / 10) * 0.4 + (team1_form.get("matches", 0) / 10) * 0.3 + (team2_form.get("matches", 0) / 10) * 0.3)
        }
        
    def extract_teams_from_question(self, question: str) -> Dict:
        """
        Extrae nombres de equipos de una pregunta de mercado
        
        Args:
            question: Pregunta del mercado
            
        Returns:
            Dict: Información de equipos encontrados
        """
        # Patrones comunes para preguntas de fútbol
        patterns = [
            r"Will (.*?) (beat|defeat|win against) (.*?)(?: in| at| on|\?|$)",
            r"Will (.*?) vs\.? (.*?) (end in a draw|result in a draw|be a draw)",
            r"(.*?) vs\.? (.*?)( -|:| result| winner| outcome)",
            r"Who will win( between| in)? (.*?) (?:vs\.?|and|or|versus) (.*?)(\?|$|:| in)",
            r"Will (.*?) qualify",
            r"Will (.*?) reach",
            r"Will (.*?) advance",
            r"Will (.*?) win"
        ]
        
        for pattern in patterns:
            matches = re.search(pattern, question, re.IGNORECASE)
            if matches:
                groups = matches.groups()
                
                # Diferentes patrones capturan equipos en diferentes grupos
                if "vs" in pattern or "between" in pattern:
                    if len(groups) >= 3:
                        return {"team1": groups[1].strip(), "team2": groups[2].strip()}
                    else:
                        return {"team1": groups[0].strip(), "team2": groups[1].strip()}
                elif "beat" in pattern or "defeat" in pattern or "win against" in pattern:
                    return {"team1": groups[0].strip(), "team2": groups[2].strip()}
                elif "qualify" in pattern or "reach" in pattern or "advance" in pattern or "win" in pattern:
                    # Solo un equipo en la pregunta
                    return {"team1": groups[0].strip(), "single_team": True}
                    
        # No se encontraron equipos con los patrones
        return {"error": "Could not extract teams from question"}
        
    def extract_market_type(self, question: str) -> str:
        """
        Detecta el tipo de mercado basado en la pregunta
        
        Args:
            question: Pregunta del mercado
            
        Returns:
            str: Tipo de mercado
        """
        question_lower = question.lower()
        
        # Match result
        if ("win" in question_lower or "beat" in question_lower or "defeat" in question_lower) and "vs" in question_lower:
            return "match_winner"
            
        # Draw
        if "draw" in question_lower:
            return "draw"
            
        # Over/Under
        if "over" in question_lower and "goals" in question_lower:
            return "over_under_goals"
            
        # Both teams to score
        if "both" in question_lower and "score" in question_lower:
            return "btts"
            
        # Competition winner
        if "win the" in question_lower:
            competitions = ["champions league", "premier league", "la liga", "serie a", 
                           "bundesliga", "world cup", "euro", "copa america", "uefa"]
            for comp in competitions:
                if comp in question_lower:
                    return "competition_winner"
                    
        # Qualification
        if "qualify" in question_lower or "reach" in question_lower or "advance" in question_lower:
            return "qualification"
            
        # Default
        return "match_winner"
        
    def analyze_football_market(self, question: str) -> Dict:
        """
        Analiza un mercado relacionado con fútbol
        
        Args:
            question: Pregunta del mercado
            
        Returns:
            Dict: Análisis del mercado incluyendo probabilidades
        """
        # Identificar equipos en la pregunta
        teams_info = self.extract_teams_from_question(question)
        if "error" in teams_info:
            return {"error": f"Could not identify teams: {teams_info['error']}", 
                    "probability_yes": 0.5, "probability_no": 0.5}
                    
        # Identificar tipo de mercado
        market_type = self.extract_market_type(question)
        
        # Single team markets (qualification, competition winner)
        if teams_info.get("single_team"):
            team = teams_info["team1"]
            
            if market_type == "competition_winner":
                # Implementación básica - se podría mejorar con datos reales
                return {
                    "teams": {"team1": team},
                    "market_type": "competition_winner",
                    "probability_yes": 0.2,  # Probabilidad baja por defecto
                    "probability_no": 0.8,
                    "explanation": f"Las probabilidades de que {team} gane una competición importante son generalmente bajas debido a la alta competencia.",
                    "confidence": 0.6
                }
                
            elif market_type == "qualification":
                # Implementación básica - se podría mejorar con datos reales
                return {
                    "teams": {"team1": team},
                    "market_type": "qualification",
                    "probability_yes": 0.4,  # Probabilidad moderada por defecto
                    "probability_no": 0.6,
                    "explanation": f"Las probabilidades de que {team} se clasifique son moderadas, basadas en estadísticas generales.",
                    "confidence": 0.5
                }
                
            else:
                return {
                    "teams": {"team1": team},
                    "market_type": market_type,
                    "probability_yes": 0.5,
                    "probability_no": 0.5,
                    "explanation": f"No se dispone de suficiente información para analizar este tipo de mercado para {team}.",
                    "confidence": 0.3
                }
                
        # Match markets (dos equipos)
        team1 = teams_info["team1"]
        team2 = teams_info["team2"]
        
        # Obtener predicción
        prediction = self.predict_match(team1, team2)
        
        # Convertir predicción según tipo de mercado
        if market_type == "match_winner":
            # Pregunta: "Will [team1] win against [team2]?"
            prob_yes = prediction["prediction"]["team1_win"]
            prob_no = prediction["prediction"]["draw"] + prediction["prediction"]["team2_win"]
            
            explanation = f"Para la victoria de {team1} contra {team2}, "
            explanation += f"la probabilidad es {prob_yes:.0%}. {prediction['explanation']}"
            
            return {
                "teams": {"team1": team1, "team2": team2},
                "market_type": "match_winner",
                "probability_yes": prob_yes,
                "probability_no": prob_no,
                "explanation": explanation,
                "prediction_details": prediction["prediction"],
                "confidence": prediction.get("confidence", 0.6)
            }
            
        elif market_type == "draw":
            # Pregunta: "Will [team1] vs [team2] end in a draw?"
            prob_yes = prediction["prediction"]["draw"]
            prob_no = prediction["prediction"]["team1_win"] + prediction["prediction"]["team2_win"]
            
            explanation = f"Para un empate entre {team1} y {team2}, "
            explanation += f"la probabilidad es {prob_yes:.0%}. {prediction['explanation']}"
            
            return {
                "teams": {"team1": team1, "team2": team2},
                "market_type": "draw",
                "probability_yes": prob_yes,
                "probability_no": prob_no,
                "explanation": explanation,
                "prediction_details": prediction["prediction"],
                "confidence": prediction.get("confidence", 0.6)
            }
            
        elif market_type == "over_under_goals":
            # Pregunta: "Will [team1] vs [team2] have over 2.5 goals?"
            prob_yes = prediction["additional_predictions"]["over_2_5_goals"]
            prob_no = 1 - prob_yes
            
            explanation = f"Para más de 2.5 goles en el partido entre {team1} y {team2}, "
            explanation += f"la probabilidad es {prob_yes:.0%}. Se espera un promedio de "
            explanation += f"{prediction['additional_predictions']['expected_goals_team1']:.1f} goles de {team1} "
            explanation += f"y {prediction['additional_predictions']['expected_goals_team2']:.1f} goles de {team2}."
            
            return {
                "teams": {"team1": team1, "team2": team2},
                "market_type": "over_under_goals",
                "probability_yes": prob_yes,
                "probability_no": prob_no,
                "explanation": explanation,
                "prediction_details": prediction["additional_predictions"],
                "confidence": prediction.get("confidence", 0.6) * 0.8  # Menor confianza para este tipo
            }
            
        elif market_type == "btts":
            # Pregunta: "Will both [team1] and [team2] score?"
            prob_yes = prediction["additional_predictions"]["both_teams_to_score"]
            prob_no = 1 - prob_yes
            
            explanation = f"Para que ambos equipos marquen en el partido entre {team1} y {team2}, "
            explanation += f"la probabilidad es {prob_yes:.0%}. Se espera un promedio de "
            explanation += f"{prediction['additional_predictions']['expected_goals_team1']:.1f} goles de {team1} "
            explanation += f"y {prediction['additional_predictions']['expected_goals_team2']:.1f} goles de {team2}."
            
            return {
                "teams": {"team1": team1, "team2": team2},
                "market_type": "btts",
                "probability_yes": prob_yes,
                "probability_no": prob_no,
                "explanation": explanation,
                "prediction_details": prediction["additional_predictions"],
                "confidence": prediction.get("confidence", 0.6) * 0.8  # Menor confianza para este tipo
            }
            
        else:
            # Tipo de mercado no reconocido, usar predicción básica
            return {
                "teams": {"team1": team1, "team2": team2},
                "market_type": "unknown",
                "probability_yes": 0.5,
                "probability_no": 0.5,
                "explanation": f"No se dispone de suficiente información para analizar este tipo específico de mercado entre {team1} y {team2}.",
                "prediction_details": prediction["prediction"],
                "confidence": 0.4
            } 