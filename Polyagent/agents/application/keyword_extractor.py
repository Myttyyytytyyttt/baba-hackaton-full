"""
Módulo para extracción de palabras clave de textos.
Provee funcionalidad básica para identificar términos relevantes en consultas.
"""

import re
import string
from typing import List, Dict, Set, Optional
from collections import Counter

# Lista de stopwords en inglés (comunes)
ENGLISH_STOPWORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what', 'which', 'this', 'that', 'these', 'those',
    'then', 'just', 'so', 'than', 'such', 'both', 'through', 'about', 'for', 'is', 'of', 'while', 'during', 'to',
    'from', 'in', 'on', 'by', 'at', 'be', 'with', 'about', 'against', 'between', 'into', 'through', 'after', 'before',
    'above', 'below', 'up', 'down', 'in', 'out', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there',
    'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
    'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'don', 'should', 'now'
}

# Lista de stopwords en español (comunes)
SPANISH_STOPWORDS = {
    'a', 'al', 'algo', 'algunas', 'algunos', 'ante', 'antes', 'como', 'con', 'contra', 'cual', 'cuando', 'de', 'del', 
    'desde', 'donde', 'durante', 'e', 'el', 'ella', 'ellas', 'ellos', 'en', 'entre', 'era', 'erais', 'eran', 'eras', 
    'eres', 'es', 'esa', 'esas', 'ese', 'eso', 'esos', 'esta', 'estaba', 'estabais', 'estaban', 'estabas', 'estad', 
    'estada', 'estadas', 'estado', 'estados', 'estamos', 'estando', 'estar', 'estaremos', 'estará', 'estarán', 'estarás', 
    'estaré', 'estaréis', 'estaría', 'estaríais', 'estaríamos', 'estarían', 'estarías', 'estas', 'este', 'estemos', 
    'esto', 'estos', 'estoy', 'estuve', 'estuviera', 'estuvierais', 'estuvieran', 'estuvieras', 'estuvieron', 'estuviese', 
    'estuvieseis', 'estuviesen', 'estuvieses', 'estuvimos', 'estuviste', 'estuvisteis', 'estuviéramos', 'estuviésemos', 
    'estuvo', 'está', 'estábamos', 'estáis', 'están', 'estás', 'esté', 'estéis', 'estén', 'estés', 'fue', 'fuera', 
    'fuerais', 'fueran', 'fueras', 'fueron', 'fuese', 'fueseis', 'fuesen', 'fueses', 'fui', 'fuimos', 'fuiste', 'fuisteis', 
    'fuéramos', 'fuésemos', 'ha', 'habida', 'habidas', 'habido', 'habidos', 'habiendo', 'habremos', 'habrá', 'habrán', 
    'habrás', 'habré', 'habréis', 'habría', 'habríais', 'habríamos', 'habrían', 'habrías', 'habéis', 'había', 'habíais', 
    'habíamos', 'habían', 'habías', 'han', 'has', 'hasta', 'hay', 'haya', 'hayamos', 'hayan', 'hayas', 'hayáis', 'he', 
    'hemos', 'hube', 'hubiera', 'hubierais', 'hubieran', 'hubieras', 'hubieron', 'hubiese', 'hubieseis', 'hubiesen', 
    'hubieses', 'hubimos', 'hubiste', 'hubisteis', 'hubiéramos', 'hubiésemos', 'hubo', 'la', 'las', 'le', 'les', 'lo', 
    'los', 'me', 'mi', 'mis', 'mucho', 'muchos', 'muy', 'más', 'mí', 'mía', 'mías', 'mío', 'míos', 'nada', 'ni', 'no', 
    'nos', 'nosotras', 'nosotros', 'nuestra', 'nuestras', 'nuestro', 'nuestros', 'o', 'os', 'otra', 'otras', 'otro', 
    'otros', 'para', 'pero', 'poco', 'por', 'porque', 'que', 'quien', 'quienes', 'qué', 'se', 'sea', 'seamos', 'sean', 
    'seas', 'seremos', 'será', 'serán', 'serás', 'seré', 'seréis', 'sería', 'seríais', 'seríamos', 'serían', 'serías', 
    'seáis', 'si', 'sido', 'siendo', 'sin', 'sobre', 'sois', 'somos', 'son', 'soy', 'su', 'sus', 'suya', 'suyas', 'suyo', 
    'suyos', 'sí', 'también', 'tanto', 'te', 'tendremos', 'tendrá', 'tendrán', 'tendrás', 'tendré', 'tendréis', 'tendría', 
    'tendríais', 'tendríamos', 'tendrían', 'tendrías', 'tened', 'tenemos', 'tenga', 'tengamos', 'tengan', 'tengas', 'tengo', 
    'tengáis', 'tenida', 'tenidas', 'tenido', 'tenidos', 'teniendo', 'tenéis', 'tenía', 'teníais', 'teníamos', 'tenían', 
    'tenías', 'ti', 'tiene', 'tienen', 'tienes', 'todo', 'todos', 'tu', 'tus', 'tuve', 'tuviera', 'tuvierais', 'tuvieran', 
    'tuvieras', 'tuvieron', 'tuviese', 'tuvieseis', 'tuviesen', 'tuvieses', 'tuvimos', 'tuviste', 'tuvisteis', 'tuviéramos', 
    'tuviésemos', 'tuvo', 'tuya', 'tuyas', 'tuyo', 'tuyos', 'tú', 'un', 'una', 'uno', 'unos', 'vosotras', 'vosotros', 
    'vuestra', 'vuestras', 'vuestro', 'vuestros', 'y', 'ya', 'yo', 'él', 'éramos'
}

