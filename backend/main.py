from fastapi import FastAPI
app = FastAPI(title="GridSense AI API", version="0.1.0",
              description="Electricity supply econometrics, forecasting and intelligence API")
@app.get("/health")
def health():
    return {"status": "ok", "service": "gridsense-api"}
@app.get("/")
def root():
    return {"message": "GridSense AI API", "docs": "/docs"}
