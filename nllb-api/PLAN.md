# Fix Swagger UI for Airgapped Environments

## Problem

Swagger UI loads but shows no content when running in Kubernetes (airgapped environment).

## Root Cause

The monkey patching of `get_swagger_ui_html` in `server/plugins/swagger_ui.py` happens **after** FastAPI has already set up the docs route.

**Order of operations (current - broken):**

1. `FastAPI()` constructor is called (`app.py:164`)
2. FastAPI's `__init__` calls `self.setup()`
3. `setup()` registers `/api/schema/swagger` route using `get_swagger_ui_html` **with CDN URLs**
4. Later (`app.py:240`), `setup_swagger_ui()` monkey patches `get_swagger_ui_html`

The patch comes too late - the docs endpoint already uses CDN URLs which are unreachable in airgapped environments.

## Proposed Solution: Custom Swagger Endpoint (Option A)

Disable FastAPI's built-in docs and create a custom endpoint that explicitly uses local assets.

### Changes Required

#### 1. Modify `server/app.py`

```python
# Change this:
fastapi_app = FastAPI(
    title=app_name,
    version="4.2.0",
    docs_url=f"{config.server_root_path}/schema/swagger",  # Remove this
    ...
)

# To this:
fastapi_app = FastAPI(
    title=app_name,
    version="4.2.0",
    docs_url=None,  # Disable built-in docs
    ...
)
```

#### 2. Rewrite `server/plugins/swagger_ui.py`

Instead of monkey patching, create an explicit route:

```python
from pathlib import Path
from os import environ

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse


def setup_swagger_ui(app: FastAPI, server_root_path: str = "/api") -> None:
    """
    Set up custom Swagger UI endpoint with local assets for airgapped environments.
    """
    home_dir = Path(environ.get("HOME", str(Path.home())))
    swagger_ui_assets_path = home_dir / "swagger-ui-assets"
    
    # Determine asset URLs based on availability
    if swagger_ui_assets_path.exists():
        css_file = swagger_ui_assets_path / "swagger-ui.css"
        js_file = swagger_ui_assets_path / "swagger-ui-bundle.js"
        if css_file.exists() and js_file.exists():
            swagger_css_url = f"{server_root_path}/swagger-ui-assets/swagger-ui.css"
            swagger_js_url = f"{server_root_path}/swagger-ui-assets/swagger-ui-bundle.js"
        else:
            # Fall back to CDN if local files missing
            swagger_css_url = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"
            swagger_js_url = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"
    else:
        # Fall back to CDN if directory doesn't exist
        swagger_css_url = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"
        swagger_js_url = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"

    @app.get(f"{server_root_path}/schema/swagger", include_in_schema=False)
    async def custom_swagger_ui() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url=f"{server_root_path}/schema/openapi.json",
            title=f"{app.title} - Swagger UI",
            swagger_js_url=swagger_js_url,
            swagger_css_url=swagger_css_url,
            swagger_favicon_url="",
        )
```

#### 3. Update `server/app.py` to always call `setup_swagger_ui`

```python
# Change this (around line 234-240):
if swagger_ui_assets_path.exists():
    fastapi_app.mount(...)
    setup_swagger_ui(fastapi_app, config.server_root_path)

# To this:
if swagger_ui_assets_path.exists():
    fastapi_app.mount(
        f"{config.server_root_path}/swagger-ui-assets",
        StaticFiles(directory=str(swagger_ui_assets_path)),
        name="swagger-ui-assets",
    )

# Always set up swagger UI (will use CDN fallback if assets don't exist)
setup_swagger_ui(fastapi_app, config.server_root_path)
```

### Benefits

1. **Explicit control** - No monkey patching, clear code flow
2. **Graceful fallback** - Uses CDN when local assets unavailable (dev environment)
3. **Airgapped support** - Uses local assets in Docker/K8s
4. **Simpler code** - Removes complex monkey patching and custom script injection

### Optional: Keep Custom Styling

If the custom JavaScript (hide servers dropdown, add openapi.json link) is needed, it can be added by creating a fully custom HTML response instead of using `get_swagger_ui_html`.

## Testing

1. **Local development** (no assets): Should fall back to CDN and work
2. **Docker**: Should use local assets from `/home/user/swagger-ui-assets/`
3. **Kubernetes (airgapped)**: Should use local assets and work without internet
