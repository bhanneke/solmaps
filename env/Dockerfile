# solmaps compute environment: pykep (MPL-2.0), pygmo, scipy from conda-forge, plus the engine's web and test tools.
# Every version is pinned so that a fresh checkout builds the same environment: the base image by digest, the conda
# packages and the pip packages by exact version. Build: docker build -t solmaps-env env/
FROM condaforge/miniforge3:26.9.4-0@sha256:63d72eadf0ab73ee63bad8f5cfdfe1754530415b4aeba99e466e9a6f77ceec95
RUN mamba install -y -c conda-forge python=3.14 pykep=3.0.0 pygmo=2.19.8 heyoka=7.10.0 numpy=2.5.4 scipy=1.18.1 \
    && mamba clean -afy
RUN pip install --no-cache-dir fastapi==0.120.4 uvicorn==0.38.0 pytest==8.4.2 httpx==0.28.1
# data releases: Parquet export and the Hugging Face upload (Zenodo uploads use its REST API through httpx)
RUN pip install --no-cache-dir pyarrow==26.0.0 huggingface_hub==2.2.0
WORKDIR /work
