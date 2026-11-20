# 0001. API sin estado

Estado: aceptado

## Contexto

El HR Assistant debe escalar corriendo más copias del proceso. Si una copia guarda la
conversación, la siguiente petición podría llegar a otra copia que no la conoce.

## Decisión

La API FastAPI no guarda nada entre peticiones. El cliente (la página web) guarda el
historial y lo manda en `history` en cada `POST /ask`. Las dependencias que comparte
el proceso (configuración, modelo, directorio) son de solo lectura y se inyectan en
`create_app()`.

## Consecuencias

- Escalar es correr más copias; `GET /health` devuelve el `pid` para distinguirlas.
- Cada petición lleva el historial completo: crece el tamaño de las peticiones y los
  tokens de entrada.
- El servidor no puede confiar en el historial: solo valida su forma.
- Las pruebas son simples: cada petición es independiente.
