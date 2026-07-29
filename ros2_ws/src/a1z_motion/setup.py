from setuptools import find_packages, setup


package_name = "a1z_motion"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", ["launch/a1z_stack.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="A1Z",
    maintainer_email="devnull@example.com",
    description="Docker-first ROS 2 motion integration layer for A1Z.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "motion_executor = a1z_motion.motion_executor:main",
            "robot_state = a1z_motion.robot_state:main",
        ],
    },
)
