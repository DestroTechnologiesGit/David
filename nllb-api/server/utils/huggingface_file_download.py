import os
from pathlib import Path

from huggingface_hub import hf_hub_download


def huggingface_file_download(repository: str, file: str) -> str:
    """
    Summary
    -------
    get the local huggingface file path, downloading if not found locally

    Parameters
    ----------
    repository (str) : the name of the Hugging Face repository
    file (str) : the filename to download

    Returns
    -------
    file_path (str) : local path to the file
    """
    cache_dir = Path.home() / ".cache" / "huggingface"
    repo_name = repository.replace("/", "--")
    
    # Check hub format: hub/models--repo-name/snapshots/hash/file
    hub_path = cache_dir / "hub" / f"models--{repo_name}" / "snapshots"
    if hub_path.exists():
        snapshots = [s for s in hub_path.iterdir() if s.is_dir()]
        if snapshots:
            file_path = snapshots[0] / file
            if file_path.exists():
                return str(file_path)
    
    # Check legacy format: models--repo-name/snapshots/hash/file
    legacy_path = cache_dir / f"models--{repo_name}" / "snapshots"
    if legacy_path.exists():
        snapshots = [s for s in legacy_path.iterdir() if s.is_dir()]
        if snapshots:
            file_path = snapshots[0] / file
            if file_path.exists():
                return str(file_path)
    
    # File not found locally - download if HUGGINGFACE_LOCAL_ONLY is not set
    huggingface_local_only = os.getenv("HUGGINGFACE_LOCAL_ONLY", "0")
    if huggingface_local_only in ("1", "true", "True"):
        raise FileNotFoundError(
            f"File {file} from {repository} not found in {cache_dir}. "
            f"Run 'make download-models' to download models."
        )
    
    # Download the file
    try:
        file_path = hf_hub_download(
            repo_id=repository,
            filename=file,
            cache_dir=str(cache_dir),
        )
        return file_path
    except Exception as e:
        raise FileNotFoundError(
            f"Failed to download {file} from {repository}: {e}"
        ) from e
