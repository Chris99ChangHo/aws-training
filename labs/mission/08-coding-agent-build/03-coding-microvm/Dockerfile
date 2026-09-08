FROM public.ecr.aws/lambda/microvms:al2023-minimal

RUN dnf install -y python3.12 python3.12-pip shadow-utils && dnf clean all

RUN pip3.12 install --no-cache-dir pytest coverage fastapi uvicorn

RUN useradd -m -s /bin/bash sandbox \
    && mkdir -p /sandbox \
    && chown sandbox:sandbox /sandbox

COPY sandbox_server.py /app/sandbox_server.py

USER sandbox
WORKDIR /sandbox
EXPOSE 8080

CMD ["python3.12", "-m", "uvicorn", "--app-dir", "/app", "sandbox_server:app", "--host", "0.0.0.0", "--port", "8080"]
