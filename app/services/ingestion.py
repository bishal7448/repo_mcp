from typing import List
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import Document
from app.db.vector import vector_store_factory
from app.repositories.metadata import store_ingested_repo

async def ingest_documents_async(documents: List[Document], repo_name: str = None):
    """Async version of document ingestion with detailed logging and repo tracking"""
    print(f"🔄 Starting async ingestion of {len(documents)} documents")
    
    if repo_name:
        print(f"📍 Repository: {repo_name}")

    try:
        # Get vector store
        vector_store = vector_store_factory.create()
        print(f"✅ Vector store retrieved: {type(vector_store)}")

        # Create storage context
        vector_store_context = StorageContext.from_defaults(vector_store=vector_store)
        print(f"✅ Vector Store context created: {type(vector_store_context)}")

        # Process documents and ensure repo metadata
        print("🔄 Processing documents through pipeline...")
        ingested_files = []
        
        for i, doc in enumerate(documents):
            print(f"📄 Doc {i + 1}: {doc.doc_id} - {len(doc.text)} chars")
            print(f"   Metadata: {doc.metadata}")
            
            # Ensure repo metadata is properly set
            if repo_name and "repo" not in doc.metadata:
                doc.metadata["repo"] = repo_name
                print(f"   ✅ Added repo metadata: {repo_name}")
            
            # Track ingested file paths
            file_path = doc.metadata.get("file_path", doc.doc_id)
            if file_path not in ingested_files:
                ingested_files.append(file_path)

        # Run the ingestion
        print("🚀 Starting vector store ingestion...")
        vc_store_index = VectorStoreIndex.from_documents(
            documents=documents,
            storage_context=vector_store_context,
            show_progress=True,
        )
        print("✅ Document Ingestion completed Successfully")

        # Store repository metadata if repo_name is provided
        if repo_name and ingested_files:
            store_success = store_ingested_repo(repo_name, ingested_files)
            if store_success:
                print(f"✅ Repository metadata stored for {repo_name}")
            else:
                print(f"⚠️ Failed to store repository metadata for {repo_name}")

        return vc_store_index

    except Exception as e:
        print(f"❌ Error in async ingestion: {str(e)}")
        import traceback
        traceback.print_exc()
        raise e
