# Rasa NLU: el modelo se entrena al construir la imagen, así el contenedor
# arranca listo y cada versión del modelo queda ligada a una versión de la imagen.
FROM rasa/rasa:3.6.20
WORKDIR /app
COPY --chown=1001 services/nlu-rasa/config.yml ./config.yml
COPY --chown=1001 services/nlu-rasa/data ./data
COPY --chown=1001 services/nlu-rasa/tests ./tests
RUN rasa train nlu --config config.yml --nlu data/nlu.yml --out models --fixed-model-name medicai-nlu
EXPOSE 5005
HEALTHCHECK --interval=20s --timeout=5s --retries=10 --start-period=60s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:5005/status')"
CMD ["run", "--enable-api", "--port", "5005", "--model", "models"]
