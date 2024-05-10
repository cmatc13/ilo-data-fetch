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
import csv
from typing import Dict, List, Optional
from langchain.document_loaders.base import BaseLoader
from langchain.docstore.document import Document
import lark
from langchain.chains.llm import LLMChain
from google.cloud import storage
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import json
from dotenv import load_dotenv
import pandas as pd

# Load environment variables from .env file
load_dotenv()


def download_eplex_data(theme_value, file_name):


    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=chrome_options)


    # URL of the website
    url = "https://eplex.ilo.org/"

    # Open the website
    driver.get(url)

    try:
        # Click on the 'Download EPLex legal data' button
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/section[3]/div/div/div/div/p[2]/a"))
        )
        button.click()

        # Wait for the theme dropdown to be clickable
        theme_select = WebDriverWait(driver, 4).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/div[2]/form/div[1]/div/select"))
        )

        # Click on the theme dropdown to open it
        theme_select.click()

        # Select the theme
        theme_option = WebDriverWait(driver, 4).until(
            EC.visibility_of_element_located((By.XPATH, f"//option[@value='{theme_value}']"))
        )
        theme_option.click()

        # Select year
        year_select = Select(driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div[2]/form/div[2]/div/select"))
        year_select.select_by_value("latest")  # Change to the desired year

        # Select format
        format_select = Select(driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div[2]/form/div[3]/div/select"))
        format_select.select_by_value("csv")  # Change to the desired format

        # Wait for the download button to be clickable
        download_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/div[2]/form/div[4]/button[2]"))
        )
        
         # Click the download button   
        download_button.click()

        # Wait for the file to be downloaded
        while not os.path.exists(file_name):
            time.sleep(10)  # Wait for 10 seconds

    finally:
        # Close the webdriver
        driver.quit()

def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client.from_service_account_json('/app/rare-daylight-418614-e1907d935d97.json')
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)

    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

#

# Iterate through the dictionary items
#for theme, filename in theme_files.items():
#    download_eplex_data(theme, filename)
    #upload_to_gcs("ilo_data_storage", file_path, filename)


# upload the embeddings to the bucket
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



import json

def serialize_documents(documents):
    """Serializes a list of langchain_core Document objects to a single JSON string.
    
    Args:
        documents (list): A list of Document instances that have a .to_json() method.
        
    Returns:
        str: A JSON string representing the list of serialized documents.
    """
    serialized_docs = [doc.to_json() if isinstance(doc.to_json(), dict) else json.loads(doc.to_json()) for doc in documents]
    return json.dumps(serialized_docs)

#data_ser = serialize_documents(data)



def upload_blob(bucket_name, data_string, destination_blob_name):
    """Uploads data to the bucket as a file."""
    storage_client = storage.Client.from_service_account_json('rare-daylight-418614-e1907d935d97.json')
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    
    # Upload the JSON string
    blob.upload_from_string(data_string, content_type='application/json')


# Upload the JSON data to GCS
#upload_blob("ilo_data_storage", data_ser, "embeddings.json")





import inspect
import chromadb
from typing import List, Optional, Type, Any
from langchain_community.vectorstores import FAISS, Chroma
import os
from langchain_openai import OpenAIEmbeddings
#embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
#embeddings = OpenAIEmbeddings()
#vectorstore = Chroma.from_documents(documents=data, embedding=embeddings, persist_directory='chroma')



import os
from google.cloud import storage

def upload_dir_to_gcs(bucket_name, source_folder, destination_blob_folder):
    """Uploads a directory to the GCS bucket, including handling for symbolic links to avoid infinite recursion.
    
    Args:
        bucket_name (str): Name of the Google Cloud Storage bucket.
        source_folder (str): Local path to the directory to be uploaded.
        destination_blob_folder (str): Path in the GCS bucket where the directory and files will be uploaded.
    """
    # Initialize Google Cloud Storage client
    storage_client = storage.Client.from_service_account_json('rare-daylight-418614-e1907d935d97.json')
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




