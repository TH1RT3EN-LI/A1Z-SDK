from glob import glob

from setuptools import find_packages, setup


package_name = "a1z_open_vocab"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/config", glob("config/*.yaml")),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="A1Z",
    maintainer_email="devnull@example.com",
    description="ROS 2 VLM request bridge for A1Z open-vocabulary workflows.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "vision_request = a1z_open_vocab.vision_request_node:main",
        ],
    },
)
