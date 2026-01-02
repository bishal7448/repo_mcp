import asyncio
import base64
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import aiohttp
import requests
from llama_index.core.schema import Document

logger = logging.getLogger(__name__)

class GithubFileLoader:
    """
    GitHub file loader that fetches specific files asynchronously.

    Returns LlamaIndex Document objects for each successfully loaded file.
    """

    def __init__(
        self,
        github_token: Optional[str] = None,
        concurrent_requests: int = 10,
        timeout: int = 30,
        retries: int = 3,
    ):
        """
        Initialize GitHub file loader.

        Args:
            github_token: GitHub API token for higher rate limits
            concurrent_requests: Number of concurrent requests
            timeout: Request timeout in seconds
            retries: Number of retry attempts for failed requests
        """
        self.github_token = github_token
        self.concurrent_requests = concurrent_requests
        self.timeout = timeout
        self.retries = retries

        # Setup headers
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "LlamaIndex-GitHub-Loader/1.0",
        }

        if self.github_token:
            self.headers["Authorization"] = f"token {self.github_token}"

    def fetch_repository_files(
        self,
        repo_url: str,
        file_extensions: Optional[List[str]] = None,
        branch: str = "main",
    ) -> Tuple[List[str], str]:
        """
        Fetch files from GitHub repository using GitHub API

        Args:
            repo_url: GitHub repository URL or owner/repo format
            file_extensions: List of file extensions to filter. If None, fetch all files.
            branch: Branch name to fetch from

        Returns:
            Tuple of (list_of_file_paths, status_message)
        """
        try:
            # Parse GitHub URL to extract owner and repo
            repo_name = self._parse_repo_name(repo_url)
            if not repo_name:
                return (
                    [],
                    "Invalid GitHub URL format. Use: https://github.com/owner/repo or owner/repo",
                )

            # GitHub API endpoint for repository tree
            api_url = f"https://api.github.com/repos/{repo_name}/git/trees/{branch}?recursive=1"

            # Make request with authentication if token is available
            response = requests.get(api_url, headers=self.headers, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                filtered_files = []

                # Filter for specified file extensions
                for item in data.get("tree", []):
                    if item["type"] == "blob":
                        file_path = item["path"]
                        
                        # If file_extensions is None, include all files
                        if file_extensions is None:
                            filtered_files.append(file_path)
                            continue
                            
                        # Check if file has any of the specified extensions
                        if any(
                            file_path.lower().endswith(ext.lower())
                            for ext in file_extensions
                        ):
                            filtered_files.append(file_path)

                if filtered_files:
                    ext_str = ", ".join(file_extensions) if file_extensions else "all files"
                    return (
                        filtered_files,
                        f"Found {len(filtered_files)} files ({ext_str}) in {repo_name}/{branch}",
                    )
                else:
                    ext_str = ", ".join(file_extensions) if file_extensions else "all files"
                    return (
                        [],
                        f"No files ({ext_str}) found in repository {repo_name}/{branch}",
                    )

            elif response.status_code == 404:
                return (
                    [],
                    f"Repository '{repo_name}' not found or branch '{branch}' doesn't exist",
                )
            elif response.status_code == 403:
                if "rate limit" in response.text.lower():
                    return (
                        [],
                        "GitHub API rate limit exceeded. Consider using a GitHub token.",
                    )
                else:
                    return (
                        [],
                        "Access denied. Repository may be private or require authentication.",
                    )
            else:
                return (
                    [],
                    f"GitHub API Error: {response.status_code} - {response.text[:200]}",
                )

        except requests.exceptions.Timeout:
            return [], f"Request timeout after {self.timeout} seconds"
        except requests.exceptions.RequestException as e:
            return [], f"Network error: {str(e)}"
        except Exception as e:
            return [], f"Unexpected error: {str(e)}"

    def _parse_repo_name(self, repo_url: str) -> Optional[str]:
        """
        Parse repository URL to extract owner/repo format

        Args:
            repo_url: GitHub repository URL or owner/repo format

        Returns:
            Repository name in "owner/repo" format or None if invalid
        """
        if "github.com" in repo_url:
            # Extract from full URL
            parts = (
                repo_url.replace("https://github.com/", "")
                .replace("http://github.com/", "")
                .strip("/")
                .split("/")
            )
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"
        else:
            # Assume format is owner/repo
            parts = repo_url.strip().split("/")
            if len(parts) == 2 and all(part.strip() for part in parts):
                return repo_url.strip()

        return None

    def fetch_markdown_files(
        self, repo_url: str, branch: str = "main"
    ) -> Tuple[List[str], str]:
        """
        Fetch markdown files from GitHub repository (backward compatibility method)

        Args:
            repo_url: GitHub repository URL or owner/repo format
            branch: Branch name to fetch from

        Returns:
            Tuple of (list_of_markdown_files, status_message)
        """
        return self.fetch_repository_files(
            repo_url=repo_url, file_extensions=[".md", ".mdx"], branch=branch
        )

    async def load_files(
        self, repo_name: str, file_paths: List[str], branch: str = "main"
    ) -> Tuple[List[Document], List[str]]:
        """
        Load files from GitHub repository asynchronously.

        Args:
            repo_name: Repository name in format "owner/repo"
            file_paths: List of file paths to load
            branch: Branch name to load from

        Returns:
            Tuple of (successfully_loaded_documents, failed_file_paths)
        """
        if not file_paths:
            return [], []

        # Validate repo name format
        if not re.match(r"^[^/]+/[^/]+$", repo_name):
            raise ValueError(f"Invalid repo format: {repo_name}. Expected 'owner/repo'")

        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.concurrent_requests)

        # Create session
        connector = aiohttp.TCPConnector(limit=self.concurrent_requests)
        timeout_config = aiohttp.ClientTimeout(total=self.timeout)

        async with aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout_config
        ) as session:
            # Create tasks for all files
            tasks = []
            for file_path in file_paths:
                task = asyncio.create_task(
                    self._fetch_file_with_retry(
                        session, semaphore, repo_name, file_path, branch
                    )
                )
                tasks.append(task)

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        documents = []
        failed_files = []

        for i, result in enumerate(results):
            file_path = file_paths[i]

            if isinstance(result, Exception):
                logger.error(f"Failed to load {file_path}: {result}")
                failed_files.append(file_path)
            elif result is None:
                logger.warning(f"No content returned for {file_path}")
                failed_files.append(file_path)
            else:
                documents.append(result)

        logger.info(
            f"Successfully loaded {len(documents)} files, failed: {len(failed_files)}"
        )
        return documents, failed_files

    async def _fetch_file_with_retry(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        repo_name: str,
        file_path: str,
        branch: str,
    ) -> Optional[Document]:
        """Fetch a single file with retry logic."""
        async with semaphore:
            for attempt in range(self.retries + 1):
                try:
                    return await self._fetch_single_file(
                        session, repo_name, file_path, branch
                    )
                except Exception as e:
                    if attempt == self.retries:
                        logger.error(
                            f"Failed to fetch {file_path} after {self.retries + 1} attempts: {e}"
                        )
                        raise
                    else:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {file_path}: {e}"
                        )
                        await asyncio.sleep(2**attempt)  # Exponential backoff

        return None

    async def _fetch_single_file(
        self,
        session: aiohttp.ClientSession,
        repo_name: str,
        file_path: str,
        branch: str,
    ) -> Document:
        """Fetch a single file from GitHub API."""
        # Clean file path
        clean_path = file_path.strip("/")

        # Build API URL
        api_url = f"https://api.github.com/repos/{repo_name}/contents/{clean_path}"
        params = {"ref": branch}

        logger.debug(f"Fetching: {api_url}")

        async with session.get(api_url, params=params) as response:
            if response.status == 404:
                raise FileNotFoundError(f"File not found: {file_path}")
            elif response.status == 403:
                raise PermissionError("API rate limit exceeded or access denied")
            elif response.status != 200:
                raise Exception(f"HTTP {response.status}: {await response.text()}")

            data = await response.json()

            # Handle directory case
            if isinstance(data, list):
                raise ValueError(f"Path {file_path} is a directory, not a file")

            # Decode file content
            if data.get("encoding") == "base64":
                try:
                    content_bytes = base64.b64decode(data["content"])
                    content_text = content_bytes.decode("utf-8")
                except Exception as e:
                    logger.warning(f"Failed to decode {file_path}: {e}")
                    # Try to decode as latin-1 as fallback
                    content_text = content_bytes.decode("latin-1", errors="ignore")
            else:
                raise ValueError(f"Unsupported encoding: {data.get('encoding')}")

            # Create Document
            document = self._create_document(
                content=content_text,
                file_path=clean_path,
                repo_name=repo_name,
                branch=branch,
                file_data=data,
            )

            return document

    def _create_document(
        self, content: str, file_path: str, repo_name: str, branch: str, file_data: Dict
    ) -> Document:
        """Create a LlamaIndex Document from file content and metadata."""

        # Extract file info
        filename = Path(file_path).name
        file_extension = Path(file_path).suffix.lower()
        directory = (
            str(Path(file_path).parent) if Path(file_path).parent != Path(".") else ""
        )

        # Build URLs
        html_url = f"https://github.com/{repo_name}/blob/{branch}/{file_path}"
        raw_url = file_data.get("download_url", "")

        # Create metadata
        metadata = {
            "file_path": file_path,
            "file_name": filename,
            "file_extension": file_extension,
            "directory": directory,
            "repo": repo_name,
            "branch": branch,
            "sha": file_data.get("sha", ""),
            "size": file_data.get("size", 0),
            "url": html_url,
            "raw_url": raw_url,
            "type": file_data.get("type", "file"),
        }

        # Create document with unique ID
        doc_id = f"{repo_name}:{branch}:{file_path}"

        document = Document(
            text=content,
            doc_id=doc_id,
            metadata=metadata,  # For backward compatibility
        )

        return document

    def load_files_sync(
        self, repo_name: str, file_paths: List[str], branch: str = "main"
    ) -> Tuple[List[Document], List[str]]:
        """
        Synchronous wrapper for load_files.

        Args:
            repo_name: Repository name in format "owner/repo"
            file_paths: List of file paths to load
            branch: Branch name to load from

        Returns:
            Tuple of (successfully_loaded_documents, failed_file_paths)
        """

        return asyncio.run(self.load_files(repo_name, file_paths, branch))


