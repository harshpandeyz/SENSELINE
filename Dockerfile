FROM python:3.11.18-slim-bookworm@sha256:ef521de1d817dc92a6358c906bbadb9a0b7e38040038642833521b9d582c2233
WORKDIR /opt/senseline
COPY requirements.txt pyproject.toml README.md ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "pytest", "-m", "not docker_integration", "-q"]
