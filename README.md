# ilo-data-fetch

Fetching data from the International Labor Organization (ILO) on a schedule and storing the data and embeddings in a Google Cloud bucket.

## Prerequisites

### Install GCP Dependencies
Run these two lines to get the dependencies for GCP. This is a highly stripped-down version since naively installing the GCP dependencies from the Google documentation results in bloated and unnecessary files clogging up space.
```bash
curl -LO https://github.com/tonymet/gcloud-lite/releases/download/472.0.0/google-cloud-cli-472.0.0-linux-x86_64-lite.tar.gz
tar -zxf *gz
```

## Docker Implementation

### Build the Docker Image
Build the Dockerfile without cache and show the logs in the docker_build.log file.
```bash
docker build . -t ilo-data-fetch:latest --no-cache > docker_build.log 2>&1
```

For GCP:
```bash
docker build -t gcr.io/[PROJECT-ID]/[IMAGE-NAME]:[TAG] .
# Example:
docker build -t gcr.io/lano-app-project/ilo-data-fetch:ilo-data-fetch .
```

### Free Up Space
Running Docker commands can easily take up critical space in GitHub Codespace environment.
```bash
docker system prune -f
```

### Remove Docker Images and Containers
```bash
# Remove an image
docker rmi <image_id> -f

# Remove all containers
docker container prune -f
```

### Run a Container Locally
```bash
docker run --rm <image_id>
```

### Run the Docker Image as a Container in Bash
Check inside the container and find files.
```bash
docker run -it <image_id> /bin/bash
# Example:
docker run -it ilo-data-fetch /bin/bash
```

## Google Cloud Deployment

### Authenticate with GCP
Login to GCP with the account connected to the project.
```bash
pip install gcloud
gcloud auth login
gcloud auth list
```

### Create and Configure the Project
Create the project if not already done in the web UI.
```bash
gcloud app create --project=[YOUR_PROJECT_ID]
gcloud config set project [YOUR_PROJECT_ID]
# Example:
gcloud config set project llm-app-project
```

### Provide Billing Account
Provide a billing account for this project by running:
```bash
gcloud beta billing accounts list
```
Or you can do it manually from the GCP console.

### Enable Services for the Project
Enable services for Cloud Run.
```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
```

### Create Service Accounts with Permissions
If not already done in the web UI.
```bash
gcloud iam service-accounts create [PROJECT_NAME] --display-name="[PROJECT_NAME]"
```


### Assign Roles to Service Accounts
```bash
gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] --member="serviceAccount:[SERVICE_ACCOUNT_EMAIL_ADDRESS]" --role="roles/run.invoker"
# Example:
gcloud projects add-iam-policy-binding llm-app-project --member="serviceAccount:lano-llm-app@llm-app-project.iam.gserviceaccount.com" --role="roles/run.invoker"

gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] --member="serviceAccount:[SERVICE_ACCOUNT_EMAIL_ADDRESS]" --role="roles/serviceusage.serviceUsageConsumer"
gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] --member="serviceAccount:[SERVICE_ACCOUNT_EMAIL_ADDRESS]" --role="roles/run.admin"
gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] --member="serviceAccount:[SERVICE_ACCOUNT_EMAIL_ADDRESS]" --role="roles/storage.objectCreator"
gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] --member="serviceAccount:[SERVICE_ACCOUNT_EMAIL_ADDRESS]" --role="roles/storage.objectAdmin"
```
![image](https://github.com/cmatc13/ilo-data-fetch/assets/9800102/30a0b0e3-05ad-45ae-acfd-5b733b4b69aa)

### Check the Artifacts Location
```bash
gcloud artifacts locations list
```

### Generate Docker Image with Region
```bash
DOCKER_BUILDKIT=1 docker build --target=runtime . -t europe-west10-docker.pkg.dev/[YOUR_PROJECT_ID]/clapp/[YOUR_DOCKER_IMAGE]:latest
```

### Push Docker to Artifacts Registry
Create a repository `clapp`.
```bash
gcloud artifacts repositories create clapp --repository-format=docker --location=europe-west10 --description="A Langachain Chainlit App" --async
```

Assign authentication:
```bash
gcloud auth configure-docker europe-west10-docker.pkg.dev
```

Push the container to the repository:
```bash
docker push europe-west10-docker.pkg.dev/[YOUR_PROJECT_ID]/clapp/[YOUR_DOCKER_IMAGE]:latest
```

### Deploy the App using Cloud Run
Memory may need to be adjusted based on the size of the app.
```bash
gcloud run deploy lano-llm-app --image=europe-west10-docker.pkg.dev/[YOUR_PROJECT_ID]/clapp/[YOUR_DOCKER_IMAGE]:latest --region=europe-west6 --service-account=[SERVICE_ACCOUNT_EMAIL_ADDRESS] --port=8000 --memory=2G
```

## Handling Large Files in GitHub

### Install Git Large File Storage (Git LFS)
Install Git LFS in the terminal in Visual Studio Code Codespace.
```bash
sudo apt-get install git-lfs
git lfs install
```

Track large files:
```bash
# Example:
git lfs track "chroma.sqlite3"
git lfs track "data_level0.bin"

# Add the path to the file
git add chroma/chroma.sqlite3
git add chroma/78475352-1745-45d8-bd39-2174bd32a103/data_level0.bin
```

Now you can commit along with other changes. If there are issues with committing, you can undo the last commit with:
```bash
git reset HEAD~1
```

## Cloud Functions and Scheduler

### Deploy Cloud Function
```bash
gcloud functions deploy iloFetchFunction --runtime python39 --trigger-http --allow-unauthenticated --entry-point main --region europe-west1 --source .
```

### Create Scheduler Job
```bash
gcloud scheduler jobs create http my-job --schedule "0 1 * * 1" --uri "https://europe-west1-llm-app-project.cloudfunctions.net/iloFetchFunction" --http-method GET --time-zone "Europe/Paris" --location europe-west1
```

### Verify the Scheduler Job
```bash
gcloud scheduler jobs list --location europe-west1
```
