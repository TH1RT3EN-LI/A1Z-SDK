"""ROS 2 node that sends the latest camera frame to a configured VLM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_srvs.srv import Trigger

from a1z_ext.llm import LLMClient, LLMClientError, LLMImage, LLMProviderConfig

from .image_encoding import ImageEncodingError, ros_image_to_png_data_url


@dataclass(slots=True)
class LatestImage:
    message: Image
    sequence: int


class VLMRequestNode(Node):
    def __init__(self) -> None:
        super().__init__("a1z_vlm_request")
        self._declare_parameters()

        self._latest_image: LatestImage | None = None
        self._image_sequence = 0

        color_topic = str(self.get_parameter("color_topic").value)
        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self._image_sub = self.create_subscription(
            Image,
            color_topic,
            self._handle_image,
            qos,
        )

        service_name = str(self.get_parameter("service_name").value)
        self._service = self.create_service(Trigger, service_name, self._handle_trigger)

        self.get_logger().info(
            f"VLM request node ready: image_topic={color_topic}, service={service_name}"
        )

    def _declare_parameters(self) -> None:
        self.declare_parameter("color_topic", "/a1z/d405/color/image_raw")
        self.declare_parameter("service_name", "/a1z/open_vocab/request_vlm")
        self.declare_parameter("request_text", "Describe this image briefly.")
        self.declare_parameter("system_text", "")
        self.declare_parameter("image_detail", "auto")
        self.declare_parameter("response_message_max_chars", 4096)

        self.declare_parameter("llm_provider", "openai")
        self.declare_parameter("llm_model", "")
        self.declare_parameter("llm_base_url", "")
        self.declare_parameter("llm_api_key_env", "")
        self.declare_parameter("llm_timeout_s", 30.0)
        self.declare_parameter("llm_max_tokens", 512)
        self.declare_parameter("llm_temperature", 0.0)

    def _handle_image(self, message: Image) -> None:
        self._image_sequence += 1
        self._latest_image = LatestImage(message=message, sequence=self._image_sequence)

    def _handle_trigger(
        self,
        request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        del request
        latest = self._latest_image
        if latest is None:
            response.success = False
            response.message = "no image has been received yet"
            return response

        try:
            llm_response = self._send_latest_image(latest)
        except (ImageEncodingError, LLMClientError, ValueError) as exc:
            self.get_logger().warn(f"VLM request failed: {exc}")
            response.success = False
            response.message = str(exc)
            return response

        limit = int(self.get_parameter("response_message_max_chars").value)
        content = llm_response.content
        if limit > 0 and len(content) > limit:
            content = content[:limit] + "...[truncated]"

        response.success = True
        response.message = (
            f"provider={llm_response.provider} model={llm_response.model} "
            f"image_sequence={latest.sequence} content={content}"
        )
        return response

    def _send_latest_image(self, latest: LatestImage):
        data_url = ros_image_to_png_data_url(latest.message)
        config = self._build_llm_config()
        client = LLMClient(config)

        system_text = str(self.get_parameter("system_text").value).strip() or None
        request_text = str(self.get_parameter("request_text").value)
        image_detail = str(self.get_parameter("image_detail").value)

        self.get_logger().info(
            f"Sending image_sequence={latest.sequence} to VLM provider={config.provider} model={config.model}"
        )
        return client.complete_with_images(
            text=request_text,
            images=[LLMImage(data_url=data_url, detail=image_detail)],
            system_text=system_text,
        )

    def _build_llm_config(self) -> LLMProviderConfig:
        return LLMProviderConfig.for_provider(
            str(self.get_parameter("llm_provider").value),
            model=_optional_string(self.get_parameter("llm_model").value),
            base_url=_optional_string(self.get_parameter("llm_base_url").value),
            api_key_env=_optional_string(self.get_parameter("llm_api_key_env").value),
            timeout_s=float(self.get_parameter("llm_timeout_s").value),
            max_tokens=int(self.get_parameter("llm_max_tokens").value),
            temperature=float(self.get_parameter("llm_temperature").value),
        )


def _optional_string(value: object) -> Optional[str]:
    text = str(value).strip()
    return text or None


def main(args: Optional[list[str]] = None) -> None:
    rclpy.init(args=args)
    node = VLMRequestNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
