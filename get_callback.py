from fastapi import FastAPI, Request
from pydantic import BaseModel


class OutputMessage(BaseModel):
    text: str


app = FastAPI()


@app.post("/")
async def webhook(message: Request):
    body = await message.body()
    print(body.decode("utf-8"))
    return {"message": "message.text"}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="localhost", port=8080)