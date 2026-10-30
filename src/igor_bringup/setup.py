import os
from glob import glob
from setuptools import setup, find_packages

package_name = 'igor_bringup'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*')),
    ],
    install_requires=['setuptools', 'numpy', 'pyserial'],
    zip_safe=True,
    maintainer='Karol',
    maintainer_email='karol@todo.todo',
    description='Master Bringup Launch, RPLiDAR Driver, and System Config for Hiwonder JetAuto Mecanum AMR.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'rplidar_driver = igor_bringup.rplidar_driver_node:main',
        ],
    },
)
