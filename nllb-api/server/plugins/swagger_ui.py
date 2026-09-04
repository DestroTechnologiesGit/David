from pathlib import Path
from os import environ

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html


def setup_swagger_ui(app: FastAPI, server_root_path: str = "/api") -> None:
    """
    Summary
    -------
    Set up custom Swagger UI for FastAPI to match whisper-asr-webservice look and feel

    Parameters
    ----------
    app (FastAPI)
        the FastAPI application instance

    server_root_path (str)
        the server root path
    """
    # Check if swagger-ui assets exist
    home_dir = Path(environ.get("HOME", str(Path.home())))
    swagger_ui_assets_path = home_dir / "swagger-ui-assets"
    if not swagger_ui_assets_path.exists():
        return

    css_file = swagger_ui_assets_path / "swagger-ui.css"
    js_file = swagger_ui_assets_path / "swagger-ui-bundle.js"
    if not (css_file.exists() and js_file.exists()):
        return

    # Monkey patch get_swagger_ui_html to use custom assets
    original_get_swagger_ui_html = get_swagger_ui_html

    def custom_get_swagger_ui_html(*args, **kwargs):
        from fastapi.responses import HTMLResponse
        
        html_response = original_get_swagger_ui_html(
            *args,
            **kwargs,
            swagger_favicon_url="",
            swagger_css_url=f"{server_root_path}/swagger-ui-assets/swagger-ui.css",
            swagger_js_url=f"{server_root_path}/swagger-ui-assets/swagger-ui-bundle.js",
        )
        # Inject custom JavaScript to hide servers dropdown and add openapi.json link
        openapi_json_url = f"{server_root_path}/schema/openapi.json"
        custom_script = f"""
        <script type='text/javascript'>
        const openapiJsonUrl = "{openapi_json_url}";
        
        function addOpenApiLink() {{
          const selectors = [
            '.swagger-ui .info .title',
            '.swagger-ui .info h2',
            '.swagger-ui .info h2.title',
            '.swagger-ui .info h2.main-title',
          ];
          
          let titleElement = null;
          for (const selector of selectors) {{
            titleElement = document.querySelector(selector);
            if (titleElement) break;
          }}
          
          if (titleElement) {{
            const existingLink = titleElement.querySelector('a[href="' + openapiJsonUrl + '"]') || 
                                (titleElement.parentElement && titleElement.parentElement.querySelector('a[href="' + openapiJsonUrl + '"]'));
            
            if (!existingLink) {{
              const link = document.createElement('a');
              link.href = openapiJsonUrl;
              link.textContent = '/openapi.json';
              link.style.marginLeft = '1rem';
              link.style.fontSize = '0.9em';
              link.style.color = '#3b49df';
              link.style.textDecoration = 'none';
              link.addEventListener('mouseenter', function() {{ this.style.textDecoration = 'underline'; }});
              link.addEventListener('mouseleave', function() {{ this.style.textDecoration = 'none'; }});
              
              if (titleElement.parentElement) {{
                titleElement.parentElement.insertBefore(link, titleElement.nextSibling);
              }} else {{
                titleElement.appendChild(document.createTextNode(' '));
                titleElement.appendChild(link);
              }}
            }}
          }}
        }}
        
        function hideServers() {{
          const selectors = [
            '.swagger-ui .scheme-container',
            '.swagger-ui .servers',
            '.swagger-ui .servers-container',
            '.swagger-ui select[data-name="servers"]',
            '.swagger-ui label:has(+ select)',
            '.swagger-ui label[role="label"]:has(combobox)',
          ];
          selectors.forEach(function(selector) {{
            try {{
              const elements = document.querySelectorAll(selector);
              elements.forEach(function(el) {{
                if (el.textContent && el.textContent.includes('/api')) {{
                  el.style.display = 'none';
                }}
              }});
            }} catch (e) {{
              // Ignore errors for unsupported selectors
            }}
          }});
          
          const labels = document.querySelectorAll('.swagger-ui label[role="label"]');
          labels.forEach(function(label) {{
            const combobox = label.querySelector('combobox');
            if (combobox && combobox.getAttribute('name') === '/api') {{
              label.style.display = 'none';
              if (label.parentElement) {{
                label.parentElement.style.display = 'none';
              }}
            }}
          }});
        }}
        
        addOpenApiLink();
        hideServers();
        
        window.addEventListener('load', function() {{
          addOpenApiLink();
          hideServers();
          setTimeout(addOpenApiLink, 50);
          setTimeout(hideServers, 50);
          setTimeout(addOpenApiLink, 100);
          setTimeout(hideServers, 100);
          setTimeout(addOpenApiLink, 300);
          setTimeout(hideServers, 300);
          setTimeout(addOpenApiLink, 500);
          setTimeout(hideServers, 500);
          setTimeout(addOpenApiLink, 1000);
          setTimeout(hideServers, 1000);
        }});
        
        if (window.MutationObserver) {{
          const observer = new MutationObserver(function(mutations) {{
            let shouldRun = false;
            for (let i = 0; i < mutations.length; i++) {{
              const mutation = mutations[i];
              if (mutation.addedNodes.length > 0) {{
                for (let j = 0; j < mutation.addedNodes.length; j++) {{
                  const node = mutation.addedNodes[j];
                  if (node.nodeType === 1 && (
                    (node.classList && node.classList.contains('swagger-ui')) ||
                    (node.querySelector && node.querySelector('.swagger-ui .info'))
                  )) {{
                    shouldRun = true;
                    break;
                  }}
                }}
              }}
            }}
            if (shouldRun) {{
              setTimeout(addOpenApiLink, 10);
              setTimeout(hideServers, 10);
            }}
          }});
          observer.observe(document.body, {{
            childList: true,
            subtree: true
          }});
        }}
        </script>
        <style>
        .swagger-ui .scheme-container,
        .swagger-ui .servers,
        .swagger-ui .servers-container,
        .swagger-ui select[data-name="servers"],
        .swagger-ui label[for="servers"],
        .swagger-ui .opblock-section label:has(+ select[data-name="servers"]) {{
          display: none !important;
        }}
        .swagger-ui .info .title {{
          display: flex;
          align-items: center;
          gap: 1rem;
        }}
        .swagger-ui .info .title a {{
          display: inline-block;
          font-size: 0.9em;
          color: #3b49df;
          text-decoration: none;
        }}
        .swagger-ui .info .title a:hover {{
          text-decoration: underline;
        }}
        </style>
        """
        # Get HTML content and inject script
        html_content = html_response.body.decode() if hasattr(html_response, 'body') else html_response
        if isinstance(html_content, bytes):
            html_content = html_content.decode()
        html_content = html_content.replace("</body>", custom_script + "</body>")
        return HTMLResponse(content=html_content)

    # Monkey patch
    import fastapi.openapi.docs
    fastapi.openapi.docs.get_swagger_ui_html = custom_get_swagger_ui_html
