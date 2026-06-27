FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3-colcon-common-extensions \
    python3-pip \
    ros-humble-tf2-ros \
    ros-humble-tf2-geometry-msgs \
    && pip3 install --no-cache-dir pin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/A1Z/ros2_ws
