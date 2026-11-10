FROM python:3.12.15-slim-bookworm
ARG APP_UID=10001
ARG APP_GID=10001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Debian DLA-4880-1: bootstrap APT without retry-based verification bypass.
RUN set -eu; \
    apt-get -o Acquire::Retries=0 update; \
    apt-get -o Acquire::Retries=0 install -y --no-install-recommends --only-upgrade apt libapt-pkg6.0; \
    dpkg --compare-versions "$(dpkg-query -W -f='${Version}' apt)" ge '2.6.2'; \
    dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libapt-pkg6.0)" ge '2.6.2'; \
    rm -rf /var/lib/apt/lists/*
RUN test "$APP_UID" -gt 0 && test "$APP_GID" -gt 0 \
    && groupadd -g "$APP_GID" foxden \
    && useradd -u "$APP_UID" -g "$APP_GID" -M foxden
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
USER foxden:foxden
EXPOSE 8020
CMD ["uvicorn", "foxden_portal.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8020", "--workers", "1", "--no-proxy-headers"]
