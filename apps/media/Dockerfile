FROM python:3.12.15-slim-bookworm
ARG APP_UID=10001
ARG APP_GID=10001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN test "$APP_UID" -gt 0 && test "$APP_GID" -gt 0 \
    && apt-get -o Acquire::Retries=0 update \
    && apt-get -o Acquire::Retries=0 install -y --no-install-recommends --only-upgrade apt libapt-pkg6.0 \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' apt)" ge '2.6.2' \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libapt-pkg6.0)" ge '2.6.2' \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && apt-get install -y --no-install-recommends --only-upgrade openssl libssl3 \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' openssl)" ge '3.0.22-1~deb12u2' \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libssl3)" ge '3.0.22-1~deb12u2' \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g "$APP_GID" foxden && useradd -u "$APP_UID" -g "$APP_GID" -M foxden
WORKDIR /app
COPY apps/media/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/media/app/ ./app/
COPY apps/portal/src/foxden_identity/ ./foxden_identity/
COPY apps/media/VERSION ./VERSION
# NAS source copies may have mode 0700; keep application code readable by the non-root runtime.
RUN chmod -R a+rX /app
USER foxden:foxden
EXPOSE 8010
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8010", "--workers", "1", "--no-proxy-headers"]
