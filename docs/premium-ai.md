# IA premium (diseño — NO implementado aún)

Nota de diseño para una fase futura. Se documenta ahora para no perder las
decisiones; **no hay código todavía**. El foco actual es consolidar el MVP.

## Objetivo

Funciones premium apoyadas en IA generativa, limitadas y con coste acotado:
- Explicación ampliada de un veredicto ("¿por qué exactamente?", en lenguaje
  natural, sobre la regla y su fuente).
- Consulta libre acotada ("¿puedo tomar X preparado de tal forma?").
- Posible: resumen del diario para llevar a la matrona.

## Arquitectura elegida

**Gemini (Google) configurado detrás de LiteLLM**, que ya corre en el VPS
(`litellm-eoro`). La app/backend nunca ven la API key de Google: hablan con
LiteLLM, que centraliza modelo, clave, presupuesto y observabilidad.

```
app ──► yema-backend /ai/* ──► LiteLLM (VPS) ──► Gemini
                │                    │
        gating premium        budget + rate limit
        (RevenueCat)          por virtual key
```

## Por qué LiteLLM en medio

- **Límite de coste real**: LiteLLM asigna presupuesto por *virtual key* y
  corta al alcanzarlo — exactamente el "bajo un límite de coste" pedido.
- **Modelo intercambiable**: hoy Gemini; si cambia el precio/calidad, se
  cambia en LiteLLM sin tocar la app.
- **Clave protegida**: la de Google vive solo en LiteLLM. El backend usa una
  virtual key de LiteLLM, revocable.
- **Observabilidad**: gasto por usuaria/función en un panel.

## Reglas de producto (heredadas del resto del sistema)

- **La IA no da veredictos de seguridad.** Los veredictos siguen saliendo del
  motor de reglas auditable. La IA *explica* o *conversa* sobre contenido ya
  validado; nunca decide "seguro/evitar" por su cuenta (frontera MDR + moat).
- **Gating**: solo suscriptoras premium; límite por usuaria además del global.
- **Fallback**: si LiteLLM corta por presupuesto o falla, la función degrada a
  la explicación estática de la regla (que ya existe: campo `education`).

## Esbozo de endpoints (futuro)

```
POST /ai/explain   {ean|rule_id, question}  → texto (solo premium, budget-gated)
POST /ai/ask       {question, week, conditions} → texto acotado + disclaimer matrona
```

Cada respuesta lleva el disclaimer de compañera-no-experta y, cuando se apoya
en una regla, cita su fuente oficial.
