# Integración de Perplexity en PolyAgent

Este documento explica cómo se ha integrado la API de Perplexity en PolyAgent para mejorar el análisis de mercados de predicción con acceso a información en tiempo real de Internet.

## Descripción general

La integración de Perplexity permite que PolyAgent realice análisis de mercados de predicción con acceso a información actualizada de Internet, lo que mejora significativamente la calidad de las predicciones al incorporar datos en tiempo real.

### Beneficios principales

- **Información en tiempo real**: Acceso a noticias, eventos y datos actualizados relevantes para los mercados.
- **Análisis contextualizado**: Mayor precisión en las estimaciones de probabilidad al considerar el contexto actual.
- **Mejor detección de oportunidades**: Identificación más precisa de ventajas (edge) entre probabilidades reales y precios de mercado.
- **Respaldo de decisiones**: Fundamentación sólida para las recomendaciones de trading basadas en información actual.

## Configuración

Para utilizar la integración con Perplexity, debes configurar las siguientes variables de entorno en tu archivo `.env`:

```
PERPLEXITY_API_KEY=tu_api_key_de_perplexity
USE_PERPLEXITY=true
```

### Obtener una API key de Perplexity

1. Regístrate en [Perplexity AI](https://www.perplexity.ai/)
2. Navega a tu perfil y selecciona la sección de API
3. Genera una nueva API key
4. Copia la key y agrégala a tu archivo `.env`

## Uso

### Activar/Desactivar Perplexity

Puedes activar o desactivar el uso de Perplexity cambiando la variable `USE_PERPLEXITY` en el archivo `.env`:

- `USE_PERPLEXITY=true`: Activa el uso de Perplexity (predeterminado)
- `USE_PERPLEXITY=false`: Desactiva Perplexity y usa el análisis tradicional

### Probar la integración

Ejecuta el script de prueba para verificar que Perplexity funciona correctamente:

```bash
python scripts/python/perplexity_test.py
```

Este script verificará la configuración, realizará un análisis de mercado de ejemplo y mostrará los resultados.

### Ejecución con Perplexity

Al ejecutar el monitor de mercados, verás indicaciones de que Perplexity está en uso:

```bash
python agents/application/trade.py
```

El sistema mostrará mensajes como:
```
Perplexity API disponible para análisis en tiempo real
Obteniendo análisis en tiempo real con Perplexity...
```

## Arquitectura

La integración de Perplexity consta de los siguientes componentes:

### 1. Conector de Perplexity (`agents/connectors/perplexity.py`)

Este módulo gestiona la comunicación con la API de Perplexity y proporciona métodos para:
- Verificar disponibilidad de la API
- Realizar consultas de análisis de mercados
- Extraer probabilidades estimadas de los análisis

### 2. Integración en Executor (`agents/application/executor.py`)

El componente Executor ha sido modificado para:
- Inicializar el conector de Perplexity
- Proporcionar métodos para analizar mercados con Perplexity
- Implementar lógica fallback en caso de que Perplexity no esté disponible

### 3. Flujo de datos

```
Market Question → Perplexity API → Análisis en tiempo real → Extracción de probabilidad → Cálculo de ventaja → Decisión de trading
```

## Personalización

### Cambiar el modelo de Perplexity

Por defecto, la integración utiliza el modelo `sonar-reasoning`. Si deseas usar otro modelo de Perplexity, puedes editar el archivo `agents/connectors/perplexity.py` y cambiar la propiedad `self.default_model`.

Modelos disponibles:
- `sonar-small-online`: Modelo más ligero y rápido
- `sonar-medium-online`: Balance entre rendimiento y velocidad
- `sonar-pro`: Modelo más potente para análisis complejos
- `sonar-reasoning`: Especializado en razonamiento (recomendado para mercados de predicción)

### Ajustar la temperatura

La temperatura controla la creatividad vs precisión del modelo. Valores más bajos (0.1) producen respuestas más conservadoras y deterministas, mientras que valores más altos (0.7+) generan respuestas más creativas y variadas.

Puedes ajustar la temperatura en el método `get_market_analysis` en `perplexity.py`.

## Limitaciones

- **Costos de API**: El uso de Perplexity consume créditos de API según su modelo de precios.
- **Tiempos de respuesta**: Las consultas pueden tardar entre 5-15 segundos debido a la búsqueda en Internet.
- **Disponibilidad**: Depende de la disponibilidad del servicio de Perplexity.
- **Límites de tasa**: La API de Perplexity tiene límites de solicitudes por minuto/hora.

## Resolución de problemas

### Error: "API de Perplexity no configurada"

Asegúrate de que:
- Has añadido `PERPLEXITY_API_KEY` a tu archivo `.env`
- La API key es válida y está correctamente formateada

### Error al extraer probabilidad

Si el sistema no puede extraer una probabilidad numérica del análisis:
- Verifica el formato de respuesta en `perplexity.py`
- Ajusta el prompt para que solicite explícitamente un valor numérico

### Tiempos de respuesta lentos

- Considera usar un modelo más ligero como `sonar-small-online`
- Implementa caché para análisis recientes de los mismos mercados
- Reduce la frecuencia de consultas a la API

## Próximos pasos

Futuras mejoras planeadas para la integración de Perplexity:

1. Sistema de caché para reducir llamadas a la API
2. Análisis comparativo entre diferentes modelos de Perplexity
3. Integración de fuentes específicas para categorías de mercados
4. Personalización de prompts por tipo de mercado
5. Análisis de sentimiento en noticias relacionadas

## Referencias

- [Documentación oficial de Perplexity API](https://docs.perplexity.ai/)
- [Guía de inicio rápido de Perplexity](https://docs.perplexity.ai/guides/getting-started)
- [Modelos disponibles en Perplexity](https://docs.perplexity.ai/docs/models)
- [Ejemplos de código de Perplexity](https://docs.perplexity.ai/examples) 