# athena

## Desplegar

```ps
sam build
```

```ps
sam deploy --guided
```

## Perfil

Para ejecutar desde el lambda la query de Athena necesitamos lo siguiente:

- Para Consultar queries en Athena
    - Permisos para acceder a `AWS Glue`. Esto es necesario porque Athena va a necesitar recuperar los metadatos de AWS Glue
    - Permisos en Athena para iniciar la query, ejecutarla y recuperar la respuesta
    - Permisos para consultar los buckets de `S3` en los que se guardan los datos que Athena va a consultar
    - Permisos para poder crear objetos en el bucket de resultados

- Para poder borrar los resultados que ha registrado Athena - esto es opcional, para poder hacer `miathena.cleanup(session, params)`
    - Permisos para poder listar el bucket de resultados y los objetos que contiene, así como borrarlos

Esto se implementa como sigue. Al rol que usamos para ejecutar la lambda le asociamos las siguientes policies:

![Rol](.\imagenes\Perfil.png)

La policy `AWSLambdaBasicExecutionRole` es la estandard para ejecutar Lambdas. Le hemos añadido otra policy gestionada, `AmazonS3ReadOnlyAccess`. Esta policy nos permite cubrir las necesidad de poder consultar los buckets de S3 que consultará Athena:

- Permisos para consultar los buckets de `S3` en los que se guardan los datos que Athena va a consultar
- Permisos para poder crear objetos en el bucket de resultados

Usamos una policy custom que nos permitirá cubrir el resto de permisos que precisamos. El [json de la policy](.\policy.json) contiene los permisos y los recursos sobre los que se aplican. Veamos su representación gráfica:
- Permisos para acceder a `AWS Glue`. Esto es necesario porque Athena va a necesitar recuperar los metadatos de AWS Glue

![Glue](.\imagenes\Glue.png)

- Permisos en Athena para iniciar la query, ejecutarla y recuperar la respuesta

![Glue](.\imagenes\Athena.png)

- Permisos para poder listar el bucket de resultados y los objetos que contiene, así como borrarlos

![S3](.\imagenes\S3.png)

## Modulos Python

Para crear un módulo en Python:
1. Creamos un directorio donde crearemos nuestro módulo. Le llamaremos `miathena`:

![Modulo](.\imagenes\modulo.png)

2. Añadimos los archivos donde se implementa el módulo `miathena.`py`
3. Creamos un archivo `__init__.py` donde incluiremos el código de inicialización del módulo, así como los componentes que se exportarán. En nuestro caso exportamos todos los métodos. Nótese el "." antes del nombre del archivo donde se incluyen los métodos que se exportan:

```py
from .miathena import *
```

4. Finalmente ya estamos en condiciones de utilizar el módulo. En `app.py`:

```py
import miathena

(...)

location, data = miathena.query_results(session, params)
```

## Código

Para ejecutar una query en Athena tenemos que hacer tres pasos. El primero es iniciar la ejecución `start_query_execution`. Indicamos donde depositar los resultados - tendremos que tener permisos para escribir en este bucket -, la base por defecto - cuando no se cualifica una tabla con el nombre de la base de datos, se usará esta base de datos -, y por supuesto, la propia query que vamos a ejecutar:

```py
def query_results(session, params, wait=True):
    # Creamos el cliente para consultar a Athena
    client = session.client('athena')

    # This function executes the query and returns the query execution ID
    response_query_execution_id = client.start_query_execution(
        QueryString=params['query'],
        QueryExecutionContext={
            'Database': params['database']
        },
        ResultConfiguration={
            'OutputLocation': 's3://' + params['bucket'] + '/' + params['path']
        }
    )
```

Con esta llamada obtenemos el id de la query: `response_query_execution_id`. Con este id podemos hacer el segundo paso, comprobar cual es el estado de la ejecución de la query en Athena. La función que hemos creado nos permite que en el propio método se haga pooling para comprobar si la query a o no terminado:

```py
response_get_query_details = client.get_query_execution(
    QueryExecutionId=response_query_execution_id['QueryExecutionId']
)
```

En la respuesta que obtenemos tenemos el estado de ejecución:

```py
if 'QueryExecution' in response_get_query_details and 'Status' in response_get_query_details['QueryExecution'] and 'State' in response_get_query_details['QueryExecution']['Status']:
    status = response_get_query_details['QueryExecution']['Status']['State']
    if (status == 'FAILED') or (status == 'CANCELLED'):
        return False, None
    elif status == 'SUCCEEDED':
```

Si la query ha terminado, `SUCCEEDED`, podemos recuperar los datos:

```py
response_query_result = client.get_query_results(
    QueryExecutionId=response_query_execution_id['QueryExecutionId']
)
```

### Borrado de resultados

En el módulo se incluye también una función que nos permite elimiar el objeto con los resultados de la query:

```py
def cleanup(session, params):
    s3 = session.resource('s3')
    my_bucket = s3.Bucket(params['bucket'])
    for item in my_bucket.objects.filter(Prefix=params['path']):
        item.delete()
```