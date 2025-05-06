<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/polymarket/agents">
    <img src="public/0110(1)/0110(1).gif" alt="banner" width="466" height="262">
  </a>

<h3 align="center">PolyAgent</h3>

  <p align="center">
    Trade autonomously on Polymarket using AI Agents
    <br />
    <a href="https://twitter.com/PolyAgent_ai"><strong>Twitter »</strong></a>
  </p>
</div>


<!-- CONTENT -->
# PolyAgent: Monitor de Mercados de Predicción en Tiempo Real

Sistema inteligente para el análisis y monitoreo de mercados de predicción en tiempo real, ofreciendo recomendaciones de trading basadas en IA.

## Características principales

- **Análisis en tiempo real**: Monitorea mercados de Polymarket y detecta oportunidades de trading.
- **Análisis de noticias**: Integra información de noticias recientes para contextualizar predicciones.
- **Detección de ventajas**: Compara probabilidades estimadas por IA con precios de mercado para identificar oportunidades.
- **Recomendaciones claras**: Genera decisiones explícitas sobre si operar, qué posición tomar y a qué precio.
- **Interfaz visual**: Presenta los análisis con formato visual mejorado para facilitar la toma de decisiones.
- **Monitoreo continuo**: Capacidad para ejecutar análisis periódicos automáticamente.

## Componentes del sistema

### Núcleo de análisis (`agents/application/executor.py`)
- Implementa algoritmos de análisis de mercados y extracción de probabilidades
- Integra con modelo de lenguaje GPT-4 para el análisis
- Proporciona funciones para obtener y filtrar mercados relevantes

### Monitor de mercados (`market_monitor.py`)
- Obtiene mercados activos de Polymarket
- Filtra los mercados más interesantes para analizar
- Ejecuta análisis individual y ciclos de monitoreo
- Guarda historial de análisis para comparación

### Interfaz de usuario mejorada (`market_monitor_ui.py`)
- Muestra análisis con formato visual atractivo
- Proporciona visualización de probabilidades y ventajas
- Permite monitoreo continuo en segundo plano
- Ofrece modo de prueba para demostraciones sin depender de APIs externas

## Modos de operación

### Modo tiempo real
Conecta con APIs externas para obtener datos actuales de mercados:
```bash
python market_monitor_ui.py --real
```

### Modo simulación
Utiliza datos simulados para demostraciones y pruebas:
```bash
python market_monitor_ui.py --test
```

### Monitoreo continuo
Ejecuta ciclos de análisis periódicos:
```bash
python run_monitor.py
```

## Flujo de trabajo

1. **Obtención de mercados**: El sistema obtiene mercados activos de Polymarket.
2. **Filtrado**: Se seleccionan los mercados más relevantes o interesantes.
3. **Análisis de noticias**: Se recopilan y analizan noticias relacionadas con cada mercado.
4. **Estimación de probabilidad**: La IA estima la probabilidad real del resultado.
5. **Cálculo de ventaja**: Se compara la probabilidad estimada con el precio de mercado.
6. **Decisión de trading**: Se determina si existe una oportunidad favorable.
7. **Presentación**: Se muestra el análisis completo con recomendaciones claras.

## Ejemplos de análisis

El sistema muestra cada análisis en un formato visual como este:

```
┌──────────────────────────────────────────────────────────────────────┐
│ ¿Superará Bitcoin los $100,000 antes de julio de 2025?             │
├──────────────────────────────────────────────────────────────────────┤
│ ID: 23456                                                            │
│ Actualizado: 2025-04-26 21:05:01                                      │
├──────────────────────────────────────────────────────────────────────┤
│ Precios actuales:  YES: 0.2800  NO: 0.7200                     │
│ Probabilidad AI: 0.42        [████████████████                     │
│ Ventaja detectada: +14.0%                                             │
├──────────────────────────────────────────────────────────────────────┤
│ Decisión: OPERAR posición YES                                        │
│ Posición: YES                                                        │
│ Precio objetivo: 0.2800                                               │
└──────────────────────────────────────────────────────────────────────┘
```

## Requisitos

- Python 3.9+
- Paquetes requeridos: `langchain_openai`, `openai`, `colorama`, `tabulate`, `spacy`, etc.
- API Key de OpenAI para análisis basado en LLM

## Trabajo futuro

- Integración con sistema de ejecución de órdenes
- Mejora de algoritmos de selección de mercados
- Analítica de desempeño histórico de predicciones
- Interfaz gráfica más avanzada

# Getting started 🚀

This repo is inteded for use with Python 3.9

1. Clone the repository

   ```
   git clone https://github.com/{username}/Polyagent.git
   cd Polyagent
   ```

2. Create the virtual environment

   ```
   virtualenv --python=python3.9 .venv
   ```

3. Activate the virtual environment

   - On Windows:

   ```
   .venv\Scripts\activate
   ```

   - On macOS and Linux:

   ```
   source .venv/bin/activate
   ```

4. Install the required dependencies:

   ```
   pip install -r requirements.txt
   - (In case of error, try: pip cache purge && pip install -r requirements.txt --no-cache-dir)

   +++

   ```
5. Set up your environment variables:

   - Create a `.env` file in the project root directory

   ```
   cp .env.example .env
   ```

   - Add the following environment variables:

   ```
   POLYGON_WALLET_PRIVATE_KEY=""
   OPENAI_API_KEY=""
   TAVILY_API_KEY=""
   NEWSAPI_API_KEY=""
   export PYTHONPATH="."
   DRY_RUN=
   ANALYSIS_DELAY_SECONDS= #Default is 30secs
   MARKET_CATEGORY="all"  # Options: all, sports, politics, crypto, entertainment, tech
   ```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Download spaCy model:
