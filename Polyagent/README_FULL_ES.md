# Polyagent: Sistema Integrado para Predicción, Trading y Redención en Polymarket

<div align="center">
  <img src="public/0110(1)/0110(1).gif" alt="banner" width="466" height="262">
</div>

## Descripción General

Polyagent es un sistema completo para interactuar con la plataforma Polymarket que integra tres capacidades fundamentales:

1. **Análisis y Predicción**: Utiliza IA para analizar mercados de predicción y estimar probabilidades reales.
2. **Trading Automatizado**: Ejecuta operaciones basadas en análisis autónomos cuando detecta oportunidades.
3. **Redención de Ganancias**: Automatiza la reclamación de ganancias en mercados resueltos.

## Stack Tecnológico

### Lenguajes y Frameworks
- **Python 3.9**: Lenguaje principal del proyecto
- **FastAPI/ASGI**: Para componentes de API y servicios web
- **Web3.py**: Interacción con blockchain (Polygon)

### Inteligencia Artificial
- **OpenAI GPT-4**: Análisis de mercados y estimación de probabilidades
- **LangChain**: Framework para crear aplicaciones basadas en LLM
- **spaCy**: Para procesamiento de lenguaje natural (NLP)
- **ChromaDB**: Base de datos vectorial para almacenamiento de embeddings

### Blockchain y Contratos
- **Polymarket CLOB Client**: Cliente para el libro de órdenes centralizado
- **Py-order-utils**: Utilidades para gestión de órdenes en blockchain
- **Web3.py**: Interacción con contratos inteligentes en Polygon

### Almacenamiento y Datos
- **Firebase/Firestore**: Almacenamiento de predicciones y análisis
- **ChromaDB**: Almacenamiento vectorial para búsqueda semántica
- **Almacenamiento local**: Respaldo para registros y predicciones

### Análisis y Búsqueda
- **Tavily**: API de búsqueda para información en tiempo real
- **NewsAPI**: Obtención de noticias para análisis de contexto
- **Perplexity**: Análisis en tiempo real (opcional)

## Componentes Principales

### Módulo de Predicción
- **Executor (`agents/application/executor.py`)**: Motor principal de análisis que integra LLMs con fuentes de datos.
- **Market Search (`agents/connectors/search.py`)**: Conectores para búsqueda de información relevante.
- **News (`agents/connectors/news.py`)**: Conectores para obtener noticias recientes.

### Módulo de Trading
- **Trader (`agents/application/trade.py`)**: Gestiona la selección y ejecución de operaciones.
- **Polymarket (`agents/polymarket/polymarket.py`)**: Cliente principal para interactuar con Polymarket.
- **Gamma Client (`agents/polymarket/gamma.py`)**: Cliente para la API Gamma de Polymarket.

### Módulo de Redención
- **PolymarketRedeemer (`agents/application/redeem_winnings.py`)**: Automatiza la redención de ganancias.

### Almacenamiento de Datos
- **PredictionStore (`agents/predictions/prediction_store.py`)**: Gestiona el almacenamiento de predicciones.

## Requisitos y Configuración

### Requisitos del Sistema
- Python 3.9+
- Conexión a internet estable
- Espacio en disco para logs y cache (>500MB recomendado)

### Variables de Entorno Principales
```
POLYGON_WALLET_PRIVATE_KEY=""  # Clave privada para operaciones en Polygon
OPENAI_API_KEY=""              # API Key de OpenAI para análisis con GPT-4
TAVILY_API_KEY=""              # API Key de Tavily para búsqueda
NEWSAPI_API_KEY=""             # API Key de NewsAPI para obtención de noticias
DRY_RUN=                       # "true" para modo simulación (sin transacciones reales)
ANALYSIS_DELAY_SECONDS=        # Retraso entre análisis (predeterminado: 30 segundos)
MARKET_CATEGORY="all"          # Categoría de mercados a analizar (opciones: all, sports, politics, crypto, entertainment, tech)
```

### Configuración de Firebase (Opcional)
Para habilitar la sincronización con Firebase, coloca el archivo de credenciales en:
```
config/babavangabd.json
```

## Guía de Uso

### 1. Predicción y Análisis de Mercados

#### Análisis de Mercado Único
Para analizar un mercado específico:
```bash
python -m agents.application.single_market_analysis --market-id <ID_DEL_MERCADO>
```

#### Monitor Continuo de Mercados
Interfaz para monitorear mercados en tiempo real:
```bash
python market_monitor_ui.py --real
```

En modo simulación (sin conexión a APIs):
```bash
python market_monitor_ui.py --test
```

### 2. Trading Automatizado

#### Ejecutar Trading Automatizado
Inicia el sistema completo de trading:
```bash
python -m agents.application.trade
```

Opciones disponibles:
- `--dry-run`: Ejecuta sin realizar transacciones reales
- `--delay`: Configura el retraso entre análisis (en segundos)
- `--category`: Filtra mercados por categoría (por defecto: all)

#### Modo de Prueba con Una Operación
Para ejecutar una única operación de prueba:
```bash
python -m agents.application.trade --one-trade --dry-run
```

### 3. Redención de Ganancias

