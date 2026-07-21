from fastapi import FastAPI

from app.api.routes_webhooks import router as webhooks_router

app = FastAPI(title="P6 Consent Propagation Satellite")
app.include_router(webhooks_router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
