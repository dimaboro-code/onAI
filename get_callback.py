from fastapi import FastAPI, Request
from pydantic import BaseModel


class OutputMessage(BaseModel):
    message: str


app = FastAPI()


@app.post("/")
async def webhook(message: OutputMessage):
    print(message.message)
    return {"status": "ok"}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="localhost", port=8080)