# Convenience functions
async def load_github_files_async(
    repo_name: str,
    file_paths: List[str],
    branch: str = "main",
    github_token: Optional[str] = None,
    concurrent_requests: int = 10,
) -> Tuple[List[Document], List[str]]:
    """
    Convenience function to load GitHub files asynchronously.

    Args:
        repo_name: Repository name in format "owner/repo"
        file_paths: List of file paths to load
        branch: Branch name to load from
        github_token: GitHub API token
        concurrent_requests: Number of concurrent requests

    Returns:
        Tuple of (documents, failed_files)
    """
    loader = GithubFileLoader(
        github_token=github_token, concurrent_requests=concurrent_requests
    )
    return await loader.load_files(repo_name, file_paths, branch)


def load_github_files(
    repo_name: str,
    file_paths: List[str],
    branch: str = "main",
    github_token: Optional[str] = None,
    concurrent_requests: int = 10,
) -> Tuple[List[Document], List[str]]:
    """
    Convenience function to load GitHub files synchronously.

    Args:
        repo_name: Repository name in format "owner/repo"
        file_paths: List of file paths to load
        branch: Branch name to load from
        github_token: GitHub API token
        concurrent_requests: Number of concurrent requests

    Returns:
        Tuple of (documents, failed_files)
    """
    loader = GithubFileLoader(
        github_token=github_token, concurrent_requests=concurrent_requests
    )
    return loader.load_files_sync(repo_name, file_paths, branch)


