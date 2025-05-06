from datetime import datetime, timedelta
import os
import requests
import json
from typing import List, Dict, Any, Optional

from newsapi import NewsApiClient

from agents.utils.objects import Article


class News:
    def __init__(self) -> None:
        self.configs = {
            "language": "en",
            "country": "us",
            "top_headlines": "https://newsapi.org/v2/top-headlines?country=us&apiKey=",
            "base_url": "https://newsapi.org/v2/",
        }

        self.categories = {
            "business",
            "entertainment",
            "general",
            "health",
            "science",
            "sports",
            "technology",
        }

        self.API = NewsApiClient(os.getenv("NEWSAPI_API_KEY"))
        self.api_key = os.getenv("NEWSAPI_API_KEY", "")
        self.base_url = "https://newsapi.org/v2/everything"

    def get_articles_for_cli_keywords(self, keywords) -> "list[Article]":
        query_words = keywords.split(",")
        all_articles = self.get_articles_for_options(query_words)
        article_objects: list[Article] = []
        for _, articles in all_articles.items():
            for article in articles:
                article_objects.append(Article(**article))
        return article_objects

    def get_top_articles_for_market(self, market_object: dict) -> "list[Article]":
        return self.API.get_top_headlines(
            language="en", country="usa", q=market_object["description"]
        )

    def get_articles_for_options(
        self,
        market_options: "list[str]",
        date_start: datetime = None,
        date_end: datetime = None,
    ) -> "list[Article]":

        all_articles = {}
        # Default to top articles if no start and end dates are given for search
        if not date_start and not date_end:
            for option in market_options:
                response_dict = self.API.get_top_headlines(
                    q=option.strip(),
                    language=self.configs["language"],
                    country=self.configs["country"],
                )
                articles = response_dict["articles"]
                all_articles[option] = articles
        else:
            for option in market_options:
                response_dict = self.API.get_everything(
                    q=option.strip(),
                    language=self.configs["language"],
                    country=self.configs["country"],
                    from_param=date_start,
                    to=date_end,
                )
                articles = response_dict["articles"]
                all_articles[option] = articles

        return all_articles

    def get_category(self, market_object: dict) -> str:
        news_category = "general"
        market_category = market_object["category"]
        if market_category in self.categories:
            news_category = market_category
        return news_category

    def get_related_news(self, query: str, days_back: int = 7, max_results: Optional[int] = None) -> str:
        """
        Obtiene noticias relacionadas con una consulta
        
        Args:
            query: La consulta para buscar noticias
            days_back: Días hacia atrás para buscar (por defecto: 7)
            max_results: Número máximo de noticias a devolver (si es None, usa MAX_NEWS_PER_MARKET de entorno o 10)
            
        Returns:
            Texto con las noticias relevantes
        """
        # Verificar si hay un límite configurado en las variables de entorno
        env_limit = os.getenv("MAX_NEWS_PER_MARKET")
        if max_results is None:
            if env_limit and env_limit.isdigit():
                max_results = int(env_limit)
            else:
                max_results = 10  # Valor por defecto
        
        if not self.api_key:
            return "Error: API key no configurada para el servicio de noticias."
        
        try:
            # Calcular fechas
            today = datetime.now()
            from_date = (today - timedelta(days=days_back)).strftime('%Y-%m-%d')
            to_date = today.strftime('%Y-%m-%d')
            
            # Construir parámetros
            params = {
                'q': query,
                'from': from_date,
                'to': to_date,
                'language': 'en',
                'sortBy': 'relevancy',
                'pageSize': max_results,  # Limitar el número de resultados
                'apiKey': self.api_key
            }
            
            # Realizar solicitud
            response = requests.get(self.base_url, params=params)
            
            # Verificar si la solicitud fue exitosa
            if response.status_code != 200:
                return f"Error obteniendo noticias relacionadas: {response.json()}"
            
            # Procesar resultados
            data = response.json()
            articles = data.get('articles', [])
            
            # Limitar el número de artículos si es necesario
            articles = articles[:max_results]
            
            # Formatear resultados
            formatted_news = ""
            for i, article in enumerate(articles):
                title = article.get('title', 'Sin título')
                description = article.get('description', 'Sin descripción')
                content = article.get('content', 'Sin contenido')
                published_at = article.get('publishedAt', '')
                source = article.get('source', {}).get('name', 'Fuente desconocida')
                
                formatted_news += f"ARTÍCULO {i+1}:\n"
                formatted_news += f"Título: {title}\n"
                formatted_news += f"Fuente: {source}\n"
                formatted_news += f"Fecha: {published_at}\n"
                formatted_news += f"Descripción: {description}\n"
                formatted_news += f"Contenido: {content}\n\n"
            
            if not formatted_news:
                return f"No se encontraron noticias relacionadas con: {query}"
                
            return formatted_news
            
        except Exception as e:
            return f"Error obteniendo noticias: {str(e)}"

    def _extract_keywords(self, query: str) -> str:
        """Extrae palabras clave de una consulta para buscar noticias más relevantes"""
        # Eliminar palabras comunes y mantener solo sustantivos importantes
        # Simplificado para este ejemplo
        words = query.lower().split()
        common_words = {"will", "the", "a", "an", "in", "on", "at", "to", "be", "is", "are", "was", 
                        "were", "have", "has", "had", "do", "does", "did", "can", "could", "would", 
                        "should", "may", "might", "must", "shall", "win", "lose", "become"}
        
        filtered_words = [word for word in words if word not in common_words and len(word) > 2]
        
        # Limitar a 5 palabras clave para evitar consultas demasiado restrictivas
        keywords = " OR ".join(filtered_words[:5])
        
        return keywords

    def search_news(self, query: str, max_results: int = 5, days_back: int = 7) -> List[Dict]:
        """
        Busca noticias relacionadas con una consulta y devuelve una lista de artículos
        
        Args:
            query: La consulta para buscar noticias
            max_results: Número máximo de noticias a devolver
            days_back: Días hacia atrás para buscar (por defecto: 7)
            
        Returns:
            Lista de artículos de noticias en formato de diccionario
        """
        if not self.api_key:
            print("Error: API key no configurada para el servicio de noticias.")
            return []
        
        try:
            # Extraer palabras clave relevantes de la consulta si es muy larga
            if len(query) > 50:
                search_query = self._extract_keywords(query)
            else:
                search_query = query
            
            # Calcular fechas
            today = datetime.now()
            from_date = (today - timedelta(days=days_back)).strftime('%Y-%m-%d')
            to_date = today.strftime('%Y-%m-%d')
            
            # Construir parámetros
            params = {
                'q': search_query,
                'from': from_date,
                'to': to_date,
                'language': 'en',
                'sortBy': 'relevancy',
                'pageSize': max_results,
                'apiKey': self.api_key
            }
            
            # Realizar solicitud
            response = requests.get(self.base_url, params=params)
            
            # Verificar si la solicitud fue exitosa
            if response.status_code != 200:
                print(f"Error obteniendo noticias: {response.status_code} - {response.text}")
                return []
            
            # Procesar resultados
            data = response.json()
            articles = data.get('articles', [])
            
            # Limitar el número de artículos si es necesario
            articles = articles[:max_results]
            
            return articles
            
        except Exception as e:
            print(f"Error en search_news: {str(e)}")
            return []
