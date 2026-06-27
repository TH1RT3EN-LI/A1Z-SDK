from setuptools import find_packages
from setuptools import setup

setup(
    name='a1z_msgs',
    version='0.1.0',
    packages=find_packages(
        include=('a1z_msgs', 'a1z_msgs.*')),
)
