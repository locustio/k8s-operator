FROM python:3.13-slim AS builder

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


FROM builder

ENV PYTHONUNBUFFERED=1

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

ADD ./locust_operator .

ENTRYPOINT ["kopf", "run", "main.py", "--liveness=http://0.0.0.0:8080/healthz"]
CMD ["--all-namespaces"]
