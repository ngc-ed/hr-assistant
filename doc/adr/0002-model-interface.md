# 0002. Interfaz del modelo y modelo simulado

Estado: propuesto (ampliado por ADR 0007 y 0008)

## Contexto

Queremos cambiar de proveedor de modelo sin tocar el agente, y en esta sesión probar
sin red ni costo.

## Decisión

El agente solo depende del protocolo `LanguageModel` con un método
`complete(messages) -> Completion(text, input_tokens, output_tokens)`. La única
implementación es `FakeModel`, determinista y basada en reglas sobre el último
mensaje. `build_model(settings, directory)` elige la implementación según
`MODEL_PROVIDER`; un valor no soportado impide arrancar.

Desde la sesión 3, `Completion` agrega `cached`, existe `GatewayModel` (ADR 0008) y
`build_models` crea un modelo por nombre (`MODEL_SMALL`, `MODEL_LARGE`) para el
enrutador (ADR 0007).

## Consecuencias

- Agregar un modelo real es una clase nueva y una rama en `build_model`.
- Las pruebas inyectan modelos falsos para forzar casos (JSON mal formado,
  herramienta desconocida).
- Los tokens del modelo simulado son aproximados (palabras), no comparables con los de
  un proveedor real.
