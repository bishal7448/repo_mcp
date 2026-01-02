import asyncio
import os
import time
import traceback
from typing import Dict, List, Optional

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nicegui import ui, app
from dotenv import load_dotenv

from llama_index.core import Settings
from llama_index.core.text_splitter import SentenceSplitter

from app.core.config import settings
from app.llm.client import llm_provider
from app.llm.embedding import embedding_provider
from app.repositories.metadata import (
    get_available_repos,
    get_repo_details,
    delete_repository_data,
    get_repository_stats
)
from app.services.github import fetch_markdown_files as fetch_files_with_loader
from app.services.github import fetch_repository_files, load_github_files
from app.services.ingestion import ingest_documents_async
from app.services.search import QueryRetriever

load_dotenv()

# Initialize LLM and embedding models
Settings.llm = llm_provider.get_llm()
Settings.embed_model = embedding_provider.get_embedding()
Settings.node_parser = SentenceSplitter(chunk_size=3072)

ENABLE_REPO_MANAGEMENT = os.getenv("ENABLE_REPO_MANAGEMENT", "true").lower() == "true"

@ui.page('/')
def index_page():
    # Page Layout
    ui.add_head_html('<style>body { background-color: #f0f4f8; }</style>')
    
    # Header
    with ui.header().classes('bg-slate-800 text-white shadow-lg items-center px-4 py-2'):
        ui.icon('library_books', size='2em').classes('mr-2')
        ui.label('Repo-MCP: Repository Documentation RAG System').classes('text-xl font-bold')

    # Tabs interface
    with ui.tabs().classes('w-full') as tabs:
        ingestion_tab = ui.tab('Ingestion', icon='download')
        query_tab = ui.tab('Query', icon='search')
        if ENABLE_REPO_MANAGEMENT:
            management_tab = ui.tab('Management', icon='settings')
        api_tab = ui.tab('API', icon='api')
        about_tab = ui.tab('About', icon='info')

    with ui.tab_panels(tabs, value=ingestion_tab).classes('w-full p-4 bg-transparent error-none'):
        
        # --- INGESTION TAB ---
        with ui.tab_panel(ingestion_tab):
            with ui.card().classes('w-full max-w-4xl mx-auto p-4'):
                ui.markdown('### 🚀 Documentation Ingestion')
                ui.markdown('**Step 1:** Fetch files')
                ui.markdown('**Step 2:** Ingest into Vector DB')
                
                repo_url_input = ui.input('GitHub Repository URL', placeholder='owner/repo or https://github.com/owner/repo').classes('w-full')
                
                # Container for dynamic content
                files_area = ui.column().classes('w-full')
                
                async def discover_files():
                    files_area.clear()
                    url = repo_url_input.value
                    if not url:
                        ui.notify('Please enter a valid URL', type='warning')
                        return
                    
                    with files_area:
                        ui.spinner('dots', size='lg').classes('self-center')
                    
                    # Fetch files
                    files, message = await asyncio.get_event_loop().run_in_executor(
                        None, fetch_files_with_loader, url
                    )
                    
                    files_area.clear()
                    if not files:
                        ui.notify(message or 'No md files found', type='negative')
                        return
                    
                    ui.notify(f'Found {len(files)} files', type='positive')
                    
                    # File Selection Area
                    with files_area:
                        ui.label(f'Select Files from {url}').classes('text-lg font-bold mt-4')
                        
                        checkboxes = []
                        with ui.row():
                            ui.button('Select All', on_click=lambda: [c.set_value(True) for c in checkboxes]).props('flat dense')
                            ui.button('Clear', on_click=lambda: [c.set_value(False) for c in checkboxes]).props('flat dense')
                        
                        with ui.scroll_area().classes('h-64 border rounded p-2'):
                            for f in files:
                                c = ui.checkbox(f, value=False)
                                checkboxes.append(c)
                        
                        # Progress Area
                        progress_log = ui.log().classes('w-full h-48 bg-gray-100 p-2 rounded mt-4 text-xs font-mono')
                        progress_bar = ui.linear_progress(value=0).props('instant-feedback').classes('mt-2')
                        progress_status = ui.label('Ready').classes('text-sm text-gray-600')

                        async def run_ingestion():
                            selected = [c.text for c in checkboxes if c.value]
                            if not selected:
                                ui.notify('No files selected', type='warning')
                                return
                            
                            step1_btn.disable()
                            progress_log.clear()
                            progress_bar.value = 0
                            
                            # Step 1: Load Files
                            progress_status.set_text('Step 1: Loading files...')
                            repo_name = url.strip().replace('https://github.com/', '').strip('/')
                            
                            loaded_docs = []
                            failed_docs = []
                            
                            total_files = len(selected)
                            batch_size = 10
                            for i in range(0, total_files, batch_size):
                                batch = selected[i:i+batch_size]
                                progress_log.push(f'Loading batch {i//batch_size + 1}...')
                                
                                docs, failed = await asyncio.get_event_loop().run_in_executor(
                                    None, 
                                    lambda: load_github_files(
                                        repo_name=repo_name,
                                        file_paths=batch,
                                        github_token=settings.GITHUB_API_KEY
                                    )
                                )
                                loaded_docs.extend(docs)
                                failed_docs.extend(failed)
                                
                                # Add repo metadata
                                for doc in docs:
                                    if "repo" not in doc.metadata:
                                        doc.metadata["repo"] = repo_name
                                
                                progress_bar.value = (i + len(batch)) / total_files * 0.5
                                # force ui update not needed in async usually, but nicegui handles it
                                
                            progress_log.push(f'Loaded {len(loaded_docs)} documents. Failed: {len(failed_docs)}')
                            
                            # Step 2: Vector Ingestion
                            if loaded_docs:
                                progress_status.set_text('Step 2: Vector Ingestion (this may take a while)...')
                                progress_log.push('Starting vector ingestion...')
                                try:
                                    await ingest_documents_async(loaded_docs, repo_name)
                                    progress_bar.value = 1.0
                                    progress_status.set_text('Ingestion Complete!')
                                    ui.notify('Ingestion Complete!', type='positive')
                                    progress_log.push('Vector ingestion finished successfully.')
                                except Exception as e:
                                    progress_status.set_text('Error during vector ingestion')
                                    progress_log.push(f'Error: {str(e)}')
                                    ui.notify('Ingestion Failed', type='negative')
                            else:
                                ui.notify('No documents loaded to ingest.', type='warning')
                            
                            step1_btn.enable()

                        step1_btn = ui.button('Start Ingestion', on_click=run_ingestion).classes('mt-4 w-full bg-blue-600 text-white')

                ui.button('Discover Docs', on_click=discover_files).classes('mt-2')

        # --- QUERY TAB ---
        with ui.tab_panel(query_tab):
            with ui.row().classes('w-full'):
                # Left Col: Chat
                with ui.column().classes('w-2/3'):
                    ui.markdown('### 🤖 AI Documentation Assistant')
                    
                    repos = get_available_repos() or []
                    repo_select = ui.select(repos, label='Select Repository', with_input=True).classes('w-full')
                    
                    def refresh_repos():
                        new_repos = get_available_repos() or []
                        repo_select.options = new_repos
                        repo_select.update()
                        ui.notify('Repositories Refreshed')

                    ui.button('Refresh Repos', on_click=refresh_repos).props('flat dense')
                    
                    chat_container = ui.column().classes('w-full h-96 border rounded p-4 bg-white overflow-y-auto')
                    
                    query_input = ui.input('Ask a question...').classes('w-full').props('rounded outlined')
                    
                    # Sources display references
                    sources_display = ui.column().classes('w-full')

                    async def process_query():
                        q = query_input.value
                        repo = repo_select.value
                        if not q: return
                        if not repo: 
                            ui.notify('Select a repository first', type='warning')
                            return
                        
                        query_input.value = ''
                        with chat_container:
                            ui.chat_message(q, name='User', sent=True)
                            spinner = ui.spinner('dots')
                        
                        try:
                            # Run query
                            retriever = QueryRetriever(repo)
                            result = await asyncio.get_event_loop().run_in_executor(
                                None, lambda: retriever.make_query(q, "default")
                            )
                            
                            chat_container.remove(spinner)
                            
                            response_text = result.get('response', 'No response')
                            source_nodes = result.get('source_nodes', [])
                            
                            with chat_container:
                                ui.chat_message(response_text, name='AI', sent=False)
                            
                            # Update sources display
                            sources_display.clear()
                            with sources_display:
                                ui.markdown('### Sources')
                                for node in source_nodes:
                                    with ui.expansion(f"Source: {node.get('file_name', 'unknown')} ({node.get('score', 0):.2f})"):
                                        ui.markdown(f"```text\n{node.get('text', '')}\n```")
                                        
                        except Exception as e:
                            print(e)
                            if 'spinner' in locals(): chat_container.remove(spinner)
                            ui.notify(f'Error: {str(e)}', type='negative')

                    query_input.on('keydown.enter', process_query)
                    ui.button('Send', on_click=process_query).classes('mt-2')

                # Right Col: Sources
                with ui.column().classes('w-1/3 p-2 bg-gray-50 h-full border-l'):
                    with sources_display:
                        ui.label('Sources will appear here...')

        # --- MANAGEMENT TAB ---
        if ENABLE_REPO_MANAGEMENT:
            with ui.tab_panel(management_tab):
                ui.markdown('### 🗂️ Repository Management')
                
                stats_container = ui.column().classes('w-full mb-4')
                
                async def refresh_stats():
                    stats_container.clear()
                    try:
                        stats = await asyncio.get_event_loop().run_in_executor(None, get_repository_stats)
                        with stats_container:
                            ui.json_editor({'content': {'json': stats}}).classes('w-full')
                    except Exception as e:
                        ui.notify(f'Failed to load stats: {e}', type='negative')

                ui.button('Refresh Stats', on_click=refresh_stats).props('flat')
                
                ui.separator()
                
                repo_table_container = ui.column().classes('w-full')
                delete_repo_select = ui.select([], label='Select Repo to Delete').classes('w-64')

                async def refresh_repo_table():
                    repo_table_container.clear()
                    try:
                        details = await asyncio.get_event_loop().run_in_executor(None, get_repo_details)
                    except: details = []
                    
                    rows = []
                    if details:
                        for d in details:
                            rows.append({
                                'repo_name': d.get('repo_name'),
                                'file_count': d.get('file_count'),
                                'last_updated': str(d.get('last_updated'))
                            })
                    
                    with repo_table_container:
                        ui.table(
                            columns=[
                                {'name': 'repo_name', 'label': 'Repository', 'field': 'repo_name'},
                                {'name': 'file_count', 'label': 'Files', 'field': 'file_count'},
                                {'name': 'last_updated', 'label': 'Last Updated', 'field': 'last_updated'},
                            ],
                            rows=rows,
                            row_key='repo_name'
                        ).classes('w-full')

                    # Refresh delete dropdown too
                    repos = get_available_repos() or []
                    delete_repo_select.options = repos
                    delete_repo_select.update()
                        
                ui.button('Refresh Table', on_click=refresh_repo_table).props('flat')
                
                # Initial loads on tab valid? No easier to click. Or use timer.
                # Just call once
                refresh_stats()
                refresh_repo_table()

                ui.separator().classes('my-4')
                
                ui.markdown('#### 🗑️ Delete Repository')
                
                async def delete_repo():
                    repo = delete_repo_select.value
                    if not repo: return
                    
                    # Confirm dialog
                    with ui.dialog() as dialog, ui.card():
                        ui.label(f'Are you sure you want to delete {repo}?')
                        with ui.row():
                            ui.button('Cancel', on_click=dialog.close)
                            def confirm():
                                dialog.close()
                                try:
                                    res = delete_repository_data(repo)
                                    ui.notify(res.get('message', 'Deleted'), type='positive')
                                    refresh_repo_table() # Refresh table
                                    refresh_stats()
                                except Exception as e:
                                    ui.notify(str(e), type='negative')
                                    
                            ui.button('Delete', on_click=confirm, color='red')
                    dialog.open()

                ui.button('Delete Repository', on_click=delete_repo, color='red').classes('mt-2')


        # --- API TAB ---
        with ui.tab_panel(api_tab):
            ui.markdown('### 🔧 GitHub Tools API')
            
            with ui.row():
                repo_in = ui.input('Repository', placeholder='owner/repo')
                path_in = ui.input('File Path', placeholder='README.md')
                
            api_result = ui.json_editor({'content': {'json': {}}}).classes('w-full h-64')
            
            async def get_file_content():
                try:
                    docs, failed = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: load_github_files(
                            repo_name=repo_in.value.strip(),
                            file_paths=[path_in.value.strip()],
                            github_token=settings.GITHUB_API_KEY
                        )
                    )
                    if docs:
                        api_result.properties['content']['json'] = {'content': docs[0].text, 'metadata': docs[0].metadata}
                    else:
                        api_result.properties['content']['json'] = {'error': 'File not found', 'failed': failed}
                    api_result.update()
                except Exception as e:
                    api_result.properties['content']['json'] = {'error': str(e)}
                    api_result.update()

            ui.button('Get File', on_click=get_file_content)

        # --- ABOUT TAB ---
        with ui.tab_panel(about_tab):
            ui.markdown('# 📚 Repo-MCP')
            ui.markdown('NiceGUI version of the Repository Documentation RAG System.')
            
            ui.link('NiceGUI Documentation', 'https://nicegui.io')

ui.run(title='Repo-MCP', port=8000)
