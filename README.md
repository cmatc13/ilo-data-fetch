# ilo-data-fetch
Fetching data from the International Labor Organization (ILO) on a schedule and storing the data and embeddings in a google cloud bucket. 

- Run these two lines to get the dependencies for GCP. This is a highly stripped down version since naively installing the GCP dependencies from the Google documentation results in bloated and unneccesary files clogging up space. 

curl -LO https://github.com/tonymet/gcloud-lite/releases/download/472.0.0/google-cloud-cli-472.0.0-linux-x86_64-lite.tar.gz

tar -zxf *gz

# Build the dockerfile without cache and show the logs in the docker_build.log file
docker build . -t ilo-data-fetch:latest --no-cache > docker_build.log 2>&1

# For GCP
docker build -t gcr.io/[PROJECT-ID]/[IMAGE-NAME]:[TAG] .
- e.g.

docker build -t gcr.io/lano-app-project/ilo-data-fetch:ilo-data-fetch .

# To free up space since running docker commands can easily take up critical space in github codespace environment.
docker system prune -f

# docker command to remove an image
docker rmi <image_id> -f

# docker command to remove all containers
docker container prune -f

# run a container locally
docker run --rm <image_id>

# run the docker image as a container in bash so you can check inside the container and find files
docker run -it <image_id> /bin/bash
- e.g.

docker run -it ilo-data-fetch /bin/bash

# Main steps to Deploy to GCP 
- login to gcp with the account connected to the project 

pip install gcloud
gcloud auth login

gcloud auth list

- Create the project if not already done in the web UI

gcloud app create --project=[YOUR_PROJECT_ID]

# set the project 

gcloud config set project [YOUR_PROJECT_ID]

- e.g.

gcloud config set project llm-app-project

- Provide billing account for this project by running gcloud beta billing accounts list OR you can do it manually from the GCP console.
- Enable Services for the Project: We have to enable services for Cloud Run using below set of commands

gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com

# Create Service Accounts with Permissions if not already done in the web UI
gcloud iam service-accounts create [PROJECT_NAME] \
    --display-name="[PROJECT_NAME]"

- Service account email addresses

![image](https://github.com/cmatc13/ilo-data-fetch/assets/9800102/30a0b0e3-05ad-45ae-acfd-5b733b4b69aa)

# needed for cloud run to run the application
gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] \
    --member="serviceAccount:[SERVICE_ACCOUNT_EMAIL_ADDRESS]" \
    --role="roles/run.invoker"    
- e.g.

gcloud projects add-iam-policy-binding llm-app-project \
    --member="serviceAccount:lano-llm-app@llm-app-project.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] \
    --member="serviceAccount:[SERVICE_ACCOUNT_EMAIL_ADDRESS]" \
    --role="roles/serviceusage.serviceUsageConsumer"

- set the role to admin for the service account

gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] \
    --member="serviceAccount:[SERVICE_ACCOUNT_EMAIL_ADDRESS]" \
    --role="roles/run.admin"

- needed for read/write of storage blob

gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] \
    --member="serviceAccount:[SERVICE_ACCOUNT_EMAIL_ADDRESS]" \
    --role="roles/storage.objectCreator"

gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] \
    --member="serviceAccount:[SERVICE_ACCOUNT_EMAIL_ADDRESS]" \
    --role="roles/storage.objectAdmin"    

    
# Check the artifacts location
gcloud artifacts locations list
# Generate Docker image with Region  
DOCKER_BUILDKIT=1 docker build --target=runtime . -t europe-west10-docker.pkg.dev/[YOUR_PROJECT_ID]/clapp/[YOUR_DOCKER_IMAGE]:latest

# Push Docker to Artifacts Registry
- Create a repository clapp

gcloud artifacts repositories create clapp \
    --repository-format=docker \
    --location=europe-west10 \
    --description="A Langachain Chainlit App" \
    --async

# Assign authuntication
gcloud auth configure-docker europe-west10-docker.pkg.dev

# Push the Container to Repository (Artifacts registry)
docker images
docker push europe-west10-docker.pkg.dev/[YOUR_PROJECT_ID]/clapp/[YOUR_DOCKER_IMAGE]:latest

# Deploy the App using Cloud Run
# memory may need to be adjusted based on size of app
gcloud run deploy lano-llm-app --image=europe-west10-docker.pkg.dev/[YOUR_PROJECT_ID]/clapp/[YOUR_DOCKER_IMAGE]:latest \
    --region=europe-west6 \
    --service-account=[SERVICE_ACCOUNT_EMAIL_ADDRESS] \
    --port=8000 \
    --memory=2G


# Committing large files (>100mb) to github
Will need to use  Git Large File Storage (Git LFS)
install it in the terminal in visual studio code codespace

sudo apt-get install git-lfs
git lfs install

e.g. chroma.sqlite3 and data_level0.bin are >100mb
git lfs track "chroma.sqlite3"
git lfs track "data_level0.bin"

add the path to the file e.g.
git add chroma/chroma.sqlite3
git add chroma/78475352-1745-45d8-bd39-2174bd32a103/data_level0.bin

Now you can commit along with other changes
If there are issues with commiting you can undo the last commit with 
git reset HEAD~1


gcloud functions deploy iloFetchFunction \
  --runtime python39 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point main \
  --region europe-west1 \
  --source .


gcloud scheduler jobs create http my-job \
  --schedule "0 1 * * 1" \
  --uri "https://europe-west1-llm-app-project.cloudfunctions.net/iloFetchFunction" \
  --http-method GET \
  --time-zone "Europe/Paris" \
  --location europe-west1

# verify the Scheduler job
gcloud scheduler jobs list --location europe-west1

