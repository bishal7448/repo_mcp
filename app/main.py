import asyncio
import os
import time
import traceback
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from uuid import uuid4

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
from app.services.github import fetch_repository_files as fetch_files_with_loader
from app.services.github import load_github_files
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
    ui.add_css(r'a:link, a:visited {color: inherit !important; text-decoration: none; font-weight: 500}')
    
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
                        None, lambda: fetch_files_with_loader(url, file_extensions=None)
                    )
                    
                    files_area.clear()
                    if not files:
                        ui.notify(message or 'No md files found', type='negative')
                        return
                    
                    ui.notify(f'Found {len(files)} files', type='positive')
                    
                    # Extract extensions for filter
                    extensions = sorted(list(set(os.path.splitext(f)[1].lower() for f in files)))
                    extensions.insert(0, 'All')

                    # File Selection Area
                    with files_area:
                        ui.label(f'Select Files from {url}').classes('text-lg font-bold mt-4')
                        
                        checkboxes = []
                        with ui.row().classes('items-center gap-4'):
                            filter_select = ui.select(extensions, value='All', label='Filter by Extension').classes('w-48')
                            
                            ui.button('Select Visible', on_click=lambda: [c.set_value(True) for c in checkboxes if c.visible]).props('flat dense')
                            ui.button('Clear All', on_click=lambda: [c.set_value(False) for c in checkboxes]).props('flat dense')
                        
                        with ui.scroll_area().classes('h-64 border rounded p-2'):
                            for f in files:
                                c = ui.checkbox(f, value=False)
                                c.classes('w-full') # block style
                                checkboxes.append(c)

                        def apply_filter(e):
                            ext = filter_select.value
                            for c in checkboxes:
                                if ext == 'All' or c.text.lower().endswith(ext):
                                    c.visible = True
                                else:
                                    c.visible = False
                        
                        filter_select.on_value_change(apply_filter)
                        
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
            with ui.row().classes('w-full no-wrap items-start'):
                # Left Col: Chat Wrapper
                chat_wrapper = ui.column().classes('w-2/3 h-full')
                with chat_wrapper:
                    ui.markdown('### 🤖 AI Assistant')
                    
                    repos = get_available_repos() or []
                    repo_select = ui.select(repos, label='Select Repository', with_input=True).classes('w-full')
                    
                    def refresh_repos():
                        new_repos = get_available_repos() or []
                        repo_select.options = new_repos
                        repo_select.update()
                        ui.notify('Repositories Refreshed')

                    with ui.row().classes('items-center w-full justify-between'):
                        ui.button('Refresh Repos', on_click=refresh_repos).props('flat dense')
                        source_switch = ui.switch('Show Sources', value=True)
                    
                    # Chat Setup
                    user_id = str(uuid4())
                    avatar = f'https://robohash.org/{user_id}?bgset=bg2'
                    
                    messages: List[Tuple[str, str, str, str]] = []

                    @ui.refreshable
                    def chat_messages(own_id: str) -> None:
                        if messages:
                            for uid, av, text, stamp in messages:
                                ui.chat_message(text=text, stamp=stamp, avatar=av, sent=own_id == uid)
                            ui.run_javascript('var el = document.getElementById("chat-container"); if(el) el.scrollTop = el.scrollHeight;')
                        else:
                            ui.label('No messages yet').classes('mx-auto my-36 text-gray-400')

                    with ui.column().classes('w-full h-96 border rounded p-4 bg-white overflow-y-auto').props('id=chat-container'):
                        chat_messages(user_id)
                    
                    query_input = ui.input('Ask a question...').classes('w-full').props('rounded outlined')
                    ui.button('Send', on_click=lambda: process_query()).classes('mt-2')

                # Right Col: Sources Wrapper
                sources_wrapper = ui.column().classes('w-1/3 p-2 bg-gray-50 h-full border-l')
                with sources_wrapper:
                    sources_display = ui.column().classes('w-full')
                    with sources_display:
                        ui.label('Sources will appear here...')

                # Toggle Logic
                def toggle_layout():
                    if source_switch.value:
                        sources_wrapper.visible = True
                        chat_wrapper.classes(remove='w-full', add='w-2/3')
                    else:
                        sources_wrapper.visible = False
                        chat_wrapper.classes(remove='w-2/3', add='w-full')
                
                source_switch.on('update:model-value', toggle_layout)

                async def process_query():
                    q = query_input.value
                    repo = repo_select.value
                    if not q: return
                    if not repo: 
                        ui.notify('Select a repository first', type='warning')
                        return
                    
                    stamp = datetime.now().strftime('%X')
                    messages.append((user_id, avatar, q, stamp))
                    query_input.value = ''
                    chat_messages.refresh()
                    
                    try:
                        # Run query
                        retriever = QueryRetriever(repo)
                        result = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: retriever.make_query(q, "default")
                        )
                        
                        response_text = result.get('response', 'No response')
                        source_nodes = result.get('source_nodes', [])
                        
                        system_stamp = datetime.now().strftime('%X')
                        messages.append(('REPO_MCP', 'https://robohash.org/REPO_MCP?bgset=bg2', response_text, system_stamp))
                        chat_messages.refresh()
                        
                        # Update sources display
                        sources_display.clear()
                        with sources_display:
                            ui.markdown('### Sources')
                            for node in source_nodes:
                                with ui.expansion(f"Source: {node.get('file_name', 'unknown')} ({node.get('score', 0):.2f})"):
                                    ui.markdown(f"```text\n{node.get('text', '')}\n```")
                                    
                    except Exception as e:
                        print(e)
                        ui.notify(f'Error: {str(e)}', type='negative')

                query_input.on('keydown.enter', process_query)

        # --- MANAGEMENT TAB ---
        if ENABLE_REPO_MANAGEMENT:
            with ui.tab_panel(management_tab):
                repo_content = ui.column().classes('w-full')

                async def show_repo_details(repo_data):
                    repo_content.clear()
                    with repo_content:
                        ui.button('Back to List', on_click=show_repo_list).props('flat icon=arrow_back')
                        
                        ui.markdown(f"### 📦 {repo_data.get('repo_name')}")
                        
                        with ui.card().classes('w-full p-4 mb-4'):
                            with ui.row().classes('w-full justify-between'):
                                ui.label(f"Files: {repo_data.get('file_count')}").classes('text-lg')
                                ui.label(f"Last Updated: {repo_data.get('last_updated')}").classes('text-gray-500')
                        
                        ui.markdown('#### 📄 Ingested Files')
                        files = repo_data.get('ingested_files', [])
                        if files:
                            with ui.scroll_area().classes('h-64 border rounded p-2 w-full'):
                                for f in files:
                                    ui.label(f).classes('block border-b py-1')
                        else:
                            ui.label('No files listed (might be legacy data)').classes('text-gray-500')

                        ui.separator().classes('my-4')
                        
                        async def delete_current_repo():
                            repo = repo_data.get('repo_name')
                            with ui.dialog() as dialog, ui.card():
                                ui.label(f'DELETE {repo}? This cannot be undone.')
                                with ui.row().classes('w-full justify-end'):
                                    ui.button('Cancel', on_click=dialog.close).props('flat')
                                    async def confirm():
                                        dialog.close()
                                        try:
                                            # Wrap blocking call
                                            res = await asyncio.get_event_loop().run_in_executor(None, lambda: delete_repository_data(repo))
                                            ui.notify(res.get('message', 'Deleted'), type='positive')
                                            show_repo_list()
                                        except Exception as e:
                                            ui.notify(str(e), type='negative')
                                    ui.button('Confirm Delete', on_click=confirm, color='red')
                            dialog.open()

                        ui.button('Delete Repository', on_click=delete_current_repo, color='red').props('icon=delete')

                async def show_repo_list():
                    repo_content.clear()
                    with repo_content:
                        ui.markdown('### 🗂️ Repository Management')
                        
                        # Stats
                        stats_container = ui.column().classes('w-full mb-4')
                        try:
                            stats = await asyncio.get_event_loop().run_in_executor(None, get_repository_stats)
                            with stats_container:
                                stat_rows = [
                                    {'metric': 'Total Repositories', 'value': stats.get('total_repositories', 0)},
                                    {'metric': 'Total Documents', 'value': stats.get('total_documents', 0)},
                                    {'metric': 'Total Files', 'value': stats.get('total_files', 0)},
                                ]
                                ui.table(
                                    columns=[
                                        {'name': 'metric', 'label': 'Metric', 'field': 'metric', 'align': 'left'},
                                        {'name': 'value', 'label': 'Value', 'field': 'value', 'align': 'left'},
                                    ],
                                    rows=stat_rows,
                                    row_key='metric'
                                ).classes('w-full')
                        except Exception as e:
                            ui.notify(f'Failed to load stats: {e}', type='negative')

                        ui.separator().classes('my-4')

                        # Table
                        try:
                            details = await asyncio.get_event_loop().run_in_executor(None, get_repo_details)
                        except: details = []
                        
                        rows = []
                        if details:
                            for d in details:
                                rows.append({
                                    'repo_name': d.get('repo_name'),
                                    'file_count': d.get('file_count'),
                                    'last_updated': str(d.get('last_updated')),
                                    'ingested_files': d.get('ingested_files', [])
                                })
                        
                        if not rows:
                             ui.label('No repositories found. Add one in the Ingestion tab.').classes('italic text-gray-500')
                        else:
                            ui.label('Click a row to view details').classes('text-xs text-gray-400 mb-2')
                            ui.table(
                                columns=[
                                    {'name': 'repo_name', 'label': 'Repository', 'field': 'repo_name', 'align': 'left'},
                                    {'name': 'file_count', 'label': 'Files', 'field': 'file_count', 'sortable': True},
                                    {'name': 'last_updated', 'label': 'Last Updated', 'field': 'last_updated', 'sortable': True},
                                ],
                                rows=rows,
                                row_key='repo_name',
                                pagination=10
                            ).classes('w-full').on('row-click', lambda e: show_repo_details(e.args[1]))
                        
                        ui.button('Refresh', on_click=show_repo_list).props('flat icon=refresh').classes('mt-4')

                # Initial load
                ui.timer(0, show_repo_list, once=True)


        # --- API TAB ---
        with ui.tab_panel(api_tab):
            ui.markdown('### 🔧 GitHub Tools API')
            
            with ui.row():
                repo_in = ui.input('Repository', placeholder='owner/repo')
                path_in = ui.input('File Path', placeholder='README.md')
                
            api_content = ui.column().classes('w-full')
            
            async def get_file_content():
                api_content.clear()
                with api_content:
                    ui.spinner('dots')
                
                try:
                    docs, failed = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: load_github_files(
                            repo_name=repo_in.value.strip(),
                            file_paths=[path_in.value.strip()],
                            github_token=settings.GITHUB_API_KEY
                        )
                    )
                    
                    api_content.clear()
                    with api_content:
                        if docs:
                            doc = docs[0]
                            # Metadata Table
                            ui.label('Metadata').classes('text-lg font-bold')
                            meta_rows = [{'key': k, 'value': str(v)} for k, v in doc.metadata.items()]
                            ui.table(
                                columns=[
                                    {'name': 'key', 'label': 'Key', 'field': 'key', 'align': 'left'},
                                    {'name': 'value', 'label': 'Value', 'field': 'value', 'align': 'left'},
                                ],
                                rows=meta_rows,
                                row_key='key',
                                pagination=5
                            ).classes('w-full mb-4')
                            
                            # Content
                            ui.label('Content').classes('text-lg font-bold')
                            with ui.expansion('Show File Content', icon='description').classes('w-full border rounded').props('default-opened'):
                                ui.code(doc.text, language='markdown').classes('w-full')
                        else:
                            ui.notify('File not found', type='warning')
                            if failed:
                                ui.label(f"Failed: {failed}").classes('text-red-500')
                                
                except Exception as e:
                    api_content.clear()
                    with api_content:
                         ui.label(f'Error: {str(e)}').classes('text-red-500 font-bold')
                    ui.notify(f'Error: {str(e)}', type='negative')

            ui.button('Get File', on_click=get_file_content)

        # --- ABOUT TAB ---
        with ui.tab_panel(about_tab):
            ui.markdown('# 📚 Repo-MCP')
            ui.markdown('NiceGUI version of the Repository RAG System.')
            
            ui.separator().classes('my-4')
            
            ui.markdown('## 🚀 Hackathon Project')
            ui.markdown('This project was built for the **TechSprint 2025**.')
            ui.markdown('Our goal is to assist developers in navigating and understanding complex codebases using RAG + MCP.')

            ui.separator().classes('my-4')

            ui.markdown('## 👥 Team Members')
            
            # Hardcoded Team Info
            team_members = [
                {'name': 'Jaydeep Biswas', 'username': 'Jaydeep1236', 'role': 'Team Lead & Dev'},
                {'name': 'Bishal Saha', 'username': 'bishal7448', 'role': 'RAG + MCP Specialist'},
                {'name': 'Debjit Saha', 'username': 'Debjit07-alpha', 'role': 'Ppt Designer & frontend'},
                {'name': 'Tamanna Khatick', 'username': 'tamannakhatick', 'role': 'Ppt Designer & Research'}
                
            ]

            with ui.row().classes('gap-4'):
                for member in team_members:
                    username = member['username']
                    with ui.card().classes('w-64 items-center p-4'):
                        # GitHub Avatar URL pattern
                        avatar_url = f"https://github.com/{username}.png"
                        profile_url = f"https://github.com/{username}"
                        
                        ui.image(avatar_url).classes('w-24 h-24 rounded-full mb-2')
                        ui.label(member['name']).classes('font-bold text-lg')
                        ui.label(member['role']).classes('text-sm text-gray-500 text-center')
                        ui.link(f'@{username}', profile_url, new_tab=True).classes('text-sm mt-2 text-blue-600')

            ui.separator().classes('my-4')
            
            ui.link('NiceGUI Documentation', 'https://nicegui.io')

ui.run(title='Repo-MCP', port=8000)