```bash
python -m spacy download en_core_web_sm
```

3. Configure environment variables:
...

4. Load your wallet with USDC.

5. Try the command line interface...

   ```
   python scripts/python/cli.py
   ```

   Or just go trade! 

   ```
   python agents/application/trade.py
   ```

6. Note: If running the command outside of docker, please set the following env var:

   ```
   export PYTHONPATH="."
   ```

   If running with docker is preferred, we provide the following scripts:

   ```
   ./scripts/bash/build-docker.sh
   ./scripts/bash/run-docker-dev.sh
   ```

## Common issues

1. OSError: [E050] Can't find model 'en_core_web_sm'. It doesn't seem to be
a Python package or a valid path to a data directory.
```bash
python -m spacy download en_core_web_sm
-
self.nlp = spacy.load("en_core_web_sm") OR python -m spacy download en_core_web_sm
```

## Architecture 📚

The Polyagent architecture features modular components that can be maintained and extended by individual community members.

### APIs 🌐

Polyagent connectors standardize data sources and order types.

- `Chroma.py`: chroma DB for vectorizing news sources and other API data. Developers are able to add their own vector database implementations.

- `Gamma.py`: defines `GammaMarketClient` class, which interfaces with the Polymarket Gamma API to fetch and parse market and event metadata. Methods to retrieve current and tradable markets, as well as defined information on specific markets and events.

- `Polymarket.py`: defines a Polymarket class that interacts with the Polymarket API to retrieve and manage market and event data, and to execute orders on the Polymarket DEX. It includes methods for API key initialization, market and event data retrieval, and trade execution. The file also provides utility functions for building and signing orders, as well as examples for testing API interactions.

- `Objects.py`: data models using Pydantic; representations for trades, markets, events, and related entities.

### Scripts 📜

Files for managing your local environment, server set-up to run the application remotely, and cli for end-user commands.

`cli.py` is the primary user interface for the repo. Users can run various commands to interact with the Polymarket API, retrieve relevant news articles, query local data, send data/prompts to LLMs, and execute trades in Polymarkets.

Commands should follow this format:

`python scripts/python/cli.py command_name [attribute value] [attribute value]`

Example:

`get-all-markets`
Retrieve and display a list of markets from Polymarket, sorted by volume.

   ```
   python scripts/python/cli.py get-all-markets --limit <LIMIT> --sort-by <SORT_BY>
   ```

- limit: The number of markets to retrieve (default: 5).
- sort_by: The sorting criterion, either volume (default) or another valid attribute.

# Prediction markets reading 📚

- Prediction Markets: Bottlenecks and the Next Major Unlocks, Mikey 0x: https://mirror.xyz/1kx.eth/jnQhA56Kx9p3RODKiGzqzHGGEODpbskivUUNdd7hwh0
- The promise and challenges of crypto + AI applications, Vitalik Buterin: https://vitalik.eth.limo/general/2024/01/30/cryptoai.html
- Superforecasting: How to Upgrade Your Company's Judgement, Schoemaker and Tetlock: https://hbr.org/2016/05/superforecasting-how-to-upgrade-your-companys-judgment
- The Future of Prediction Markets, Mikey 0x: https://mirror.xyz/1kx.eth/jnQhA56Kx9p3RODKiGzqzHGGEODpbskivUUNdd7hwh0

# PolyAgent

A sophisticated AI system for automated analysis and trading on Polymarket prediction markets.

## Getting Started

### Prerequisites

- Python 3.9+
- Pip package manager
- Internet connection

### Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/Polyagent.git
cd Polyagent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up a virtual environment (recommended):
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

## Configuration

### Environment Variables

Create a `.env` file in the root directory with the following variables:

```
# API Keys
PERPLEXITY_API_KEY=your_perplexity_api_key
POLYMARKET_API_KEY=your_polymarket_api_key

# Firebase Config (optional, for storing predictions)
FIREBASE_API_KEY=your_firebase_api_key
FIREBASE_AUTH_DOMAIN=your_firebase_auth_domain
FIREBASE_PROJECT_ID=your_firebase_project_id
FIREBASE_STORAGE_BUCKET=your_firebase_storage_bucket
FIREBASE_MESSAGING_SENDER_ID=your_firebase_messaging_sender_id
FIREBASE_APP_ID=your_firebase_app_id

# Trading Configuration
DRY_RUN=false  # Set to "true" for simulation mode without real transactions
```

## Running the Program

⚠️ **IMPORTANT**: Always set the Python path before running:

```bash
export PYTHONPATH="."
```

Or run with the path directly:

```bash
PYTHONPATH="." python -m agents/application/trade.py
```

### Running Options

1. **Regular Mode (with real transactions)**:
```bash
PYTHONPATH="." python -m agents/application/trade.py
```

2. **Dry Run Mode (simulation only)**:
```bash
PYTHONPATH="." DRY_RUN=true python -m agents/application/trade.py
```

## Features

- Automated market analysis using AI
- Real-time news analysis with Perplexity API
- Strategy-based trading decisions
- Random delay between trades (2-6 hours)
- Detailed analysis reports
- Firebase integration for prediction storage

## Output Files

- `market_reports/`: Detailed analysis of individual markets
- `daily_reports/`: Daily summaries of all analyses
- `local_predictions/`: Backup of prediction data
- `logs/`: System logs

## Troubleshooting

- **"Module not found" errors**: Always run with `PYTHONPATH="."` or from the project root
- **Perplexity API errors**: Verify your API key and internet connection
- **Trading failures**: Check that:
  - `DRY_RUN` is set to "false"
  - Your Polymarket API keys are valid
  - Your region allows Polymarket trading

## License

This project is licensed under the MIT License - see the LICENSE file for details.
