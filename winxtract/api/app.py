try:
    from fastapi import FastAPI
except Exception:  # pragma: no cover
    FastAPI = None


def create_app():
    if FastAPI is None:
        raise RuntimeError("Install API deps with: python -m pip install -e .[api]")
    app = FastAPI(title="WinXtract API")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
