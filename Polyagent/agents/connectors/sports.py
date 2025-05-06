#!/usr/bin/env python3
"""
Módulo conector para estadísticas deportivas

Este módulo se conecta a la API de api-sports.io para obtener estadísticas
de fútbol, incluida información de equipos, ligas, partidos, y predicciones.
"""

import os
import re
import json
import time
import logging
import requests
import datetime
from typing import Dict, List, Any, Union, Optional, Tuple
from pathlib import Path
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

# Configurar logging
logger = logging.getLogger(__name__)

# Asegurar que NLTK tiene los recursos necesarios
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)

class FootballStats:
    """
    Conector para acceder a estadísticas de fútbol a través de la API de api-sports.io.
    
    Proporciona métodos para obtener información sobre equipos, ligas, partidos,
    y estadísticas, así como para analizar mercados relacionados con fútbol.
    """
    
    BASE_URL = "https://v3.football.api-sports.io"
    CACHE_DIR = os.path.join(os.path.expanduser("~"), ".football_stats_cache")
    CACHE_FILE = os.path.join(CACHE_DIR, "cache.json")
    CACHE_EXPIRY = 86400  # 24 horas en segundos
    
    def __init__(self, api_key=None):
        """
        Inicializa el conector de estadísticas de fútbol.
        
        Args:
            api_key: Clave API para api-sports.io (opcional, si no se proporciona
                    se busca en las variables de entorno FOOTBALL_API_KEY)
        """
        self.api_key = api_key or os.environ.get("FOOTBALL_API_KEY")
        if not self.api_key:
            logger.warning("No se proporcionó clave API. Se usará una clave por defecto con límites restrictivos.")
            self.api_key = "68b6cc667fb6febb5aae17539e7caf1e"  # Clave demo con límites
            
        self.headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "v3.football.api-sports.io"
        }
        
        # Inicializar cache
        self.cache = self._load_cache()
        self.request_count = 0
        
        # Patrones regex para extracción de equipos y ligas
        self.team_pattern = re.compile(r'(Barcelona|Real Madrid|Manchester (United|City)|Liverpool|Chelsea|Arsenal|Juventus|Inter|AC Milan|Bayern|PSG|Atletico|Dortmund|Ajax|Porto|Celtic|Rangers|Sevilla|Valencia|Villarreal|Napoli|Roma|Lazio|Benfica|Lyon|Monaco)', re.IGNORECASE)
        self.league_pattern = re.compile(r'(La Liga|Premier League|Serie A|Bundesliga|Ligue 1|Champions League|Europa League|World Cup|Copa America|Euro|Carabao Cup|FA Cup|Copa del Rey|DFB Pokal|Coppa Italia)', re.IGNORECASE)
        
        logger.debug(f"Conector FootballStats inicializado con clave API: {self.api_key[:4]}...{self.api_key[-4:]}")
    
    def _load_cache(self) -> Dict:
        """Carga el cache desde el archivo"""
        try:
            # Crear directorio de cache si no existe
            if not os.path.exists(self.CACHE_DIR):
                os.makedirs(self.CACHE_DIR)
                
            if os.path.exists(self.CACHE_FILE):
                with open(self.CACHE_FILE, 'r') as f:
                    cache = json.load(f)
                logger.debug(f"Cache cargado, {len(cache)} entradas encontradas")
                return cache
        except Exception as e:
            logger.warning(f"Error al cargar cache: {str(e)}")
        
        return {}
    
    def _save_cache(self):
        """Guarda el cache en el archivo"""
        try:
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self.cache, f)
            logger.debug(f"Cache guardado, {len(self.cache)} entradas")
        except Exception as e:
            logger.warning(f"Error al guardar cache: {str(e)}")
    
    def _get_from_cache(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """
        Obtiene resultados del cache si están disponibles y no han expirado.
        
        Args:
            endpoint: Endpoint de la API
            params: Parámetros de la solicitud
            
        Returns:
            Datos cacheados o None si no están disponibles
        """
        cache_key = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            timestamp = entry.get("timestamp", 0)
            
            # Verificar si el cache ha expirado
            if time.time() - timestamp < self.CACHE_EXPIRY:
                logger.debug(f"Usando datos cacheados para {endpoint}")
                return entry.get("data")
        
        return None
    
    def _add_to_cache(self, endpoint: str, params: Dict, data: Dict):
        """
        Añade resultados al cache.
        
        Args:
            endpoint: Endpoint de la API
            params: Parámetros de la solicitud
            data: Datos a cachear
        """
        cache_key = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        
        self.cache[cache_key] = {
            "timestamp": time.time(),
            "data": data
        }
        
        # Guardar cache después de cada nueva adición
        self._save_cache()
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """
        Realiza una solicitud a la API.
        
        Args:
            endpoint: Endpoint de la API
            params: Parámetros de la solicitud (opcional)
            
        Returns:
            Respuesta de la API como diccionario
        """
        params = params or {}
        
        # Verificar si tenemos datos en cache
        cached_data = self._get_from_cache(endpoint, params)
        if cached_data:
            return cached_data
        
        # Realizar solicitud a la API
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            self.request_count += 1
            logger.debug(f"Realizando solicitud {self.request_count} a {endpoint} con params={params}")
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Verificar cuotas de API
            if "errors" in data and data["errors"]:
                logger.error(f"Error de API: {data['errors']}")
                return {"error": str(data["errors"])}
            
            # Cachear resultados
            if data.get("response") is not None:
                self._add_to_cache(endpoint, params, data)
            
            return data
        except requests.RequestException as e:
            logger.error(f"Error al realizar solicitud a {endpoint}: {str(e)}")
            return {"error": str(e)}
    
    def _get_current_season(self) -> int:
        """
        Determina la temporada actual basada en la fecha.
        
        Returns:
            Año de la temporada actual
        """
        now = datetime.datetime.now()
        return now.year if now.month > 6 else now.year - 1
    
    def _extract_team_and_league(self, query: str) -> Tuple[List[str], List[str]]:
        """
        Extrae nombres de equipos y ligas de una consulta utilizando expresiones regulares
        
        Args:
            query: Consulta de búsqueda
            
        Returns:
            Tupla de (equipos encontrados, ligas encontradas)
        """
        query = query.lower()
        teams_found = []
        leagues_found = []
        
        # Buscar equipos
        for pattern in self.team_pattern:
            for match in re.finditer(pattern, query):
                if match.group(1).strip():
                    teams_found.append(match.group(1).strip())
                    
        # Buscar ligas
        for pattern in self.league_pattern:
            for match in re.finditer(pattern, query):
                if match.group(1).strip():
                    leagues_found.append(match.group(1).strip())
                    
        # Eliminar duplicados y limpiar
        teams_found = list(set(teams_found))
        leagues_found = list(set(leagues_found))
        
        return teams_found, leagues_found
    
    def _extract_player(self, query: str) -> Optional[str]:
        """
        Extrae nombre de jugador de una consulta utilizando expresiones regulares
        
        Args:
            query: Consulta de búsqueda
            
        Returns:
            Nombre del jugador o None si no se encuentra
        """
        query = query.lower()
        
        # Patrones específicos para nombres de jugadores
        player_patterns = [
            r"(?:el jugador|footballer|soccer player|player|futbolista)\s+([A-Za-zÀ-ÖØ-öø-ÿ\s]+?)(?:\s+(?:va a|will|score|mark|get|receive|obtener|recibir|conseguir|marcar|anotar))",
            r"([A-Za-zÀ-ÖØ-öø-ÿ\s]+?)(?:\s+(?:va a|will|score|mark|get|receive|obtener|recibir|conseguir|marcar|anotar))",
            r"(?:tarjeta|card|goal|gol)(?:\s+(?:para|for|por|to|de|del))\s+([A-Za-zÀ-ÖØ-öø-ÿ\s]+?)(?:\s+(?:en|in|during|antes|before|after|después))?",
            r"([A-Za-zÀ-ÖØ-öø-ÿ\s]{2,30}?)(?:\s+(?:recibirá|recibe|will receive|receives|get|gets|conseguirá|conseguir|score|scores|marca|marcará))",
        ]
        
        # Primero intentamos con patrones específicos
        for pattern in player_patterns:
            match = re.search(pattern, query)
            if match and match.group(1).strip():
                player_name = match.group(1).strip()
                # Verificar que el nombre no sea una palabra común o tenga al menos dos partes
                name_parts = player_name.split()
                if len(name_parts) >= 2 and not any(part in ["el", "la", "los", "las", "a", "an", "the"] for part in name_parts):
                    return player_name
        
        # Si no encontramos con patrones específicos, buscamos sustantivos propios
        words = query.split()
        potential_names = []
        i = 0
        while i < len(words):
            # Buscar palabras que comiencen con mayúscula
            if words[i] and words[i][0].isupper():
                name_parts = [words[i]]
                j = i + 1
                # Añadir las siguientes palabras que comiencen con mayúscula
                while j < len(words) and words[j] and words[j][0].isupper():
                    name_parts.append(words[j])
                    j += 1
                
                if len(name_parts) >= 2:  # Al menos nombre y apellido
                    potential_names.append(" ".join(name_parts))
                i = j
            else:
                i += 1
        
        if potential_names:
            # Ordenar por longitud para priorizar nombres más completos
            return sorted(potential_names, key=len, reverse=True)[0]
        
        return None
    
    def _extract_player_stats(self, player_name: str) -> Dict:
        """
        Obtiene estadísticas de un jugador
        
        Args:
            player_name: Nombre del jugador
            
        Returns:
            Diccionario con estadísticas del jugador
        """
        player_info = {}
        
        try:
            # Buscar información del jugador
            logger.info(f"Buscando información del jugador: {player_name}")
            
            # Intentar primero por nombre exacto
            player_search_url = f"{self.BASE_URL}/players"
            params = {
                "search": player_name
            }
            
            player_data = self._make_request(player_search_url, params)
            
            if not player_data or "response" not in player_data or not player_data["response"]:
                logger.warning(f"No se encontró información del jugador {player_name}")
                return {"error": f"No se encontró información del jugador", "player_name": player_name}
            
            # Tomar el primer resultado (el más relevante)
            player = player_data["response"][0]
            player_id = player["player"]["id"]
            
            player_info = {
                "market_type": "player_performance",
                "player": {
                    "id": player_id,
                    "name": player["player"]["name"],
                    "firstname": player["player"]["firstname"],
                    "lastname": player["player"]["lastname"],
                    "age": player["player"]["age"],
                    "nationality": player["player"]["nationality"],
                    "height": player["player"].get("height", "No disponible"),
                    "weight": player["player"].get("weight", "No disponible"),
                    "position": player["statistics"][0]["games"]["position"] if player["statistics"] and "games" in player["statistics"][0] else "No disponible",
                    "team": player["statistics"][0]["team"]["name"] if player["statistics"] and "team" in player["statistics"][0] else "No disponible",
                    "statistics": {}
                }
            }
            
            # Si hay estadísticas disponibles, extraer la más reciente
            if player["statistics"] and len(player["statistics"]) > 0:
                stats = player["statistics"][0]
                
                # Estadísticas generales
                player_info["player"]["statistics"] = {
                    "season": stats.get("league", {}).get("season", ""),
                    "league": stats.get("league", {}).get("name", ""),
                    "games": {
                        "appearances": stats.get("games", {}).get("appearences", 0),  # Nota: hay un error de ortografía en la API
                        "minutes": stats.get("games", {}).get("minutes", 0),
                        "position": stats.get("games", {}).get("position", ""),
                        "rating": stats.get("games", {}).get("rating", "")
                    },
                    "goals": {
                        "total": stats.get("goals", {}).get("total", 0),
                        "assists": stats.get("goals", {}).get("assists", 0)
                    },
                    "cards": {
                        "yellow": stats.get("cards", {}).get("yellow", 0),
                        "red": stats.get("cards", {}).get("red", 0)
                    }
                }
                
                # Estadísticas específicas según la posición
                if "shots" in stats:
                    player_info["player"]["statistics"]["shots"] = {
                        "total": stats["shots"].get("total", 0),
                        "on_target": stats["shots"].get("on", 0)
                    }
                
                if "dribbles" in stats:
                    player_info["player"]["statistics"]["dribbles"] = {
                        "attempts": stats["dribbles"].get("attempts", 0),
                        "success": stats["dribbles"].get("success", 0)
                    }
                
                if "passes" in stats:
                    player_info["player"]["statistics"]["passes"] = {
                        "total": stats["passes"].get("total", 0),
                        "accuracy": stats["passes"].get("accuracy", 0)
                    }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas del jugador {player_name}: {e}")
            return {"error": f"Error obteniendo estadísticas del jugador: {str(e)}", "player_name": player_name}
        
        return player_info
    
    def _extract_keywords(self, query: str, stop_words=None) -> List[str]:
        """
        Extrae palabras clave de una consulta, eliminando palabras comunes.
        
        Args:
            query: Consulta de texto
            stop_words: Lista de palabras comunes a ignorar (opcional)
            
        Returns:
            Lista de palabras clave
        """
        if stop_words is None:
            try:
                stop_words = set(stopwords.words('english'))
                stop_words.update(["will", "win", "lose", "draw", "match", "game", "team", "play"])
            except:
                stop_words = set(["the", "a", "an", "in", "on", "at", "to", "for", "by", "will", "win", "lose", "draw"])
        
        tokens = word_tokenize(query.lower())
        keywords = [word for word in tokens if word.isalpha() and word not in stop_words]
        
        return keywords
    
    def get_team_info(self, team_name: str) -> Dict:
        """
        Obtiene información sobre un equipo por nombre.
        
        Args:
            team_name: Nombre del equipo
            
        Returns:
            Información del equipo
        """
        params = {"name": team_name}
        return self._make_request("teams", params)
    
    def get_league_info(self, league_name: str) -> Dict:
        """
        Obtiene información sobre una liga por nombre.
        
        Args:
            league_name: Nombre de la liga
            
        Returns:
            Información de la liga
        """
        params = {"name": league_name}
        return self._make_request("leagues", params)
    
    def get_team_statistics(self, team_id: int, league_id: int, season: int) -> Dict:
        """
        Obtiene estadísticas de un equipo en una liga específica.
        
        Args:
            team_id: ID del equipo
            league_id: ID de la liga
            season: Temporada (año)
            
        Returns:
            Estadísticas del equipo
        """
        params = {
            "team": team_id,
            "league": league_id,
            "season": season
        }
        return self._make_request("teams/statistics", params)
    
    def get_team_fixtures(self, team_id: int, status: str = "FT", last: int = 10) -> Dict:
        """
        Obtiene los últimos partidos de un equipo.
        
        Args:
            team_id: ID del equipo
            status: Estado de los partidos (FT = terminados)
            last: Número de partidos a obtener
            
        Returns:
            Partidos del equipo
        """
        params = {
            "team": team_id,
            "status": status,
            "last": last
        }
        return self._make_request("fixtures", params)
    
    def get_standings(self, league_id: int, season: int) -> Dict:
        """
        Obtiene la clasificación de una liga.
        
        Args:
            league_id: ID de la liga
            season: Temporada (año)
            
        Returns:
            Clasificación de la liga
        """
        params = {
            "league": league_id,
            "season": season
        }
        return self._make_request("standings", params)
    
    def get_h2h(self, team1_id: int, team2_id: int, last: int = 10) -> Dict:
        """
        Obtiene el historial de enfrentamientos directos entre dos equipos.
        
        Args:
            team1_id: ID del primer equipo
            team2_id: ID del segundo equipo
            last: Número de partidos a obtener
            
        Returns:
            Historial de enfrentamientos
        """
        params = {
            "h2h": f"{team1_id}-{team2_id}",
            "last": last
        }
        return self._make_request("fixtures/headtohead", params)
    
    def get_match_prediction(self, team1_name: str, team2_name: str) -> Dict:
        """
        Genera una predicción para un partido entre dos equipos.
        
        Args:
            team1_name: Nombre del primer equipo (local)
            team2_name: Nombre del segundo equipo (visitante)
            
        Returns:
            Predicción del partido con probabilidades
        """
        # Obtener información de los equipos
        team1_info = self.get_team_info(team1_name)
        team2_info = self.get_team_info(team2_name)
        
        if "error" in team1_info or not team1_info.get("response"):
            return {"error": f"No se pudo encontrar el equipo: {team1_name}"}
        
        if "error" in team2_info or not team2_info.get("response"):
            return {"error": f"No se pudo encontrar el equipo: {team2_name}"}
        
        team1_id = team1_info["response"][0]["team"]["id"]
        team1_name = team1_info["response"][0]["team"]["name"]
        
        team2_id = team2_info["response"][0]["team"]["id"]
        team2_name = team2_info["response"][0]["team"]["name"]
        
        # Obtener historial H2H
        h2h_data = self.get_h2h(team1_id, team2_id, last=10)
        
        if "error" in h2h_data:
            return {"error": f"No se pudo obtener historial H2H: {h2h_data['error']}"}
        
        # Obtener fixtures recientes de ambos equipos
        team1_fixtures = self.get_team_fixtures(team1_id, last=5)
        team2_fixtures = self.get_team_fixtures(team2_id, last=5)
        
        # Analizar datos y generar predicción
        try:
            # Analizar historial H2H
            h2h_matches = h2h_data.get("response", [])
            total_matches = len(h2h_matches)
            team1_wins = 0
            team2_wins = 0
            draws = 0
            
            for match in h2h_matches:
                teams = match.get("teams", {})
                goals = match.get("goals", {})
                
                if teams.get("home", {}).get("id") == team1_id:
                    if goals.get("home", 0) > goals.get("away", 0):
                        team1_wins += 1
                    elif goals.get("home", 0) < goals.get("away", 0):
                        team2_wins += 1
                    else:
                        draws += 1
                else:
                    if goals.get("away", 0) > goals.get("home", 0):
                        team1_wins += 1
                    elif goals.get("away", 0) < goals.get("home", 0):
                        team2_wins += 1
                    else:
                        draws += 1
            
            h2h_summary = {
                "total_matches": total_matches,
                "team1_wins": team1_wins,
                "team2_wins": team2_wins,
                "draws": draws
            }
            
            # Calcular probabilidades
            # Base inicial para cada resultado
            team1_prob_base = 0.33
            team2_prob_base = 0.33
            draw_prob_base = 0.34
            
            # Ajustar con historial H2H
            h2h_weight = 0.4
            if total_matches > 0:
                team1_h2h = team1_wins / total_matches
                team2_h2h = team2_wins / total_matches
                draw_h2h = draws / total_matches
                
                team1_prob = team1_prob_base * (1 - h2h_weight) + team1_h2h * h2h_weight
                team2_prob = team2_prob_base * (1 - h2h_weight) + team2_h2h * h2h_weight
                draw_prob = draw_prob_base * (1 - h2h_weight) + draw_h2h * h2h_weight
            else:
                team1_prob = team1_prob_base
                team2_prob = team2_prob_base
                draw_prob = draw_prob_base
            
            # Ajustar con forma reciente
            recent_weight = 0.3
            team1_form_score = self._calculate_form_score(team1_fixtures.get("response", []), team1_id)
            team2_form_score = self._calculate_form_score(team2_fixtures.get("response", []), team2_id)
            
            form_diff = team1_form_score - team2_form_score
            max_diff = 15  # Diferencia máxima esperada
            
            if form_diff > 0:
                # team1 en mejor forma
                adj_factor = min(form_diff, max_diff) / max_diff * recent_weight
                team1_prob += adj_factor
                team2_prob -= adj_factor * 0.7
                draw_prob -= adj_factor * 0.3
            elif form_diff < 0:
                # team2 en mejor forma
                adj_factor = min(abs(form_diff), max_diff) / max_diff * recent_weight
                team2_prob += adj_factor
                team1_prob -= adj_factor * 0.7
                draw_prob -= adj_factor * 0.3
            
            # Normalizar probabilidades
            total_prob = team1_prob + team2_prob + draw_prob
            team1_prob = team1_prob / total_prob
            team2_prob = team2_prob / total_prob
            draw_prob = draw_prob / total_prob
            
            # Nivel de confianza basado en cantidad de datos
            confidence = "Medio"
            if total_matches >= 5:
                confidence = "Alto"
            elif total_matches <= 1:
                confidence = "Bajo"
            
            # Generar respuesta
            prediction = {
                "teams": {
                    "team1": {
                        "id": team1_id,
                        "name": team1_name,
                        "win_probability": team1_prob,
                        "form_score": team1_form_score
                    },
                    "team2": {
                        "id": team2_id,
                        "name": team2_name,
                        "win_probability": team2_prob,
                        "form_score": team2_form_score
                    }
                },
                "draw_probability": draw_prob,
                "confidence": confidence,
                "h2h_summary": h2h_summary
            }
            
            return prediction
            
        except Exception as e:
            logger.error(f"Error al generar predicción: {str(e)}")
            return {"error": f"Error al generar predicción: {str(e)}"}
    
    def _calculate_form_score(self, fixtures: List[Dict], team_id: int) -> float:
        """
        Calcula una puntuación de forma basada en resultados recientes.
        
        Args:
            fixtures: Lista de partidos
            team_id: ID del equipo a evaluar
            
        Returns:
            Puntuación de forma (mayor = mejor)
        """
        if not fixtures:
            return 0
        
        score = 0
        recency_weight = 1.5  # Partidos más recientes tienen más peso
        
        # Ordenar por fecha (más reciente primero)
        fixtures.sort(key=lambda x: x.get("fixture", {}).get("date", ""), reverse=True)
        
        for i, match in enumerate(fixtures):
            teams = match.get("teams", {})
            goals = match.get("goals", {})
            
            # Calcular peso por recencia
            weight = recency_weight ** (len(fixtures) - i - 1)
            
            # Determinar si el equipo es local o visitante
            is_home = teams.get("home", {}).get("id") == team_id
            team_goals = goals.get("home" if is_home else "away", 0)
            opponent_goals = goals.get("away" if is_home else "home", 0)
            
            # Calcular puntos por este partido
            if team_goals > opponent_goals:
                match_score = 3 * weight  # Victoria
            elif team_goals == opponent_goals:
                match_score = 1 * weight  # Empate
            else:
                match_score = 0  # Derrota
            
            # Bonus por goles marcados (máximo 2 puntos extra)
            goal_bonus = min(team_goals, 2) * 0.5 * weight
            
            score += match_score + goal_bonus
        
        return score
    
    def analyze_football_market(self, question: str, description: str = "") -> Dict:
        """
        Analiza un mercado relacionado con fútbol para obtener estadísticas relevantes
        
        Args:
            question: Pregunta del mercado
            description: Descripción adicional del mercado (opcional)
            
        Returns:
            Diccionario con estadísticas relevantes sobre el mercado
        """
        logger.info("Analizando mercado de fútbol...")
        full_text = f"{question} {description}".strip()
        
        # Primero intentar extraer equipos y ligas
        teams_found, leagues_found = self._extract_team_and_league(full_text)
        
        # Luego intentar extraer jugadores
        player_name = self._extract_player(full_text)
        
        # Si encontramos un jugador, obtener sus estadísticas
        if player_name:
            logger.info(f"Jugador encontrado: {player_name}")
            player_stats = self._extract_player_stats(player_name)
            if player_stats and "error" not in player_stats:
                return player_stats
        
        # Si no hay un jugador o no se encontraron estadísticas, continuar con equipos
        if not teams_found:
            logger.warning("No se pudieron extraer equipos de la pregunta")
            return {"error": "No se pudieron extraer equipos de la pregunta"}
        
        logger.info(f"Equipos encontrados: {teams_found}")
        logger.info(f"Ligas encontradas: {leagues_found}")
        
        # Tipo de mercado
        is_win_market = any(word in full_text.lower() for word in ["win", "champion", "title", "cup"])
        is_h2h_market = len(teams_found) >= 2 and any(word in full_text.lower() for word in ["vs", "against", "match", "beat", "defeat"])
        is_relegation_market = "relegat" in full_text.lower()
        
        try:
            # Caso 1: Mercado sobre un equipo ganando una competición
            if is_win_market and len(teams_found) == 1 and len(leagues_found) >= 1:
                team_name = teams_found[0]
                league_name = leagues_found[0]
                
                team_info = self.get_team_info(team_name)
                if "error" in team_info or not team_info.get("response"):
                    return {"error": f"No se pudo encontrar información del equipo: {team_name}"}
                
                league_info = self.get_league_info(league_name)
                if "error" in league_info or not league_info.get("response"):
                    return {"error": f"No se pudo encontrar información de la liga: {league_name}"}
                
                team_id = team_info["response"][0]["team"]["id"]
                team_name = team_info["response"][0]["team"]["name"]
                
                league_id = league_info["response"][0]["league"]["id"]
                league_name = league_info["response"][0]["league"]["name"]
                
                season = self._get_current_season()
                
                # Obtener estadísticas y posición actual
                team_stats = self.get_team_statistics(team_id, league_id, season)
                standings = self.get_standings(league_id, season)
                
                # Procesar estadísticas
                stats_data = {}
                
                if "response" in team_stats and team_stats["response"]:
                    response = team_stats["response"]
                    fixtures = response.get("fixtures", {})
                    
                    # Calcular tasa de victorias
                    played = fixtures.get("played", {}).get("total", 0)
                    wins = fixtures.get("wins", {}).get("total", 0)
                    win_rate = wins / played if played > 0 else 0
                    
                    stats_data["total_matches"] = played
                    stats_data["wins"] = wins
                    stats_data["draws"] = fixtures.get("draws", {}).get("total", 0)
                    stats_data["losses"] = fixtures.get("loses", {}).get("total", 0)
                    stats_data["win_rate"] = win_rate
                    
                    # Extrae forma reciente
                    fixture_results = self.get_team_fixtures(team_id, last=5)
                    form = []
                    
                    if "response" in fixture_results:
                        for match in fixture_results["response"]:
                            teams = match.get("teams", {})
                            goals = match.get("goals", {})
                            
                            is_home = teams.get("home", {}).get("id") == team_id
                            team_goals = goals.get("home" if is_home else "away")
                            opponent_goals = goals.get("away" if is_home else "home")
                            
                            if team_goals > opponent_goals:
                                form.append("W")
                            elif team_goals < opponent_goals:
                                form.append("L")
                            else:
                                form.append("D")
                    
                    stats_data["recent_form"] = "".join(form)
                
                # Obtener posición actual
                team_position = None
                if "response" in standings and standings["response"]:
                    for league_data in standings["response"]:
                        if "league" in league_data and "standings" in league_data["league"]:
                            for group in league_data["league"]["standings"]:
                                for team_standing in group:
                                    if team_standing.get("team", {}).get("id") == team_id:
                                        team_position = team_standing.get("rank")
                                        stats_data["position"] = team_position
                                        stats_data["points"] = team_standing.get("points")
                                        stats_data["total_teams"] = len(group)
                
                # Calcular probabilidad aproximada de victoria
                win_probability = None
                if team_position is not None:
                    total_teams = stats_data.get("total_teams", 20)
                    # Fórmula simple, puede mejorarse
                    position_factor = 1 - ((team_position - 1) / total_teams)
                    win_rate_factor = stats_data.get("win_rate", 0)
                    
                    win_probability = (position_factor * 0.7) + (win_rate_factor * 0.3)
                    stats_data["win_probability"] = win_probability
                
                return {
                    "market_type": "team_competition_win",
                    "team": team_info["response"][0]["team"],
                    "league": league_info["response"][0]["league"],
                    "season": season,
                    "statistics": stats_data
                }
            
            # Caso 2: Mercado sobre un partido entre dos equipos
            elif is_h2h_market and len(teams_found) >= 2:
                team1_name = teams_found[0]
                team2_name = teams_found[1]
                
                # Usar función de predicción de partido
                return self.get_match_prediction(team1_name, team2_name)
            
            # Caso 3: Otros tipos de mercados
            else:
                # Obtener información general sobre equipos y ligas
                results = {
                    "market_type": "general",
                    "teams_found": teams_found,
                    "leagues_found": leagues_found,
                }
                
                # Si hay al menos un equipo, obtener su información
                if teams_found:
                    team_info = self.get_team_info(teams_found[0])
                    if "response" in team_info and team_info["response"]:
                        results["primary_team"] = team_info["response"][0]["team"]
                
                # Si hay al menos una liga, obtener su información
                if leagues_found:
                    league_info = self.get_league_info(leagues_found[0])
                    if "response" in league_info and league_info["response"]:
                        results["primary_league"] = league_info["response"][0]["league"]
                
                return results
        
        except Exception as e:
            logger.error(f"Error al analizar mercado: {str(e)}")
            return {
                "error": f"Error al analizar mercado: {str(e)}",
                "teams_found": teams_found,
                "leagues_found": leagues_found
            } 