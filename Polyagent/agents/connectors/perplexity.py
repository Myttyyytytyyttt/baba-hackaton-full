import os
from typing import List, Dict, Any, Optional
from openai import OpenAI
from datetime import datetime

class PerplexityConnector:
    """
    Conector para la API de Perplexity que permite obtener información
    en tiempo real de Internet para análisis de mercados.
    """
    
    def __init__(self) -> None:
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            print("WARNING: No se encontró PERPLEXITY_API_KEY en variables de entorno")
        
        self.client = None
        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.perplexity.ai"
            )
        
        # Modelo predeterminado con acceso a Internet
        self.default_model = "sonar-reasoning"
    
    def is_available(self) -> bool:
        """Verifica si el conector está disponible y configurado"""
        return self.client is not None and self.api_key is not None
    
    def get_market_analysis(self, market_question: str, additional_context: Optional[str] = None) -> Dict:
        """
        Gets real-time analysis for a market using Perplexity
        
        Args:
            market_question: The market question to analyze
            additional_context: Additional information about the market
            
        Returns:
            Dictionary with market analysis
        """
        if not self.is_available():
            return {"error": "Perplexity API not configured", "analysis": ""}
        
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # Build system prompts
            system_message = (
                "You are an expert analyst in prediction markets. "
                "Your task is to analyze the following market question to estimate its real probability. "
                f"Today is {current_date}. "
                "You must search for up-to-date information on the internet to support your analysis. "
                "Include relevant sources and recent news that affect the probability. "
                "At the end, provide a precise numerical estimate of the probability between 0 and 1."
            )
            
            # Build user message
            user_message = f"Market question: {market_question}\n\n"
            if additional_context:
                user_message += f"Additional context: {additional_context}\n\n"
            
            user_message += (
                "Perform the following tasks:\n"
                "1. Search for recent news and data related to this question\n"
                "2. Identify key factors that affect the probability\n"
                "3. Perform an objective analysis of the current situation\n"
                "4. Estimate numerically the real probability (between 0 and 1) of the 'YES' outcome\n"
                "5. Explain your reasoning for this probability estimation\n\n"
                "Response format:\n"
                "=== NEWS ANALYSIS ===\n"
                "(Detail relevant news and sources)\n\n"
                "=== KEY FACTORS ===\n"
                "(List important factors that affect the probability)\n\n"
                "=== DETAILED ANALYSIS ===\n"
                "(Complete analysis of the situation)\n\n"
                "=== PROBABILITY ESTIMATION ===\n"
                "The estimated probability for the 'YES' outcome is: [NUMBER BETWEEN 0 AND 1]"
            )
            
            # Configure messages
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ]
            
            # Make API call
            response = self.client.chat.completions.create(
                model=self.default_model,
                messages=messages,
                temperature=0.1,  # Low temperature for more precise answers
            )
            
            # Extract response
            analysis = response.choices[0].message.content
            
            return {
                "success": True,
                "analysis": analysis,
                "model": self.default_model
            }
            
        except Exception as e:
            print(f"Error getting Perplexity analysis: {str(e)}")
            return {
                "error": f"Perplexity API error: {str(e)}",
                "analysis": "",
                "success": False
            }
    
    def extract_probability(self, analysis_text: str) -> float:
        """
        Extracts the estimated probability from the analysis text
        
        Args:
            analysis_text: Complete analysis text
            
        Returns:
            Estimated probability as float between 0 and 1
        """
        try:
            # Look for probability estimation section
            if "=== PROBABILITY ESTIMATION ===" in analysis_text:
                # Extract part after the section
                prob_section = analysis_text.split("=== PROBABILITY ESTIMATION ===")[1]
                
                # Look for numbers in 0.XX format
                import re
                prob_matches = re.findall(r"(\d+\.\d+|\d+)", prob_section)
                
                if prob_matches:
                    for match in prob_matches:
                        prob = float(match)
                        # Verify it's in valid range
                        if 0 <= prob <= 1:
                            return prob
                        # If expressed as percentage (e.g. 25.5)
                        elif 0 <= prob <= 100:
                            return prob / 100
                
                # If no valid number found, look for keywords
                if "high" in prob_section.lower() or "elevated" in prob_section.lower():
                    return 0.8
                elif "medium" in prob_section.lower() or "moderate" in prob_section.lower():
                    return 0.5
                elif "low" in prob_section.lower() or "reduced" in prob_section.lower():
                    return 0.2
            
            # Fallback: look for any number between 0 and 1 in the complete text
            import re
            all_numbers = re.findall(r"(\d+\.\d+|\d+)", analysis_text)
            
            for num_str in all_numbers:
                try:
                    num = float(num_str)
                    if 0 <= num <= 1:
                        return num
                    elif 0 <= num <= 100:
                        return num / 100
                except:
                    continue
                    
            # If nothing found, return neutral value
            return 0.5
            
        except Exception as e:
            print(f"Error extracting probability: {e}")
            return 0.5  # Neutral value in case of error 