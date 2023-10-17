FROM python:3.10.13

WORKDIR /app

RUN pip install --upgrade pip
RUN pip install pipenv

COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy --ignore-pipfile --verbose

# Install browsers
RUN apt-get update && apt-get install -y \
    chromium-driver firefox-esr \
    ca-certificates libnss3 \
    sqlite3 libsqlite3-dev

COPY data/ ./data/
COPY jarvis/ ./jarvis/

RUN mkdir /app/workspace

EXPOSE 51155

# ENV MY_ENV_VAR=value

# Run jarvis-server
CMD ["pipenv", "run", "python", "-m", "jarvis.server"]
