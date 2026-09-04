import os
from pathlib import Path

from huggingface_hub import snapshot_download
from server.logging_config import get_logger

logger = get_logger(__name__)


def huggingface_download(repository: str) -> str:
    """
    Summary
    -------
    get the local huggingface model path, downloading if not found locally

    Parameters
    ----------
    repository (str) : the name of the Hugging Face repository

    Returns
    -------
    repository_path (str) : local path to the model
    """
    cache_dir = Path.home() / ".cache" / "huggingface"
    repo_name = repository.replace("/", "--")
    
    logger.debug(
        "Searching for model",
        repository=repository,
        cache_dir=str(cache_dir),
        repo_name=repo_name,
    )
    
    # Check hub format: hub/models--repo-name/snapshots/hash/
    hub_path = cache_dir / "hub" / f"models--{repo_name}" / "snapshots"
    if hub_path.exists():
        snapshots = [s for s in hub_path.iterdir() if s.is_dir()]
        if snapshots:
            logger.debug("Found model in hub/snapshots format", path=str(snapshots[0]))
            return str(snapshots[0])
    
    # Check hub format without snapshots: hub/models--repo-name/ (direct model files)
    hub_direct_path = cache_dir / "hub" / f"models--{repo_name}"
    if hub_direct_path.exists() and hub_direct_path.is_dir():
        # Check if it contains model files (not just snapshots directory)
        model_files = [f for f in hub_direct_path.iterdir() if f.is_file() or (f.is_dir() and f.name != "snapshots")]
        if model_files or (hub_direct_path / "snapshots").exists():
            # If snapshots exist, use first snapshot, otherwise use the directory itself
            snapshots_dir = hub_direct_path / "snapshots"
            if snapshots_dir.exists():
                snapshots = [s for s in snapshots_dir.iterdir() if s.is_dir()]
                if snapshots:
                    return str(snapshots[0])
            # Fallback: use the directory itself if it contains model files
            logger.debug("Found model in hub format (direct)", path=str(hub_direct_path))
            return str(hub_direct_path)
    
    # Check legacy format: models--repo-name/snapshots/hash/
    legacy_path = cache_dir / f"models--{repo_name}" / "snapshots"
    if legacy_path.exists():
        snapshots = [s for s in legacy_path.iterdir() if s.is_dir()]
        if snapshots:
            logger.debug("Found model in legacy/snapshots format", path=str(snapshots[0]))
            return str(snapshots[0])
    
    # Check legacy format without snapshots: models--repo-name/ (direct model files)
    legacy_direct_path = cache_dir / f"models--{repo_name}"
    if legacy_direct_path.exists() and legacy_direct_path.is_dir():
        # Check if snapshots directory exists first
        snapshots_dir = legacy_direct_path / "snapshots"
        if snapshots_dir.exists():
            snapshots = [s for s in snapshots_dir.iterdir() if s.is_dir()]
            if snapshots:
                logger.debug("Found model in legacy format (with snapshots)", path=str(snapshots[0]))
                return str(snapshots[0])
        # Fallback: check if directory contains model files directly
        model_files = [f for f in legacy_direct_path.iterdir() if f.is_file() or (f.is_dir() and f.name not in ["snapshots", "blobs", "refs"])]
        if model_files:
            logger.debug("Found model in legacy format (direct files)", path=str(legacy_direct_path))
            return str(legacy_direct_path)
    
    # Model not found locally - log what we found
    logger.warning(
        "Model not found in expected locations",
        repository=repository,
        cache_dir=str(cache_dir),
        cache_dir_exists=cache_dir.exists(),
        hub_dir_exists=(cache_dir / "hub").exists() if cache_dir.exists() else False,
    )
    if cache_dir.exists():
        # List what's actually in the cache directory
        try:
            contents = list(cache_dir.iterdir())
            logger.debug("Cache directory contents", contents=[str(c) for c in contents[:10]])
            if (cache_dir / "hub").exists():
                hub_contents = list((cache_dir / "hub").iterdir())
                logger.debug("Hub directory contents", contents=[str(c) for c in hub_contents[:10]])
        except Exception as e:
            logger.debug("Could not list cache directory", error=str(e))
    
    # Model not found locally - download if HUGGINGFACE_LOCAL_ONLY is not set
    huggingface_local_only = os.getenv("HUGGINGFACE_LOCAL_ONLY", "0")
    if huggingface_local_only in ("1", "true", "True"):
        raise FileNotFoundError(
            f"Model {repository} not found in {cache_dir}. "
            f"Run 'make download-models' to download models."
        )
    
    # Download the model
    try:
        model_path = snapshot_download(
            repo_id=repository,
            cache_dir=str(cache_dir),
        )
        return model_path
    except Exception as e:
        raise FileNotFoundError(
            f"Failed to download {repository}: {e}"
        ) from e
