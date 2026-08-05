ARG BASE_IMAGE=a1z-ros2-humble-base:local
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive
ARG PIP_INDEX_URL=https://pypi.org/simple

RUN apt-get update && apt-get install -y \
    can-utils \
    iproute2 \
    ros-humble-realsense2-camera \
    && pip3 install --no-cache-dir --index-url "$PIP_INDEX_URL" \
        'python-can>=4.0' \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/A1Z/ros2_ws
