from fastapi import FastAPI

from kurioto.api.education import router as education_router

app = FastAPI(title="Kurioto API")
app.include_router(education_router)
