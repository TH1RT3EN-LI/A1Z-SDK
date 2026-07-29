ARG BASE_IMAGE=a1z-ros2-humble-base:local
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    can-utils \
    iproute2 \
    python3-can \
    ros-humble-realsense2-camera \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/A1Z/ros2_ws
