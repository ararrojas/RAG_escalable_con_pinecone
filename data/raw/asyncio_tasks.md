# Concurrencia con asyncio: tareas, gather y semáforos

El módulo `asyncio` de la biblioteca estándar permite escribir código concurrente con un único hilo, mediante corrutinas definidas con `async def` y suspendidas con `await`. Es ideal para trabajo limitado por entrada/salida, como peticiones HTTP, acceso a bases de datos o sockets, y no acelera cálculos intensivos de CPU.

## Corrutinas y asyncio.run

Llamar a una función `async def` no la ejecuta: devuelve un objeto corrutina. Para correrla desde código síncrono se usa `asyncio.run(main())`, que crea el bucle de eventos, ejecuta la corrutina y lo cierra al terminar. Dentro de una corrutina, `await` cede el control al bucle para que otras tareas avancen mientras se espera.

## Tareas con create_task

`asyncio.create_task(coro)` programa una corrutina para que se ejecute de forma concurrente y devuelve un objeto `Task`. A diferencia de hacer `await` directamente, la tarea empieza a correr en segundo plano y se puede esperar después. Conviene guardar una referencia a la tarea, porque el bucle solo mantiene referencias débiles y una tarea sin referencia podría ser eliminada antes de terminar.

## Ejecutar varias a la vez con gather

`await asyncio.gather(a(), b(), c())` ejecuta varias corrutinas concurrentemente y devuelve la lista de resultados en el mismo orden en que se pasaron. Si una lanza una excepción, esa excepción se propaga al `await`, pero las demás siguen corriendo. Con `return_exceptions=True` las excepciones se devuelven como valores dentro de la lista en lugar de propagarse.

## TaskGroup (Python 3.11+)

`asyncio.TaskGroup` ofrece concurrencia estructurada, más segura que `gather`. Se usa como gestor de contexto asíncrono y garantiza que todas las tareas terminen al salir del bloque:

```python
async with asyncio.TaskGroup() as tg:
    t1 = tg.create_task(descargar("a"))
    t2 = tg.create_task(descargar("b"))
# aquí ambas ya terminaron
print(t1.result(), t2.result())
```

Si una tarea falla, el grupo cancela las restantes y lanza un `ExceptionGroup`, que se captura con la sintaxis `except*`.

## Limitar la concurrencia con Semaphore

Lanzar miles de peticiones a la vez puede saturar un servidor o agotar los descriptores de archivo. `asyncio.Semaphore(n)` limita a `n` el número de corrutinas que pueden estar dentro de una sección crítica al mismo tiempo. Las demás esperan hasta que otra libere el semáforo:

```python
sem = asyncio.Semaphore(5)

async def pedir(url):
    async with sem:
        return await cliente.get(url)

resultados = await asyncio.gather(*(pedir(u) for u in urls))
```

Con este patrón se crean todas las tareas, pero solo cinco hacen la petición simultáneamente. Es la técnica habitual para controlar límites de tasa (rate limiting).

## Tiempos de espera y cancelación

`asyncio.timeout(segundos)`, disponible desde Python 3.11, es un gestor de contexto que cancela el bloque si tarda demasiado y lanza `TimeoutError`. La función `asyncio.wait_for(coro, timeout)` cumple un papel similar para una sola corrutina. Una tarea se cancela con `task.cancel()`, lo que provoca una excepción `CancelledError` dentro de ella; si se captura, debe volver a lanzarse para no romper la cancelación.

## Otras primitivas

`asyncio.Queue` implementa colas productor-consumidor. `asyncio.Lock` y `asyncio.Event` coordinan tareas. Para ejecutar una función bloqueante sin congelar el bucle, `asyncio.to_thread(funcion, *args)` la envía a un hilo aparte.

## Error típico: bloquear el bucle

Llamar a `time.sleep()` o a una librería síncrona dentro de una corrutina detiene todas las tareas. Se debe usar `await asyncio.sleep()` o una librería asíncrona equivalente, o bien `to_thread`.
