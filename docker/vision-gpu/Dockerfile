ARG BASE_IMAGE=a1z-economicgrasp-gpu:local
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONUNBUFFERED=1
ENV CUDA_HOME=/usr/local/cuda
ENV A1Z_VISION_VENV_DIR=/opt/venvs/a1z-vision

RUN apt-get update && apt-get install -y \
    build-essential \
    ca-certificates \
    curl \
    git \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libopenblas-dev \
    libsm6 \
    libusb-1.0-0 \
    libxext6 \
    libxrender1 \
    ninja-build \
    pkg-config \
    python-is-python3 \
    python3 \
    net-tools \
    python3-dev \
    python3-pip \
    python3-venv \
    unzip \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/A1Z
