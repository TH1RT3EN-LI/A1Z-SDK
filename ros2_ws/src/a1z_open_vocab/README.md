# a1z_open_vocab

ROS 2 VLM request bridge for A1Z open-vocabulary workflows.

This package currently only provides the transport foundation:

- subscribe to the latest RGB image
- encode it as a PNG data URL
- send one text + image request to an OpenAI-compatible VLM endpoint
- return the provider response through a `std_srvs/Trigger` service

It does not implement prompt design, grounding, segmentation, grasp planning, or
motion execution.

## Provider Configuration

Default GPT-style configuration:

```bash
set -a
source /workspace/A1Z/config/a1z_vlm.env
set +a
ros2 launch a1z_open_vocab a1z_open_vocab.launch.py
```

Kimi/Moonshot-style configuration:

```bash
set -a
source /workspace/A1Z/config/a1z_vlm.env
set +a
ros2 launch a1z_open_vocab a1z_open_vocab.launch.py llm_provider:=kimi
```

For custom models or endpoints, override parameters in `config/vlm.yaml`:

- `llm_provider`
- `llm_model`
- `llm_base_url`
- `llm_api_key_env`
- `llm_timeout_s`
- `llm_max_tokens`
- `llm_temperature`

## Trigger One Request

After the node has received at least one image:

```bash
ros2 service call /a1z/open_vocab/request_vlm std_srvs/srv/Trigger {}
```
