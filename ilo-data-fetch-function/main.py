import os
import time
import sys
sys.path.append(os.path.abspath('.'))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait, Select
from google.cloud import storage
from langchain.document_loaders.base import BaseLoader
import csv
from typing import Dict, List, Optional
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.document_loaders.csv_loader import CSVLoader
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate,  ChatPromptTemplate
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import EmbeddingsFilter
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.chains.query_constructor.base import AttributeInfo
from langchain_community.vectorstores import FAISS, Chroma
from typing import Dict, List, Optional
from langchain.document_loaders.base import BaseLoader
from langchain.docstore.document import Document
import lark
from langchain.chains.llm import LLMChain
from google.cloud import storage
__import__('pysqlite3')
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import json
from dotenv import load_dotenv
import pandas as pd

# Load environment variables from .env file
load_dotenv()

# function to download the eplex csv files 
def download_eplex_data(theme_value, file_name):
    # Set up download directory
    download_folder = os.path.join(os.getcwd(), "download")
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    # Chrome driver setup
    chrome_options = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": download_folder,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Initialize the Chrome driver
    driver = webdriver.Chrome(options=chrome_options)

    # URL of the website
    url = "https://eplex.ilo.org/"
    driver.get(url)

    try:
        # Click on the 'Download EPLex legal data' button
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/section[3]/div/div/div/div/p[2]/a"))
        )
        button.click()

        # Interact with form elements
        theme_select = WebDriverWait(driver, 4).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/div[2]/form/div[1]/div/select"))
        )
        theme_select.click()
        theme_option = WebDriverWait(driver, 4).until(
            EC.visibility_of_element_located((By.XPATH, f"//option[@value='{theme_value}']"))
        )
        theme_option.click()

        # More form interactions
        year_select = Select(driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div[2]/form/div[2]/div/select"))
        year_select.select_by_value("latest")
        format_select = Select(driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div[2]/form/div[3]/div/select"))
        format_select.select_by_value("csv")

        # Download the file
        download_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/div[2]/form/div[4]/button[2]"))
        )
        download_button.click()

        # Check for the file download completion
        file_path = os.path.join(download_folder, file_name)
        while not os.path.exists(file_path):
            time.sleep(1)  # Check every second

    finally:
        driver.quit()


class MetaDataCSVLoader(BaseLoader):
    """Loads a CSV file into a list of documents.

    Each document represents one row of the CSV file. Every row is converted into a
    key/value pair and outputted to a new line in the document's page_content.

    The source for each document loaded from csv is set to the value of the
    `file_path` argument for all doucments by default.
    You can override this by setting the `source_column` argument to the
    name of a column in the CSV file.
    The source of each document will then be set to the value of the column
    with the name specified in `source_column`.

    Output Example:
        .. code-block:: txt

            column1: value1
            column2: value2
            column3: value3
    """

    def __init__(
        self,
        file_path: str,
        source_column: Optional[str] = None,
        metadata_columns: Optional[List[str]] = None,
        content_columns: Optional[List[str]] =None ,
        csv_args: Optional[Dict] = None,
        encoding: Optional[str] = None,
    ):
        self.file_path = file_path
        self.source_column = source_column
        self.encoding = encoding
        self.csv_args = csv_args or {}
        self.content_columns= content_columns
        self.metadata_columns = metadata_columns        # < ADDED

    def load(self) -> List[Document]:
        """Load data into document objects."""

        docs = []
        with open(self.file_path, newline="", encoding=self.encoding) as csvfile:
            csv_reader = csv.DictReader(csvfile, **self.csv_args)  # type: ignore
            for i, row in enumerate(csv_reader):
                if self.content_columns:
                    content = "\n".join(f"{k.strip()}: {v.strip()}" for k, v in row.items() if k in self.content_columns)
                else:
                    content = "\n".join(f"{k.strip()}: {v.strip()}" for k, v in row.items())
                try:
                    source = (
                        row[self.source_column]
                        if self.source_column is not None
                        else self.file_path
                    )
                except KeyError:
                    raise ValueError(
                        f"Source column '{self.source_column}' not found in CSV file."
                    )
                metadata = {"source": source, "row": i}
                # ADDED TO SAVE METADATA
                if self.metadata_columns:
                    for k, v in row.items():
                        if k in self.metadata_columns:
                            metadata[k] = v
                # END OF ADDED CODE
                doc = Document(page_content=content, metadata=metadata)
                docs.append(doc)

        return docs




import inspect
import chromadb
from typing import List, Optional, Type, Any
from langchain_community.vectorstores import FAISS, Chroma
import os
from langchain_openai import OpenAIEmbeddings
from google.cloud import storage

# function to upload the document embeddings to cloud storage
def upload_dir_to_gcs(bucket_name, source_folder, destination_blob_folder):
    """Uploads a directory to the GCS bucket, including handling for symbolic links to avoid infinite recursion.
    
    Args:
        bucket_name (str): Name of the Google Cloud Storage bucket.
        source_folder (str): Local path to the directory to be uploaded.
        destination_blob_folder (str): Path in the GCS bucket where the directory and files will be uploaded.
    """
    # Initialize Google Cloud Storage client
    storage_client = storage.Client.from_service_account_json('llm-app-project-26a82e769088.json')
    bucket = storage_client.bucket(bucket_name)
    
    # Walk through the directory tree
    for root, dirs, files in os.walk(source_folder):
        # Exclude symbolic links that resolve to directories
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        for file_name in files:
            local_path = os.path.join(root, file_name)
            # Check if the path is a symbolic link and skip it
            if os.path.islink(local_path):
                print(f"Skipping symbolic link at {local_path}")
                continue
            # Construct the full path for the file in GCS
            relative_path = os.path.relpath(local_path, source_folder)
            remote_path = os.path.join(destination_blob_folder, relative_path)
            blob = bucket.blob(remote_path)
            blob.upload_from_filename(local_path)
            print(f"{local_path} uploaded to {remote_path}.")



# function to upload a folder to cloud storage
def upload_folder_to_gcs(bucket_name, source_folder, destination_blob_folder):
    """Uploads a folder to the specified GCS bucket"""
    storage_client = storage.Client.from_service_account_json('llm-app-project-26a82e769088.json')
    bucket = storage_client.bucket(bucket_name)

    for local_file in os.listdir(source_folder):
        local_file_path = os.path.join(source_folder, local_file)
        
        if os.path.isfile(local_file_path):
            remote_path = os.path.join(destination_blob_folder, local_file)
            blob = bucket.blob(remote_path)
            blob.upload_from_filename(local_file_path)
            print(f"Uploaded {local_file_path} to {remote_path}")
        elif os.path.isdir(local_file_path):
            new_folder = os.path.join(destination_blob_folder, local_file)
            upload_folder_to_gcs(bucket_name, local_file_path, new_folder)


# remove the csv files from memory after files are uploaded
def remove_csv_files(directory):
    # Loop over the list of files in the given directory
    for filename in os.listdir(directory):
        if filename.endswith(".csv"):  # Check for CSV files
            file_path = os.path.join(directory, filename)  # Create full path to the file
            os.remove(file_path)  # Remove the file
            print(f"Removed {file_path}")

# to clean up the ilo csv files
def process_csv(file_path, merge_columns, new_column_name, drop_columns):
    # Step 1: Read the CSV file
    df = pd.read_csv(file_path)
    
    # Step 2: Merge columns (assuming you want to merge columns specified in merge_columns into new_column_name)
    df[new_column_name] = df[merge_columns[0]].astype(str).fillna('') + ' ' + df[merge_columns[1]].astype(str).fillna('')
    
    # Step 3: Remove original columns
    df.drop(drop_columns, axis=1, inplace=True)
    
    # Step 4: Save the DataFrame as a CSV file with the same name as the original file
    df.to_csv(file_path, index=False)  # Set index=False to avoid writing row indices to the CSV file

# Special case for Legal_Coverage_Reference with date conversion
def process_date_csv(file_path, date_column):
    # Read the CSV file into a DataFrame
    df = pd.read_csv(file_path)

    # Convert year to datetime with the first day of January of that year
    year_dates = pd.to_datetime(df[date_column], format='%Y', errors='coerce')

    # Convert yearmonth to datetime with the first day of the respective month
    year_month_dates = pd.to_datetime(df[date_column], format='%Y%m', errors='coerce')

    # Convert yearmonthdate to datetime
    year_month_date_dates = pd.to_datetime(df[date_column], format='%Y%m%d', errors='coerce')

    # Combine the three datetime series
    combined_dates = year_dates.fillna(year_month_dates).fillna(year_month_date_dates)

    # Update the date_column with the combined dates
    df[date_column] = combined_dates

    # Save the DataFrame as a CSV file with the same name as the original file
    df.to_csv(file_path, index=False)  # Set index=False to avoid writing row indices to the CSV file




import http.server
import socketserver
import threading
# function to run the app so that a cronjob can be run for the script
def run_http_server():
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"Hello, world!")
            else:
                self.send_response(404)
                self.end_headers()

    with socketserver.TCPServer(("", 8080), Handler) as httpd:
        print("serving at port", 8080)
        httpd.serve_forever()

