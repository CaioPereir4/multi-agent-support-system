from fastapi import FastAPI
from src.api.api import api_router

app = FastAPI()

app.include_router(api_router, prefix="/api")

def main():
    print("Hello from getnet-support-system!")

if __name__ == "__main__":
    main()
