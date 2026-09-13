from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings


print("Loading PDFs from 'docs' folder...")
loader = PyPDFDirectoryLoader("docs") 
documents = loader.load()

print(f"Loaded {len(documents)} pages in total.")

print("Splitting text...")
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
docs = text_splitter.split_documents(documents)

embeddings = OpenAIEmbeddings(
    openai_api_key="sk-jOn337n0y1yYP7kWTQVFRzuCsvfXlA5Y56kUDkRaQeoqhORC" , 
    openai_api_base="https://api.gapgpt.app/v1" 
    
)

print("Creating Vector Database...")
vectorstore = FAISS.from_documents(docs, embeddings)

vectorstore.save_local("my_vector_db") 
print("Done! Database saved to 'my_vector_db' folder.")
