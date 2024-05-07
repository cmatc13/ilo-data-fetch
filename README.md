# ilo-data-fetch
fetching data from the International Labor Organization (ILO) on a schedule and storing the data in a google cloud bucket


curl -LO https://github.com/tonymet/gcloud-lite/releases/download/472.0.0/google-cloud-cli-472.0.0-linux-x86_64-lite.tar.gz

tar -zxf *gz

docker build . -t ilo-data-fetch:latest --no-cache > docker_build.log 2>&1

# For GCP
docker build -t gcr.io/[PROJECT-ID]/[IMAGE-NAME]:[TAG] .
docker build -t gcr.io/rare-daylight-418614/ilo-data-fetch:ilo-data-fetch .


docker system prune -f

docker rmi <image_id> -f

docker container prune -f

#test image locally
docker run --rm ilo-data-fetch

run the docker image as a container in bash so you can be inside the container and find files
docker run -it <image id> /bin/bash

docker run -it ilo-data-fetch /bin/bash


Main steps to Deploy 🚀
Initialise & Configure the App
First create a project in GCP console

pip install gcloud
gcloud auth login
gcloud auth list
gcloud app create --project=[YOUR_PROJECT_ID]
gcloud config set project [YOUR_PROJECT_ID]
Provide billing account for this project by running gcloud beta billing accounts list OR you can do it manually from the GCP console.

Enable Services for the Project: We have to enable services for Cloud Run using below set of commands
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
#Create Service Accounts with Permissions
gcloud iam service-accounts create langchain-app-cr \
    --display-name="langchain-app-cr"

gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] \
    --member="serviceAccount:lano-ilo-app-service-account@rare-daylight-418614.iam.gserviceaccount.com" \
    --role="roles/run.invoker"    

gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] \
    --member="serviceAccount:lano-ilo-app-service-account@rare-daylight-418614.iam.gserviceaccount.com" \
    --role="roles/serviceusage.serviceUsageConsumer"


gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] \
    --member="serviceAccount:lano-ilo-app-service-account@rare-daylight-418614.iam.gserviceaccount.com" \
    --role="roles/run.admin"


    
# Check the artifacts location
gcloud artifacts locations list
# Generate Docker with Region
DOCKER_BUILDKIT=1 docker build --target=runtime . -t europe-west6-docker.pkg.dev/[YOUR_PROJECT_ID]/clapp/[YOUR_DOCKER_IMAGE]:latest
# Push Docker to Artifacts Registry
# Create a repository clapp
gcloud artifacts repositories create clapp \
    --repository-format=docker \
    --location=europe-west6 \
    --description="A Langachain Chainlit App" \
    --async
# Assign authuntication
gcloud auth configure-docker europe-west6-docker.pkg.dev

# Push the Container to Repository
docker images
docker push europe-west6-docker.pkg.dev/[YOUR_PROJECT_ID]/clapp/langchain-chainlit-chat-app:latest
# Deploy the App using Cloud Run
gcloud run deploy langchain-cl-chat-with-csv-app --image=europe-west6-docker.pkg.dev/langchain-cl-chat-with-csv/clapp/langchain-chainlit-chat-app:latest \
    --region=europe-west6 \
    --service-account=langchain-app-cr@langchain-cl-chat-with-csv.iam.gserviceaccount.com \
    --port=8000

gcloud run deploy lano-llm-app --image=europe-west6-docker.pkg.dev/rare-daylight-418614/clapp/langchain-chainlit-chat-app:latest \
    --region=europe-west6 \
    --service-account=lano-ilo-app-service-account@rare-daylight-418614.iam.gserviceaccount.com \
    --port=8000 \
    --memory=2G
