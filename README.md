# ilo-data-fetch
fetching data from the International Labor Organization (ILO) on a schedule and storing the data in a google cloud bucket


curl -LO https://github.com/tonymet/gcloud-lite/releases/download/472.0.0/google-cloud-cli-472.0.0-linux-x86_64-lite.tar.gz

tar -zxf *gz

docker build . -t ilo-data-fetch:latest --no-cache > docker_build.log 2>&1


docker system prune -f

docker rmi <image_id> -f

docker container prune -f

#test image locally
docker run --rm ilo-data-fetch

run the docker image as a container in bash so you can be inside the container and find files
docker run -it <image id> /bin/bash