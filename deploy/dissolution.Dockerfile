FROM node:22-bookworm-slim AS web
WORKDIR /build/frontend
COPY frontend/package*.json ./
# Match the repository's existing BlockNote/TipTap peer-resolution settings.
COPY frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
# Public origin only. NEVER pass an API key as a frontend build argument.
ARG PUBLIC_API_ORIGIN=https://semant-dissolution.onrender.com
RUN VITE_API_URL=$PUBLIC_API_ORIGIN VITE_API_KEY= npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements-dissolution.txt ./
RUN pip install --no-cache-dir -r requirements-dissolution.txt
COPY backend/ ./backend/
COPY contracts/ ./contracts/
COPY --from=web /build/frontend/dist ./frontend/dist
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn backend.dissolution_main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