def fetch_markdown_files(
    repo_url: str, github_token: Optional[str] = None, branch: str = "main"
) -> Tuple[List[str], str]:
    """
    Convenience function to fetch markdown files from GitHub repository

    Args:
        repo_url: GitHub repository URL or owner/repo format
        github_token: GitHub API token for higher rate limits
        branch: Branch name to fetch from

    Returns:
        Tuple of (list_of_files, status_message)
    """
    loader = GithubFileLoader(github_token=github_token)
    return loader.fetch_markdown_files(repo_url, branch)


def fetch_repository_files(
    repo_url: str,
    file_extensions: Optional[List[str]] = None,
    github_token: Optional[str] = None,
    branch: str = "main",
) -> Tuple[List[str], str]:
    """
    Convenience function to fetch files with specific extensions from GitHub repository

    Args:
        repo_url: GitHub repository URL or owner/repo format
        file_extensions: List of file extensions to filter. If None, fetch all files.
        github_token: GitHub API token for higher rate limits
        branch: Branch name to fetch from

    Returns:
        Tuple of (list_of_files, status_message)
    """
    loader = GithubFileLoader(github_token=github_token)
    return loader.fetch_repository_files(repo_url, file_extensions, branch)


# Example usage
if __name__ == "__main__":
    # Example file paths
    file_paths = [
        "docs/contribute/docs.mdx",
        "docs/contribute/ml-handlers.mdx",
        "docs/contribute/community.mdx",
        "docs/contribute/python-coding-standards.mdx",
        "docs/features/data-integrations.mdx",
        "docs/features/ai-integrations.mdx",
        "docs/integrations/ai-engines/langchain_embedding.mdx",
        "docs/integrations/ai-engines/langchain.mdx",
        "docs/integrations/ai-engines/google_gemini.mdx",
        "docs/integrations/ai-engines/anomaly.mdx",
        "docs/integrations/ai-engines/amazon-bedrock.mdx",
    ]

    # Load files synchronously
    documents, failed = load_github_files(
        repo_name="mindsdb/mindsdb",
        file_paths=file_paths,
        branch="main",  # Optional
    )

    print(f"Loaded {len(documents)} documents")
    print(f"Failed to load {len(failed)} files: {failed}")

    # Print first document info
    if documents:
        doc = documents[0]
        print("\nFirst document:")
        print(f"ID: {doc.doc_id}")
        print(f"File: {doc.metadata['file_path']}")
        print(f"Size: {len(doc.text)} characters")
        print(f"Content preview: {doc.text[:200]}...")
