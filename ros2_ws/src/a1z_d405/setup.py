from setuptools import find_packages, setup


package_name = "a1z_d405"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="A1Z",
    maintainer_email="devnull@example.com",
    description="Isaac-to-ROS D405 device adapter for A1Z.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "isaac_d405_bridge = a1z_d405.publisher:main",
        ],
    },
)
