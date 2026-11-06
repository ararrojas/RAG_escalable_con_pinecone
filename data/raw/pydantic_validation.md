# Validación de datos con Pydantic v2

Pydantic es la biblioteca de validación de datos más utilizada de Python. Define modelos mediante anotaciones de tipo y valida y convierte los datos al crear cada instancia. Es la base de la validación de FastAPI. Esta guía describe la versión 2, cuyo núcleo está escrito en Rust y es mucho más rápido que la versión 1.

## Modelos básicos

Un modelo hereda de `BaseModel` y declara sus campos con tipos:

```python
from pydantic import BaseModel

class Usuario(BaseModel):
    nombre: str
    edad: int
    email: str | None = None

u = Usuario(nombre="Ana", edad="31")   # "31" se convierte a 31
```

Si un dato no se puede convertir al tipo declarado se lanza `ValidationError`, cuyo método `.errors()` devuelve una lista estructurada con la ubicación y el motivo de cada fallo.

## Restricciones con Field

La función `Field` añade restricciones y metadatos: `gt`, `ge`, `lt`, `le` para rangos numéricos, `min_length` y `max_length` para cadenas y listas, `pattern` para expresiones regulares, `alias` para otro nombre en los datos de entrada y `default_factory` para valores por defecto mutables:

```python
from pydantic import BaseModel, Field

class Producto(BaseModel):
    nombre: str = Field(min_length=3, max_length=50)
    precio: float = Field(gt=0)
    etiquetas: list[str] = Field(default_factory=list)
```

## Validadores de campo con field_validator

Para reglas que no se expresan con `Field` se usa el decorador `field_validator`, que en la versión 2 reemplaza al antiguo `validator`. Se aplica sobre un método de clase y recibe el valor del campo; debe devolver el valor, posiblemente transformado, o lanzar `ValueError`:

```python
from pydantic import BaseModel, field_validator

class Cuenta(BaseModel):
    usuario: str

    @field_validator("usuario")
    @classmethod
    def sin_espacios(cls, v: str) -> str:
        if " " in v:
            raise ValueError("el usuario no puede contener espacios")
        return v.lower()
```

El parámetro `mode` controla el momento de ejecución: `mode="after"` (por defecto) valida después de que Pydantic haya convertido el valor al tipo declarado, mientras que `mode="before"` recibe el dato crudo, lo que permite normalizarlo antes. Un mismo validador puede aplicarse a varios campos pasando varios nombres.

## Validadores de modelo con model_validator

Cuando la regla involucra varios campos a la vez, por ejemplo comprobar que una fecha de fin sea posterior a la de inicio, se usa `model_validator`. Con `mode="after"` el método recibe la instancia ya construida:

```python
from pydantic import model_validator

class Rango(BaseModel):
    inicio: int
    fin: int

    @model_validator(mode="after")
    def orden(self):
        if self.fin < self.inicio:
            raise ValueError("fin debe ser mayor que inicio")
        return self
```

## Configuración con ConfigDict

El atributo `model_config = ConfigDict(...)` ajusta el comportamiento del modelo. Opciones frecuentes: `strict=True` desactiva las conversiones automáticas de tipo, `extra="forbid"` rechaza campos desconocidos, `frozen=True` vuelve inmutables las instancias y `str_strip_whitespace=True` recorta espacios en las cadenas.

## Serialización

En la versión 2 los métodos cambiaron de nombre respecto a la 1: `model_dump()` reemplaza a `.dict()`, `model_dump_json()` a `.json()`, `model_validate()` a `parse_obj()` y `model_validate_json()` a `parse_raw()`. Se pueden filtrar campos con `include`, `exclude` y `exclude_none=True`.

## TypeAdapter y campos calculados

`TypeAdapter` permite validar tipos que no son modelos, como `list[int]` o un diccionario tipado, sin definir una clase: `TypeAdapter(list[int]).validate_python(["1", "2"])`. El decorador `computed_field` expone una propiedad calculada como parte de la serialización del modelo.
