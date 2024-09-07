FROM python:3.11.9
COPY . .

ENTRYPOINT ["/entrypoint.sh"]

CMD ["fastapi", "run", "src/unicon_backend/__init__.py","--port", "9000"]