import http.server
import socketserver
import threading

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
    # Place the main logic of your application here

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
    
    #Fixed_Term_Contracts_FTCs
    # Step 1: Read the CSV file
    file_path = 'Fixed_Term_Contracts_FTCs.csv'  # Replace 'your_file.csv' with the actual file path
    df = pd.read_csv(file_path)

    # Step 2: Merge columns (assuming you want to merge columns 'A' and 'B' into 'C')
    # Using the + operator
    df['Max cumulative duration of successive FTCs'] = df['Maximum cumulative duration of successive FTCs'].astype(str).fillna('') + ' ' + df['Unit'].astype(str).fillna('')

    df['Max cumulative duration of successive FTCs'] = df['Max cumulative duration of successive FTCs'].fillna('')

    # Step 3: Remove columns 'A' and 'B'
    df.drop(['Maximum cumulative duration of successive FTCs', 'Unit'], axis=1, inplace=True)

    # Step 4: Save the DataFrame as a CSV file with the same name as the original file
    df.to_csv(file_path, index=False)  # Set index=False to avoid writing row indices to the CSV file


    #Probationary_Trial_Period

    # Step 1: Read the CSV file
    file_path = 'Probationary_Trial_Period.csv'  # Replace 'your_file.csv' with the actual file path
    df = pd.read_csv(file_path)

    # Step 2: Merge columns (assuming you want to merge columns 'A' and 'B' into 'C')
    # Using the + operator
    df['Max probationary (trial) period'] = df['Maximum probationary (trial) period'].astype(str).fillna('') + ' ' + df['Unit'].astype(str).fillna('')

    df['Max probationary (trial) period'] = df['Max probationary (trial) period'].fillna('')

    # Step 3: Remove columns 'A' and 'B'
    df.drop(['Maximum probationary (trial) period', 'Unit'], axis=1, inplace=True)

    # Step 4: Save the DataFrame as a CSV file with the same name as the original file
    df.to_csv(file_path, index=False)  # Set index=False to avoid writing row indices to the CSV file

    #Legal_Coverage_Reference

    file_path = 'Legal_Coverage_Reference.csv'
    # Read the CSV file into a DataFrame
    df = pd.read_csv(file_path)

    # Convert year to datetime with the first day of January of that year
    year_dates = pd.to_datetime(df['Reference date'], format='%Y', errors='coerce')

    # Convert yearmonth to datetime with the first day of the respective month
    year_month_dates = pd.to_datetime(df['Reference date'], format='%Y%m', errors='coerce')

    # Convert yearmonthdate to datetime
    year_month_date_dates = pd.to_datetime(df['Reference date'], format='%Y%m%d', errors='coerce')

    # Combine the three datetime series
    combined_dates = year_dates.fillna(year_month_dates).fillna(year_month_date_dates)

    # Update the date_column with the combined dates
    df['Reference date'] = combined_dates

    # Now the 'date_column' will have the desired format

    df.to_csv(file_path, index=False)  # Set index=False to avoid writing row indices to the CSV file


    #Procedures_for_individual_dismissals_notice_period

    # Step 1: Read the CSV file
    file_path = 'Procedures_for_individual_dismissals_notice_period.csv'  # Replace 'your_file.csv' with the actual file path
    df = pd.read_csv(file_path)

    # Step 2: Merge columns (assuming you want to merge columns 'A' and 'B' into 'C')
    # Using the + operator
    df['Notice_period'] = df['Notice period'].astype(str).fillna('') + ' ' + df['Unit'].astype(str).fillna('')

    df['Notice_period'] = df['Notice_period'].fillna('')

    # Step 3: Remove columns 'A' and 'B'
    df.drop(['Notice period', 'Unit'], axis=1, inplace=True)

    # Step 4: Save the DataFrame as a CSV file with the same name as the original file
    df.to_csv(file_path, index=False)  # Set index=False to avoid writing row indices to the CSV file


    #Redundancy_and_severance_pay

    # Step 1: Read the CSV file
    file_path = 'Redundancy_and_severance_pay.csv'  # Replace 'your_file.csv' with the actual file path
    df = pd.read_csv(file_path)

    # Step 2: Merge columns (assuming you want to merge columns 'A' and 'B' into 'C')
    # Using the + operator
    df['Severance pay amount in time'] = df['Number'].astype(str).fillna('') + ' ' + df['Time unit'].astype(str).fillna('')

    df['Severance pay amount in time'] = df['Severance pay amount in time'].fillna('')

    # Step 3: Remove columns 'A' and 'B'
    df.drop(['Number', 'Time unit'], axis=1, inplace=True)

    # Step 4: Save the DataFrame as a CSV file with the same name as the original file
    df.to_csv(file_path, index=False)  # Set index=False to avoid writing row indices to the CSV file


    # Load data and set embeddings
    loader1 = MetaDataCSVLoader(file_path="Fixed_Term_Contracts_FTCs.csv",metadata_columns=['Region','Country', 'Year'])
    data1 = loader1.load()

    # Load data and set embeddings
    loader2 = MetaDataCSVLoader(file_path="Probationary_Trial_Period.csv",metadata_columns=['Region','Country', 'Year'])
    data2 = loader2.load()

    # Load data and set embeddings
    loader3 = MetaDataCSVLoader(file_path="Legal_Coverage_General.csv",metadata_columns=['Region','Country', 'Year'])
    data3 = loader3.load()

    # Load data and set embeddings
    loader4 = MetaDataCSVLoader(file_path="Legal_Coverage_Reference.csv",metadata_columns=['Region','Country', 'Year'])
    data4 = loader4.load()

    # Load data and set embeddings
    loader5 = MetaDataCSVLoader(file_path="Procedures_for_collective_dismissals.csv",metadata_columns=['Region','Country', 'Year'])
    data5 = loader5.load()

    # Load data and set embeddings
    loader5 = MetaDataCSVLoader(file_path="Procedures_for_individual_dismissals_general.csv",metadata_columns=['Region','Country', 'Year'])
    data5 = loader5.load()

    # Load data and set embeddings
    loader6 = MetaDataCSVLoader(file_path="Procedures_for_individual_dismissals_notice_period.csv",metadata_columns=['Region','Country', 'Year'])
    data6 = loader6.load()

    # Load data and set embeddings
    loader7 = MetaDataCSVLoader(file_path="Redress.csv",metadata_columns=['Region','Country', 'Year'])
    data7 = loader7.load()

    # Load data and set embeddings
    loader8 = MetaDataCSVLoader(file_path="Redundancy_and_severance_pay.csv",metadata_columns=['Region','Country', 'Year'])
    data8 = loader8.load()

    # Load data and set embeddings
    loader9 = MetaDataCSVLoader(file_path="Valid_and_prohibited_grounds_for_dismissal.csv",metadata_columns=['Region','Country', 'Year'])
    data9 = loader9.load()

    # Load data and set embeddings
    loader10 = MetaDataCSVLoader(file_path="Workers_enjoying_special_protection_against_dismissal.csv",metadata_columns=['Region','Country', 'Year'])
    data10 = loader10.load()

    
    data = data1 + data2 + data3 + data4 + data5 + data6 + data7 + data8 + data9 + data10

    data_ser = serialize_documents(data)

    embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
    vectorstore = Chroma.from_documents(documents=data, embedding=embeddings, persist_directory='chroma')

    bucket_name = "ilo_data_storage"
    local_persistence_dir = 'chroma'  # Your local directory
    gcs_persistence_dir = 'chroma_persistence'  # Path in your GCS bucket

    upload_dir_to_gcs(bucket_name, local_persistence_dir, gcs_persistence_dir)


# Run the HTTP server in a separate thread
thread = threading.Thread(target=run_http_server)
thread.start()

# Run the main process
run_main_process()
