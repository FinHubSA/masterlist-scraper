# Local

## Run MongoDB

```
docker-compose up -d
```

## Run Property Listing Scraper

Build the image

```
docker image build -t property_data_scraper .
```

Run the image. Specify arguments for the script being run AND the mongodb connection uri.

```
docker run --network="host" -e script="property_list.py" -e mongodb_uri="mongodb://127.0.0.1:27017" property_data_scraper:latest
```

## Setup GCR Jobs

First register this docker container with google's Artifact Registry. Follow the steps in the link below:

https://cloud.google.com/artifact-registry/docs/docker/store-docker-container-images

Build the image for amd like this

```
docker buildx build --platform linux/amd64 -t gcr_property_data_scraper .
```

Tag your image

```
docker tag gcr_property_data_scraper:latest us-central1-docker.pkg.dev/danae-rust-scraper-one/property-scraper-repo/property_data_scraper:1
```

Push your image to the remote:

```
docker push us-central1-docker.pkg.dev/danae-rust-scraper-one/property-scraper-repo/property_data_scraper:1
```

If you face permission denied run this

```
gcloud auth configure-docker us-central1-docker.pkg.dev
```

\*\* NB

make sure the timeout of the tasks is in a good range so that they are not stopped prematurely

make sure the memory allocated to each task is large enough as well
