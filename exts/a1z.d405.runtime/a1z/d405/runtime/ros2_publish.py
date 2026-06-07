"""ROS2 publishing setup for the runtime D405 simulated sensor."""

from __future__ import annotations

import carb
import omni.graph.core as og

from .settings import D405Ros2Settings


def setup_d405_ros2_publishers(attachment) -> str | None:
    settings = D405Ros2Settings.from_env()
    if not settings.enabled:
        carb.log_info("A1Z D405 ROS2 publishers disabled by A1Z_D405_ROS2_ENABLED.")
        return None
    if attachment is None:
        return None
    depth_camera_path = attachment.camera_paths.get("depth")
    color_camera_path = attachment.camera_paths.get("color")
    if not depth_camera_path or not color_camera_path:
        carb.log_info("A1Z D405 ROS2 publishers skipped because camera prims are unavailable.")
        return None

    try:
        import usdrt.Sdf
    except Exception as exc:
        carb.log_warn(f"A1Z D405 ROS2 publishers unavailable: usdrt import failed: {exc}")
        return None

    try:
        og.Controller.edit(
            {"graph_path": settings.graph_path, "evaluator_name": "execution"},
            {
                og.Controller.Keys.CREATE_NODES: [
                    ("OnPlaybackTick", "omni.graph.action.OnPlaybackTick"),
                    ("CreateColorRenderProduct", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
                    ("CreateDepthRenderProduct", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
                    ("ColorImagePublish", "isaacsim.ros2.bridge.ROS2CameraHelper"),
                    ("ColorInfoPublish", "isaacsim.ros2.bridge.ROS2CameraInfoHelper"),
                    ("DepthImagePublish", "isaacsim.ros2.bridge.ROS2CameraHelper"),
                    ("DepthPclPublish", "isaacsim.ros2.bridge.ROS2CameraHelper"),
                    ("DepthInfoPublish", "isaacsim.ros2.bridge.ROS2CameraInfoHelper"),
                ],
                og.Controller.Keys.SET_VALUES: [
                    ("CreateColorRenderProduct.inputs:cameraPrim", [usdrt.Sdf.Path(color_camera_path)]),
                    ("CreateColorRenderProduct.inputs:width", settings.width),
                    ("CreateColorRenderProduct.inputs:height", settings.height),
                    ("CreateDepthRenderProduct.inputs:cameraPrim", [usdrt.Sdf.Path(depth_camera_path)]),
                    ("CreateDepthRenderProduct.inputs:width", settings.width),
                    ("CreateDepthRenderProduct.inputs:height", settings.height),
                    ("ColorImagePublish.inputs:nodeNamespace", settings.namespace),
                    ("ColorImagePublish.inputs:frameId", settings.color_frame_id),
                    ("ColorImagePublish.inputs:topicName", "color/image_raw"),
                    ("ColorImagePublish.inputs:type", "rgb"),
                    ("ColorImagePublish.inputs:frameSkipCount", settings.frame_skip_count),
                    ("ColorInfoPublish.inputs:nodeNamespace", settings.namespace),
                    ("ColorInfoPublish.inputs:frameId", settings.color_frame_id),
                    ("ColorInfoPublish.inputs:topicName", "color/camera_info"),
                    ("ColorInfoPublish.inputs:frameSkipCount", settings.frame_skip_count),
                    ("DepthImagePublish.inputs:nodeNamespace", settings.namespace),
                    ("DepthImagePublish.inputs:frameId", settings.depth_frame_id),
                    ("DepthImagePublish.inputs:topicName", "depth/image_rect"),
                    ("DepthImagePublish.inputs:type", "depth"),
                    ("DepthImagePublish.inputs:frameSkipCount", settings.frame_skip_count),
                    ("DepthPclPublish.inputs:nodeNamespace", settings.namespace),
                    ("DepthPclPublish.inputs:frameId", settings.depth_frame_id),
                    ("DepthPclPublish.inputs:topicName", "depth/points"),
                    ("DepthPclPublish.inputs:type", "depth_pcl"),
                    ("DepthPclPublish.inputs:frameSkipCount", settings.frame_skip_count),
                    ("DepthInfoPublish.inputs:nodeNamespace", settings.namespace),
                    ("DepthInfoPublish.inputs:frameId", settings.depth_frame_id),
                    ("DepthInfoPublish.inputs:topicName", "depth/camera_info"),
                    ("DepthInfoPublish.inputs:frameSkipCount", settings.frame_skip_count),
                ],
                og.Controller.Keys.CONNECT: [
                    ("OnPlaybackTick.outputs:tick", "CreateColorRenderProduct.inputs:execIn"),
                    ("OnPlaybackTick.outputs:tick", "CreateDepthRenderProduct.inputs:execIn"),
                    ("CreateColorRenderProduct.outputs:execOut", "ColorImagePublish.inputs:execIn"),
                    ("CreateColorRenderProduct.outputs:execOut", "ColorInfoPublish.inputs:execIn"),
                    ("CreateDepthRenderProduct.outputs:execOut", "DepthImagePublish.inputs:execIn"),
                    ("CreateDepthRenderProduct.outputs:execOut", "DepthPclPublish.inputs:execIn"),
                    ("CreateDepthRenderProduct.outputs:execOut", "DepthInfoPublish.inputs:execIn"),
                    ("CreateColorRenderProduct.outputs:renderProductPath", "ColorImagePublish.inputs:renderProductPath"),
                    ("CreateColorRenderProduct.outputs:renderProductPath", "ColorInfoPublish.inputs:renderProductPath"),
                    ("CreateDepthRenderProduct.outputs:renderProductPath", "DepthImagePublish.inputs:renderProductPath"),
                    ("CreateDepthRenderProduct.outputs:renderProductPath", "DepthPclPublish.inputs:renderProductPath"),
                    ("CreateDepthRenderProduct.outputs:renderProductPath", "DepthInfoPublish.inputs:renderProductPath"),
                ],
            },
        )
        carb.log_info(
            "A1Z D405 ROS2 publishers configured: "
            f"graph={settings.graph_path} namespace={settings.namespace} "
            f"color={color_camera_path} depth={depth_camera_path}"
        )
        return settings.graph_path
    except Exception as exc:
        carb.log_warn(f"A1Z D405 ROS2 publisher setup failed: {exc}")
        return None


__all__ = ["setup_d405_ros2_publishers"]
