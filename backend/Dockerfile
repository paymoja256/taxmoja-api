FROM python:3.9

WORKDIR /backend

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONBUFFERED 1

# install python dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt /backend/requirements.txt
RUN pip install -r requirements.txt

COPY . /backend

ENTRYPOINT ["bash", "-c", "alembic upgrade head && uvicorn app.api.server:app --reload --host 0.0.0.0 --port 8000"]
