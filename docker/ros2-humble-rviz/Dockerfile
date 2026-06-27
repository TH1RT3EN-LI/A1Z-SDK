ARG BASE_IMAGE=a1z-ros2-humble:local
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    ros-humble-rviz2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/A1Z/ros2_ws
