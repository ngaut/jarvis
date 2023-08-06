FROM python:3.10.12-bullseye

WORKDIR /app

RUN pip install --upgrade pip
RUN pip install pipenv

COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy --ignore-pipfile --verbose

COPY data/ ./data/
COPY jarvis/ ./jarvis/

RUN mkdir /app/workspace

EXPOSE 51155

# ENV MY_ENV_VAR=value

# Run jarvis-server
CMD ["pipenv", "run", "python", "-m", "jarvis.server"]
