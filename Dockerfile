FROM alpine:edge

# Directory where to deploy
ENV APP_DIR=pingrr

RUN \
  # Upgrade all packages
  apk --no-cache -U upgrade && \
  # Install OS dependencies
  apk --no-cache -U add python2 && \
  apk --no-cache -U add --virtual .build-deps git gcc linux-headers python2-dev musl-dev && \
  # Python2 PIP
  python -m ensurepip && \
  # Get Pingrr
  git clone --depth 1 --single-branch https://github.com/Dec64/pingrr.git /${APP_DIR} && \
  # Install PIP dependencies
  pip install --no-cache-dir --upgrade pip setuptools && \
  pip install --no-cache-dir --upgrade -r /${APP_DIR}/requirements.txt && \
  # Remove build dependencies
  apk --no-cache del .build-deps

# Change directory
WORKDIR /${APP_DIR}

# Config volume
VOLUME /config

# Pingrr config file
ENV PINGRR_CONFIG=/config/config.json
# Pingrr log file
ENV PINGRR_LOGFILE=/config/pingrr.log

# Entrypoint
ENTRYPOINT ["python2", "pingrr.py"]