def run_main_process():

    # Dictionary of theme values to filenames
    theme_files = {
        "EMPCONTRACT1": "Fixed_Term_Contracts_FTCs.csv",
        "EMPCONTRACT2": "Probationary_Trial_Period.csv",
        "SOURCESCOPE1": "Legal_Coverage_General.csv",
        "SOURCESCOPE2": "Legal_Coverage_Reference.csv", 
        "DISMISSREQT1": "Valid_and_prohibited_grounds_for_dismissal.csv", 
        "DISMISSREQT2": "Workers_enjoying_special_protection_against_dismissal.csv", 
        "PROCREQTINDIV1": "Procedures_for_individual_dismissals_general.csv", 
        "PROCREQTINDIV2": "Procedures_for_individual_dismissals_notice_period.csv",
        "PROCREQTCOLLECT": "Procedures_for_collective_dismissals.csv",
        "SEVERANCEPAY": "Redundancy_and_severance_pay.csv",
        "REDRESS": "Redress.csv"
    }
    # For example, you can place the loop that downloads and processes the files
    for theme, filename in theme_files.items():
        download_eplex_data(theme, filename)

    # Process each file using the function
    process_csv('download/Fixed_Term_Contracts_FTCs.csv',
                merge_columns=['Maximum cumulative duration of successive FTCs', 'Unit'],
                new_column_name='Max cumulative duration of successive FTCs',
                drop_columns=['Maximum cumulative duration of successive FTCs', 'Unit'])

    process_csv('download/Probationary_Trial_Period.csv',
                merge_columns=['Maximum probationary (trial) period', 'Unit'],
                new_column_name='Max probationary (trial) period',
                drop_columns=['Maximum probationary (trial) period', 'Unit'])

    process_csv('download/Procedures_for_individual_dismissals_notice_period.csv',
                merge_columns=['Notice period', 'Unit'],
                new_column_name='Notice_period',
                drop_columns=['Notice period', 'Unit'])

    process_csv('download/Redundancy_and_severance_pay.csv',
                merge_columns=['Number', 'Time unit'],
                new_column_name='Severance pay amount in time',
                drop_columns=['Number', 'Time unit'])

    # Process the Legal_Coverage_Reference.csv file
    process_date_csv('download/Legal_Coverage_Reference.csv', 'Reference date')

    bucket_name = 'ilo_storage'
    source_folder = 'download'
    destination_blob_folder = 'download'

    upload_folder_to_gcs(bucket_name, source_folder, destination_blob_folder)

    directory_path = 'download/'

    # Metadata columns
    metadata_columns = ['Region','Country', 'Year']

    # Dictionary to store data
    data_list = []

    # Loop through the theme_files dictionary and load data
    for theme, file_name in theme_files.items():
        loader = MetaDataCSVLoader(file_path=directory_path + file_name, metadata_columns=metadata_columns)
        documents = loader.load()  # returns a Document object
        data_list.extend(documents)


    #set the embeddings and save them to the chroma folder
    embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
    vectorstore = Chroma.from_documents(documents=data_list, embedding=embeddings, persist_directory='chroma')

    # save the embeddings from chroma into the chroma_persistence directory in the gcp storage bucket
    bucket_name = "ilo_storage"
    local_persistence_dir = 'chroma'  # local directory
    gcs_persistence_dir = 'chroma_persistence'  # Path in GCS bucket

    upload_dir_to_gcs(bucket_name, local_persistence_dir, gcs_persistence_dir)
    remove_csv_files("download")

# Run the HTTP server in a separate thread
thread = threading.Thread(target=run_http_server)
thread.start()

# Run the main process
run_main_process()
