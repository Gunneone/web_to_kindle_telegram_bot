# Build the web client (Eselsohr); the Python image below only carries the result
FROM node:24-slim AS client
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# The shared gunne.one design system the client links to (override to build against a local copy)
ARG G1_DS_URL=https://gunne.one/ds/v1
ENV G1_DS_URL=$G1_DS_URL
RUN npm run build

FROM python:3.12.11-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# The built web client lives outside /app, because docker-compose bind-mounts the project over /app
COPY --from=client /build/dist /srv/eselsohr-dist
ENV WEB_DIST_DIR=/srv/eselsohr-dist

# Copy the real .env file (make sure to create it from .env.example)
COPY .env .

CMD ["python", "src/telegram_bot.py"]
