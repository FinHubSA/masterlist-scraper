# Local

## Install Postgres - Mac

Update brew

```
brew update
```

If there is an error

```
brew tap --repair
brew cleanup
brew update-reset
```

Install specific version of postgresql

```
brew install postgresql@14
```

If there is an error with starting postgres check the error logs:

```
brew services list
tail -f /opt/homebrew/var/log/postgresql@14.log
```

If there is no folder for postgresql@14, create the folder like so:

```
initdb /opt/homebrew/var/postgresql@14
```

Create the user and database for the migrations:

```
psql postgres
postgres=# create database masterlist;
postgres=# create user admin;
```

Get into the python environment and migrate the tables

```
python manage.py migrate
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

## Setup Proxy for TOR network

Build the image for proxy and TOR network setup. On docker hub the image is on the link below:

https://hub.docker.com/r/dperson/torproxy

Pull image from docker hub

```
docker pull --platform linux/amd64 dperson/torproxy
```

Tag your image

```
docker tag dperson/torproxy:latest us-central1-docker.pkg.dev/danae-rust-scraper-one/tor-proxy-repo/tor_proxy:1
```

Push your image to the registry:

```
docker push us-central1-docker.pkg.dev/danae-rust-scraper-one/tor-proxy-repo/tor_proxy:1
```

Create a GCE instance from the docker container

- Go to the artifact registry and find repository with you container
- Open the container then open the image.
- On the digests page select the digest/version you want and on the actions click deploy to GCE

Set firewall rules

- Open the VM and click on it
- Go to network interfaces and click on it
- Go to firewalls and click on 'Add firewall rule'
- In the source IPV4 ranges put 0.0.0.0/0 (to allow all)
- In the ports put 8118, 9050-9051 (tor proxy listening ports)
