# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
import re
import asyncio
import httpx
from typing import List, Optional

app = FastAPI(title="RADAR Politico Engine", version="2.0")

# Permitir CORS para que tu Dashboard HTML consulte este backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos de Entrada / Salida
class RequestPayload(BaseModel):
    nombre: str
    fecha: Optional[str] = "julio 2026"
    forceRefresh: Optional[bool] = False

# Módulo de Limpieza de Texto (NLP Prep)
def limpiar_texto(texto: str) -> str:
    if not texto:
        return ""
    # Remover URLs complejas y caracteres ruidosos de scraping
    texto = re.sub(r'http\S+', '', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

# Extractor Multi-Fuente Asíncrono
async def extraer_datos_apify(nombre: str, fecha_ctx: str):
    apify_token = os.getenv("APIFY_API_TOKEN")
    if not apify_token:
        return "No hay token de Apify configurado. Generando análisis deducido."

    async with httpx.AsyncClient(timeout=45.0) as client:
        # Tarea 1: X / Twitter
        task_tweets = client.post(
            f"https://api.apify.com/v2/acts/apidojo~twitter-scraper-lite/run-sync-get-dataset-items?token={apify_token}",
            json={
                "searchTerms": [f"{nombre}", f"{nombre} oposicion", f"{nombre} columna opinion"],
                "sort": "Latest",
                "maxItems": 30,
                "tweetLanguage": "es"
            }
        )

        # Tarea 2: Google Search & Noticias
        task_noticias = client.post(
            f"https://api.apify.com/v2/acts/apify~google-search-scraper/run-sync-get-dataset-items?token={apify_token}",
            json={
                "queries": f"{nombre} noticias columna opinion {fecha_ctx}\n{nombre} oposicion denuncias mexico",
                "resultsPerPage": 20,
                "maxPagesPerQuery": 1,
                "languageCode": "es",
                "countryCode": "mx"
            }
        )

        # Tarea 3: Facebook
        task_fb = client.post(
            f"https://api.apify.com/v2/acts/apify~facebook-posts-scraper/run-sync-get-dataset-items?token={apify_token}",
            json={"searchTerm": nombre, "maxPosts": 20}
        )

        # Ejecución en paralelo ultra-rápida
        res_tweets, res_noticias, res_fb = await asyncio.gather(
            task_tweets, task_noticias, task_fb, return_exceptions=True
        )

    # Procesar y Limpiar Tweets
    tweets_clean = []
    if not isinstance(res_tweets, Exception) and res_tweets.status_code == 200:
        for t in res_tweets.json()[:25]:
            txt = limpiar_texto(t.get("text") or t.get("fullText") or "")
            if txt:
                user = t.get("author", {}).get("userName", "anon")
                likes = t.get("likeCount", 0)
                tweets_clean.append(f"[@{user} | Likes:{likes}]: {txt}")

    # Procesar y Limpiar Noticias
    noticias_clean = []
    if not isinstance(res_noticias, Exception) and res_noticias.status_code == 200:
        for item in res_noticias.json():
            for r in item.get("organicResults", [])[:15]:
                title = limpiar_texto(r.get("title", ""))
                desc = limpiar_texto(r.get("description", ""))
                noticias_clean.append(f"TITULAR: {title}\nRESUMEN: {desc}")

    # Procesar y Limpiar Facebook
    fb_clean = []
    if not isinstance(res_fb, Exception) and res_fb.status_code == 200:
        for f in res_fb.json()[:15]:
            txt = limpiar_texto(f.get("text") or f.get("caption") or "")
            if txt:
                fb_clean.append(f"[FB Post]: {txt}")

    # Consolidado de Contexto Limpio
    return (
        f"=== FUENTES EN TIEMPO REAL PARA '{nombre}' ===\n\n"
        f"--- TWEETS Y REDES (X) [{len(tweets_clean)} items] ---\n" + "\n".join(tweets_clean) + "\n\n"
        f"--- NOTICIAS Y PRENSA [{len(noticias_clean)} items] ---\n" + "\n---\n".join(noticias_clean) + "\n\n"
        f"--- FACEBOOK [{len(fb_clean)} items] ---\n" + "\n".join(fb_clean)
    )

@app.post("/api/analizar")
async def analizar_actor(payload: RequestPayload):
    nombre = payload.nombre.strip()
    fecha_ctx = payload.fecha or "julio 2026"

    # 1. Pipeline de Extracción y Limpieza en Python
    contexto_procesado = await extraer_datos_apify(nombre, fecha_ctx)

    # 2. Prompt Analítico Estructurado
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY no configurada")

    prompt = f"""Eres un Director General de Inteligencia Político-Digital. La fecha de consulta es: {fecha_ctx}.

DATOS EXTRAÍDOS Y LIMPIADOS MEDIANTE PIPELINE DE PYTHON PARA "{nombre}":
{contexto_procesado}

MANDATO DE RIGOR Y EXPLICACIÓN:
Debes entregar un análisis minucioso, profesional y sin omitir explicaciones detalladas en ninguna pestaña. Devuelve UNICAMENTE un JSON válido con la siguiente estructura exacta:

{{
  "nombre": "{nombre}",
  "cargo": "Cargo oficial a {fecha_ctx} · Entidad / Partido",
  "fecha_analisis": "{fecha_ctx}",
  "tags": ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5"],
  "kpis": [
    {{"label": "SEGUIDORES TOTALES", "valor": "X.XM", "nota": "Alcance estimado", "tipo": "acc"}},
    {{"label": "APROBACIÓN DIGITAL", "valor": "XX%", "nota": "Proporción favorable", "tipo": "suc"}},
    {{"label": "PANTALLAS DE CRISIS", "valor": "X", "nota": "Focos de volatilidad", "tipo": "dan"}},
    {{"label": "MECANISMO NARRATIVO", "valor": "XX/XX", "nota": "Propia vs Impuesta", "tipo": "gld"}},
    {{"label": "SENTIMIENTO POSITIVO", "valor": "XX%", "nota": "Aceptación neta", "tipo": "suc"}},
    {{"label": "TENDENCIA", "valor": "Alta / Estable", "nota": "Evolución de conversación", "tipo": "acc"}}
  ],
  "vision_general": {{
    "resumen_ejecutivo": "Escribe un análisis de 3 párrafos explicando la postura estratégica del personaje, ataques principales, respaldos y balance general a {fecha_ctx}.",
    "sentimiento": [
      {{"label": "Positivo", "pct": 38}},
      {{"label": "Neutro/Informativo", "pct": 30}},
      {{"label": "Negativo", "pct": 22}},
      {{"label": "Polarizado", "pct": 10}}
    ],
    "temas": [
      {{"tema": "Tema principal 1", "pct": 35}},
      {{"tema": "Tema principal 2", "pct": 22}},
      {{"tema": "Tema principal 3", "pct": 15}},
      {{"tema": "Tema principal 4", "pct": 12}},
      {{"tema": "Tema principal 5", "pct": 9}},
      {{"tema": "Tema principal 6", "pct": 7}}
    ],
    "plataformas": [
      {{"nombre": "Facebook", "pct": 38, "tono_positivo": 45, "tono_negativo": 30}},
      {{"nombre": "X/Twitter", "pct": 28, "tono_positivo": 25, "tono_negativo": 60}},
      {{"nombre": "Noticias/Medios", "pct": 18, "tono_positivo": 30, "tono_negativo": 45}},
      {{"nombre": "Google Search", "pct": 10, "tono_positivo": 40, "tono_negativo": 35}},
      {{"nombre": "Instagram", "pct": 6, "tono_positivo": 50, "tono_negativo": 20}}
    ]
  }},
  "actores_politicos": {{
    "explicacion_ecosistema": "Análisis exhaustivo sobre el comportamiento mediático, editorialistas, oposición y ecosistema algorítmico.",
    "analisis_actores": [
      {{
        "categoria": "Prensa Nacional & Columnistas",
        "impacto": "Alto",
        "narrativa_dominante": "Explicación detallada del encuadre en medios de alcance nacional.",
        "tendencia_actitud": "Desfavorable (60%) / Neutro (40%)"
      }},
      {{
        "categoria": "Prensa Local & Portales Regionales",
        "impacto": "Medio",
        "narrativa_dominante": "Explicación detallada de la cobertura en portales regionales.",
        "tendencia_actitud": "Favorable (70%)"
      }},
      {{
        "categoria": "Oposición & Voceros Críticos",
        "impacto": "Crítico",
        "narrativa_dominante": "Detalle de los voceros opositores y sus principales señalamientos.",
        "tendencia_actitud": "Adverso (90%)"
      }},
      {{
        "categoria": "Ecosistema Ciudadano & Digital",
        "impacto": "Alto",
        "narrativa_dominante": "Análisis de la respuesta en comentarios de redes masivas.",
        "tendencia_actitud": "Dividido / Polarizado"
      }}
    ],
    "cruces_bivariados": [
      {{
        "eje_x": "Plataforma (X vs Facebook)",
        "eje_y": "Tono de Conversación",
        "hallazgo": "Explicación analítica del cruce bivariado entre canales y sesgo de la audiencia."
      }},
      {{
        "eje_x": "Sentimiento",
        "eje_y": "Ejes Temáticos Clave",
        "hallazgo": "Análisis explícito sobre qué temas detonan conversación adversa o favorable."
      }}
    ]
  }},
  "segmentacion_demografica": {{
    "analisis_demografico": "Análisis detallado de perfiles sociodemográficos, diferencias por género y rangos de edad.",
    "por_genero": [
      {{"segmento": "Hombres", "positivo": 35, "neutro": 30, "negativo": 35}},
      {{"segmento": "Mujeres", "positivo": 30, "neutro": 28, "negativo": 42}}
    ],
    "por_edad": [
      {{"segmento": "18-29 años", "positivo": 25, "neutro": 25, "negativo": 50}},
      {{"segmento": "30-44 años", "positivo": 35, "neutro": 30, "negativo": 35}},
      {{"segmento": "45-59 años", "positivo": 45, "neutro": 30, "negativo": 25}},
      {{"segmento": "60+ años", "positivo": 50, "neutro": 28, "negativo": 22}}
    ]
  }},
  "mapa_narrativas": {{
    "explicacion_narrativas": "Análisis de la batalla narrativa entre el relato oficial y las líneas de ataque.",
    "favorables": [
      {{"titulo": "Narrativa A favor 1", "descripcion": "Explicación extensa del alcance y argumentos positivos."}},
      {{"titulo": "Narrativa A favor 2", "descripcion": "Explicación extensa del alcance y argumentos positivos."}},
      {{"titulo": "Narrativa A favor 3", "descripcion": "Explicación extensa del alcance y argumentos positivos."}}
    ],
    "criticas": [
      {{"titulo": "Narrativa En contra 1", "descripcion": "Explicación extensa del impacto y origen de la línea crítica."}},
      {{"titulo": "Narrativa En contra 2", "descripcion": "Explicación extensa del impacto y origen de la línea crítica."}},
      {{"titulo": "Narrativa En contra 3", "descripcion": "Explicación extensa del impacto y origen de la línea crítica."}}
    ],
    "neutras": [
      {{"titulo": "Narrativa Neutra 1", "descripcion": "Detalle de temas informativos en disputa."}},
      {{"titulo": "Narrativa Neutra 2", "descripcion": "Detalle de temas informativos en disputa."}}
    ]
  }},
  "cronologia_eventos": {{
    "analisis_coyuntural": "Lectura analítica sobre cómo los eventos recientes afectaron la reputación.",
    "eventos": [
      {{"fecha": "Fecha/Periodo", "badge": "EVENTO DESTACADO", "evento": "Hito 1", "lectura": "Explicación estratégica profunda."}},
      {{"fecha": "Fecha/Periodo", "badge": "PANTALLA DE CRISIS", "evento": "Hito 2", "lectura": "Explicación estratégica profunda."}},
      {{"fecha": "Fecha/Periodo", "badge": "EVENTO DESTACADO", "evento": "Hito 3", "lectura": "Explicación estratégica profunda."}},
      {{"fecha": "Fecha/Periodo", "badge": "PANTALLA DE CRISIS", "evento": "Hito 4", "lectura": "Explicación estratégica profunda."}}
    ]
  }},
  "riesgos_oportunidades": {{
    "dictamen_estrategico": "Evaluación estratégica final para la toma de decisiones ejecutivas.",
    "riesgos": [
      {{"nivel": "CRÍTICO", "titulo": "Riesgo 1", "descripcion": "Análisis extenso del riesgo y probabilidad de escalamiento."}},
      {{"nivel": "ALTO", "titulo": "Riesgo 2", "descripcion": "Análisis extenso del riesgo y probabilidad de escalamiento."}},
      {{"nivel": "MEDIO", "titulo": "Riesgo 3", "descripcion": "Análisis extenso del riesgo y probabilidad de escalamiento."}}
    ],
    "oportunidades": [
      {{"nivel": "ALTO", "titulo": "Oportunidad 1", "descripcion": "Análisis de la veta aprovechable y potencial de agenda."}},
      {{"nivel": "MEDIO", "titulo": "Oportunidad 2", "descripcion": "Análisis de la veta aprovechable y potencial de agenda."}}
    ]
  }}
}}"""

    # 3. Consulta a GPT-4o vía OpenRouter
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4o",
                "max_tokens": 7500,
                "messages": [{"role": "user", "content": prompt}]
            }
        )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Error OpenRouter: {response.text}")

    res_data = response.json()
    raw_text = res_data["choices"][0]["message"]["content"]

    # Limpieza estricta de JSON
    cleaned = re.sub(r'```json\s*', '', raw_text)
    cleaned = re.sub(r'```\s*$', '', cleaned).strip()
    
    match = re.search(r'\{[\s\S]*\}', cleaned)
    if not match:
        raise HTTPException(status_code=500, detail="La IA no devolvió un JSON estructural válido")

    try:
        data_json = json.loads(match.group(0))
        return data_json
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parseando JSON: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
