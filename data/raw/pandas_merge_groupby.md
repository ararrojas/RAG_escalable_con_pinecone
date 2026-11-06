# Combinar y agrupar datos con pandas: merge y groupby

Dos operaciones fundamentales al analizar datos tabulares con pandas son combinar tablas por una clave, con `merge`, y resumir por grupos, con `groupby`.

## merge: unir DataFrames por columnas

`pd.merge(izquierda, derecha, on="clave", how="inner")` combina filas de dos DataFrames cuando coinciden los valores de la clave, de forma parecida a un JOIN de SQL. El parámetro `how` define qué filas se conservan:

- `inner`: solo las claves presentes en ambas tablas (valor por defecto).
- `left`: todas las filas de la tabla izquierda; si no hay coincidencia, las columnas de la derecha quedan en NaN.
- `right`: lo mismo, pero conservando la tabla derecha.
- `outer`: la unión de todas las claves de ambas tablas.
- `cross`: producto cartesiano, sin clave.

Cuando las columnas clave se llaman distinto en cada tabla se usan `left_on` y `right_on`. Si ambas tablas tienen columnas con el mismo nombre que no son clave, pandas añade los sufijos `_x` y `_y`, que se pueden personalizar con `suffixes=("_pedido", "_cliente")`. Para unir por el índice, el método `DataFrame.join` es una alternativa más corta.

## Detectar filas sin pareja con indicator

Con `indicator=True` pandas agrega una columna llamada `_merge` que indica el origen de cada fila: `left_only` si la clave solo estaba en la tabla izquierda, `right_only` si solo estaba en la derecha, y `both` si estaba en las dos. Es la forma más directa de auditar una unión y encontrar claves huérfanas:

```python
r = pd.merge(pedidos, clientes, on="cliente_id", how="outer", indicator=True)
sin_cliente = r[r["_merge"] == "left_only"]
```

El nombre de la columna se puede cambiar pasando una cadena: `indicator="origen"`.

## Validar la cardinalidad con validate

El parámetro `validate` comprueba que la relación entre las tablas sea la esperada y lanza `MergeError` si no se cumple. Los valores son `one_to_one`, `one_to_many`, `many_to_one` y `many_to_many`. Es una defensa útil contra claves duplicadas que multiplican filas sin avisar.

## groupby: dividir, aplicar, combinar

`df.groupby("columna")` divide el DataFrame en grupos según los valores de una o varias columnas y permite aplicar una operación a cada grupo. El patrón se conoce como split-apply-combine.

```python
df.groupby("region")["ventas"].sum()
```

Para calcular varias métricas a la vez se usa `agg`. La sintaxis de agregación con nombre es la más legible, porque define directamente el nombre de cada columna resultante:

```python
df.groupby("region").agg(
    total=("ventas", "sum"),
    promedio=("ventas", "mean"),
    pedidos=("pedido_id", "count"),
)
```

Con `as_index=False` las claves del grupo quedan como columnas normales en lugar de pasar al índice. Por defecto, `groupby` descarta los grupos cuya clave es NaN; se evita con `dropna=False`.

## transform y apply

`transform` devuelve un resultado con el mismo tamaño que el original, lo que permite añadir una columna calculada por grupo, por ejemplo el porcentaje que representa cada venta dentro de su región:

```python
df["pct_region"] = df["ventas"] / df.groupby("region")["ventas"].transform("sum")
```

`apply` es más general pero más lento, así que conviene preferir `agg` o `transform` cuando alcanzan.

## Tablas dinámicas

`pivot_table(values="ventas", index="region", columns="mes", aggfunc="sum")` produce una tabla de doble entrada y equivale a un groupby seguido de un reordenamiento. Con `margins=True` añade totales por fila y columna. Para apilar DataFrames con las mismas columnas se usa `pd.concat`, que no debe confundirse con `merge`.
