FROM python:3.13-slim as builder

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


FROM builder

ENV PYTHONUNBUFFERED=1

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /locust_operator
COPY ./locust_operator .

ENTRYPOINT ["kopf", "run"]
CMD ["locust_operator.py"]
