# Inyección de dependencias en FastAPI

FastAPI incluye un sistema de inyección de dependencias basado en la función `Depends`. Una dependencia es cualquier objeto invocable (una función o una clase) cuyo resultado se entrega como parámetro a una función de ruta. Sirve para compartir lógica repetida: obtener una sesión de base de datos, validar un token, leer parámetros de paginación o comprobar permisos.

## Dependencias básicas

Se declara una función normal y se referencia con `Depends` en los parámetros de la ruta. FastAPI la ejecuta antes de la ruta y le pasa el valor devuelto. Desde las versiones recientes se recomienda usar `Annotated`, de modo que el tipo y la dependencia queden juntos y se puedan reutilizar como alias:

```python
from typing import Annotated
from fastapi import Depends, FastAPI

app = FastAPI()

def paginacion(skip: int = 0, limit: int = 100):
    return {"skip": skip, "limit": limit}

Paginacion = Annotated[dict, Depends(paginacion)]

@app.get("/items")
def listar_items(p: Paginacion):
    return p
```

Los parámetros de la dependencia (`skip`, `limit`) se interpretan igual que los de una ruta: aparecen en la documentación OpenAPI y se validan automáticamente.

## Dependencias con yield

Cuando una dependencia necesita liberar un recurso al terminar la petición, como cerrar una conexión o hacer commit de una transacción, se escribe con `yield`. El código anterior al `yield` se ejecuta antes de la ruta y el código posterior se ejecuta después de enviar la respuesta:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Es el patrón estándar para sesiones de SQLAlchemy. Si la ruta lanza una excepción, el bloque `finally` igualmente se ejecuta.

## Subdependencias y caché por petición

Una dependencia puede declarar a su vez otras dependencias, formando un árbol. Por ejemplo, `get_current_user` puede depender de `oauth2_scheme`, que extrae el token del encabezado `Authorization`. FastAPI resuelve el árbol completo.

Si la misma dependencia aparece varias veces dentro de una misma petición, FastAPI la ejecuta una sola vez y reutiliza el resultado. Este comportamiento se llama caché por petición y está activado por defecto (`use_cache=True`). Para forzar que se ejecute cada vez que se la menciona se escribe `Depends(mi_funcion, use_cache=False)`.

## Dependencias a nivel de decorador y de aplicación

Si la dependencia solo hace una comprobación y no devuelve un valor útil, por ejemplo verificar una clave de API, se pasa en el parámetro `dependencies` del decorador:

```python
@app.get("/admin", dependencies=[Depends(verificar_clave)])
def panel(): ...
```

También se puede aplicar a todo un router con `APIRouter(dependencies=[...])` o a toda la aplicación con `FastAPI(dependencies=[...])`.

## Clases como dependencias

Una clase también es invocable, así que puede usarse como dependencia. FastAPI llama a la clase, que ejecuta su `__init__`, y entrega la instancia. Resulta cómodo para agrupar parámetros relacionados y obtener autocompletado en el editor.

## Sustituir dependencias en las pruebas con dependency_overrides

Uno de los usos más importantes del sistema es el testing. La aplicación expone el diccionario `app.dependency_overrides`, donde la clave es la dependencia original y el valor es la función que la reemplaza. Así se puede cambiar una base de datos real por una en memoria, o saltarse la autenticación, sin modificar el código de producción:

```python
from fastapi.testclient import TestClient

def get_db_de_prueba():
    yield sesion_en_memoria

app.dependency_overrides[get_db] = get_db_de_prueba
client = TestClient(app)

def test_listar():
    r = client.get("/items")
    assert r.status_code == 200

# al terminar, restaurar el comportamiento normal
app.dependency_overrides.clear()
```

Conviene limpiar los overrides al final de cada prueba, por ejemplo dentro de una fixture de pytest con `yield`, para que no afecten a otros tests. La función que reemplaza puede recibir sus propios parámetros, que se resuelven como los de cualquier dependencia.

## Errores comunes

Lanzar `HTTPException` dentro de una dependencia es válido y detiene la petición con el código elegido. Evitá realizar trabajo bloqueante dentro de dependencias declaradas con `async def`, porque bloquea el bucle de eventos. Si la dependencia es una función síncrona normal, FastAPI la ejecuta en un pool de hilos.
