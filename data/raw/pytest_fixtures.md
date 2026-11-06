# Fixtures en pytest

Una fixture es una función que prepara datos o recursos para las pruebas y que pytest entrega automáticamente a los tests que la piden por nombre. Reemplaza los métodos `setUp` y `tearDown` de unittest con un mecanismo más flexible y explícito.

## Definir y usar una fixture

Se define con el decorador `@pytest.fixture` y se usa añadiendo su nombre como parámetro del test:

```python
import pytest

@pytest.fixture
def usuario():
    return {"nombre": "Ana", "rol": "admin"}

def test_rol(usuario):
    assert usuario["rol"] == "admin"
```

Pytest detecta que el test pide `usuario`, ejecuta la fixture y pasa el valor devuelto.

## El parámetro scope

Por defecto una fixture se crea de nuevo para cada test, lo que corresponde a `scope="function"`. Con el parámetro `scope` se controla cada cuánto se recrea el recurso. Los valores válidos son `function`, `class`, `module`, `package` y `session`. Con `scope="session"` la fixture se crea una única vez para toda la ejecución de pytest y se comparte entre todos los tests, lo cual es útil para recursos caros como una conexión a base de datos, un servidor de prueba o la carga de un modelo:

```python
@pytest.fixture(scope="session")
def conexion():
    c = abrir_conexion()
    yield c
    c.close()
```

Una fixture solo puede depender de fixtures de su mismo alcance o de alcance mayor. Una fixture de sesión no puede pedir una de función.

## Limpieza con yield

Para ejecutar código de limpieza después del test se usa `yield` en lugar de `return`. Lo que está antes del `yield` es la preparación, el valor cedido es lo que recibe el test, y lo que sigue se ejecuta al terminar, incluso si el test falla. Si varias fixtures tienen limpieza, se ejecutan en orden inverso al de su creación.

## conftest.py

Las fixtures definidas en un archivo llamado `conftest.py` quedan disponibles automáticamente para todos los tests de ese directorio y sus subdirectorios, sin importarlas. Es el lugar habitual para fixtures compartidas. Puede haber varios `conftest.py` en niveles distintos, y el más cercano al test tiene prioridad.

## autouse

Con `@pytest.fixture(autouse=True)` la fixture se aplica a todos los tests de su alcance sin que la pidan explícitamente. Sirve, por ejemplo, para reiniciar un estado global o fijar una variable de entorno antes de cada prueba.

## Fixtures parametrizadas

El argumento `params` ejecuta cada test que usa la fixture una vez por cada valor, y el valor actual llega mediante `request.param`:

```python
@pytest.fixture(params=["sqlite", "postgres"])
def motor(request):
    return crear_motor(request.param)
```

No debe confundirse con `@pytest.mark.parametrize`, que parametriza directamente los argumentos de un test concreto.

## Fixtures incluidas

Pytest trae fixtures listas para usar. `tmp_path` entrega un directorio temporal único por test, como objeto `pathlib.Path`. `monkeypatch` permite modificar variables de entorno, atributos o diccionarios y los restaura al terminar. `capsys` captura lo que el código imprime en pantalla. `request` da acceso a información del test que se está ejecutando.

## Depuración

El comando `pytest --fixtures` lista las fixtures disponibles con su documentación. La opción `--setup-show` muestra en qué momento se crea y destruye cada fixture, lo que ayuda a entender el efecto del alcance. Con `-k expresion` se seleccionan tests por nombre y con `-x` se detiene la ejecución en el primer fallo.
