import json
import boto3
import miathena

params = {
    'region': 'eu-west-2',
    'database': 'ratings',
    'bucket': 'egsmartin',
    'path': 'resultados',
    'query': 'SELECT m.title, r.rating FROM ratings_pelicula as r inner join peliculas.peliculas as m ON r.movieid=m.movieid order by r.rating desc limit 10'
}


def lambda_handler(event, context):
    session = boto3.Session()

    # Fucntion for obtaining query results and location
    location, data = miathena.query_results(session, params)
    print("Locations: ", location)
    print("Result Data: ")
    print(data)
    # Function for cleaning up the query results to avoid redundant data
    miathena.cleanup(session, params)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "location": location,
            "ratings": data
        }),
    }