class KeywordExtractor:
    """Clase para extraer palabras clave relevantes de textos"""
    
    def __init__(self):
        """Inicializa el extractor de palabras clave"""
        # Palabras comunes a ignorar (stopwords)
        self.stopwords = set(ENGLISH_STOPWORDS)
        self.stopwords.update(SPANISH_STOPWORDS)
        
        # Añadir palabras adicionales específicas a ignorar
        additional_stopwords = {
            'will', 'would', 'could', 'should', 'may', 'might', 'can', 'cannot',
            'yes', 'no', 'question', 'market', 'prediction', 'price', 'probability',
            'likely', 'unlikely', 'possible', 'impossible', 'certain', 'uncertain',
            'happen', 'event', 'outcome', 'result', 'pregunta', 'mercado', 'predicción',
            'precio', 'probabilidad'
        }
        self.stopwords.update(additional_stopwords)
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Tokeniza un texto en palabras individuales sin usar NLTK
        
        Args:
            text: Texto a tokenizar
            
        Returns:
            Lista de tokens (palabras)
        """
        # Limpiar texto
        text = text.lower()
        # Eliminar signos de puntuación
        for char in string.punctuation:
            text = text.replace(char, ' ')
        # Tokenizar por espacios
        return text.split()
    
    def extract_keywords(self, text: str, top_n: int = 5) -> List[str]:
        """
        Extrae las palabras clave más relevantes de un texto
        
        Args:
            text: Texto del cual extraer palabras clave
            top_n: Número máximo de palabras clave a retornar
            
        Returns:
            Lista de palabras clave ordenadas por relevancia
        """
        if not text or not text.strip():
            return []
            
        # Limpieza básica del texto
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)  # Remover puntuación
        
        # Tokenizar con método simple
        tokens = self._tokenize(text)
        
        # Remover stopwords y palabras cortas
        filtered_tokens = [word for word in tokens if word not in self.stopwords and len(word) > 2]
        
        # Contar frecuencia de palabras
        word_freq = Counter(filtered_tokens)
        
        # Extraer las palabras más frecuentes
        keywords = [word for word, _ in word_freq.most_common(top_n)]
        
        return keywords
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Intenta extraer entidades nombradas del texto
        
        Args:
            text: Texto del cual extraer entidades
            
        Returns:
            Diccionario con categorías de entidades y sus valores
        """
        entities = {
            'persons': [],
            'organizations': [],
            'locations': []
        }
        
        # Implementación básica - buscar patrones comunes
        # Extraer nombres propios (palabras que comienzan con mayúscula)
        words = text.split()
        for i, word in enumerate(words):
            if word and word[0].isupper() and word.lower() not in self.stopwords:
                # Verificar si es parte de una entidad multipalabra
                entity = [word]
                j = i + 1
                while j < len(words) and words[j] and words[j][0].isupper():
                    entity.append(words[j])
                    j += 1
                
                if len(entity) > 1:
                    entity_text = ' '.join(entity)
                    if any(location in entity_text.lower() for location in ['city', 'country', 'state', 'nation']):
                        entities['locations'].append(entity_text)
                    elif any(org in entity_text.lower() for org in ['inc', 'corp', 'company', 'organization', 'association']):
                        entities['organizations'].append(entity_text)
                    else:
                        entities['persons'].append(entity_text)
                else:
                    entities['persons'].append(word)
        
        return entities
        
    def extract_phrases(self, text: str, max_phrases: int = 3) -> List[str]:
        """
        Extrae frases relevantes del texto
        
        Args:
            text: Texto del cual extraer frases
            max_phrases: Número máximo de frases a extraer
            
        Returns:
            Lista de frases relevantes
        """
        if not text:
            return []
            
        # Dividir en oraciones
        sentences = re.split(r'[.!?]', text)
        
        # Filtrar oraciones vacías o muy cortas
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        # Ordenar por longitud (asumiendo que las oraciones más largas son más informativas)
        sentences.sort(key=len, reverse=True)
        
        return sentences[:max_phrases] 