#### Listar Mercados Participados
Para ver todos los mercados donde has participado:
```bash
python -m agents.application.redeem_winnings --list-markets
```

#### Buscar Mercado por Palabra Clave
Para encontrar un mercado específico:
```bash
python -m agents.application.redeem_winnings --search-market "palabra_clave"
```

#### Redimir Mercado Específico
Para redimir ganancias de un mercado específico por ID:
```bash
python -m agents.application.redeem_winnings --force-redeem-market <ID_DEL_MERCADO>
```

#### Redimir Todas las Ganancias Automáticamente
Para redimir automáticamente todas las posiciones donde sea posible determinar un resultado:
```bash
python -m agents.application.redeem_winnings --auto-redeem-all
```

#### Modo Debug
Añade el flag `--debug` a cualquier comando para ver información detallada:
```bash
python -m agents.application.redeem_winnings --debug --auto-redeem-all
```

## Flujos de Trabajo Completos

### 1. Flujo de Trading

1. **Análisis Inicial**: El sistema ejecuta `trade.py` que obtiene mercados actuales
2. **Filtrado**: Se seleccionan mercados basados en liquidez, volumen y categoría
3. **Análisis Profundo**: Para cada mercado, se analizan noticias y datos con GPT-4
4. **Estimación de Probabilidad**: Se determina la probabilidad "real" del resultado
5. **Detección de Oportunidades**: Se compara con el precio de mercado para calcular ventaja
6. **Decisión**: Si hay ventaja significativa, se programa una transacción
7. **Ejecución**: Se ejecuta la operación (YES/NO) con el tamaño calculado
8. **Almacenamiento**: Se registra la predicción en Firebase y localmente

### 2. Flujo de Redención

1. **Obtención de Datos**: `redeem_winnings.py` obtiene mercados resueltos y posiciones del usuario
2. **Identificación**: Se identifican mercados resueltos donde el usuario participó
3. **Análisis de Resultados**: Se determina el resultado ganador y si el usuario ganó
4. **Preparación de Transacción**: Se construye la transacción para redimir posiciones
5. **Ejecución**: Se firma y envía la transacción a la red Polygon
6. **Verificación**: Se espera confirmación y se notifica el resultado

## Estructura de Directorios

```
Polyagent/
├── agents/                     # Componentes principales
│   ├── application/            # Aplicaciones y ejecutores
│   │   ├── executor.py         # Motor de análisis
│   │   ├── redeem_winnings.py  # Sistema de redención
│   │   ├── trade.py            # Sistema de trading
│   │   └── single_market_analysis.py  # Análisis de mercado único
│   ├── connectors/             # Conectores a servicios externos
│   │   ├── search.py          # Conectores para búsqueda de información relevante
│   │   └── news.py            # Conectores para obtener noticias recientes
│   ├── polymarket/             # Clientes de Polymarket
│   │   ├── polymarket.py      # Cliente principal para interactuar con Polymarket
│   │   └── gamma.py           # Cliente para la API Gamma de Polymarket
│   ├── predictions/            # Almacenamiento de predicciones
│   ├── utils/                  # Utilidades comunes
│   └── application/            # Aplicaciones y ejecutores
│       └── single_market_analysis.py  # Análisis de mercado único
├── config/                     # Archivos de configuración
├── local_predictions/          # Almacenamiento local de predicciones
├── logs/                       # Registros del sistema
├── market_monitor.py           # Monitor de mercados (consola)
├── market_monitor_ui.py        # Monitor de mercados (interfaz)
├── requirements.txt            # Dependencias del proyecto
```

## Recomendaciones de Uso

1. **Inicio Recomendado**: Comienza con el modo `--dry-run` para familiarizarte con el sistema sin riesgo.
2. **Monitoreo de Mercados**: Usa `market_monitor_ui.py` para ver análisis de mercados antes de activar el trading.
3. **Redención Periódica**: Ejecuta `redeem_winnings.py --auto-redeem-all` semanalmente para reclamar ganancias.
4. **Gestión de Riesgo**: Ajusta el tamaño de las apuestas en `trade.py` según tu tolerancia al riesgo.
5. **Mantenimiento**: Revisa los logs en la carpeta `/logs` para detectar problemas.

## Limitaciones Actuales

1. La calidad del análisis depende de la disponibilidad y calidad de noticias recientes.
2. El sistema de redención puede requerir intervención manual para mercados con resolución ambigua.
3. Las ventajas detectadas pueden cambiar rápidamente en mercados con alta volatilidad.
4. Los modelos LLM tienen sesgos inherentes que pueden afectar las estimaciones de probabilidad.

## Contribuciones y Extensiones

El sistema está diseñado de forma modular para facilitar extensiones:

- **Modelos Alternativos**: Puedes integrar otros LLMs en `executor.py`
- **Fuentes de Datos**: Añade nuevas fuentes en el directorio `connectors/`
- **Estrategias de Trading**: Personaliza la lógica en `trade.py`
- **Interfaz de Usuario**: Mejora la visualización en `market_monitor_ui.py`

---

## Advertencia Legal

Este software es para fines educativos y de investigación. El trading en mercados de predicción conlleva riesgos financieros. No es asesoramiento financiero ni garantiza resultados. Utilízalo bajo tu propia responsabilidad. 