from fastapi import Header, HTTPException, Request, status


def requires_secret(request: Request, authorization: str = Header(default="")):
    """
    Summary
    -------
    guards the route with a secret token

    Parameters
    ----------
    request (Request)
        the FastAPI request
    authorization (str)
        the Authorization header value
    """
    config = request.app.state.config
    if authorization != config.auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

