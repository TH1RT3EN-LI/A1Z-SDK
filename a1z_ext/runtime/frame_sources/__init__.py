"""Frame-source adapters for shared RGB-D observation capture."""

from .base import FrameSource, RGBDFrameCapture
from .ros_rgbd import RosRGBDFrameSource, capture_ros_rgbd_frame
from .sample_rgbd import SampleRGBDFrameSource

__all__ = [
    "FrameSource",
    "RGBDFrameCapture",
    "RosRGBDFrameSource",
    "SampleRGBDFrameSource",
    "capture_ros_rgbd_frame",
]
